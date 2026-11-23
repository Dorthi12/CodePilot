import pytest
from httpx import AsyncClient
from src.config import settings


@pytest.mark.asyncio
async def test_csrf_missing_token_rejected(client: AsyncClient, authenticated_session):
    """Mutating request without X-CSRF-Token or cp_csrf cookie is rejected with 403."""
    session_id = authenticated_session["session_id"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.asyncio
async def test_csrf_mismatched_token_rejected(client: AsyncClient, authenticated_session):
    """Mutating request with incorrect X-CSRF-Token is rejected with 403."""
    session_id = authenticated_session["session_id"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)

    headers = {
        "X-CSRF-Token": "incorrect-forged-csrf-token",
        "Origin": settings.FRONTEND_BASE_URL
    }
    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.asyncio
async def test_csrf_untrusted_origin_rejected(client: AsyncClient, authenticated_session):
    """Mutating request with an attacker's origin is rejected with 403."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": "https://malicious-attacker-site.com"
    }
    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


@pytest.mark.asyncio
async def test_csrf_valid_token_and_origin_accepted(client: AsyncClient, authenticated_session):
    """Mutating request with matching CSRF token and allowed origin succeeds."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }
    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["message"] == "Successfully logged out"
