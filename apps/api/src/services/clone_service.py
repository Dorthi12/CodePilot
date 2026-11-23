import os
import sys
import re
import uuid
import time
import shutil
import base64
import logging
import asyncio
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

import httpx
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update

from src.config import settings
from src.models.job import Job
from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.services.crypto_service import crypto_service
from src.services.auth_service import AuthService
from src.services.github_service import GitHubService, GITHUB_HTTP_USER_AGENT, TRUSTED_GITHUB_API_HOSTS

logger = logging.getLogger(__name__)

# Valid git ref / branch pattern (prevents flag injection and path traversal)
# Must not start with '-', no control chars, no .., no spaces
SAFE_BRANCH_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*$")

# Sensitive token redaction regex
TOKEN_REDACT_REGEX = re.compile(r"(ghp_[A-Za-z0-9_]+|gho_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|Bearer\s+[A-Za-z0-9_.-]+|Basic\s+[A-Za-z0-9+/=]+)")

# Trusted hosts for zipball archive downloads
TRUSTED_ARCHIVE_HOSTS = {"api.github.com", "codeload.github.com", "github.com"}

# Directories and file extensions to skip during scanning
IGNORED_SCAN_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "dist", "build", "target", "vendor",
    "__pycache__", ".venv", "venv", ".idea", ".vscode", ".next", ".nuxt",
    ".cache", "coverage", ".pytest_cache"
}
IGNORED_SCAN_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pdf", ".zip", ".tar",
    ".gz", ".7z", ".rar", ".exe", ".dll", ".so", ".dylib", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".avi", ".mov", ".wav", ".pyc", ".pyo",
    ".class", ".o", ".a", ".min.js", ".min.css", ".map"
}


def sanitize_text(text: Optional[str]) -> Optional[str]:
    """Redacts any potential GitHub or OAuth tokens from strings before logging or storing."""
    if not text:
        return text
    return TOKEN_REDACT_REGEX.sub("[REDACTED]", text)


def validate_branch_name(branch: str) -> str:
    """
    Validates branch name to prevent flag injection (e.g. --upload-pack)
    and path traversal.
    """
    if not branch or not isinstance(branch, str):
        raise CloneError("Branch name must be provided.", code="INVALID_BRANCH")

    cleaned = branch.strip()
    if cleaned.startswith("-"):
        raise CloneError("Branch name cannot start with a hyphen.", code="INVALID_BRANCH")

    if ".." in cleaned or "\\" in cleaned or "\x00" in cleaned:
        raise CloneError("Branch name contains illegal traversal characters.", code="INVALID_BRANCH")

    if not SAFE_BRANCH_REGEX.match(cleaned) or len(cleaned) > 255:
        raise CloneError(f"Invalid branch name '{cleaned}'.", code="INVALID_BRANCH")

    return cleaned


def get_repository_workspace_path(user_id: uuid.UUID, repository_id: uuid.UUID) -> Path:
    """
    Resolves and strictly bounds the isolated workspace path for a user/repository.
    Guarantees that the destination is constrained inside settings.WORKSPACE_BASE_DIR.
    """
    base_dir = Path(settings.WORKSPACE_BASE_DIR).resolve()
    target_dir = (base_dir / str(user_id) / str(repository_id)).resolve()

    # Path traversal verification
    if not str(target_dir).startswith(str(base_dir)):
        raise CloneError("Path traversal detected in workspace path resolution.", code="PATH_TRAVERSAL_DETECTED")

    return target_dir


class CloneError(Exception):
    def __init__(self, message: str, code: str = "CLONE_ERROR", retryable: bool = False):
        super().__init__(message)
        self.message = sanitize_text(message) or ""
        self.code = code
        self.retryable = retryable


class CloneService:
    def __init__(
        self,
        db: AsyncSession,
        redis: aioredis.Redis,
        auth_service: AuthService,
        github_service: GitHubService
    ):
        self.db = db
        self.redis = redis
        self.auth_service = auth_service
        self.github_service = github_service

    def _lock_key(self, repo_id: uuid.UUID) -> str:
        return f"lock:repo:clone:{repo_id}"

    def _job_progress_key(self, job_id: uuid.UUID) -> str:
        return f"job:{job_id}:progress"

    def _cancel_key(self, job_id: uuid.UUID) -> str:
        return f"job:{job_id}:cancel"

    async def get_job(self, job_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Job]:
        """Fetches a job by ID verifying multi-tenant ownership."""
        stmt = select(Job).where(Job.id == job_id, Job.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_repository_job(self, repository_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Job]:
        """Fetches the latest job for a repository verifying multi-tenant access."""
        stmt = (
            select(Job)
            .where(Job.repository_id == repository_id, Job.user_id == user_id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def cancel_job(self, job_id: uuid.UUID, user_id: uuid.UUID) -> Job:
        """Requests cancellation for an active job."""
        job = await self.get_job(job_id, user_id)
        if not job:
            raise CloneError("Job not found or access denied.", code="JOB_NOT_FOUND")

        if job.status not in ("QUEUED", "RUNNING"):
            return job

        job.cancel_requested = True
        job.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)

        # Set cancellation flag in Redis for real-time runner check
        await self.redis.set(self._cancel_key(job_id), "1", ex=300)
        logger.info("Cancellation requested for job %s (user: %s)", job_id, user_id)
        return job

    async def is_cancelled(self, job_id: uuid.UUID) -> bool:
        """Checks if cancellation was requested for a job."""
        val = await self.redis.get(self._cancel_key(job_id))
        return val is not None

    async def update_job_progress(
        self,
        job: Job,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        progress_message: Optional[str] = None,
        bytes_downloaded: Optional[int] = None,
        total_bytes: Optional[int] = None,
        files_discovered: Optional[int] = None,
        files_processed: Optional[int] = None,
        files_skipped: Optional[int] = None,
        files_failed: Optional[int] = None,
        force_db: bool = False
    ) -> None:
        """
        Updates job progress in both Redis (immediate) and PostgreSQL (debounced/forced).
        """
        if stage:
            job.stage = stage
        if progress is not None:
            job.progress = min(max(progress, 0.0), 1.0)
        if progress_message:
            job.progress_message = sanitize_text(progress_message)
        if bytes_downloaded is not None:
            job.bytes_downloaded = bytes_downloaded
        if total_bytes is not None:
            job.total_bytes = total_bytes
        if files_discovered is not None:
            job.files_discovered = files_discovered
        if files_processed is not None:
            job.files_processed = files_processed
        if files_skipped is not None:
            job.files_skipped = files_skipped
        if files_failed is not None:
            job.files_failed = files_failed

        # Cache snapshot in Redis for high-frequency polling
        try:
            cache_data = {
                "id": str(job.id),
                "repository_id": str(job.repository_id),
                "status": job.status,
                "stage": job.stage,
                "retrieval_method": job.retrieval_method,
                "progress": job.progress,
                "progress_message": job.progress_message,
                "bytes_downloaded": job.bytes_downloaded,
                "total_bytes": job.total_bytes,
                "files_discovered": job.files_discovered,
                "files_processed": job.files_processed,
                "files_skipped": job.files_skipped,
                "files_failed": job.files_failed,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            import json
            await self.redis.set(self._job_progress_key(job.id), json.dumps(cache_data), ex=3600)
        except Exception as e:
            logger.debug("Failed to cache progress in Redis: %s", e)

        if force_db:
            try:
                await self.db.commit()
            except Exception as e:
                logger.warning("Could not persist job progress to DB: %s", e)

    async def initiate_clone(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        branch: Optional[str] = None,
        retrieval_method: str = "GIT_CLONE"
    ) -> Job:
        """
        Validates authorization, checks duplicate concurrent runs, acquires lock,
        and creates a QUEUED Job record.
        """
        # 1. Verify user permission on repository
        stmt = (
            select(Repository)
            .outerjoin(RepositoryPermission, RepositoryPermission.repository_id == Repository.id)
            .where(
                Repository.id == repository_id,
                or_(
                    Repository.owner_user_id == user_id,
                    RepositoryPermission.user_id == user_id
                )
            )
        )
        repo = (await self.db.execute(stmt)).scalar_one_or_none()
        if not repo:
            raise CloneError("Repository not found or access denied.", code="REPOSITORY_NOT_FOUND")

        # 2. Prevent duplicate concurrent jobs (PostgreSQL check)
        active_job_stmt = select(Job).where(
            Job.repository_id == repository_id,
            Job.status.in_(["QUEUED", "RUNNING"])
        )
        active_job = (await self.db.execute(active_job_stmt)).scalar_one_or_none()
        if active_job:
            raise CloneError(
                f"A clone job ({active_job.id}) is already in progress for repository '{repo.owner}/{repo.name}'.",
                code="CLONE_ALREADY_IN_PROGRESS"
            )

        # 3. Prevent duplicate concurrent jobs (Redis lock check)
        lock_key = self._lock_key(repository_id)
        temp_lock_id = str(uuid.uuid4())
        acquired = await self.redis.set(lock_key, temp_lock_id, nx=True, ex=600)
        if not acquired:
            raise CloneError(
                f"A clone job is already locked for repository '{repo.owner}/{repo.name}'.",
                code="CLONE_ALREADY_IN_PROGRESS"
            )

        # 4. Validate branch
        target_branch = validate_branch_name(branch or repo.tracked_branch or repo.default_branch or "main")

        # 5. Check repository size limit from metadata
        if repo.size_kb > settings.MAX_REPO_SIZE_KB:
            await self.redis.delete(lock_key)
            raise CloneError(
                f"Repository size ({repo.size_kb // 1024} MB) exceeds maximum allowed limit ({settings.MAX_REPO_SIZE_KB // 1024} MB).",
                code="REPO_TOO_LARGE"
            )

        # 6. Create Job record
        job = Job(
            user_id=user_id,
            repository_id=repository_id,
            job_type="CLONE",
            status="QUEUED",
            stage="VALIDATING",
            retrieval_method=retrieval_method,
            progress=None,
            progress_message="Job queued for processing.",
            branch=target_branch,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        # Update Redis lock to point to actual job_id
        await self.redis.set(lock_key, str(job.id), ex=600)

        # Update repository analysis_status to indicate cloning
        repo.analysis_status = "ANALYZING"
        await self.db.commit()

        logger.info(
            "Created clone job %s for repo %s/%s (branch: %s, method: %s)",
            job.id, repo.owner, repo.name, target_branch, retrieval_method
        )
        return job

    async def execute_clone_job(self, job_id: uuid.UUID) -> None:
        """
        Executes the entire clone and scanning pipeline in the background:
        VALIDATING -> CLONING (GIT or ZIP) -> SCANNING -> COMPLETED
        Handles retries, timeouts, cleanup, and multi-tenant workspace isolation.
        """
        # Reload job and repository
        job_stmt = select(Job).where(Job.id == job_id)
        job = (await self.db.execute(job_stmt)).scalar_one_or_none()
        if not job:
            logger.error("Job %s not found for execution", job_id)
            return

        repo_stmt = select(Repository).where(Repository.id == job.repository_id)
        repo = (await self.db.execute(repo_stmt)).scalar_one_or_none()
        if not repo:
            logger.error("Repository %s not found for job %s", job.repository_id, job_id)
            job.status = "FAILED"
            job.stage = "FAILED"
            job.error_code = "REPOSITORY_NOT_FOUND"
            job.error_message = "Repository record was deleted or not found."
            await self.db.commit()
            await self.redis.delete(self._lock_key(job.repository_id))
            return

        target_dir = get_repository_workspace_path(job.user_id, job.repository_id)
        lock_key = self._lock_key(job.repository_id)

        try:
            # Stage 1: VALIDATING
            job.status = "RUNNING"
            job.started_at = datetime.now(timezone.utc)
            await self.update_job_progress(
                job,
                stage="VALIDATING",
                progress=None,
                progress_message="Validating repository authorization and environment...",
                force_db=True
            )

            # Check if cancelled
            if await self.is_cancelled(job.id):
                raise CloneError("Job was cancelled before execution.", code="CANCELLED")

            # Resolve user's access token if private repo or available
            access_token: Optional[str] = None
            conn = await self.auth_service.get_github_connection(job.user_id)
            if conn and conn.encrypted_access_token:
                try:
                    access_token = crypto_service.decrypt_token(conn.encrypted_access_token)
                except Exception as e:
                    logger.warning("Failed to decrypt access token for user %s: %s", job.user_id, e)

            if repo.visibility == "PRIVATE" and not access_token:
                raise CloneError(
                    "Private repository requires an authorized GitHub token. Please re-authenticate.",
                    code="TOKEN_REQUIRED"
                )

            # Stage 2: CLONING
            await self.update_job_progress(
                job,
                stage="CLONING",
                progress=None,
                progress_message=f"Starting {job.retrieval_method} for {repo.owner}/{repo.name} ({job.branch})...",
                force_db=True
            )

            # Ensure parent directories exist
            target_dir.parent.mkdir(parents=True, exist_ok=True)

            # Clean any old workspace directory before starting fresh
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)

            commit_sha: Optional[str] = None

            if job.retrieval_method == "ZIP_DOWNLOAD":
                commit_sha = await self._download_via_zip(
                    job=job,
                    owner=repo.owner,
                    name=repo.name,
                    branch=job.branch,
                    target_dir=target_dir,
                    access_token=access_token
                )
            else:
                commit_sha = await self._clone_via_git(
                    job=job,
                    owner=repo.owner,
                    name=repo.name,
                    branch=job.branch,
                    target_dir=target_dir,
                    access_token=access_token
                )

            job.commit_sha = commit_sha
            job.workspace_path = str(target_dir)

            # Check if cancelled before scanning
            if await self.is_cancelled(job.id):
                raise CloneError("Job was cancelled by user.", code="CANCELLED")

            # Stage 3: SCANNING
            await self.update_job_progress(
                job,
                stage="SCANNING",
                progress=None,
                progress_message="Scanning workspace files and calculating disk usage...",
                force_db=True
            )

            disc, proc, skip, fail = await self._scan_workspace(job, target_dir)

            # Stage 4: Run AST ingestion and Code Understanding (Module 3.2)
            try:
                from src.services.ingestion_service import IngestionService
                ingestion_svc = IngestionService(self.db)
                await ingestion_svc.ingest_repository(
                    repository_id=repo.id,
                    user_id=job.user_id,
                    branch=job.branch,
                    commit_sha=job.commit_sha
                )
            except Exception as ing_err:
                logger.warning("Code ingestion warning for job %s: %s", job.id, ing_err)

            # Stage 5: COMPLETED
            job.stage = "COMPLETED"
            job.status = "SUCCEEDED"
            job.progress = 1.0
            job.progress_message = (
                f"Repository cloned and scanned successfully. "
                f"Discovered: {disc}, Source files: {proc}, Skipped: {skip}."
            )
            job.ended_at = datetime.now(timezone.utc)
            job.error_code = None
            job.error_message = None

            repo.analysis_status = "READY"
            repo.tracked_branch = job.branch

            await self.db.commit()
            logger.info("Successfully completed clone and scan for job %s (workspace: %s)", job.id, target_dir)

        except CloneError as e:
            logger.warning("Clone job %s failed: %s (%s)", job.id, e.message, e.code)
            job.status = "CANCELLED" if e.code == "CANCELLED" else "FAILED"
            job.stage = "FAILED"
            job.error_code = e.code
            job.error_message = e.message
            job.retryable = e.retryable
            job.ended_at = datetime.now(timezone.utc)
            repo.analysis_status = "FAILED"

            # Clean up incomplete workspace on failure
            if target_dir.exists():
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                except Exception as clean_err:
                    logger.error("Failed to clean up workspace %s: %s", target_dir, clean_err)

            await self.db.commit()

        except Exception as e:
            logger.exception("Unexpected error in clone job %s: %s", job.id, e)
            job.status = "FAILED"
            job.stage = "FAILED"
            job.error_code = "INTERNAL_CLONE_ERROR"
            job.error_message = "An unexpected error occurred during cloning."
            job.retryable = True
            job.ended_at = datetime.now(timezone.utc)
            repo.analysis_status = "FAILED"

            if target_dir.exists():
                try:
                    shutil.rmtree(target_dir, ignore_errors=True)
                except Exception:
                    pass

            await self.db.commit()

        finally:
            # Release Redis locks and cancellation flags
            await self.redis.delete(lock_key)
            await self.redis.delete(self._cancel_key(job.id))

    async def _clone_via_git(
        self,
        job: Job,
        owner: str,
        name: str,
        branch: str,
        target_dir: Path,
        access_token: Optional[str]
    ) -> Optional[str]:
        """
        Executes secure Git clone using asyncio subprocess.
        Guarantees token is NEVER in argv, remote URL, logs, or .git/config.
        Parses live git progress output from stderr.
        """
        clone_url = f"https://github.com/{owner}/{name}.git"

        # Build clean subprocess environment
        sub_env = os.environ.copy()
        sub_env["GIT_TERMINAL_PROMPT"] = "0"

        # Pass credential securely via environment variable read by git --config-env
        # The token is never exposed in process arguments (argv) or written into .git/config!
        git_args = [
            "git",
            "-c", "core.hooksPath=",
            "-c", "filter.lfs.smudge=",
            "-c", "filter.lfs.clean=",
            "-c", "filter.lfs.process=",
        ]

        if access_token:
            auth_b64 = base64.b64encode(f"x-access-token:{access_token}".encode("ascii")).decode("ascii")
            sub_env["GITHUB_AUTH_HEADER"] = f"Authorization: Basic {auth_b64}"
            git_args.append("--config-env=http.extraheader=GITHUB_AUTH_HEADER")

        git_args.extend([
            "clone",
            "--depth", "1",
            "--branch", branch,
            "--progress",
            clone_url,
            str(target_dir)
        ])

        logger.info("Executing git clone for %s/%s into isolated workspace", owner, name)

        try:
            proc = await asyncio.create_subprocess_exec(
                *git_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=sub_env
            )
        except FileNotFoundError:
            raise CloneError("Git executable is not installed or not available in PATH.", code="GIT_NOT_FOUND")

        stderr_lines = []
        last_db_update = time.time()

        # Regex for git progress output
        receiving_re = re.compile(r"Receiving objects:\s+(\d+)%")
        resolving_re = re.compile(r"Resolving deltas:\s+(\d+)%")

        # Read stderr line-by-line while process is active
        async def read_stderr():
            nonlocal last_db_update
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue

                clean_line = sanitize_text(decoded)
                stderr_lines.append(clean_line)

                # Check for cancellation
                if await self.is_cancelled(job.id):
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    return

                # Parse percentage if present
                rec_match = receiving_re.search(clean_line)
                res_match = resolving_re.search(clean_line)

                pct: Optional[float] = None
                if rec_match:
                    pct = int(rec_match.group(1)) / 100.0
                elif res_match:
                    pct = int(res_match.group(1)) / 100.0

                now = time.time()
                force = (now - last_db_update) > 1.0
                if force:
                    last_db_update = now

                await self.update_job_progress(
                    job,
                    stage="CLONING",
                    progress=pct,
                    progress_message=clean_line,
                    force_db=force
                )

        try:
            await asyncio.wait_for(
                asyncio.gather(proc.wait(), read_stderr()),
                timeout=settings.CLONE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            raise CloneError(
                f"Git clone operation timed out after {settings.CLONE_TIMEOUT_SECONDS} seconds.",
                code="CLONE_TIMEOUT",
                retryable=True
            )

        if await self.is_cancelled(job.id):
            raise CloneError("Clone operation cancelled by user.", code="CANCELLED")

        if proc.returncode != 0:
            error_details = " ".join(stderr_lines[-5:]) if stderr_lines else "Unknown git error"
            logger.warning("Git clone failed with code %s: %s", proc.returncode, error_details)

            if "Remote branch" in error_details and "not found" in error_details:
                raise CloneError(f"Branch '{branch}' was not found in repository.", code="BRANCH_NOT_FOUND")
            if "Repository not found" in error_details or "Authentication failed" in error_details:
                raise CloneError(
                    f"Repository '{owner}/{name}' not found or authorization failed.",
                    code="REPOSITORY_NOT_FOUND_OR_UNAUTHORIZED"
                )
            if "Could not resolve host" in error_details or "Failed to connect" in error_details:
                raise CloneError(
                    "Network error connecting to GitHub. Please verify your connection.",
                    code="NETWORK_ERROR",
                    retryable=True
                )

            raise CloneError(f"Git clone failed: {error_details}", code="GIT_CLONE_FAILED", retryable=True)

        # Resolve commit SHA
        commit_sha = await self._resolve_commit_sha(target_dir)
        return commit_sha

    async def _resolve_commit_sha(self, target_dir: Path) -> Optional[str]:
        """Resolves the current HEAD commit SHA of the cloned repository."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(target_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0:
                return stdout.decode().strip()
        except Exception as e:
            logger.debug("Could not resolve commit sha: %s", e)
        return None

    async def _download_via_zip(
        self,
        job: Job,
        owner: str,
        name: str,
        branch: str,
        target_dir: Path,
        access_token: Optional[str]
    ) -> Optional[str]:
        """
        Streams GitHub zipball archive, reports real-time downloaded bytes & progress,
        and securely unpacks into workspace preventing ZipSlip path traversal.
        """
        initial_url = f"https://api.github.com/repos/{owner}/{name}/zipball/{branch}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": GITHUB_HTTP_USER_AGENT
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        temp_zip_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_zip_path = Path(temp_zip_file.name)
        temp_zip_file.close()

        commit_sha: Optional[str] = None
        bytes_downloaded = 0
        total_bytes: Optional[int] = None
        last_db_update = time.time()

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                current_url = initial_url
                redirect_count = 0

                # 1. Handle redirects safely (validating hosts against SSRF)
                while True:
                    req = client.build_request("GET", current_url, headers=headers)
                    resp = await client.send(req, stream=True)

                    if resp.status_code in (301, 302, 307, 308):
                        redirect_count += 1
                        if redirect_count > 5:
                            raise CloneError("Too many redirects while downloading archive.", code="TOO_MANY_REDIRECTS")

                        loc = resp.headers.get("location")
                        if not loc:
                            raise CloneError("Redirect without Location header.", code="INVALID_REDIRECT")

                        parsed_loc = urlparse(loc)
                        if parsed_loc.scheme.lower() != "https":
                            raise CloneError("Insecure redirect protocol rejected.", code="UNTRUSTED_REDIRECT")

                        target_host = (parsed_loc.hostname or "").lower()
                        if target_host not in TRUSTED_ARCHIVE_HOSTS:
                            raise CloneError(f"Redirect to untrusted host '{target_host}' rejected.", code="UNTRUSTED_REDIRECT")

                        current_url = loc
                        await resp.aclose()
                        continue

                    if resp.status_code == 404:
                        await resp.aclose()
                        raise CloneError(
                            f"Repository '{owner}/{name}' or branch '{branch}' was not found on GitHub.",
                            code="NOT_FOUND"
                        )
                    if resp.status_code in (401, 403):
                        await resp.aclose()
                        raise CloneError("Access denied or rate limit exceeded on GitHub.", code="FORBIDDEN")

                    resp.raise_for_status()
                    break

                # Inspect content length
                content_len = resp.headers.get("content-length")
                if content_len and content_len.isdigit():
                    total_bytes = int(content_len)

                # Stream chunks into temporary file
                with open(temp_zip_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        if await self.is_cancelled(job.id):
                            await resp.aclose()
                            raise CloneError("ZIP download cancelled by user.", code="CANCELLED")

                        f.write(chunk)
                        bytes_downloaded += len(chunk)

                        pct: Optional[float] = None
                        if total_bytes and total_bytes > 0:
                            pct = bytes_downloaded / total_bytes

                        now = time.time()
                        force = (now - last_db_update) > 1.0
                        if force:
                            last_db_update = now

                        dl_mb = bytes_downloaded / (1024 * 1024)
                        if total_bytes:
                            tot_mb = total_bytes / (1024 * 1024)
                            msg = f"Downloading archive: {dl_mb:.1f} MB / {tot_mb:.1f} MB ({int((pct or 0)*100)}%)"
                        else:
                            msg = f"Downloading archive: {dl_mb:.1f} MB"

                        await self.update_job_progress(
                            job,
                            stage="CLONING",
                            progress=pct,
                            progress_message=msg,
                            bytes_downloaded=bytes_downloaded,
                            total_bytes=total_bytes,
                            force_db=force
                        )

            # 2. Extract ZIP archive with strict ZipSlip protection
            await self.update_job_progress(
                job,
                stage="CLONING",
                progress=None,
                progress_message="Extracting repository archive into workspace...",
                force_db=True
            )

            target_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(temp_zip_path, "r") as zf:
                # Check for ZipSlip vulnerability on all members
                resolved_target = target_dir.resolve()
                members = zf.namelist()

                # GitHub archives typically have a single root directory prefix: owner-repo-sha/
                root_prefix = members[0].split("/")[0] if members and "/" in members[0] else ""

                # Extract commit SHA if in root folder name (e.g. pallets-flask-1234567)
                if root_prefix and "-" in root_prefix:
                    parts = root_prefix.rsplit("-", 1)
                    if len(parts) == 2 and len(parts[1]) >= 7:
                        commit_sha = parts[1]

                for member in members:
                    # Strip outer folder if present to unpack directly into target_dir
                    rel_path = member
                    if root_prefix and member.startswith(root_prefix + "/"):
                        rel_path = member[len(root_prefix) + 1:]

                    if not rel_path:
                        continue

                    # ZipSlip security validation
                    dest_file = (resolved_target / rel_path).resolve()
                    if not str(dest_file).startswith(str(resolved_target)):
                        raise CloneError(
                            "Malicious zip entry attempting path traversal detected.",
                            code="PATH_TRAVERSAL_DETECTED"
                        )

                    if member.endswith("/"):
                        dest_file.mkdir(parents=True, exist_ok=True)
                    else:
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as source, open(dest_file, "wb") as target:
                            shutil.copyfileobj(source, target)

            return commit_sha

        finally:
            if temp_zip_path.exists():
                try:
                    os.unlink(temp_zip_path)
                except Exception:
                    pass

    async def _scan_workspace(self, job: Job, workspace_dir: Path) -> Tuple[int, int, int, int]:
        """
        Scans workspace directory, counting discovered, processed, skipped, and failed files.
        Enforces maximum workspace disk quota limits.
        """
        discovered = 0
        processed = 0
        skipped = 0
        failed = 0
        total_size_bytes = 0
        max_bytes = settings.MAX_WORKSPACE_DISK_USAGE_MB * 1024 * 1024

        last_db_update = time.time()

        for root, dirs, files in os.walk(workspace_dir):
            if await self.is_cancelled(job.id):
                raise CloneError("Scan cancelled by user.", code="CANCELLED")

            # Prune ignored directory trees
            dirs[:] = [d for d in dirs if d not in IGNORED_SCAN_DIRS and not d.startswith(".")]

            for filename in files:
                discovered += 1
                file_path = Path(root) / filename

                try:
                    stat = file_path.stat()
                    total_size_bytes += stat.st_size

                    # Verify disk quota limit
                    if total_size_bytes > max_bytes:
                        raise CloneError(
                            f"Cloned repository exceeded disk usage limit of {settings.MAX_WORKSPACE_DISK_USAGE_MB} MB.",
                            code="DISK_QUOTA_EXCEEDED"
                        )

                    ext = file_path.suffix.lower()
                    if ext in IGNORED_SCAN_EXTS or filename.startswith("."):
                        skipped += 1
                    else:
                        processed += 1

                except CloneError:
                    raise
                except Exception:
                    failed += 1

                # Update progress periodically
                now = time.time()
                if (now - last_db_update) > 1.0:
                    last_db_update = now
                    await self.update_job_progress(
                        job,
                        stage="SCANNING",
                        files_discovered=discovered,
                        files_processed=processed,
                        files_skipped=skipped,
                        files_failed=failed,
                        progress_message=f"Scanning files: {discovered} found, {processed} source files indexed...",
                        force_db=True
                    )

        await self.update_job_progress(
            job,
            stage="SCANNING",
            files_discovered=discovered,
            files_processed=processed,
            files_skipped=skipped,
            files_failed=failed,
            force_db=True
        )

        return discovered, processed, skipped, failed
