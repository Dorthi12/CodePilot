"""Authenticated AI Code Intelligence API endpoints (Code Search & Explanation)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status

from AIservices.api.index_store import list_indexes
from src.api.deps import get_ai_service, get_current_user, verify_csrf
from src.models.user import User
from src.schemas.ai import (
    CodeExplainRequest,
    CodeExplainResponse,
    CodeSearchRequest,
    CodeSearchResponse,
    RepoIndexRequest,
    RepoIndexResponse,
)
from src.schemas.common import APIResponse
from src.services.ai_service import AIServiceBridge, AIServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["AI Code Intelligence"])

# Per-repository async locks to prevent concurrent duplicate indexing of the same snapshot
_INDEX_LOCKS: Dict[str, asyncio.Lock] = {}


def _get_repo_index_lock(repository_id: uuid.UUID) -> asyncio.Lock:
    key = str(repository_id)
    lock = _INDEX_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _INDEX_LOCKS[key] = lock
    return lock


def _raise_for_ai_error(exc: AIServiceError) -> None:
    """Map AIServiceError to sanitized HTTP responses without leaking internals."""
    if exc.code in ("NOT_FOUND", "NO_SNAPSHOT", "WORKSPACE_NOT_FOUND"):
        status_code = status.HTTP_404_NOT_FOUND
    elif exc.code == "INVALID_INPUT":
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.post(
    "/{repository_id}/index",
    response_model=APIResponse[RepoIndexResponse],
    status_code=status.HTTP_200_OK,
)
async def index_repository_for_ai(
    repository_id: uuid.UUID,
    body: RepoIndexRequest = RepoIndexRequest(),
    current_user: User = Depends(get_current_user),
    ai_service: AIServiceBridge = Depends(get_ai_service),
    _: None = Depends(verify_csrf),
) -> APIResponse[RepoIndexResponse]:
    """
    Idempotently index a repository's completed snapshot for AI code search and explanation.
    """
    lock = _get_repo_index_lock(repository_id)
    async with lock:
        try:
            existing_keys = {
                (item["repo_id"], item["snapshot_id"]) for item in list_indexes()
            }
            repo_index, snapshot = await ai_service.get_or_build_repo_index(
                repository_id=repository_id,
                user_id=current_user.id,
                snapshot_id=body.snapshot_id,
                force_rebuild=body.force,
            )
            was_cached = (
                not body.force
                and (str(repository_id), str(snapshot.id)) in existing_keys
            )
            return APIResponse(
                data=RepoIndexResponse(
                    repo_id=repo_index.repo_id,
                    snapshot_id=repo_index.snapshot_id,
                    symbol_count=len(repo_index.symbols),
                    file_count=len(repo_index.files),
                    warnings=repo_index.warnings,
                    cached=was_cached,
                    message=(
                        f"Snapshot index ready ({len(repo_index.symbols)} symbols "
                        f"across {len(repo_index.files)} files)."
                    ),
                )
            )
        except AIServiceError as exc:
            _raise_for_ai_error(exc)
        except Exception:
            logger.exception("Unexpected error indexing repository %s", repository_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "AI_INDEX_ERROR",
                    "message": "Failed to index repository snapshot.",
                },
            )


@router.post(
    "/{repository_id}/search",
    response_model=APIResponse[CodeSearchResponse],
    status_code=status.HTTP_200_OK,
)
async def search_repository_code(
    repository_id: uuid.UUID,
    body: CodeSearchRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIServiceBridge = Depends(get_ai_service),
) -> APIResponse[CodeSearchResponse]:
    """
    Search symbols across an analyzed repository snapshot (exact, symbol, fuzzy modes).
    """
    try:
        result = await ai_service.search_code(
            repository_id=repository_id,
            user_id=current_user.id,
            query=body.query,
            kinds=body.filters.kinds if body.filters else None,
            languages=body.filters.languages if body.filters else None,
            path_prefix=body.filters.path_prefix if body.filters else None,
            top_k=body.top_k,
            snapshot_id=body.snapshot_id,
        )
        return APIResponse(data=CodeSearchResponse(**result.model_dump()))
    except AIServiceError as exc:
        _raise_for_ai_error(exc)
    except Exception:
        logger.exception("Unexpected error searching repository %s", repository_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "AI_SEARCH_ERROR",
                "message": "Failed to execute code search.",
            },
        )


@router.post(
    "/{repository_id}/explain",
    response_model=APIResponse[CodeExplainResponse],
    status_code=status.HTTP_200_OK,
)
async def explain_repository_code(
    repository_id: uuid.UUID,
    body: CodeExplainRequest,
    current_user: User = Depends(get_current_user),
    ai_service: AIServiceBridge = Depends(get_ai_service),
) -> APIResponse[CodeExplainResponse]:
    """
    Generate a grounded AI code explanation with cross-file context and citations.
    """
    try:
        result = await ai_service.explain_code(
            repository_id=repository_id,
            user_id=current_user.id,
            code=body.code,
            file_path=body.file_path,
            start_line=body.start_line,
            end_line=body.end_line,
            symbol_id=body.symbol_id,
            question=body.question,
            explanation_style=body.explanation_style,
            snapshot_id=body.snapshot_id,
        )
        return APIResponse(data=CodeExplainResponse(**result.model_dump()))
    except AIServiceError as exc:
        _raise_for_ai_error(exc)
    except Exception:
        logger.exception("Unexpected error explaining code in repository %s", repository_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "AI_EXPLAIN_ERROR",
                "message": "Failed to generate code explanation.",
            },
        )
