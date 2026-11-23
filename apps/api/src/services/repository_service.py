import logging
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.models.repository_import import RepositoryImport
from src.services.github_service import GitHubService, parse_github_url, GitHubOAuthError
from src.services.auth_service import AuthService
from src.services.crypto_service import crypto_service
from src.services.ai_service import AIService, AIServiceError

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
        auth_service: AuthService,
        ai_service: Optional[AIService] = None,
    ):
        self.db = db
        self.github_service = github_service
        self.auth_service = auth_service
        self.ai_service = ai_service

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
        Fetches repository source files and builds the AI code index.
        """
        repo = await self.get_repository(repo_id, user_id)
        if not repo:
            raise RepositoryError("Repository not found or access denied.", code="NOT_FOUND")

        if not self.ai_service:
            raise RepositoryError("AI services are not configured.", code="AI_SERVICE_UNAVAILABLE")

        access_token: Optional[str] = None
        conn = await self.auth_service.get_github_connection(user_id)
        if conn and conn.encrypted_access_token:
            try:
                access_token = crypto_service.decrypt_token(conn.encrypted_access_token)
            except Exception as exc:
                logger.warning("Could not decrypt GitHub token for user %s: %s", user_id, exc)

        repo.analysis_status = "ANALYZING"
        await self.db.commit()

        error_message = "Unknown analysis error"
        try:
            files = await self.github_service.get_repository_files(
                owner=repo.owner,
                name=repo.name,
                branch=repo.tracked_branch,
                access_token=access_token,
            )
            snapshot_id = repo.tracked_branch
            await self.ai_service.index_repository(
                repo_id=str(repo.id),
                snapshot_id=snapshot_id,
                files=files,
            )
            repo.analysis_status = "READY"
        except Exception as exc:
            repo.analysis_status = "FAILED"
            error_message = getattr(exc, "message", str(exc))
            logger.exception("Repository analysis failed for %s: %s", repo.id, exc)
        finally:
            await self.db.commit()
            await self.db.refresh(repo)

        if repo.analysis_status == "FAILED":
            raise RepositoryError(
                f"Repository analysis failed: {error_message}",
                code="ANALYSIS_FAILED",
            )
        return repo
