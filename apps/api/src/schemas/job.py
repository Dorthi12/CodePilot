import uuid
from datetime import datetime
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class RetrievalMethod(str, Enum):
    GIT_CLONE = "GIT_CLONE"
    ZIP_DOWNLOAD = "ZIP_DOWNLOAD"


class JobStage(str, Enum):
    VALIDATING = "VALIDATING"
    CLONING = "CLONING"
    SCANNING = "SCANNING"
    PARSING = "PARSING"
    CHUNKING = "CHUNKING"
    STORING = "STORING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RepositoryCloneRequest(BaseModel):
    branch: Optional[str] = Field(None, description="Branch to clone. Defaults to tracked branch or default branch.")
    retrieval_method: RetrievalMethod = Field(
        default=RetrievalMethod.GIT_CLONE,
        description="Retrieval method: GIT_CLONE (standard git) or ZIP_DOWNLOAD (GitHub archive stream)"
    )


class JobResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    user_id: uuid.UUID
    job_type: str
    status: str
    stage: str
    retrieval_method: str
    progress: Optional[float] = None
    progress_message: Optional[str] = None
    branch: str
    commit_sha: Optional[str] = None
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    files_discovered: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retryable: bool = False
    cancel_requested: bool = False
    workspace_path: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
