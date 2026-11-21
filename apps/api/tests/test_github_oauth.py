import pytest
from unittest.mock import patch
from httpx import AsyncClient
from urllib.parse import urlparse, parse_qs
from src.config import settings
from src.services.crypto_service import crypto_service
from src.services.session_service import SessionService


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
