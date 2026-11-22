import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status, BackgroundTasks

from src.schemas.common import APIResponse
from src.schemas.repository import (
    RepositoryImportRequest,
    RepositoryResponse,
    RepositoryImportEventResponse
)
from src.schemas.job import RepositoryCloneRequest, JobResponse
from src.schemas.explorer import (
    FileTreeResponse,
    FileDetailResponse,
    SymbolResponse,
    SnapshotResponse,
    FileSummaryItem,
    RepositoryOverviewResponse,
    FileSummaryRequest,
    FileSummaryResponse
)
from src.models.user import User
from src.services.repository_service import (
    RepositoryService,
    RepositoryError,
    RepositoryAlreadyImportedError
)
from src.services.clone_service import CloneService, CloneError
from src.services.ingestion_service import IngestionService, IngestionError
from src.services.summary_service import SummaryService, SummaryError
from src.api.deps import (
    get_current_user,
    get_repository_service,
    get_clone_service,
    get_ingestion_service,
    get_summary_service,
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


@router.post("/{id}/clone", response_model=APIResponse[JobResponse], status_code=status.HTTP_202_ACCEPTED)
async def clone_repository(
    id: uuid.UUID,
    payload: RepositoryCloneRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    clone_service: CloneService = Depends(get_clone_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[JobResponse]:
    """
    Initiates cloning of an imported repository into an isolated local workspace.
    Supports GIT_CLONE and ZIP_DOWNLOAD retrieval methods.
    Returns 202 Accepted with the queued Job representation.
    """
    try:
        job = await clone_service.initiate_clone(
            repository_id=id,
            user_id=current_user.id,
            branch=payload.branch,
            retrieval_method=payload.retrieval_method.value
        )
        background_tasks.add_task(clone_service.execute_clone_job, job.id)
        return APIResponse(data=JobResponse.model_validate(job))
    except CloneError as e:
        status_code = status.HTTP_400_BAD_REQUEST
        if e.code == "REPOSITORY_NOT_FOUND":
            status_code = status.HTTP_404_NOT_FOUND
        elif e.code == "CLONE_ALREADY_IN_PROGRESS":
            status_code = status.HTTP_409_CONFLICT
        elif e.code == "TOKEN_REQUIRED":
            status_code = status.HTTP_401_UNAUTHORIZED
        elif e.code == "REPO_TOO_LARGE":
            status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.get("/{id}/clone/status", response_model=APIResponse[Optional[JobResponse]])
async def get_clone_status(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    clone_service: CloneService = Depends(get_clone_service)
) -> APIResponse[Optional[JobResponse]]:
    """
    Retrieves the latest clone/ingestion job progress and status for a repository.
    """
    job = await clone_service.get_latest_repository_job(repository_id=id, user_id=current_user.id)
    return APIResponse(data=JobResponse.model_validate(job) if job else None)


@router.post("/{id}/analyze", response_model=APIResponse[RepositoryResponse])
async def trigger_analysis(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    repo_service: RepositoryService = Depends(get_repository_service),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[RepositoryResponse]:
    """
    Triggers full AST ingestion and code analysis for a cloned repository.
    Parses functions, classes, methods, imports, semantic chunks, and summaries.
    """
    try:
        # Run AST ingestion on the cloned workspace if present; otherwise fallback to repo_service
        try:
            await ingestion_service.ingest_repository(repository_id=id, user_id=current_user.id)
            repo = await repo_service.get_repository(repo_id=id, user_id=current_user.id)
        except IngestionError as e:
            if e.code == "WORKSPACE_NOT_FOUND":
                repo = await repo_service.trigger_analysis(repo_id=id, user_id=current_user.id)
            else:
                raise

        if not repo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
        return APIResponse(data=RepositoryResponse.model_validate(repo))
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code in ("NOT_FOUND", "WORKSPACE_NOT_FOUND") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})
    except RepositoryError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.get("/{id}/tree", response_model=APIResponse[FileTreeResponse])
async def get_repository_file_tree(
    id: uuid.UUID,
    path: str = Query("", description="Relative path in repo directory tree"),
    snapshot_id: Optional[uuid.UUID] = Query(None, description="Specific snapshot ID"),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> APIResponse[FileTreeResponse]:
    """
    Returns files and subdirectories for Codebase Explorer navigation.
    """
    try:
        tree = await ingestion_service.get_file_tree(
            repository_id=id,
            user_id=current_user.id,
            current_path=path,
            snapshot_id=snapshot_id
        )
        return APIResponse(data=tree)
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.get("/{id}/file", response_model=APIResponse[FileDetailResponse])
async def get_repository_file_by_path(
    id: uuid.UUID,
    path: str = Query(..., description="Relative file path"),
    snapshot_id: Optional[uuid.UUID] = Query(None, description="Specific snapshot ID"),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> APIResponse[FileDetailResponse]:
    """
    Inspects an individual file by path: returns file metadata, content, symbols, imports, and chunks.
    """
    try:
        detail = await ingestion_service.get_file_detail(
            repository_id=id,
            user_id=current_user.id,
            file_path=path,
            snapshot_id=snapshot_id
        )
        return APIResponse(data=detail)
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.get("/{id}/files/{file_id}", response_model=APIResponse[FileDetailResponse])
async def get_repository_file_by_id(
    id: uuid.UUID,
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> APIResponse[FileDetailResponse]:
    """
    Inspects an individual file by its unique file ID.
    """
    try:
        detail = await ingestion_service.get_file_detail(
            repository_id=id,
            user_id=current_user.id,
            file_id=file_id
        )
        return APIResponse(data=detail)
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.get("/{id}/symbols", response_model=APIResponse[List[SymbolResponse]])
async def list_repository_symbols(
    id: uuid.UUID,
    q: Optional[str] = Query(None, description="Search query for symbol name"),
    kind: Optional[str] = Query(None, description="Filter by symbol kind (FUNCTION, CLASS, METHOD, INTERFACE)"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> APIResponse[List[SymbolResponse]]:
    """
    Searches and lists symbols across the repository codebase for the active snapshot.
    """
    try:
        symbols = await ingestion_service.list_symbols(
            repository_id=id,
            user_id=current_user.id,
            query=q,
            kind=kind,
            limit=limit
        )
        return APIResponse(data=symbols)
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.get("/{id}/overview", response_model=APIResponse[RepositoryOverviewResponse])
async def get_repository_overview(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> APIResponse[RepositoryOverviewResponse]:
    """
    Returns repository overview metrics including snapshot stats, symbols, chunks, and languages.
    """
    try:
        overview = await ingestion_service.get_repository_overview(
            repository_id=id,
            user_id=current_user.id
        )
        return APIResponse(data=overview)
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.get("/{id}/files", response_model=APIResponse[List[FileSummaryItem]])
async def list_repository_files(
    id: uuid.UUID,
    search: Optional[str] = Query(None, description="Search by file path or summary"),
    language: Optional[str] = Query(None, description="Filter by language"),
    snapshot_id: Optional[uuid.UUID] = Query(None, description="Specific snapshot ID"),
    current_user: User = Depends(get_current_user),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> APIResponse[List[FileSummaryItem]]:
    """
    Returns all indexed files in the active snapshot with their summaries, sizes, lines, and symbol counts.
    """
    try:
        files = await ingestion_service.list_files(
            repository_id=id,
            user_id=current_user.id,
            search=search,
            language=language,
            snapshot_id=snapshot_id
        )
        return APIResponse(data=files)
    except IngestionError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code == "NOT_FOUND" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.post("/{id}/files/{file_id}/summary", response_model=APIResponse[FileSummaryResponse])
async def generate_file_summary(
    id: uuid.UUID,
    file_id: uuid.UUID,
    force: bool = Query(False, description="Force regeneration even if cached"),
    current_user: User = Depends(get_current_user),
    summary_service: SummaryService = Depends(get_summary_service)
) -> APIResponse[FileSummaryResponse]:
    """
    On-demand file-level summary generation.
    Returns cached summary if file content hash has not changed, or regenerates if forced or content changed.
    """
    try:
        summary_resp = await summary_service.generate_file_summary(
            repository_id=id,
            user_id=current_user.id,
            file_id=file_id,
            force=force
        )
        return APIResponse(data=summary_resp)
    except SummaryError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code in ("NOT_FOUND", "FILE_NOT_FOUND") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})


@router.post("/{id}/files/summary", response_model=APIResponse[FileSummaryResponse])
async def generate_file_summary_by_path(
    id: uuid.UUID,
    request: FileSummaryRequest,
    current_user: User = Depends(get_current_user),
    summary_service: SummaryService = Depends(get_summary_service)
) -> APIResponse[FileSummaryResponse]:
    """
    On-demand file-level summary generation by path or file_id.
    """
    try:
        summary_resp = await summary_service.generate_file_summary(
            repository_id=id,
            user_id=current_user.id,
            file_id=request.file_id,
            file_path=request.file_path,
            force=request.force
        )
        return APIResponse(data=summary_resp)
    except SummaryError as e:
        status_code = status.HTTP_404_NOT_FOUND if e.code in ("NOT_FOUND", "FILE_NOT_FOUND") else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})
