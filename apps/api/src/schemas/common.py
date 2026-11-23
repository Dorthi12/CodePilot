from typing import Generic, TypeVar, Optional, Any, Dict
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    data: T
    request_id: Optional[str] = None
    trace_id: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    retryable: bool = False
    trace_id: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
