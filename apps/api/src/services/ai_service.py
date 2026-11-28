<<<<<<< HEAD
import logging
from typing import Any, Dict, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AIService:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.AI_SERVICES_URL).rstrip("/")

    async def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
        except httpx.RequestError as exc:
            logger.error("AI services unavailable at %s: %s", self.base_url, exc)
            raise AIServiceError("AI services are unavailable.", status_code=503)

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            message = detail.get("detail") if isinstance(detail, dict) else response.text
            if isinstance(message, dict):
                message = message.get("message") or str(message)
            raise AIServiceError(str(message or "AI services request failed."), status_code=response.status_code)
        return response.json()

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}{path}", params=params)
        except httpx.RequestError as exc:
            logger.error("AI services unavailable at %s: %s", self.base_url, exc)
            raise AIServiceError("AI services are unavailable.", status_code=503)

        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = {"detail": response.text}
            message = detail.get("detail") if isinstance(detail, dict) else response.text
            if isinstance(message, dict):
                message = message.get("message") or str(message)
            raise AIServiceError(str(message or "AI services request failed."), status_code=response.status_code)
        return response.json()

    async def index_repository(
        self,
        repo_id: str,
        snapshot_id: str,
        files: Dict[str, str],
    ) -> Dict[str, Any]:
        return await self._post("/index", {
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "files": files,
        })

    async def search(
        self,
        repo_id: str,
        snapshot_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 20,
    ) -> Dict[str, Any]:
        return await self._post("/search", {
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "query": query,
            "filters": filters,
            "top_k": top_k,
        })

    async def explain(
        self,
        repo_id: str,
        snapshot_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        body = {"repo_id": repo_id, "snapshot_id": snapshot_id, **payload}
        return await self._post("/explain", body)

    async def get_summary(
        self,
        repo_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        return await self._get(f"/summary/{repo_id}/{snapshot_id}")

    async def get_files(
        self,
        repo_id: str,
        snapshot_id: str,
    ) -> Dict[str, Any]:
        return await self._get(f"/files/{repo_id}/{snapshot_id}")

    async def get_file_content(
        self,
        repo_id: str,
        snapshot_id: str,
        path: str,
    ) -> Dict[str, Any]:
        return await self._get(f"/file-content/{repo_id}/{snapshot_id}", params={"path": path})
=======
"""AI Services Bridge for CodePilot.

Adapts the standalone AIservices engine (Basic Code Search and AI Code Explanation)
to CodePilot's authenticated FastAPI backend, PostgreSQL snapshots, and isolated
workspace directories without duplicating indexing pipelines or modifying AIservices/.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure AIservices parent directory is on sys.path (works both locally and in Docker /app)
for _parent in Path(__file__).resolve().parents:
    if (_parent / "AIservices").is_dir():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from AIservices.api.index_store import get_index, save_index  # noqa: E402
from AIservices.core.models import (  # noqa: E402
    RepoIndex,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SupportedLanguage,
    SymbolKind,
)
from AIservices.core.parser import index_repository  # noqa: E402
from AIservices.features.code_explanation import (  # noqa: E402
    ExplanationRequest,
    ExplanationResponse,
    ExplanationStyle,
    explain_code as ai_explain_code,
)
from AIservices.features.code_search import search as ai_search_code  # noqa: E402

from src.config import settings  # noqa: E402
from src.models.repo_file import RepoFile  # noqa: E402
from src.models.repository import Repository  # noqa: E402
from src.models.snapshot import Snapshot  # noqa: E402
from src.services.clone_service import get_repository_workspace_path  # noqa: E402
from src.services.ingestion_service import IngestionError, IngestionService  # noqa: E402

logger = logging.getLogger(__name__)

# Maximum single file size (2 MB) read into an AIservices RepoIndex
_MAX_INDEXABLE_FILE_BYTES = 2 * 1024 * 1024


class AIServiceError(Exception):
    """Structured domain error raised by AIServiceBridge."""

    def __init__(self, message: str, code: str = "AI_SERVICE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class AIServiceBridge:
    """Bridge connecting CodePilot repositories/snapshots to AIservices engines."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._ingestion_service = IngestionService(db)

    async def _verify_access(self, repository_id: uuid.UUID, user_id: uuid.UUID) -> Repository:
        try:
            return await self._ingestion_service.verify_user_access(repository_id, user_id)
        except IngestionError as exc:
            raise AIServiceError(exc.message, code=exc.code) from exc

    async def _resolve_snapshot(
        self,
        repository_id: uuid.UUID,
        snapshot_id: Optional[uuid.UUID] = None,
    ) -> Snapshot:
        if snapshot_id is not None:
            stmt = select(Snapshot).where(
                Snapshot.id == snapshot_id,
                Snapshot.repository_id == repository_id,
                Snapshot.status.in_(["READY", "COMPLETED"]),
            )
        else:
            stmt = (
                select(Snapshot)
                .where(
                    Snapshot.repository_id == repository_id,
                    Snapshot.status.in_(["READY", "COMPLETED"]),
                )
                .order_by(desc(Snapshot.created_at))
                .limit(1)
            )
        res = await self.db.execute(stmt)
        snapshot = res.scalar_one_or_none()
        if not snapshot:
            raise AIServiceError(
                "No completed analysis snapshot found for this repository. Please analyze the repository first.",
                code="NO_SNAPSHOT",
            )
        return snapshot

    def _read_workspace_files(
        self,
        workspace_path: Path,
        repo_files: list[RepoFile],
    ) -> dict[str, str]:
        """Safely read snapshot-tracked files from the isolated workspace directory."""
        if not workspace_path.exists() or not workspace_path.is_dir():
            raise AIServiceError(
                "Repository workspace files are not available on disk. Please clone and analyze the repository.",
                code="WORKSPACE_NOT_FOUND",
            )

        workspace_root = workspace_path.resolve()
        files_map: dict[str, str] = {}

        for repo_file in repo_files:
            rel_path = repo_file.path.lstrip("/").replace("\\", "/")
            if not rel_path:
                continue

            candidate = (workspace_root / rel_path).resolve()
            if not candidate.is_relative_to(workspace_root):
                logger.warning("Blocked path traversal attempt during AI indexing: %s", repo_file.path)
                continue

            if not candidate.is_file():
                continue

            try:
                if candidate.stat().st_size > _MAX_INDEXABLE_FILE_BYTES:
                    continue
                files_map[rel_path] = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                logger.debug("Skipping unreadable workspace file %s: %s", rel_path, exc)

        return files_map

    async def get_or_build_repo_index(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        snapshot_id: Optional[uuid.UUID] = None,
        force_rebuild: bool = False,
    ) -> tuple[RepoIndex, Snapshot]:
        """Return a cached AIservices RepoIndex for the snapshot, or build it from workspace files."""
        repo = await self._verify_access(repository_id, user_id)
        snapshot = await self._resolve_snapshot(repository_id, snapshot_id)

        repo_key = str(repo.id)
        snap_key = str(snapshot.id)

        if not force_rebuild:
            cached = get_index(repo_key, snap_key)
            if cached is not None:
                return cached, snapshot

        files_stmt = select(RepoFile).where(RepoFile.snapshot_id == snapshot.id)
        files_res = await self.db.execute(files_stmt)
        repo_files = list(files_res.scalars().all())

        workspace_path = get_repository_workspace_path(repo.owner_user_id, repo.id)
        files_map = self._read_workspace_files(workspace_path, repo_files)

        repo_index = index_repository(
            repo_id=repo_key,
            snapshot_id=snap_key,
            files=files_map,
        )
        save_index(repo_index)
        return repo_index, snapshot

    async def search_code(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        kinds: Optional[list[str]] = None,
        languages: Optional[list[str]] = None,
        path_prefix: Optional[str] = None,
        top_k: int = 20,
        snapshot_id: Optional[uuid.UUID] = None,
    ) -> SearchResponse:
        """Execute ranked, filtered code search over a repository snapshot."""
        clean_query = (query or "").strip()
        if not clean_query:
            raise AIServiceError("Search query cannot be empty.", code="INVALID_INPUT")

        repo_index, snapshot = await self.get_or_build_repo_index(
            repository_id=repository_id,
            user_id=user_id,
            snapshot_id=snapshot_id,
        )

        search_filters = None
        if kinds or languages or path_prefix:
            parsed_kinds = None
            if kinds:
                try:
                    parsed_kinds = [SymbolKind(k.upper()) for k in kinds]
                except ValueError as exc:
                    raise AIServiceError(f"Invalid symbol kind filter: {exc}", code="INVALID_INPUT") from exc

            parsed_languages = None
            if languages:
                try:
                    parsed_languages = [SupportedLanguage(lang.lower()) for lang in languages]
                except ValueError as exc:
                    raise AIServiceError(f"Invalid language filter: {exc}", code="INVALID_INPUT") from exc

            search_filters = SearchFilters(
                kinds=parsed_kinds,
                languages=parsed_languages,
                path_prefix=path_prefix,
            )

        req = SearchRequest(
            repo_id=str(repository_id),
            snapshot_id=str(snapshot.id),
            query=clean_query,
            filters=search_filters,
            top_k=top_k,
        )

        try:
            return ai_search_code(req, repo_index)
        except ValueError as exc:
            raise AIServiceError(str(exc), code="INVALID_INPUT") from exc

    async def explain_code(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        code: Optional[str] = None,
        file_path: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        symbol_id: Optional[str] = None,
        question: Optional[str] = None,
        explanation_style: str = "technical",
        snapshot_id: Optional[uuid.UUID] = None,
    ) -> ExplanationResponse:
        """Generate a grounded AI code explanation (Gemini or offline StaticAnalysisProvider)."""
        repo_index, snapshot = await self.get_or_build_repo_index(
            repository_id=repository_id,
            user_id=user_id,
            snapshot_id=snapshot_id,
        )

        try:
            style = ExplanationStyle((explanation_style or "technical").lower())
        except ValueError:
            style = ExplanationStyle.TECHNICAL

        # Propagate optional GEMINI_API_KEY from settings if configured in .env
        if settings.GEMINI_API_KEY and not os.environ.get("GEMINI_API_KEY"):
            os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY

        req = ExplanationRequest(
            repo_id=str(repository_id),
            snapshot_id=str(snapshot.id),
            code=code,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            symbol_id=symbol_id,
            question=question,
            explanation_style=style,
        )

        try:
            return ai_explain_code(req, repo_index)
        except ValueError as exc:
            raise AIServiceError(str(exc), code="INVALID_INPUT") from exc


# Alias for backward compatibility across endpoints and dependency injectors
AIService = AIServiceBridge
>>>>>>> feb1a0771f6ab6e7afa8715f6c5c30f4e2cf737e
