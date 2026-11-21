import pytest
from httpx import AsyncClient
from src.config import settings


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    """GET /api/v1/auth/me should return 401 when no session cookie is provided."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, authenticated_session):
    """GET /api/v1/auth/me should return user data when a valid cp_session cookie is sent."""
    session_id = authenticated_session["session_id"]
    user = authenticated_session["user"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert body["data"]["username"] == user.username
    assert body["data"]["github_id"] == user.github_id
    assert body["data"]["email"] == user.email


@pytest.mark.asyncio
async def test_get_me_with_invalid_session_cookie(client: AsyncClient):
    """GET /api/v1/auth/me should return 401 if cp_session contains a nonexistent session ID."""
    client.cookies.set(settings.SESSION_COOKIE_NAME, "nonexistent-session-id-12345")
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_logout_without_csrf_fails(client: AsyncClient, authenticated_session):
    """POST /api/v1/auth/logout should fail with 403 CSRF_FAILED if X-CSRF-Token is missing."""
    session_id = authenticated_session["session_id"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, authenticated_session, test_redis):
    """POST /api/v1/auth/logout with valid CSRF token should invalidate session in Redis and clear cookies."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }

    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["message"] == "Successfully logged out"

    # Verify session is deleted from Redis
    session_in_redis = await test_redis.get(f"sess:{session_id}")
    assert session_in_redis is None

    # Subsequent GET /auth/me should fail with 401
    me_resp = await client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
