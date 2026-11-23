"""
FastAPI route definitions for AIservices Code Search.
Provides endpoints for repository indexing and ranked symbol search.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from AIservices.api.index_store import (
    delete_index,
    get_index,
    list_indexes,
    save_index,
)
from AIservices.api.schemas import (
    ErrorResponse,
    ExplainHTTPRequest,
    IndexRequest,
    IndexResponse,
    SearchHTTPRequest,
)
from AIservices.core.models import SearchRequest, SearchResponse
from AIservices.core.parser import index_repository
from AIservices.features.code_explanation import (
    ExplanationRequest,
    ExplanationResponse,
    ExplanationStyle,
    explain_code,
)
from AIservices.features.code_search import search

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", tags=["system"])
def health_check():
    """Health check endpoint to verify AIservices is running."""
    return {
        "status": "ok",
        "service": "AIservices",
        "feature": "Feature 1: Basic Code Search",
        "version": "1.0.0",
    }


@router.post(
    "/index",
    response_model=IndexResponse,
    status_code=status.HTTP_200_OK,
    tags=["indexing"],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid index request"},
    },
)
def index_repo(payload: IndexRequest) -> IndexResponse:
    """
    Index a repository snapshot from provided source files.

    Accepts a map of {relative_file_path: source_code} and extracts code symbols
    (functions, classes, methods, variables, imports/exports) across supported
    languages (Python, JS, TS, Java, Go). The resulting index is stored in-memory
    keyed by (repo_id, snapshot_id) for immediate fast retrieval.
    """
    if not payload.repo_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repo_id cannot be empty",
        )
    if not payload.snapshot_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="snapshot_id cannot be empty",
        )

    try:
        repo_index = index_repository(
            repo_id=payload.repo_id,
            snapshot_id=payload.snapshot_id,
            files=payload.files,
        )
        save_index(repo_index)

        return IndexResponse(
            repo_id=repo_index.repo_id,
            snapshot_id=repo_index.snapshot_id,
            symbol_count=len(repo_index.symbols),
            warnings=repo_index.warnings,
            message=f"Successfully indexed {len(repo_index.symbols)} symbols across {len(payload.files)} files.",
        )
    except Exception as exc:
        logger.exception("Failed to index repository %s: %s", payload.repo_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {str(exc)}",
        )


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    tags=["search"],
    responses={
        404: {"model": ErrorResponse, "description": "Repository snapshot index not found"},
        400: {"model": ErrorResponse, "description": "Invalid search parameters"},
    },
)
def search_code(payload: SearchHTTPRequest):
    """
    Search for code symbols across an indexed repository snapshot.

    Performs multi-mode ranked code search (exact, symbol word-boundary, and fuzzy)
    with optional filtering by symbol kinds, programming languages, and file path prefixes.
    """
    if not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty or whitespace only",
        )

    index = get_index(payload.repo_id, payload.snapshot_id)
    if index is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=f"Index not found for repo '{payload.repo_id}' at snapshot '{payload.snapshot_id}'.",
                code="INDEX_NOT_FOUND",
                details={"repo_id": payload.repo_id, "snapshot_id": payload.snapshot_id},
            ).model_dump(),
        )

    search_req = SearchRequest(
        repo_id=payload.repo_id,
        snapshot_id=payload.snapshot_id,
        query=payload.query.strip(),
        filters=payload.filters,
        top_k=payload.top_k,
    )

    try:
        result = search(search_req, index)
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Search execution error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(exc)}",
        )


@router.post(
    "/explain",
    response_model=ExplanationResponse,
    status_code=status.HTTP_200_OK,
    tags=["explanation"],
    responses={
        404: {"model": ErrorResponse, "description": "Repository snapshot index not found"},
        400: {"model": ErrorResponse, "description": "Invalid explanation request"},
    },
)
@router.post(
    "/ai/explain",
    response_model=ExplanationResponse,
    status_code=status.HTTP_200_OK,
    tags=["explanation"],
    include_in_schema=False,
)
def explain_code_endpoint(payload: ExplainHTTPRequest):
    """
    Explain selected code snippet with repository context grounding (Feature 2).

    Accepts a code snippet or coordinates (file_path + lines / symbol_id),
    retrieves surrounding context and related symbols from Feature 1 search,
    and returns a structured explanation with line citations and edge cases.
    """
    if not payload.repo_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repo_id cannot be empty",
        )
    if not payload.snapshot_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="snapshot_id cannot be empty",
        )

    index = get_index(payload.repo_id, payload.snapshot_id)
    if index is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=f"Index not found for repo '{payload.repo_id}' at snapshot '{payload.snapshot_id}'.",
                code="INDEX_NOT_FOUND",
                details={"repo_id": payload.repo_id, "snapshot_id": payload.snapshot_id},
            ).model_dump(),
        )

    # Validate style
    try:
        style = ExplanationStyle(payload.explanation_style.lower())
    except ValueError:
        style = ExplanationStyle.TECHNICAL

    req = ExplanationRequest(
        repo_id=payload.repo_id,
        snapshot_id=payload.snapshot_id,
        code=payload.code,
        file_path=payload.file_path,
        start_line=payload.start_line,
        end_line=payload.end_line,
        symbol_id=payload.symbol_id,
        question=payload.question,
        explanation_style=style,
    )

    try:
        response = explain_code(req, index)
        return response
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.exception("Code explanation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Explanation generation failed: {str(exc)}",
        )



@router.get("/indexes", tags=["indexing"])
def get_all_indexes():
    """List all currently loaded repository snapshot indexes."""
    return {"indexes": list_indexes()}


@router.get("/indexes/{repo_id}/{snapshot_id}", tags=["indexing"])
def get_index_details(repo_id: str, snapshot_id: str):
    """Get metadata for a specific repository snapshot index."""
    idx = get_index(repo_id, snapshot_id)
    if idx is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=f"Index not found for repo '{repo_id}' at snapshot '{snapshot_id}'.",
                code="INDEX_NOT_FOUND",
                details={"repo_id": repo_id, "snapshot_id": snapshot_id},
            ).model_dump(),
        )
    return {
        "repo_id": idx.repo_id,
        "snapshot_id": idx.snapshot_id,
        "symbol_count": len(idx.symbols),
        "warnings": idx.warnings,
    }


@router.delete("/indexes/{repo_id}/{snapshot_id}", tags=["indexing"])
def remove_index(repo_id: str, snapshot_id: str):
    """Delete a repository snapshot index from memory."""
    deleted = delete_index(repo_id, snapshot_id)
    if not deleted:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=f"Index not found for repo '{repo_id}' at snapshot '{snapshot_id}'.",
                code="INDEX_NOT_FOUND",
                details={"repo_id": repo_id, "snapshot_id": snapshot_id},
            ).model_dump(),
        )
    return {"message": "Index removed successfully", "deleted": True}
