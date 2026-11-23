import pytest
from unittest.mock import patch, AsyncMock
import httpx
from httpx import AsyncClient, Response
from urllib.parse import urlparse, parse_qs
from sqlalchemy import select, func
from src.config import settings
from src.models.user import User
from src.services.crypto_service import crypto_service
from src.services.session_service import SessionService
from src.services.github_service import GitHubService, GITHUB_HTTP_USER_AGENT


@pytest.mark.asyncio
async def test_github_oauth_start_redirect(client: AsyncClient, test_redis):
    """GET /api/v1/integrations/github/start should redirect to GitHub with state stored in Redis."""
    response = await client.get("/api/v1/integrations/github/start", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers.get("location")
    assert location is not None
    assert location.startswith("https://github.com/login/oauth/authorize")

    parsed = urlparse(location)
    params = parse_qs(parsed.query)

    assert params["client_id"][0] == settings.GITHUB_CLIENT_ID
    assert params["redirect_uri"][0] == settings.GITHUB_REDIRECT_URI
    assert "state" in params

    state = params["state"][0]
    # Verify state is saved in Redis with TTL
    state_in_redis = await test_redis.get(f"oauth:state:{state}")
    assert state_in_redis is not None
    ttl = await test_redis.ttl(f"oauth:state:{state}")
    assert 0 < ttl <= 600


@pytest.mark.asyncio
async def test_github_oauth_start_json(client: AsyncClient, test_redis):
    """GET /api/v1/integrations/github/start?format=json returns authorization_url and state in JSON."""
    response = await client.get("/api/v1/integrations/github/start?format=json")

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "authorization_url" in body["data"]
    assert "state" in body["data"]

    state = body["data"]["state"]
    assert await test_redis.get(f"oauth:state:{state}") is not None


@pytest.mark.asyncio
async def test_github_callback_missing_params(client: AsyncClient):
    """Callback without code or state should redirect to /login with error."""
    response = await client.get("/api/v1/integrations/github/callback", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers.get("location")
    assert "/login?error=invalid_request" in location


@pytest.mark.asyncio
async def test_github_callback_invalid_state(client: AsyncClient):
    """Callback with nonexistent/forged state should redirect to /login with error."""
    response = await client.get(
        "/api/v1/integrations/github/callback?code=some_code&state=fake_unrecognized_state",
        follow_redirects=False
    )

    assert response.status_code == 302
    location = response.headers.get("location")
    assert "/login?error=invalid_state" in location


@pytest.mark.asyncio
async def test_github_callback_first_time_registration(client: AsyncClient, test_redis, test_db):
    """Valid OAuth callback for new user should create User, OAuthConnection, Redis session, and set cookies."""
    # 1. Generate state and store in Redis
    state = crypto_service.generate_random_token(32)
    await test_redis.set(f"oauth:state:{state}", '{"created_at":"2026-11-21T00:00:00Z"}', ex=600)

    # 2. Mock GitHub token exchange and profile fetch
    mock_token = {"access_token": "gho_mock_access_token_123", "scope": "read:user,user:email"}
    mock_profile = {
        "github_id": "98765432",
        "username": "new_codepilot_user",
        "name": "New Developer",
        "email": "newdev@example.com",
        "avatar_url": "https://avatars.githubusercontent.com/u/98765432"
    }

    with patch("src.services.github_service.GitHubService.exchange_code_for_token", return_value=mock_token), \
         patch("src.services.github_service.GitHubService.fetch_user_profile", return_value=mock_profile):

        response = await client.get(
            f"/api/v1/integrations/github/callback?code=valid_gh_code&state={state}",
            follow_redirects=False
        )

    assert response.status_code == 302
    assert response.headers.get("location") == f"{settings.FRONTEND_BASE_URL}/dashboard"

    # Verify cookies
    assert settings.SESSION_COOKIE_NAME in response.cookies
    session_id = response.cookies[settings.SESSION_COOKIE_NAME]
    assert settings.CSRF_COOKIE_NAME in response.cookies

    # Verify state was consumed (cannot be replayed)
    assert await test_redis.get(f"oauth:state:{state}") is None

    # Verify session is valid in Redis
    session_service = SessionService(test_redis)
    session = await session_service.get_session(session_id)
    assert session is not None
    assert session.username == "new_codepilot_user"

    # Now use session to call /api/v1/auth/me
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["username"] == "new_codepilot_user"
    assert me_resp.json()["data"]["email"] == "newdev@example.com"


@pytest.mark.asyncio
async def test_github_callback_replayed_state_fails(client: AsyncClient, test_redis):
    """Using the same state a second time fails because state is single-use."""
    state = crypto_service.generate_random_token(32)
    await test_redis.set(f"oauth:state:{state}", '{"created_at":"2026-11-21T00:00:00Z"}', ex=600)

    mock_token = {"access_token": "gho_token_1", "scope": "read:user"}
    mock_profile = {"github_id": "111", "username": "user1", "name": "U1", "email": "u1@e.com", "avatar_url": None}

    with patch("src.services.github_service.GitHubService.exchange_code_for_token", return_value=mock_token), \
         patch("src.services.github_service.GitHubService.fetch_user_profile", return_value=mock_profile):

        # First callback consumes state
        resp1 = await client.get(f"/api/v1/integrations/github/callback?code=c1&state={state}", follow_redirects=False)
        assert resp1.status_code == 302
        assert "/dashboard" in resp1.headers.get("location")

        # Second callback with same state must be rejected
        resp2 = await client.get(f"/api/v1/integrations/github/callback?code=c1&state={state}", follow_redirects=False)
        assert resp2.status_code == 302
        assert "/login?error=invalid_state" in resp2.headers.get("location")


@pytest.mark.asyncio
async def test_github_status_and_disconnect(client: AsyncClient, authenticated_session):
    """GET /api/v1/integrations/github/status and DELETE /api/v1/integrations/github."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    user = authenticated_session["user"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    # 1. Check status -> connected
    status_resp = await client.get("/api/v1/integrations/github/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["data"]["connected"] is True
    assert status_resp.json()["data"]["username"] == user.username

    # 2. Disconnect integration with CSRF
    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }
    del_resp = await client.delete("/api/v1/integrations/github", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["message"] == "GitHub integration successfully disconnected"

    # 3. Check status again -> disconnected
    status_resp2 = await client.get("/api/v1/integrations/github/status")
    assert status_resp2.status_code == 200
    assert status_resp2.json()["data"]["connected"] is False


@pytest.mark.asyncio
async def test_github_oauth_request_headers_ascii_safe(test_redis):
    """
    Regression test:
    Verify that all headers in GitHub OAuth token exchange and user profile fetch
    are strictly ASCII-safe (cannot raise UnicodeEncodeError with '\\u2014' or other non-ASCII chars).
    """
    assert "—" in settings.APP_NAME  # Confirm APP_NAME still has the em dash for UI/display
    assert "\u2014" in settings.APP_NAME

    service = GitHubService(test_redis)

    # 1. Test exchange_code_for_token headers
    captured_post_headers = None

    async def mock_post(url, json=None, headers=None):
        nonlocal captured_post_headers
        captured_post_headers = headers
        # Simulating what httpx / http.client does internally:
        for k, v in headers.items():
            k.encode("ascii")
            v.encode("ascii")
        req = httpx.Request("POST", url, headers=headers)
        return Response(200, json={"access_token": "gho_test_token_123", "token_type": "bearer", "scope": "read:user"}, request=req)

    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        token_data = await service.exchange_code_for_token("test_code")
        assert token_data["access_token"] == "gho_test_token_123"

    assert captured_post_headers is not None
    assert captured_post_headers["User-Agent"] == GITHUB_HTTP_USER_AGENT
    for k, v in captured_post_headers.items():
        assert k.isascii(), f"Header key {k} is not ASCII"
        assert v.isascii(), f"Header value {v} is not ASCII"

    # 2. Test fetch_user_profile headers
    captured_get_headers = None

    async def mock_get(url, headers=None):
        nonlocal captured_get_headers
        captured_get_headers = headers
        for k, v in headers.items():
            k.encode("ascii")
            v.encode("ascii")
        req = httpx.Request("GET", url, headers=headers)
        if "user/emails" in str(url):
            return Response(200, json=[{"email": "test@example.com", "primary": True, "verified": True}], request=req)
        return Response(200, json={"id": 12345, "login": "testuser", "name": "Test User", "avatar_url": None, "email": None}, request=req)

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        profile = await service.fetch_user_profile("gho_test_token_123")
        assert profile["username"] == "testuser"
        assert profile["email"] == "test@example.com"

    assert captured_get_headers is not None
    assert captured_get_headers["User-Agent"] == GITHUB_HTTP_USER_AGENT
    for k, v in captured_get_headers.items():
        assert k.isascii(), f"Header key {k} is not ASCII"
        assert v.isascii(), f"Header value {v} is not ASCII"


@pytest.mark.asyncio
async def test_github_oauth_start_does_not_request_consent_prompt(client: AsyncClient):
    """
    Verify that GET /api/v1/integrations/github/start does NOT include prompt=consent,
    ensuring that GitHub consent is not repeatedly requested for already authorized users.
    """
    response = await client.get("/api/v1/integrations/github/start", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers.get("location")
    assert location is not None

    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    assert "prompt" not in params or "consent" not in params.get("prompt", [])


@pytest.mark.asyncio
async def test_github_callback_relogin_creates_fresh_session_for_existing_user(client: AsyncClient, test_redis, test_db):
    """
    Every successful login (including re-login by an already registered user)
    must create a brand-new, unique server-side session, while keeping the user record unique.
    """
    user_github_id = "55443322"
    mock_token = {"access_token": "gho_access_token_relogin", "scope": "read:user,user:email"}
    mock_profile_login1 = {
        "github_id": user_github_id,
        "username": "relogin_user",
        "name": "Relogin User Initial",
        "email": "relogin@example.com",
        "avatar_url": "https://avatars.githubusercontent.com/u/55443322"
    }

    # First login (first-time registration)
    state1 = crypto_service.generate_random_token(32)
    await test_redis.set(f"oauth:state:{state1}", '{"created_at":"2026-11-21T00:00:00Z"}', ex=600)

    with patch("src.services.github_service.GitHubService.exchange_code_for_token", return_value=mock_token), \
         patch("src.services.github_service.GitHubService.fetch_user_profile", return_value=mock_profile_login1):
        resp1 = await client.get(
            f"/api/v1/integrations/github/callback?code=code_1&state={state1}",
            follow_redirects=False
        )

    assert resp1.status_code == 302
    session_id_1 = resp1.cookies[settings.SESSION_COOKIE_NAME]
    csrf_token_1 = resp1.cookies[settings.CSRF_COOKIE_NAME]
    assert session_id_1 is not None

    # Verify user exists in database
    count_stmt = select(func.count(User.id)).where(User.github_id == user_github_id)
    count_res = await test_db.execute(count_stmt)
    assert count_res.scalar() == 1

    # Second login (re-login with updated profile name)
    state2 = crypto_service.generate_random_token(32)
    await test_redis.set(f"oauth:state:{state2}", '{"created_at":"2026-11-21T00:00:00Z"}', ex=600)

    mock_profile_login2 = {
        "github_id": user_github_id,
        "username": "relogin_user",
        "name": "Relogin User Updated Name",
        "email": "relogin@example.com",
        "avatar_url": "https://avatars.githubusercontent.com/u/55443322"
    }

    with patch("src.services.github_service.GitHubService.exchange_code_for_token", return_value=mock_token), \
         patch("src.services.github_service.GitHubService.fetch_user_profile", return_value=mock_profile_login2):
        resp2 = await client.get(
            f"/api/v1/integrations/github/callback?code=code_2&state={state2}",
            follow_redirects=False
        )

    assert resp2.status_code == 302
    session_id_2 = resp2.cookies[settings.SESSION_COOKIE_NAME]
    assert session_id_2 is not None

    # Crucial assertion: Every login must create a fresh, distinct session ID
    assert session_id_1 != session_id_2

    # Verify user record is not duplicated in DB
    count_res2 = await test_db.execute(count_stmt)
    assert count_res2.scalar() == 1

    # Verify new session works on /auth/me and reflects updated name
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id_2)
    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["name"] == "Relogin User Updated Name"


@pytest.mark.asyncio
async def test_full_login_logout_relogin_lifecycle(client: AsyncClient, test_redis, test_db):
    """
    End-to-end verification of login -> logout -> invalidation -> re-login:
    1. Login creates session 1
    2. User is authenticated on /auth/me
    3. Logout invalidates session 1
    4. Session 1 is rejected on /auth/me
    5. Re-login creates fresh session 2
    6. Session 2 works on /auth/me
    7. Session 1 remains invalid
    """
    github_id = "77112233"
    mock_token = {"access_token": "gho_lifecycle_token", "scope": "read:user"}
    mock_profile = {
        "github_id": github_id,
        "username": "lifecycle_user",
        "name": "Lifecycle Dev",
        "email": "lifecycle@example.com",
        "avatar_url": None
    }

    # 1. First Login
    state1 = crypto_service.generate_random_token(32)
    await test_redis.set(f"oauth:state:{state1}", '{"created_at":"2026-11-21T00:00:00Z"}', ex=600)
    with patch("src.services.github_service.GitHubService.exchange_code_for_token", return_value=mock_token), \
         patch("src.services.github_service.GitHubService.fetch_user_profile", return_value=mock_profile):
        login1_resp = await client.get(
            f"/api/v1/integrations/github/callback?code=c1&state={state1}",
            follow_redirects=False
        )
    assert login1_resp.status_code == 302
    session_1 = login1_resp.cookies[settings.SESSION_COOKIE_NAME]
    csrf_1 = login1_resp.cookies[settings.CSRF_COOKIE_NAME]

    # 2. Check /auth/me with session 1
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_1)
    me_resp1 = await client.get("/api/v1/auth/me")
    assert me_resp1.status_code == 200

    # 3. Logout session 1
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_1, "Origin": settings.FRONTEND_BASE_URL}
    )
    assert logout_resp.status_code == 200

    # 4. Attempt /auth/me with old session 1 -> must fail with 401
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_1)
    me_after_logout = await client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401

    # 5. Re-login
    state2 = crypto_service.generate_random_token(32)
    await test_redis.set(f"oauth:state:{state2}", '{"created_at":"2026-11-21T00:00:00Z"}', ex=600)
    with patch("src.services.github_service.GitHubService.exchange_code_for_token", return_value=mock_token), \
         patch("src.services.github_service.GitHubService.fetch_user_profile", return_value=mock_profile):
        login2_resp = await client.get(
            f"/api/v1/integrations/github/callback?code=c2&state={state2}",
            follow_redirects=False
        )
    assert login2_resp.status_code == 302
    session_2 = login2_resp.cookies[settings.SESSION_COOKIE_NAME]

    # 6. Verify fresh session
    assert session_2 != session_1

    # 7. Access /auth/me with session 2 -> must succeed
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_2)
    me_resp2 = await client.get("/api/v1/auth/me")
    assert me_resp2.status_code == 200
    assert me_resp2.json()["data"]["username"] == "lifecycle_user"

    # 8. Re-attempt /auth/me with old session 1 -> still must fail with 401
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_1)
    me_with_old_session = await client.get("/api/v1/auth/me")
    assert me_with_old_session.status_code == 401
