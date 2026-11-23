"""Ingestion and Code Understanding Service for CodePilot Module 3.2.

Orchestrates:
1. Workspace directory traversal and AST parsing via Tree-sitter.
2. Snapshot creation and version tracking.
3. Persistent storage of files, symbols, imports, and semantic code chunks.
4. Codebase Explorer navigation and symbol lookup APIs.
5. Strict multi-tenant isolation and idempotent re-analysis.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime, timezone

from sqlalchemy import select, delete, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.repository import Repository
from src.models.repository_permission import RepositoryPermission
from src.models.snapshot import Snapshot
from src.models.repo_file import RepoFile
from src.models.symbol import Symbol
from src.models.import_statement import FileImport
from src.models.code_chunk import CodeChunk
from src.services.parser_service import parser_service, ParsedFile, IGNORE_DIRS
from src.services.clone_service import get_repository_workspace_path
from src.schemas.explorer import (
    FileTreeItem,
    FileTreeResponse,
    FileDetailResponse,
    SnapshotResponse,
    SymbolResponse,
    ImportResponse,
    CodeChunkResponse,
    FileSummaryItem,
    RepositoryOverviewResponse
)

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    def __init__(self, message: str, code: str = "INGESTION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_user_access(self, repository_id: uuid.UUID, user_id: uuid.UUID) -> Repository:
        """Verifies that the user has permission to access the repository."""
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
        res = await self.db.execute(stmt)
        repo = res.scalar_one_or_none()
        if not repo:
            raise IngestionError("Repository not found or access denied.", code="NOT_FOUND")
        return repo

    def get_commit_sha(self, workspace_path: Path) -> str:
        """Extracts HEAD commit SHA if git metadata exists, or derives deterministic hash."""
        head_file = workspace_path / ".git" / "HEAD"
        if head_file.exists():
            try:
                head_content = head_file.read_text(encoding="utf-8").strip()
                if head_content.startswith("ref: "):
                    ref_path = head_content[5:].strip()
                    ref_file = workspace_path / ".git" / ref_path
                    if ref_file.exists():
                        return ref_file.read_text(encoding="utf-8").strip()
                elif len(head_content) == 40 or len(head_content) == 64:
                    return head_content
            except Exception:
                pass
        return "head-" + str(uuid.uuid4())[:8]

    async def ingest_repository(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        branch: Optional[str] = None,
        commit_sha: Optional[str] = None
    ) -> Snapshot:
        """
        Parses all supported code files in the cloned workspace, extracting AST
        symbols, imports, summaries, and semantic code chunks into a Snapshot.
        Guarantees idempotency: re-analyzing the same commit replaces previous records.
        """
        repo = await self.verify_user_access(repository_id, user_id)

        workspace_path = get_repository_workspace_path(user_id, repository_id)
        if not workspace_path.exists():
            raise IngestionError(
                "Repository workspace has not been cloned yet. Please clone before ingestion.",
                code="WORKSPACE_NOT_FOUND"
            )

        active_branch = branch or repo.tracked_branch or repo.default_branch or "main"
        active_commit = commit_sha or self.get_commit_sha(workspace_path)

        # Update repo status to ANALYZING
        repo.analysis_status = "ANALYZING"
        await self.db.flush()

        # Idempotency check: find or clean existing snapshot for this commit
        stmt = select(Snapshot).where(
            Snapshot.repository_id == repository_id,
            Snapshot.commit_sha == active_commit
        )
        res = await self.db.execute(stmt)
        existing_snapshot = res.scalar_one_or_none()

        if existing_snapshot:
            # Delete existing snapshot to cleanly re-populate (cascade deletes repo_files, symbols, imports, chunks)
            await self.db.delete(existing_snapshot)
            await self.db.flush()

        snapshot = Snapshot(
            repository_id=repository_id,
            commit_sha=active_commit,
            branch=active_branch,
            status="PARSING",
            total_files=0,
            total_lines=0,
            metadata_json={}
        )
        self.db.add(snapshot)
        await self.db.flush()

        # Scan workspace files
        total_files = 0
        total_lines = 0
        lang_distribution: Dict[str, int] = {}

        # Collect all valid files
        for root, dirs, files in os.walk(workspace_path):
            # Exclude ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

            for filename in files:
                full_file_path = Path(root) / filename
                rel_path = full_file_path.relative_to(workspace_path).as_posix()

                # Parse file via AST parser
                parsed: Optional[ParsedFile] = parser_service.parse_file(rel_path, full_file_path)
                if not parsed:
                    continue

                total_files += 1
                total_lines += parsed.line_count
                if parsed.language:
                    lang_distribution[parsed.language] = lang_distribution.get(parsed.language, 0) + 1

                # 1. Create RepoFile
                repo_file = RepoFile(
                    snapshot_id=snapshot.id,
                    path=parsed.path,
                    filename=parsed.filename,
                    extension=parsed.extension,
                    language=parsed.language,
                    content_hash=parsed.content_hash,
                    size_bytes=parsed.size_bytes,
                    line_count=parsed.line_count,
                    summary=None
                )
                self.db.add(repo_file)
                await self.db.flush()

                # Map symbol name to its created DB Symbol for linking code chunks
                symbol_map: Dict[str, Symbol] = {}

                # 2. Insert Symbols
                for sym in parsed.symbols:
                    db_sym = Symbol(
                        file_id=repo_file.id,
                        name=sym.name,
                        qualified_name=sym.qualified_name,
                        kind=sym.kind,
                        scope=sym.scope,
                        start_line=sym.start_line,
                        end_line=sym.end_line,
                        start_column=sym.start_column,
                        end_column=sym.end_column,
                        signature=sym.signature,
                        docstring=sym.docstring
                    )
                    self.db.add(db_sym)
                    symbol_map[sym.name] = db_sym

                # 3. Insert Imports
                for imp in parsed.imports:
                    db_imp = FileImport(
                        file_id=repo_file.id,
                        source_module=imp.source_module,
                        imported_symbol=imp.imported_symbol,
                        alias=imp.alias,
                        line_number=imp.line_number
                    )
                    self.db.add(db_imp)

                await self.db.flush()

                # 4. Insert CodeChunks
                for chk in parsed.chunks:
                    matched_sym = symbol_map.get(chk.symbol_name) if chk.symbol_name else None
                    db_chunk = CodeChunk(
                        file_id=repo_file.id,
                        symbol_id=matched_sym.id if matched_sym else None,
                        content=chk.content,
                        chunk_type=chk.chunk_type,
                        start_line=chk.start_line,
                        end_line=chk.end_line,
                        token_count=chk.token_count,
                        content_hash=chk.content_hash
                    )
                    self.db.add(db_chunk)

        # Finalize snapshot
        snapshot.status = "READY"
        snapshot.total_files = total_files
        snapshot.total_lines = total_lines
        snapshot.metadata_json = {
            "languages": lang_distribution,
            "parsed_at": datetime.now(timezone.utc).isoformat()
        }

        # Finalize repository
        repo.analysis_status = "READY"
        repo.language = repo.language or (max(lang_distribution, key=lang_distribution.get) if lang_distribution else None)

        await self.db.commit()
        await self.db.refresh(snapshot)
        logger.info(
            "Ingestion completed for repo %s (snapshot %s): %d files, %d lines",
            repository_id, snapshot.id, total_files, total_lines
        )
        return snapshot

    async def get_latest_snapshot(self, repository_id: uuid.UUID) -> Optional[Snapshot]:
        """Fetches the latest READY snapshot for a repository."""
        stmt = (
            select(Snapshot)
            .where(
                Snapshot.repository_id == repository_id,
                Snapshot.status == "READY"
            )
            .order_by(Snapshot.created_at.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_file_tree(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        current_path: str = "",
        snapshot_id: Optional[uuid.UUID] = None
    ) -> FileTreeResponse:
        """
        Navigates repository directory structure and returns files and folders for a given path.
        """
        await self.verify_user_access(repository_id, user_id)

        # Resolve snapshot
        if snapshot_id:
            stmt = select(Snapshot).where(Snapshot.id == snapshot_id, Snapshot.repository_id == repository_id)
            res = await self.db.execute(stmt)
            snapshot = res.scalar_one_or_none()
        else:
            snapshot = await self.get_latest_snapshot(repository_id)

        if not snapshot:
            return FileTreeResponse(current_path=current_path, entries=[], snapshot=None)

        # Normalize path
        norm_path = current_path.strip("/").replace("\\", "/")

        # Query all files in snapshot
        stmt = (
            select(RepoFile)
            .where(RepoFile.snapshot_id == snapshot.id)
            .options(selectinload(RepoFile.symbols))
            .order_by(RepoFile.path.asc())
        )
        res = await self.db.execute(stmt)
        files = res.scalars().all()

        entries: List[FileTreeItem] = []
        seen_dirs: Set[str] = set()

        prefix = f"{norm_path}/" if norm_path else ""

        for f in files:
            f_path = f.path.replace("\\", "/")
            if norm_path and not f_path.startswith(prefix):
                continue

            rel_sub = f_path[len(prefix):] if prefix else f_path
            parts = rel_sub.split("/")

            if len(parts) == 1:
                # Direct file in current_path
                entries.append(FileTreeItem(
                    name=parts[0],
                    path=f_path,
                    type="file",
                    language=f.language,
                    size_bytes=f.size_bytes,
                    line_count=f.line_count,
                    summary=f.summary,
                    symbol_count=len(f.symbols)
                ))
            elif len(parts) > 1:
                # Subdirectory
                dir_name = parts[0]
                if dir_name not in seen_dirs:
                    seen_dirs.add(dir_name)
                    dir_path = f"{prefix}{dir_name}" if prefix else dir_name
                    entries.append(FileTreeItem(
                        name=dir_name,
                        path=dir_path,
                        type="directory",
                        language=None,
                        size_bytes=0,
                        line_count=0,
                        summary=f"Directory containing {dir_name}",
                        symbol_count=0
                    ))

        # Sort: directories first, then alphabetical
        entries.sort(key=lambda x: (0 if x.type == "directory" else 1, x.name.lower()))

        return FileTreeResponse(
            current_path=norm_path,
            entries=entries,
            snapshot=SnapshotResponse.model_validate(snapshot)
        )

    async def get_file_detail(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        file_id: Optional[uuid.UUID] = None,
        file_path: Optional[str] = None,
        snapshot_id: Optional[uuid.UUID] = None
    ) -> FileDetailResponse:
        """
        Retrieves complete details for a file including AST symbols, imports, code chunks,
        summary, and raw text content within safe workspace boundaries.
        """
        await self.verify_user_access(repository_id, user_id)

        # Resolve snapshot
        if snapshot_id:
            s_stmt = select(Snapshot).where(Snapshot.id == snapshot_id, Snapshot.repository_id == repository_id)
            s_res = await self.db.execute(s_stmt)
            snapshot = s_res.scalar_one_or_none()
        else:
            snapshot = await self.get_latest_snapshot(repository_id)

        if not snapshot:
            raise IngestionError("No snapshot available for repository.", code="NOT_FOUND")

        # Query file
        f_stmt = (
            select(RepoFile)
            .where(RepoFile.snapshot_id == snapshot.id)
            .options(
                selectinload(RepoFile.symbols),
                selectinload(RepoFile.imports),
                selectinload(RepoFile.code_chunks)
            )
        )
        if file_id:
            f_stmt = f_stmt.where(RepoFile.id == file_id)
        elif file_path:
            norm_p = file_path.strip("/").replace("\\", "/")
            f_stmt = f_stmt.where(RepoFile.path == norm_p)
        else:
            raise IngestionError("Must specify file_id or file_path.", code="INVALID_ARGUMENT")

        res = await self.db.execute(f_stmt)
        repo_file = res.scalar_one_or_none()
        if not repo_file:
            raise IngestionError("File not found in repository snapshot.", code="NOT_FOUND")

        # Read content safely from disk
        content: Optional[str] = None
        try:
            workspace_path = get_repository_workspace_path(user_id, repository_id)
            target_path = (workspace_path / repo_file.path).resolve()
            if str(target_path).startswith(str(workspace_path)) and target_path.is_file():
                content = target_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Could not read file from disk for %s: %s", repo_file.path, e)

        return FileDetailResponse(
            id=repo_file.id,
            snapshot_id=repo_file.snapshot_id,
            path=repo_file.path,
            filename=repo_file.filename,
            extension=repo_file.extension,
            language=repo_file.language,
            content_hash=repo_file.content_hash,
            size_bytes=repo_file.size_bytes,
            line_count=repo_file.line_count,
            summary=repo_file.summary,
            content=content,
            symbols=[SymbolResponse.model_validate(s) for s in repo_file.symbols],
            imports=[ImportResponse.model_validate(i) for i in repo_file.imports],
            chunks=[CodeChunkResponse.model_validate(c) for c in repo_file.code_chunks]
        )

    async def list_symbols(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        query: Optional[str] = None,
        kind: Optional[str] = None,
        limit: int = 50
    ) -> List[SymbolResponse]:
        """Searches symbols across the codebase for the active snapshot."""
        await self.verify_user_access(repository_id, user_id)
        snapshot = await self.get_latest_snapshot(repository_id)
        if not snapshot:
            return []

        stmt = (
            select(Symbol)
            .join(RepoFile, RepoFile.id == Symbol.file_id)
            .where(RepoFile.snapshot_id == snapshot.id)
        )
        if query:
            clean_q = f"%{query.strip()}%"
            stmt = stmt.where(or_(Symbol.name.ilike(clean_q), Symbol.qualified_name.ilike(clean_q)))
        if kind:
            stmt = stmt.where(Symbol.kind == kind.upper())

        stmt = stmt.order_by(Symbol.name.asc()).limit(min(100, max(1, limit)))
        res = await self.db.execute(stmt)
        symbols = res.scalars().all()
        return [SymbolResponse.model_validate(s) for s in symbols]

    async def list_files(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID,
        search: Optional[str] = None,
        language: Optional[str] = None,
        snapshot_id: Optional[uuid.UUID] = None
    ) -> List[FileSummaryItem]:
        """Lists all files in the active snapshot with their summaries, lines, and symbol counts."""
        await self.verify_user_access(repository_id, user_id)
        if snapshot_id:
            s_stmt = select(Snapshot).where(Snapshot.id == snapshot_id, Snapshot.repository_id == repository_id)
            s_res = await self.db.execute(s_stmt)
            snapshot = s_res.scalar_one_or_none()
        else:
            snapshot = await self.get_latest_snapshot(repository_id)

        if not snapshot:
            return []

        stmt = (
            select(RepoFile)
            .where(RepoFile.snapshot_id == snapshot.id)
            .options(selectinload(RepoFile.symbols))
            .order_by(RepoFile.path.asc())
        )
        if search:
            clean_s = f"%{search.strip()}%"
            stmt = stmt.where(or_(RepoFile.path.ilike(clean_s), RepoFile.filename.ilike(clean_s), RepoFile.summary.ilike(clean_s)))
        if language:
            stmt = stmt.where(RepoFile.language == language.lower())

        res = await self.db.execute(stmt)
        files = res.scalars().all()

        items: List[FileSummaryItem] = []
        for f in files:
            fn_cnt = sum(1 for s in f.symbols if s.kind in ("FUNCTION", "METHOD"))
            cls_cnt = sum(1 for s in f.symbols if s.kind in ("CLASS", "INTERFACE"))
            items.append(FileSummaryItem(
                id=f.id,
                snapshot_id=f.snapshot_id,
                path=f.path,
                filename=f.filename,
                extension=f.extension,
                language=f.language,
                size_bytes=f.size_bytes,
                line_count=f.line_count,
                summary=f.summary,
                function_count=fn_cnt,
                class_count=cls_cnt,
                symbol_count=len(f.symbols)
            ))
        return items

    async def get_repository_overview(
        self,
        repository_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> RepositoryOverviewResponse:
        """Computes overview metrics including file, symbol, chunk counts, languages and commit info."""
        repo = await self.verify_user_access(repository_id, user_id)
        snapshot = await self.get_latest_snapshot(repository_id)

        total_symbols = 0
        total_chunks = 0
        languages: Dict[str, int] = {}

        if snapshot:
            languages = snapshot.metadata_json.get("languages", {})
            total_symbols = await self.db.scalar(
                select(func.count(Symbol.id))
                .join(RepoFile, RepoFile.id == Symbol.file_id)
                .where(RepoFile.snapshot_id == snapshot.id)
            ) or 0
            total_chunks = await self.db.scalar(
                select(func.count(CodeChunk.id))
                .join(RepoFile, RepoFile.id == CodeChunk.file_id)
                .where(RepoFile.snapshot_id == snapshot.id)
            ) or 0

        return RepositoryOverviewResponse(
            repository_id=repository_id,
            total_files=snapshot.total_files if snapshot else 0,
            total_lines=snapshot.total_lines if snapshot else 0,
            total_symbols=total_symbols,
            total_chunks=total_chunks,
            languages=languages,
            latest_snapshot=SnapshotResponse.model_validate(snapshot) if snapshot else None,
            commit_sha=snapshot.commit_sha if snapshot else None,
            branch=snapshot.branch if snapshot else (repo.tracked_branch or repo.default_branch),
            last_analyzed_at=snapshot.created_at if snapshot else None
        )
