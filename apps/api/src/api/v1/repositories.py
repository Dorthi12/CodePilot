import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status

from src.schemas.common import APIResponse
from src.schemas.repository import (
    RepositoryImportRequest,
    RepositoryResponse,
    RepositoryImportEventResponse
)
from src.models.user import User
from src.services.repository_service import (
    RepositoryService,
    RepositoryError,
    RepositoryAlreadyImportedError
)
from src.api.deps import (
    get_current_user,
    get_repository_service,
    verify_csrf
)
from src.services.ai_service import AIService, AIServiceError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["Repositories"])


class RepositorySearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[dict] = None
    top_k: int = Field(default=20, ge=1, le=100)


class RepositoryExplainRequest(BaseModel):
    code: Optional[str] = None
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    symbol_id: Optional[str] = None
    question: Optional[str] = None
    explanation_style: str = "technical"


@router.get("", response_model=APIResponse[List[RepositoryResponse]])
async def list_repositories(
    search: Optional[str] = Query(None, description="Filter by name or owner"),
    visibility: Optional[str] = Query(None, description="Filter by PUBLIC or PRIVATE"),
    status_filter: str = Query("ACTIVE", alias="status", description="Filter by repository status"),
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service)
) -> APIResponse[List[RepositoryResponse]]:
    """
    Lists all repositories imported and accessible by the current authenticated user.
    """
    repos = await repo_service.list_repositories(
        user_id=current_user.id,
        search=search,
        visibility=visibility,
        status=status_filter
    )
    return APIResponse(
        data=[RepositoryResponse.model_validate(r) for r in repos]
    )


@router.post("/import", response_model=APIResponse[RepositoryResponse], status_code=status.HTTP_201_CREATED)
async def import_repository(
    payload: RepositoryImportRequest,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[RepositoryResponse]:
    """
    Imports a GitHub repository by URL or identifier.
    Supports public repositories and private repositories accessible by the user's account.
    """
    try:
        repo = await repo_service.import_repository(
            user_id=current_user.id,
            url_or_identifier=payload.url,
            branch=payload.branch
        )
        return APIResponse(
            data=RepositoryResponse.model_validate(repo)
        )
    except RepositoryAlreadyImportedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": e.code,
                "message": e.message,
                "repository_id": str(e.existing_repo.id)
            }
        )
    except RepositoryError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if e.code in ("REPOSITORY_NOT_FOUND", "REPOSITORY_NOT_FOUND_OR_FORBIDDEN"):
            status_code = status.HTTP_404_NOT_FOUND
        elif e.code in ("FORBIDDEN", "INVALID_URL_HOST"):
            status_code = status.HTTP_403_FORBIDDEN
        elif e.code == "RATE_LIMIT_EXCEEDED":
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        elif e.code in ("INVALID_URL", "INVALID_URL_PATH", "INVALID_URL_SCHEME", "INVALID_REPOSITORY_IDENTIFIER"):
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail={
                "code": e.code,
                "message": e.message
            }
        )
    except Exception as e:
        logger.exception("Unexpected error importing repository: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Failed to import repository due to an internal error."
            }
        )


@router.get("/imports", response_model=APIResponse[List[RepositoryImportEventResponse]])
async def list_imports(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service)
) -> APIResponse[List[RepositoryImportEventResponse]]:
    """
    Returns recent import history and operations for the authenticated user.
    """
    events = await repo_service.list_imports(user_id=current_user.id, limit=limit)
    return APIResponse(
        data=[RepositoryImportEventResponse.model_validate(e) for e in events]
    )


@router.get("/{id}", response_model=APIResponse[RepositoryResponse])
async def get_repository(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service)
) -> APIResponse[RepositoryResponse]:
    """
    Retrieves details for a specific repository by ID.
    Enforces multi-tenant isolation (only accessible if owned or permitted).
    """
    repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "REPOSITORY_NOT_FOUND",
                "message": f"Repository '{id}' was not found or access is denied."
            }
        )
    return APIResponse(
        data=RepositoryResponse.model_validate(repo)
    )


@router.post("/{id}/analyze", response_model=APIResponse[RepositoryResponse])
async def trigger_analysis(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[RepositoryResponse]:
    """
    Trigger analysis for an imported repository.
    Sets analysis_status to READY (Module 3 placeholder).
    """
    try:
        repo = await repo_service.trigger_analysis(repo_id=id, user_id=current_user.id)
        return APIResponse(
            data=RepositoryResponse.model_validate(repo)
        )
    except RepositoryError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.post("/{id}/ai/search")
async def search_repository(
    id: uuid.UUID,
    payload: RepositorySearchRequest,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
    _: None = Depends(verify_csrf),
) -> dict:
    repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
    if not repo:
        raise HTTPException(status_code=404, detail={"code": "REPOSITORY_NOT_FOUND", "message": "Repository not found or access denied."})
    if repo.analysis_status != "READY":
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY", "message": "Analyze the repository before searching."})

    try:
        return await AIService().search(
            repo_id=str(repo.id),
            snapshot_id=repo.tracked_branch,
            query=payload.query,
            filters=payload.filters,
            top_k=payload.top_k,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "AI_SERVICE_ERROR", "message": exc.message})


@router.post("/{id}/ai/explain")
async def explain_repository_code(
    id: uuid.UUID,
    payload: RepositoryExplainRequest,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
    _: None = Depends(verify_csrf),
) -> dict:
    repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
    if not repo:
        raise HTTPException(status_code=404, detail={"code": "REPOSITORY_NOT_FOUND", "message": "Repository not found or access denied."})
    if repo.analysis_status != "READY":
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY", "message": "Analyze the repository before explaining code."})

    try:
        return await AIService().explain(
            repo_id=str(repo.id),
            snapshot_id=repo.tracked_branch,
            payload=payload.model_dump(exclude_none=True),
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "AI_SERVICE_ERROR", "message": exc.message})


@router.get("/{id}/analysis/summary")
async def get_repository_summary(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
) -> dict:
    """
    Get generated project summary and codebase breakdown for an analyzed repository.
    """
    repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
    if not repo:
        raise HTTPException(status_code=404, detail={"code": "REPOSITORY_NOT_FOUND", "message": "Repository not found or access denied."})
    if repo.analysis_status != "READY":
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY", "message": "Repository has not been analyzed yet."})

    try:
        return await AIService().get_summary(
            repo_id=str(repo.id),
            snapshot_id=repo.tracked_branch,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "AI_SERVICE_ERROR", "message": exc.message})


@router.get("/{id}/files")
async def get_repository_files_tree(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
) -> dict:
    """
    Get indexed file structure and hierarchy for Code Explorer.
    """
    repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
    if not repo:
        raise HTTPException(status_code=404, detail={"code": "REPOSITORY_NOT_FOUND", "message": "Repository not found or access denied."})
    if repo.analysis_status != "READY":
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY", "message": "Repository has not been analyzed yet."})

    try:
        return await AIService().get_files(
            repo_id=str(repo.id),
            snapshot_id=repo.tracked_branch,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "AI_SERVICE_ERROR", "message": exc.message})


@router.get("/{id}/file-content")
async def get_repository_file_content(
    id: uuid.UUID,
    path: str = Query(..., description="POSIX relative path to source file"),
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
) -> dict:
    """
    Retrieve source code and associated symbols for a specific file.
    """
    repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
    if not repo:
        raise HTTPException(status_code=404, detail={"code": "REPOSITORY_NOT_FOUND", "message": "Repository not found or access denied."})
    if repo.analysis_status != "READY":
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY", "message": "Repository has not been analyzed yet."})

    try:
        return await AIService().get_file_content(
            repo_id=str(repo.id),
            snapshot_id=repo.tracked_branch,
            path=path,
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "AI_SERVICE_ERROR", "message": exc.message})
