import logging
import uuid
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.models.repository_import import RepositoryImport
from src.models.job import Job
from src.services.github_service import GitHubService, parse_github_url, GitHubOAuthError
from src.services.auth_service import AuthService
from src.services.crypto_service import crypto_service
from src.services.clone_service import get_repository_workspace_path

logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    def __init__(self, message: str, code: str = "REPOSITORY_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class RepositoryAlreadyImportedError(RepositoryError):
    def __init__(self, existing_repo: Repository):
        super().__init__(
            f"Repository '{existing_repo.owner}/{existing_repo.name}' has already been imported.",
            code="REPOSITORY_ALREADY_IMPORTED"
        )
        self.existing_repo = existing_repo


class RepositoryService:
    def __init__(
        self,
        db: AsyncSession,
        github_service: GitHubService,
        auth_service: AuthService
    ):
        self.db = db
        self.github_service = github_service
        self.auth_service = auth_service

    async def import_repository(
        self,
        user_id: uuid.UUID,
        url_or_identifier: str,
        branch: Optional[str] = None
    ) -> Repository:
        """
        Validates GitHub URL/identifier, fetches repository metadata from GitHub API,
        checks multi-tenant duplicates, creates Repository & RepositoryPermission,
        and logs the import event.
        """
        # 1. Parse and strictly validate URL (guards against SSRF)
        try:
            owner, name = parse_github_url(url_or_identifier)
        except GitHubOAuthError as e:
            raise RepositoryError(e.message, code=e.code)

        # 2. Get user's GitHub access token if available
        access_token: Optional[str] = None
        conn = await self.auth_service.get_github_connection(user_id)
        if conn and conn.encrypted_access_token:
            try:
                access_token = crypto_service.decrypt_token(conn.encrypted_access_token)
            except Exception as e:
                logger.warning("Could not decrypt GitHub token for user %s: %s", user_id, e)

        # 3. Fetch repository metadata from GitHub
        try:
            repo_data = await self.github_service.get_repository(owner, name, access_token=access_token)
        except GitHubOAuthError as e:
            # Log failed import attempt
            import_event = RepositoryImport(
                user_id=user_id,
                repository_id=None,
                provider="github",
                provider_repo_id=None,
                repo_name=f"{owner}/{name}",
                source_url=url_or_identifier,
                status="FAILED",
                error_message=e.message
            )
            self.db.add(import_event)
            await self.db.commit()
            raise RepositoryError(e.message, code=e.code)

        provider_repo_id = str(repo_data["id"])

        # 4. Check if user already imported this repository
        stmt = select(Repository).where(
            Repository.owner_user_id == user_id,
            Repository.provider == "github",
            Repository.provider_repo_id == provider_repo_id
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info("User %s attempted duplicate import of %s/%s", user_id, owner, name)
            raise RepositoryAlreadyImportedError(existing)

        # 5. Determine branch
        tracked_branch = branch.strip() if branch and branch.strip() else (repo_data.get("default_branch") or "main")

        # 6. Create Repository
        repo = Repository(
            owner_user_id=user_id,
            provider="github",
            provider_repo_id=provider_repo_id,
            owner=repo_data["owner"]["login"],
            name=repo_data["name"],
            canonical_url=repo_data.get("html_url") or f"https://github.com/{owner}/{name}",
            visibility="PRIVATE" if repo_data.get("private") else "PUBLIC",
            default_branch=repo_data.get("default_branch") or "main",
            tracked_branch=tracked_branch,
            description=repo_data.get("description"),
            language=repo_data.get("language"),
            stargazers_count=repo_data.get("stargazers_count", 0),
            forks_count=repo_data.get("forks_count", 0),
            open_issues_count=repo_data.get("open_issues_count", 0),
            size_kb=repo_data.get("size", 0),
            status="ACTIVE",
            analysis_status="NOT_ANALYZED"
        )
        self.db.add(repo)
        await self.db.flush()

        # 7. Grant user OWNER permission on repository
        perm = RepositoryPermission(
            repository_id=repo.id,
            user_id=user_id,
            role="OWNER"
        )
        self.db.add(perm)

        # 8. Record successful import event
        import_event = RepositoryImport(
            user_id=user_id,
            repository_id=repo.id,
            provider="github",
            provider_repo_id=provider_repo_id,
            repo_name=f"{repo.owner}/{repo.name}",
            source_url=url_or_identifier,
            status="SUCCEEDED",
            error_message=None
        )
        self.db.add(import_event)

        await self.db.commit()
        await self.db.refresh(repo)

        logger.info("User %s successfully imported repository %s/%s (id: %s)", user_id, repo.owner, repo.name, repo.id)
        return repo

    async def list_repositories(
        self,
        user_id: uuid.UUID,
        search: Optional[str] = None,
        visibility: Optional[str] = None,
        status: str = "ACTIVE"
    ) -> List[Repository]:
        """
        Lists all repositories accessible to the user with multi-tenant filtering.
        """
        # User owns repo OR has repository_permissions
        stmt = (
            select(Repository)
            .outerjoin(RepositoryPermission, RepositoryPermission.repository_id == Repository.id)
            .where(
                or_(
                    Repository.owner_user_id == user_id,
                    RepositoryPermission.user_id == user_id
                ),
                Repository.status == status
            )
            .distinct()
            .order_by(Repository.updated_at.desc())
        )

        if visibility:
            stmt = stmt.where(Repository.visibility == visibility.upper())

        if search:
            pattern = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    Repository.name.ilike(pattern),
                    Repository.owner.ilike(pattern),
                    Repository.description.ilike(pattern)
                )
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_repository(self, repo_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Repository]:
        """
        Retrieves a repository by ID ensuring multi-tenant authorization.
        """
        stmt = (
            select(Repository)
            .outerjoin(RepositoryPermission, RepositoryPermission.repository_id == Repository.id)
            .where(
                Repository.id == repo_id,
                or_(
                    Repository.owner_user_id == user_id,
                    RepositoryPermission.user_id == user_id
                )
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_imports(self, user_id: uuid.UUID, limit: int = 50) -> List[RepositoryImport]:
        """
        Lists recent import attempts and operations for the user.
        """
        stmt = (
            select(RepositoryImport)
            .where(RepositoryImport.user_id == user_id)
            .order_by(RepositoryImport.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def trigger_analysis(self, repo_id: uuid.UUID, user_id: uuid.UUID) -> Repository:
        """
        Prepares repository for analysis (Module 3 placeholder).
        Updates analysis_status to READY.
        """
        repo = await self.get_repository(repo_id, user_id)
        if not repo:
            raise RepositoryError("Repository not found or access denied.", code="NOT_FOUND")

        repo.analysis_status = "READY"
        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def delete_repository(
        self,
        repo_id: uuid.UUID,
        user_id: uuid.UUID,
        clone_service: Optional[Any] = None
    ) -> bool:
        """
        Deletes an imported repository from CodePilot with strict tenant/owner authorization.
        
        Actions:
        1. Verifies user has OWNER authority on the repository.
        2. Safely cancels any active/running clone or analysis jobs.
        3. Cleans associated Redis lock and cancel keys.
        4. Recursively removes the isolated workspace directory from disk storage.
        5. Deletes repository record and cascades all database entities (snapshots, files, symbols, imports, chunks).
        
        CRITICAL SAFETY:
        Never deletes or modifies the remote repository on GitHub.
        """
        stmt = select(Repository).where(Repository.id == repo_id)
        res = await self.db.execute(stmt)
        repo = res.scalar_one_or_none()
        if not repo:
            raise RepositoryError("Repository not found.", code="NOT_FOUND")

        # Verify OWNER authorization
        if repo.owner_user_id != user_id:
            perm_stmt = select(RepositoryPermission).where(
                RepositoryPermission.repository_id == repo_id,
                RepositoryPermission.user_id == user_id,
                RepositoryPermission.role == "OWNER"
            )
            perm = (await self.db.execute(perm_stmt)).scalar_one_or_none()
            if not perm:
                raise RepositoryError("You do not have permission to delete this repository.", code="FORBIDDEN")

        # 1. Safely handle active jobs and Redis temporary state
        if clone_service is not None:
            job_stmt = select(Job).where(
                Job.repository_id == repo_id,
                Job.status.in_(["QUEUED", "RUNNING"])
            )
            active_jobs = (await self.db.execute(job_stmt)).scalars().all()
            for job in active_jobs:
                job.status = "CANCELLED"
                job.error_message = "Repository was deleted by owner."
                try:
                    await clone_service.redis.set(clone_service._cancel_key(job.id), "1", ex=3600)
                    await clone_service.redis.delete(clone_service._job_progress_key(job.id))
                except Exception as e:
                    logger.warning("Could not update Redis for cancelled job %s: %s", job.id, e)

            try:
                await clone_service.redis.delete(clone_service._lock_key(repo_id))
            except Exception as e:
                logger.warning("Could not delete clone lock key for repo %s: %s", repo_id, e)

        # 2. Safely remove workspace directory from disk
        try:
            workspace_path = get_repository_workspace_path(repo.owner_user_id, repo.id)
            if workspace_path.exists() and workspace_path.is_dir():
                shutil.rmtree(workspace_path, ignore_errors=True)
                logger.info("Deleted workspace storage directory: %s", workspace_path)
        except Exception as e:
            logger.warning("Error deleting workspace directory for repo %s: %s", repo_id, e)

        # 3. Delete database record (cascades snapshots, files, symbols, imports, chunks, jobs, permissions)
        await self.db.delete(repo)
        await self.db.commit()

        logger.info(
            "User %s successfully deleted repository %s (%s/%s) from CodePilot",
            user_id, repo_id, repo.owner, repo.name
        )
        return True
