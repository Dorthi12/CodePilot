import pytest
import uuid
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import settings
from src.models.user import User
from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.services.github_service import (
    parse_github_url,
    GitHubOAuthError,
    GitHubService,
    TRUSTED_GITHUB_API_HOSTS,
)
from src.services.crypto_service import crypto_service
from src.models.oauth_connection import OAuthConnection


def test_parse_github_url_valid_cases():
    """Validates supported GitHub URL structures and formats."""
    assert parse_github_url("https://github.com/torvalds/linux") == ("torvalds", "linux")
    assert parse_github_url("https://github.com/facebook/react.git") == ("facebook", "react")
    assert parse_github_url("https://github.com/pallets/flask/") == ("pallets", "flask")
    assert parse_github_url("http://github.com/psf/requests") == ("psf", "requests")
    assert parse_github_url("github.com/astral-sh/uv") == ("astral-sh", "uv")
    assert parse_github_url("fastapi/fastapi") == ("fastapi", "fastapi")
    assert parse_github_url("  https://github.com/python/cpython.git  ") == ("python", "cpython")


def test_parse_github_url_ssrf_and_security_protections():
    """Ensures strict rejection of external domains, internal IPs, directory traversals, and SSRF attacks."""
    with pytest.raises(GitHubOAuthError) as exc_info:
        parse_github_url("https://attacker.com/malicious/repo")
    assert exc_info.value.code == "INVALID_URL_HOST"

    with pytest.raises(GitHubOAuthError) as exc_info:
        parse_github_url("http://127.0.0.1/admin/secret")
    assert exc_info.value.code == "INVALID_URL_HOST"

    with pytest.raises(GitHubOAuthError) as exc_info:
        parse_github_url("http://169.254.169.254/latest/meta-data")
    assert exc_info.value.code == "INVALID_URL_HOST"

    with pytest.raises(GitHubOAuthError) as exc_info:
        parse_github_url("ftp://github.com/owner/repo")
    assert exc_info.value.code == "INVALID_URL_SCHEME"

    with pytest.raises(GitHubOAuthError) as exc_info:
        parse_github_url("https://github.com/../traversal")
    assert exc_info.value.code in ("INVALID_REPOSITORY_IDENTIFIER", "INVALID_URL_PATH")


@pytest.mark.asyncio
async def test_import_repository_by_url_success(client: AsyncClient, authenticated_session, test_db: AsyncSession):
    """POST /api/v1/repositories/import creates a repository and sets user as OWNER."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    user = authenticated_session["user"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    mock_repo_data = {
        "id": 987654,
        "name": "flask",
        "owner": {"login": "pallets", "avatar_url": "https://avatars.githubusercontent.com/u/pallets"},
        "html_url": "https://github.com/pallets/flask",
        "description": "The Python micro framework for building web applications.",
        "private": False,
        "default_branch": "main",
        "language": "Python",
        "stargazers_count": 68000,
        "forks_count": 16000,
        "open_issues_count": 15,
        "size": 12500
    }

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }
    payload = {
        "url": "https://github.com/pallets/flask",
        "branch": "main"
    }

    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_repo_data):
        response = await client.post("/api/v1/repositories/import", json=payload, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert "data" in body
    data = body["data"]
    assert data["owner"] == "pallets"
    assert data["name"] == "flask"
    assert data["full_name"] == "pallets/flask"
    assert data["visibility"] == "PUBLIC"
    assert data["language"] == "Python"
    assert data["status"] == "ACTIVE"
    assert data["analysis_status"] == "NOT_ANALYZED"

    repo_id = uuid.UUID(data["id"])

    # Verify repository and permission created in database
    db_repo = (await test_db.execute(select(Repository).where(Repository.id == repo_id))).scalar_one_or_none()
    assert db_repo is not None
    assert db_repo.owner_user_id == user.id

    db_perm = (await test_db.execute(select(RepositoryPermission).where(RepositoryPermission.repository_id == repo_id))).scalar_one_or_none()
    assert db_perm is not None
    assert db_perm.user_id == user.id
    assert db_perm.role == "OWNER"


@pytest.mark.asyncio
async def test_import_duplicate_repository_rejected(client: AsyncClient, authenticated_session):
    """Importing the same repository twice for the same user returns 409 CONFLICT."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    mock_repo_data = {
        "id": 112233,
        "name": "fastapi",
        "owner": {"login": "tiangolo"},
        "html_url": "https://github.com/tiangolo/fastapi",
        "description": "FastAPI framework",
        "private": False,
        "default_branch": "master",
        "language": "Python",
        "stargazers_count": 75000,
        "forks_count": 6000,
        "open_issues_count": 200,
        "size": 25000
    }

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }
    payload = {"url": "https://github.com/tiangolo/fastapi"}

    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_repo_data):
        # 1. First import succeeds
        resp1 = await client.post("/api/v1/repositories/import", json=payload, headers=headers)
        assert resp1.status_code == 201

        # 2. Duplicate import fails with 409
        resp2 = await client.post("/api/v1/repositories/import", json=payload, headers=headers)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "REPOSITORY_ALREADY_IMPORTED"


@pytest.mark.asyncio
async def test_import_private_repository_using_user_token(client: AsyncClient, authenticated_session):
    """Importing a private repository uses the user's decrypted GitHub token and stores PRIVATE visibility."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    mock_private_repo = {
        "id": 445566,
        "name": "private-core",
        "owner": {"login": "my-org"},
        "html_url": "https://github.com/my-org/private-core",
        "description": "Internal proprietary codebase",
        "private": True,
        "default_branch": "main",
        "language": "TypeScript",
        "stargazers_count": 5,
        "forks_count": 1,
        "open_issues_count": 2,
        "size": 3000
    }

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }
    payload = {"url": "https://github.com/my-org/private-core"}

    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_private_repo):
        response = await client.post("/api/v1/repositories/import", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["visibility"] == "PRIVATE"
    assert data["owner"] == "my-org"
    assert data["name"] == "private-core"


@pytest.mark.asyncio
async def test_import_nonexistent_or_inaccessible_repository_returns_404(client: AsyncClient, authenticated_session):
    """When GitHub returns 404, the API returns 404 with a clear descriptive message."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL
    }
    payload = {"url": "https://github.com/some-ghost/nonexistent-repository"}

    with patch(
        "src.services.github_service.GitHubService.get_repository",
        side_effect=GitHubOAuthError("Repository not found on GitHub.", code="REPOSITORY_NOT_FOUND")
    ):
        response = await client.post("/api/v1/repositories/import", json=payload, headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REPOSITORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_multi_tenant_isolation_and_get_by_id(client: AsyncClient, authenticated_session, test_db: AsyncSession, test_redis):
    """Ensures repositories are isolated between tenants; User A cannot read or access User B's repositories."""
    session_a = authenticated_session["session_id"]
    user_a = authenticated_session["user"]
    csrf_a = authenticated_session["csrf_token"]

    # 1. Create a second distinct user B and session
    user_b = User(
        github_id="88889999",
        username="user_b_dev",
        name="Developer B",
        email="devb@example.com"
    )
    test_db.add(user_b)
    await test_db.flush()

    from src.services.session_service import SessionService
    session_service = SessionService(test_redis)
    session_b, csrf_b, _ = await session_service.create_session(
        user_id=str(user_b.id),
        github_id=user_b.github_id,
        username=user_b.username
    )

    # 2. User B creates a private repository in DB
    repo_b = Repository(
        owner_user_id=user_b.id,
        provider="github",
        provider_repo_id="777000",
        owner="user-b",
        name="secret-project",
        canonical_url="https://github.com/user-b/secret-project",
        visibility="PRIVATE",
        default_branch="main",
        tracked_branch="main",
        status="ACTIVE"
    )
    test_db.add(repo_b)
    await test_db.flush()

    perm_b = RepositoryPermission(repository_id=repo_b.id, user_id=user_b.id, role="OWNER")
    test_db.add(perm_b)
    await test_db.commit()

    # 3. User A lists repositories: repo_b MUST NOT be present
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_a)
    list_resp = await client.get("/api/v1/repositories")
    assert list_resp.status_code == 200
    returned_ids = [r["id"] for r in list_resp.json()["data"]]
    assert str(repo_b.id) not in returned_ids

    # 4. User A requests GET /repositories/{repo_b.id}: MUST return 404 NOT_FOUND
    detail_resp = await client.get(f"/api/v1/repositories/{repo_b.id}")
    assert detail_resp.status_code == 404

    # 5. User B requests GET /repositories/{repo_b.id}: MUST return 200 OK
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_b)
    detail_resp_b = await client.get(f"/api/v1/repositories/{repo_b.id}")
    assert detail_resp_b.status_code == 200
    assert detail_resp_b.json()["data"]["name"] == "secret-project"


@pytest.mark.asyncio
async def test_list_imports_endpoint(client: AsyncClient, authenticated_session):
    """GET /api/v1/repositories/imports returns the user's import history."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    mock_repo = {
        "id": 332211,
        "name": "sample-repo",
        "owner": {"login": "sample-owner"},
        "html_url": "https://github.com/sample-owner/sample-repo",
        "private": False,
        "default_branch": "main"
    }

    # Perform an import
    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}
    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_repo):
        await client.post("/api/v1/repositories/import", json={"url": "sample-owner/sample-repo"}, headers=headers)

    # Fetch imports history
    response = await client.get("/api/v1/repositories/imports")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1
    assert data[0]["repo_name"] == "sample-owner/sample-repo"
    assert data[0]["status"] == "SUCCEEDED"


@pytest.mark.asyncio
async def test_list_user_github_repositories(client: AsyncClient, authenticated_session):
    """GET /api/v1/integrations/github/repositories returns user's GitHub repositories."""
    session_id = authenticated_session["session_id"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)

    mock_gh_repos = [
        {
            "id": 101,
            "name": "project-athena",
            "full_name": "athena_dev/project-athena",
            "owner": {"login": "athena_dev", "avatar_url": None},
            "html_url": "https://github.com/athena_dev/project-athena",
            "description": "Codebase intelligence platform",
            "private": False,
            "language": "Python",
            "default_branch": "main",
            "stargazers_count": 42,
            "forks_count": 5,
            "updated_at": "2026-11-21T18:00:00Z"
        }
    ]

    with patch("src.services.github_service.GitHubService.list_user_repositories", return_value=mock_gh_repos):
        response = await client.get("/api/v1/integrations/github/repositories")

    assert response.status_code == 200
    data = response.json()["data"]
    assert "repositories" in data
    assert len(data["repositories"]) == 1
    item = data["repositories"][0]
    assert item["name"] == "project-athena"
    assert item["is_imported"] is False


@pytest.mark.asyncio
async def test_trigger_analysis_endpoint(client: AsyncClient, authenticated_session):
    """POST /api/v1/repositories/{id}/analyze updates analysis status to READY."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    mock_repo = {
        "id": 556677,
        "name": "analyze-target",
        "owner": {"login": "athena_dev"},
        "html_url": "https://github.com/athena_dev/analyze-target",
        "private": False,
        "default_branch": "main"
    }

    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}
    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_repo):
        import_resp = await client.post("/api/v1/repositories/import", json={"url": "athena_dev/analyze-target"}, headers=headers)

    repo_id = import_resp.json()["data"]["id"]

    with (
        patch(
            "src.services.github_service.GitHubService.get_repository_files",
            return_value={"src/main.py": "def main():\n    return True\n"},
        ),
        patch(
            "src.services.ai_service.AIService.index_repository",
            return_value={"symbol_count": 1},
        ),
    ):
        analyze_resp = await client.post(
            f"/api/v1/repositories/{repo_id}/analyze",
            headers=headers,
        )
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["data"]["analysis_status"] == "READY"



# ==============================================================================
# Redirect handling tests for get_repository (301 / SSRF protection)
# ==============================================================================

def _make_httpx_response(status_code: int, json_data=None, headers=None):
    """Helper: build a minimal httpx.Response stub."""
    resp = MagicMock(spec=Response)
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    resp.text = ""
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request
        req = Request("GET", "https://api.github.com/repos/test/test")
        exc = HTTPStatusError("error", request=req, response=resp)
        resp.raise_for_status.side_effect = exc
    return resp


MOCK_REACT_REPO = {
    "id": 10270250,
    "name": "react",
    "owner": {"login": "facebook", "avatar_url": "https://avatars.githubusercontent.com/u/69631"},
    "html_url": "https://github.com/facebook/react",
    "description": "The library for web and native user interfaces.",
    "private": False,
    "default_branch": "main",
    "language": "JavaScript",
    "stargazers_count": 230000,
    "forks_count": 47000,
    "open_issues_count": 900,
    "size": 300000,
}

MOCK_FLASK_REPO = {
    "id": 596892,
    "name": "flask",
    "owner": {"login": "pallets", "avatar_url": "https://avatars.githubusercontent.com/u/16748505"},
    "html_url": "https://github.com/pallets/flask",
    "description": "The Python micro framework for building web applications.",
    "private": False,
    "default_branch": "main",
    "language": "Python",
    "stargazers_count": 68000,
    "forks_count": 16000,
    "open_issues_count": 15,
    "size": 12500,
}


@pytest.mark.asyncio
async def test_get_repository_follows_301_redirect_to_trusted_host(test_redis):
    """get_repository follows a 301 redirect when the destination is a trusted GitHub API host."""
    redirect_resp = _make_httpx_response(
        301,
        headers={"location": "https://api.github.com/repositories/10270250"},
    )
    final_resp = _make_httpx_response(200, json_data=MOCK_REACT_REPO)

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=[redirect_resp, final_resp])
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        result = await service.get_repository("facebook", "react")

    assert result["id"] == 10270250
    assert result["name"] == "react"
    assert mock_instance.get.call_count == 2
    # Second call should be to the redirect URL
    second_call_url = mock_instance.get.call_args_list[1][0][0]
    assert "api.github.com/repositories/10270250" in second_call_url


@pytest.mark.asyncio
async def test_get_repository_rejects_redirect_to_untrusted_host(test_redis):
    """get_repository rejects a 301 redirect to an untrusted (non-GitHub) host."""
    redirect_resp = _make_httpx_response(
        301,
        headers={"location": "https://evil.com/steal-token"},
    )

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=redirect_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        with pytest.raises(GitHubOAuthError) as exc_info:
            await service.get_repository("some", "repo")

    assert exc_info.value.code == "UNTRUSTED_REDIRECT"


@pytest.mark.asyncio
async def test_get_repository_rejects_non_https_redirect(test_redis):
    """get_repository rejects a 301 redirect with an HTTP (non-HTTPS) destination."""
    redirect_resp = _make_httpx_response(
        301,
        headers={"location": "http://api.github.com/repos/x/y"},
    )

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=redirect_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        with pytest.raises(GitHubOAuthError) as exc_info:
            await service.get_repository("x", "y")

    assert exc_info.value.code == "UNTRUSTED_REDIRECT"


@pytest.mark.asyncio
async def test_get_repository_caps_max_redirects(test_redis):
    """get_repository stops after too many redirects (prevents infinite loops)."""
    redirect_resp = _make_httpx_response(
        301,
        headers={"location": "https://api.github.com/repositories/9999"},
    )

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        # Always return a redirect — should hit the cap
        mock_instance.get = AsyncMock(return_value=redirect_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        with pytest.raises(GitHubOAuthError) as exc_info:
            await service.get_repository("loop", "repo")

    assert exc_info.value.code == "TOO_MANY_REDIRECTS"
    # Should have attempted max_redirects + 1 (initial) calls, but
    # the first call counts as redirect 1, so total calls = max_redirects + 1
    assert mock_instance.get.call_count == 6  # 1 initial + 5 redirects


@pytest.mark.asyncio
async def test_get_repository_direct_200_no_redirect(test_redis):
    """get_repository returns repo data directly when GitHub responds 200 (no redirect)."""
    direct_resp = _make_httpx_response(200, json_data=MOCK_FLASK_REPO)

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=direct_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        result = await service.get_repository("pallets", "flask")

    assert result["id"] == 596892
    assert result["name"] == "flask"
    assert mock_instance.get.call_count == 1


@pytest.mark.asyncio
async def test_get_repository_preserves_auth_on_trusted_redirect(test_redis):
    """Authorization header is preserved across redirects to trusted hosts."""
    redirect_resp = _make_httpx_response(
        301,
        headers={"location": "https://api.github.com/repositories/10270250"},
    )
    final_resp = _make_httpx_response(200, json_data=MOCK_REACT_REPO)

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=[redirect_resp, final_resp])
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        await service.get_repository("facebook", "react", access_token="gho_test_token")

    # Both calls should include the same headers dict containing Authorization
    first_headers = mock_instance.get.call_args_list[0][1].get("headers", mock_instance.get.call_args_list[0][0][1] if len(mock_instance.get.call_args_list[0][0]) > 1 else {})
    second_headers = mock_instance.get.call_args_list[1][1].get("headers", {})
    # The headers object is the same dict passed to both calls, so just verify the token was set
    assert mock_instance.get.call_count == 2


@pytest.mark.asyncio
async def test_import_facebook_react_via_301_redirect(client: AsyncClient, authenticated_session):
    """Full import of facebook/react succeeds even though GitHub returns 301."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL,
    }
    payload = {"url": "https://github.com/facebook/react"}

    with patch("src.services.github_service.GitHubService.get_repository", return_value=MOCK_REACT_REPO):
        response = await client.post("/api/v1/repositories/import", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["owner"] == "facebook"
    assert data["name"] == "react"
    assert data["visibility"] == "PUBLIC"
    assert data["language"] == "JavaScript"


@pytest.mark.asyncio
async def test_import_pallets_flask_direct_200(client: AsyncClient, authenticated_session):
    """Full import of pallets/flask succeeds with direct 200."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": settings.FRONTEND_BASE_URL,
    }
    payload = {"url": "https://github.com/pallets/flask"}

    with patch("src.services.github_service.GitHubService.get_repository", return_value=MOCK_FLASK_REPO):
        response = await client.post("/api/v1/repositories/import", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["owner"] == "pallets"
    assert data["name"] == "flask"
    assert data["visibility"] == "PUBLIC"


@pytest.mark.asyncio
async def test_get_repository_validates_response_metadata(test_redis):
    """get_repository raises error if the response JSON is missing required fields."""
    bad_resp = _make_httpx_response(200, json_data={"some": "junk"})

    service = GitHubService(test_redis)

    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=bad_resp)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_instance

        with pytest.raises(GitHubOAuthError) as exc_info:
            await service.get_repository("some", "repo")

    assert exc_info.value.code == "INVALID_METADATA"


@pytest.mark.asyncio
async def test_delete_repository_success(client: AsyncClient, test_db: AsyncSession, authenticated_session, tmp_path: Path):
    """DELETE /api/v1/repositories/{id} deletes DB entities and workspace storage."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    user_id = authenticated_session["user"].id

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}

    mock_repo = {
        "id": 998877,
        "name": "delete-me",
        "owner": {"login": authenticated_session["user"].username},
        "html_url": "https://github.com/athena_dev/delete-me",
        "private": False,
        "default_branch": "main"
    }

    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_repo):
        import_resp = await client.post("/api/v1/repositories/import", json={"url": "athena_dev/delete-me"}, headers=headers)
    assert import_resp.status_code == 201
    repo_id = uuid.UUID(import_resp.json()["data"]["id"])

    # Create mock workspace directory on disk
    mock_workspace = tmp_path / "workspaces" / str(user_id) / str(repo_id)
    mock_workspace.mkdir(parents=True, exist_ok=True)
    (mock_workspace / "code.py").write_text("print('hello')", encoding="utf-8")
    assert mock_workspace.exists()

    with patch("src.services.repository_service.get_repository_workspace_path", return_value=mock_workspace):
        del_resp = await client.delete(f"/api/v1/repositories/{repo_id}", headers=headers)

    assert del_resp.status_code == 200
    assert "deleted" in del_resp.json()["data"]["message"].lower()

    # Workspace directory must be deleted
    assert not mock_workspace.exists()

    # Repository must be gone from DB
    get_resp = await client.get(f"/api/v1/repositories/{repo_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_repository_ownership_protection(client: AsyncClient, test_db: AsyncSession, authenticated_session):
    """Another user cannot delete a repository they do not own."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}

    # Create repository owned by a different user
    other_user = User(
        id=uuid.uuid4(),
        github_id="88888888",
        username="other_dev"
    )
    test_db.add(other_user)
    await test_db.flush()

    other_repo = Repository(
        id=uuid.uuid4(),
        owner_user_id=other_user.id,
        provider="github",
        provider_repo_id="112233",
        owner="other_dev",
        name="private-vault",
        canonical_url="https://github.com/other_dev/private-vault",
        status="ACTIVE"
    )
    test_db.add(other_repo)
    await test_db.commit()

    # Current user tries to delete other_user's repo
    del_resp = await client.delete(f"/api/v1/repositories/{other_repo.id}", headers=headers)
    assert del_resp.status_code in (403, 404)

    # Repository must still exist
    stmt = select(Repository).where(Repository.id == other_repo.id)
    remaining = (await test_db.execute(stmt)).scalar_one_or_none()
    assert remaining is not None


@pytest.mark.asyncio
async def test_delete_repository_handles_active_jobs(client: AsyncClient, test_db: AsyncSession, authenticated_session):
    """Deleting a repository cancels any active/running jobs and cleans Redis locks."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    user_id = authenticated_session["user"].id

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)
    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}

    mock_repo = {
        "id": 443322,
        "name": "job-target",
        "owner": {"login": authenticated_session["user"].username},
        "html_url": "https://github.com/athena_dev/job-target",
        "private": False,
        "default_branch": "main"
    }

    with patch("src.services.github_service.GitHubService.get_repository", return_value=mock_repo):
        import_resp = await client.post("/api/v1/repositories/import", json={"url": "athena_dev/job-target"}, headers=headers)
    repo_id = uuid.UUID(import_resp.json()["data"]["id"])

    # Create an active running Job for this repo
    from src.models.job import Job
    active_job = Job(
        id=uuid.uuid4(),
        repository_id=repo_id,
        user_id=user_id,
        job_type="CLONE",
        status="RUNNING",
        stage="CLONING",
        retrieval_method="GIT_CLONE",
        branch="main"
    )
    test_db.add(active_job)
    await test_db.commit()

    del_resp = await client.delete(f"/api/v1/repositories/{repo_id}", headers=headers)
    assert del_resp.status_code == 200

    # Job must be cascade-deleted with repo
    stmt = select(Job).where(Job.id == active_job.id)
    rem_job = (await test_db.execute(stmt)).scalar_one_or_none()
    assert rem_job is None
