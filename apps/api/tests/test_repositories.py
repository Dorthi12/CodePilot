import pytest
import uuid
from unittest.mock import patch
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import settings
from src.models.user import User
from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.services.github_service import parse_github_url, GitHubOAuthError
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

    analyze_resp = await client.post(f"/api/v1/repositories/{repo_id}/analyze", headers=headers)
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["data"]["analysis_status"] == "READY"
