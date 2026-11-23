import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from src.schemas.common import APIResponse
from src.schemas.job import JobResponse
from src.models.user import User
from src.services.clone_service import CloneService, CloneError
from src.api.deps import get_current_user, get_clone_service, verify_csrf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{id}", response_model=APIResponse[JobResponse])
async def get_job(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    clone_service: CloneService = Depends(get_clone_service)
) -> APIResponse[JobResponse]:
    """
    Retrieves status, progress, stage, and statistics for a specific job.
    Enforces multi-tenant ownership.
    """
    job = await clone_service.get_job(job_id=id, user_id=current_user.id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": f"Job '{id}' was not found or access is denied."
            }
        )
    return APIResponse(data=JobResponse.model_validate(job))


@router.post("/{id}/cancel", response_model=APIResponse[JobResponse])
async def cancel_job(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    clone_service: CloneService = Depends(get_clone_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[JobResponse]:
    """
    Requests cooperative cancellation of an active job.
    """
    try:
        job = await clone_service.cancel_job(job_id=id, user_id=current_user.id)
        return APIResponse(data=JobResponse.model_validate(job))
    except CloneError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if e.code == "JOB_NOT_FOUND" else status.HTTP_400_BAD_REQUEST,
            detail={"code": e.code, "message": e.message}
        )


@router.post("/{id}/retry", response_model=APIResponse[JobResponse], status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    clone_service: CloneService = Depends(get_clone_service),
    _: None = Depends(verify_csrf)
) -> APIResponse[JobResponse]:
    """
    Retries a failed or cancelled clone job.
    """
    old_job = await clone_service.get_job(job_id=id, user_id=current_user.id)
    if not old_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job '{id}' not found."}
        )

    try:
        new_job = await clone_service.initiate_clone(
            repository_id=old_job.repository_id,
            user_id=current_user.id,
            branch=old_job.branch,
            retrieval_method=old_job.retrieval_method
        )
        background_tasks.add_task(clone_service.execute_clone_job, new_job.id)
        return APIResponse(data=JobResponse.model_validate(new_job))
    except CloneError as e:
        status_code = status.HTTP_409_CONFLICT if e.code == "CLONE_ALREADY_IN_PROGRESS" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail={"code": e.code, "message": e.message})
