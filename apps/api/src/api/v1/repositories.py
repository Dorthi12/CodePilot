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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["Repositories"])


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
