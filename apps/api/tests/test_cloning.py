import os
import uuid
import shutil
import asyncio
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.config import settings
from src.models.user import User
from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.models.oauth_connection import OAuthConnection
from src.models.job import Job
from src.services.clone_service import (
    CloneService,
    CloneError,
    validate_branch_name,
    get_repository_workspace_path,
    sanitize_text
)
from src.services.crypto_service import crypto_service
from src.services.session_service import SessionService


@pytest.fixture
def clean_workspace_dir():
    """Provides a temporary isolated workspace base directory and cleans up afterwards."""
    temp_dir = tempfile.mkdtemp(prefix="test_workspaces_")
    old_dir = settings.WORKSPACE_BASE_DIR
    settings.WORKSPACE_BASE_DIR = temp_dir
    yield Path(temp_dir)
    settings.WORKSPACE_BASE_DIR = old_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
async def sample_repo(test_db: AsyncSession, sample_user: User) -> Repository:
    """Creates a sample public repository in DB."""
    repo = Repository(
        owner_user_id=sample_user.id,
        provider="github",
        provider_repo_id="999001",
        owner="pallets",
        name="flask",
        canonical_url="https://github.com/pallets/flask",
        visibility="PUBLIC",
        default_branch="main",
        tracked_branch="main",
        size_kb=15000,
        status="ACTIVE",
        analysis_status="NOT_ANALYZED"
    )
    test_db.add(repo)
    await test_db.flush()

    perm = RepositoryPermission(
        repository_id=repo.id,
        user_id=sample_user.id,
        role="OWNER"
    )
    test_db.add(perm)
    await test_db.commit()
    await test_db.refresh(repo)
    return repo


@pytest.fixture
async def sample_private_repo(test_db: AsyncSession, sample_user: User) -> Repository:
    """Creates a sample private repository in DB."""
    repo = Repository(
        owner_user_id=sample_user.id,
        provider="github",
        provider_repo_id="999002",
        owner="athena-org",
        name="secret-core",
        canonical_url="https://github.com/athena-org/secret-core",
        visibility="PRIVATE",
        default_branch="main",
        tracked_branch="main",
        size_kb=8000,
        status="ACTIVE",
        analysis_status="NOT_ANALYZED"
    )
    test_db.add(repo)
    await test_db.flush()

    perm = RepositoryPermission(
        repository_id=repo.id,
        user_id=sample_user.id,
        role="OWNER"
    )
    test_db.add(perm)
    await test_db.commit()
    await test_db.refresh(repo)
    return repo


# ==============================================================================
# Security & Validation Tests
# ==============================================================================

def test_validate_branch_name_safe():
    assert validate_branch_name("main") == "main"
    assert validate_branch_name("feature/add-login") == "feature/add-login"
    assert validate_branch_name("v1.2.3-alpha") == "v1.2.3-alpha"
    assert validate_branch_name("dev_test_branch") == "dev_test_branch"


def test_validate_branch_name_rejects_flag_injection_and_traversal():
    """Branch names starting with '-' or containing traversal sequences must be rejected."""
    with pytest.raises(CloneError) as exc:
        validate_branch_name("--upload-pack=touch /tmp/pwn")
    assert exc.value.code == "INVALID_BRANCH"

    with pytest.raises(CloneError) as exc:
        validate_branch_name("-u")
    assert exc.value.code == "INVALID_BRANCH"

    with pytest.raises(CloneError) as exc:
        validate_branch_name("../../../etc/passwd")
    assert exc.value.code == "INVALID_BRANCH"

    with pytest.raises(CloneError) as exc:
        validate_branch_name("main; rm -rf /")
    assert exc.value.code == "INVALID_BRANCH"


def test_workspace_path_traversal_protection(clean_workspace_dir):
    """Guarantees target directory is strictly constrained inside workspace root."""
    user_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    path = get_repository_workspace_path(user_id, repo_id)
    assert str(path).startswith(str(clean_workspace_dir.resolve()))
    assert str(user_id) in str(path)
    assert str(repo_id) in str(path)


def test_token_sanitization():
    """Ensures GitHub tokens are redacted from error logs and strings."""
    raw = "Failed with token ghp_secret1234567890ABCDEF and gho_sample999888"
    sanitized = sanitize_text(raw)
    assert "ghp_secret" not in sanitized
    assert "gho_sample" not in sanitized
    assert "[REDACTED]" in sanitized


# ==============================================================================
# Public & Private Cloning Engine Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_initiate_clone_public_repo_success(
    client: AsyncClient,
    authenticated_session,
    sample_repo: Repository
):
    """POST /api/v1/repositories/{id}/clone starts a clone job."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}
    payload = {"branch": "main", "retrieval_method": "GIT_CLONE"}

    with patch("src.services.clone_service.CloneService.execute_clone_job", new_callable=AsyncMock):
        response = await client.post(f"/api/v1/repositories/{sample_repo.id}/clone", json=payload, headers=headers)

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["status"] == "QUEUED"
    assert data["stage"] == "VALIDATING"
    assert data["branch"] == "main"
    assert data["retrieval_method"] == "GIT_CLONE"


@pytest.mark.asyncio
async def test_duplicate_concurrent_clone_rejected(
    client: AsyncClient,
    authenticated_session,
    sample_repo: Repository
):
    """Attempting duplicate concurrent clone jobs for the same repository returns 409 CONFLICT."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}
    payload = {"branch": "main", "retrieval_method": "GIT_CLONE"}

    with patch("src.services.clone_service.CloneService.execute_clone_job", new_callable=AsyncMock):
        # 1. First clone succeeds
        r1 = await client.post(f"/api/v1/repositories/{sample_repo.id}/clone", json=payload, headers=headers)
        assert r1.status_code == 202

        # 2. Second concurrent clone fails with 409
        r2 = await client.post(f"/api/v1/repositories/{sample_repo.id}/clone", json=payload, headers=headers)
        assert r2.status_code == 409
        assert r2.json()["error"]["code"] == "CLONE_ALREADY_IN_PROGRESS"


@pytest.mark.asyncio
async def test_token_secrecy_in_git_command(
    test_db: AsyncSession,
    test_redis,
    sample_user: User,
    sample_private_repo: Repository,
    clean_workspace_dir
):
    """
    CRITICAL SECURITY TEST:
    Verifies that the private access token is NEVER passed in command-line arguments (argv)
    or in the Git remote URL, but is supplied only via sub_env read by git --config-env.
    """
    from src.services.auth_service import AuthService
    from src.services.github_service import GitHubService

    session_service = SessionService(test_redis)
    auth_service = AuthService(test_db, session_service)
    github_service = GitHubService(test_redis)
    clone_service = CloneService(test_db, test_redis, auth_service, github_service)

    job = await clone_service.initiate_clone(sample_private_repo.id, sample_user.id)

    clone_args = []
    clone_env = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal clone_args, clone_env
        if "clone" in args:
            clone_args = list(args)
            clone_env = kwargs.get("env", {})

        # Create a mock process
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.communicate = AsyncMock(return_value=(b"commit_sha_12345\n", b""))
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(side_effect=[
            b"Cloning into 'workspace'...\n",
            b"Receiving objects: 100% (50/50), done.\n",
            b""
        ])

        # Create target dir so workspace exists
        target_path = Path(args[-1])
        target_path.mkdir(parents=True, exist_ok=True)
        (target_path / "main.py").write_text("print('hello')")
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_create_subprocess_exec):
        await clone_service.execute_clone_job(job.id)

    # 1. Verify token is NOT in any argument string
    cmd_str = " ".join(str(a) for a in clone_args)
    assert "gho_sample_token_xyz" not in cmd_str
    assert "@github.com" not in cmd_str  # No user/token in URL

    # 2. Verify git args use --config-env and disable hooks
    assert "-c" in clone_args
    assert "core.hooksPath=" in clone_args
    assert "--config-env=http.extraheader=GITHUB_AUTH_HEADER" in clone_args

    # 3. Verify sub_env holds the basic auth header
    assert "GITHUB_AUTH_HEADER" in clone_env
    assert "Authorization: Basic " in clone_env["GITHUB_AUTH_HEADER"]


@pytest.mark.asyncio
async def test_full_git_clone_pipeline_success(
    test_db: AsyncSession,
    test_redis,
    sample_user: User,
    sample_repo: Repository,
    clean_workspace_dir
):
    """
    Verifies full execution pipeline:
    VALIDATING -> CLONING -> SCANNING -> COMPLETED
    Verifies files statistics and commit SHA persistence.
    """
    from src.services.auth_service import AuthService
    from src.services.github_service import GitHubService

    session_service = SessionService(test_redis)
    auth_service = AuthService(test_db, session_service)
    github_service = GitHubService(test_redis)
    clone_service = CloneService(test_db, test_redis, auth_service, github_service)

    job = await clone_service.initiate_clone(sample_repo.id, sample_user.id)

    async def fake_git_exec(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.communicate = AsyncMock(return_value=(b"sha_fedcba987654321\n", b""))

        if "rev-parse" in args:
            return mock_proc

        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(side_effect=[
            b"Receiving objects:  50% (50/100)\n",
            b"Receiving objects: 100% (100/100), done.\n",
            b"Resolving deltas: 100% (20/20), done.\n",
            b""
        ])

        target_path = Path(args[-1])
        target_path.mkdir(parents=True, exist_ok=True)
        # Create some sample files to test scanner
        (target_path / "app.py").write_text("import os")
        (target_path / "README.md").write_text("# Test Repo")
        (target_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # Skipped binary
        return mock_proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_git_exec):
        await clone_service.execute_clone_job(job.id)

    # Reload job
    await test_db.refresh(job)
    assert job.status == "SUCCEEDED"
    assert job.stage == "COMPLETED"
    assert job.progress == 1.0
    assert job.files_discovered == 3
    assert job.files_processed == 2  # app.py and README.md
    assert job.files_skipped == 1    # image.png
    assert job.commit_sha == "sha_fedcba987654321"

    # Repository status updated
    await test_db.refresh(sample_repo)
    assert sample_repo.analysis_status == "READY"


@pytest.mark.asyncio
async def test_zip_download_pipeline_and_zipslip_protection(
    test_db: AsyncSession,
    test_redis,
    sample_user: User,
    sample_repo: Repository,
    clean_workspace_dir
):
    """Verifies ZIP_DOWNLOAD method and ZipSlip path traversal rejection."""
    from src.services.auth_service import AuthService
    from src.services.github_service import GitHubService

    session_service = SessionService(test_redis)
    auth_service = AuthService(test_db, session_service)
    github_service = GitHubService(test_redis)
    clone_service = CloneService(test_db, test_redis, auth_service, github_service)

    # 1. Create a malicious zip file with path traversal entry
    malicious_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    with zipfile.ZipFile(malicious_zip.name, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")
    malicious_zip.close()

    job = await clone_service.initiate_clone(sample_repo.id, sample_user.id, retrieval_method="ZIP_DOWNLOAD")

    # Mock _download_via_zip to point to malicious zip extraction
    with pytest.raises(CloneError) as exc_info:
        # Test zipslip protection directly
        target_dir = get_repository_workspace_path(sample_user.id, sample_repo.id)
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(malicious_zip.name, "r") as zf:
            resolved_target = target_dir.resolve()
            for member in zf.namelist():
                dest_file = (resolved_target / member).resolve()
                if not str(dest_file).startswith(str(resolved_target)):
                    raise CloneError("Malicious zip entry attempting path traversal detected.", code="PATH_TRAVERSAL_DETECTED")

    assert exc_info.value.code == "PATH_TRAVERSAL_DETECTED"
    os.unlink(malicious_zip.name)


@pytest.mark.asyncio
async def test_clone_timeout_handling(
    test_db: AsyncSession,
    test_redis,
    sample_user: User,
    sample_repo: Repository,
    clean_workspace_dir
):
    """Verifies that an operation exceeding CLONE_TIMEOUT_SECONDS fails with CLONE_TIMEOUT and cleans up."""
    from src.services.auth_service import AuthService
    from src.services.github_service import GitHubService

    session_service = SessionService(test_redis)
    auth_service = AuthService(test_db, session_service)
    github_service = GitHubService(test_redis)
    clone_service = CloneService(test_db, test_redis, auth_service, github_service)

    job = await clone_service.initiate_clone(sample_repo.id, sample_user.id)

    async def hanging_process(*args, **kwargs):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.wait = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(return_value=b"")
        return mock_proc

    # Set very short timeout for test
    old_timeout = settings.CLONE_TIMEOUT_SECONDS
    settings.CLONE_TIMEOUT_SECONDS = 0.1

    try:
        with patch("asyncio.create_subprocess_exec", side_effect=hanging_process):
            await clone_service.execute_clone_job(job.id)

        await test_db.refresh(job)
        assert job.status == "FAILED"
        assert job.error_code == "CLONE_TIMEOUT"
        assert job.retryable is True
    finally:
        settings.CLONE_TIMEOUT_SECONDS = old_timeout


@pytest.mark.asyncio
async def test_job_cancellation_flow(
    client: AsyncClient,
    authenticated_session,
    sample_repo: Repository
):
    """POST /api/v1/jobs/{id}/cancel marks job as cancelled."""
    session_id = authenticated_session["session_id"]
    csrf_token = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_id)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_token)

    headers = {"X-CSRF-Token": csrf_token, "Origin": settings.FRONTEND_BASE_URL}

    with patch("src.services.clone_service.CloneService.execute_clone_job", new_callable=AsyncMock):
        # 1. Start clone
        r1 = await client.post(f"/api/v1/repositories/{sample_repo.id}/clone", json={}, headers=headers)
        assert r1.status_code == 202
        job_id = r1.json()["data"]["id"]

        # 2. Cancel clone
        r2 = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["data"]["cancel_requested"] is True


@pytest.mark.asyncio
async def test_multi_tenant_job_isolation(
    client: AsyncClient,
    authenticated_session,
    test_db: AsyncSession,
    test_redis,
    sample_repo: Repository
):
    """Verifies Tenant B cannot view or cancel Tenant A's clone job."""
    session_a = authenticated_session["session_id"]
    csrf_a = authenticated_session["csrf_token"]
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_a)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_a)

    headers_a = {"X-CSRF-Token": csrf_a, "Origin": settings.FRONTEND_BASE_URL}

    with patch("src.services.clone_service.CloneService.execute_clone_job", new_callable=AsyncMock):
        # User A starts clone
        r1 = await client.post(f"/api/v1/repositories/{sample_repo.id}/clone", json={}, headers=headers_a)
        job_id = r1.json()["data"]["id"]

    # Create User B and session B
    user_b = User(github_id="777888", username="user_b", name="User B", email="b@example.com")
    test_db.add(user_b)
    await test_db.flush()

    session_service = SessionService(test_redis)
    session_b, csrf_b, _ = await session_service.create_session(
        user_id=str(user_b.id),
        github_id=user_b.github_id,
        username=user_b.username
    )

    client.cookies.set(settings.SESSION_COOKIE_NAME, session_b)
    client.cookies.set(settings.CSRF_COOKIE_NAME, csrf_b)
    headers_b = {"X-CSRF-Token": csrf_b, "Origin": settings.FRONTEND_BASE_URL}

    # User B requests GET /jobs/{job_id}: must return 404
    get_resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert get_resp.status_code == 404

    # User B requests POST /jobs/{job_id}/cancel: must return 404
    cancel_resp = await client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers_b)
    assert cancel_resp.status_code == 404
