"""
Pydantic models used in the HTTP layer (request/response bodies).
These wrap the core models and add HTTP-specific fields.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from AIservices.core.models import SearchFilters


class IndexRequest(BaseModel):
    """
    Payload for POST /index.
    The caller (Node backend or test) supplies raw source files.
    """
    repo_id: str = Field(description="Opaque identifier for this repository")
    snapshot_id: str = Field(description="Commit SHA or UUID identifying this snapshot")
    files: dict[str, str] = Field(
        description="Map of POSIX repo-relative paths to source text. E.g. {'app/main.py': '...'}"
    )


class IndexResponse(BaseModel):
    repo_id: str
    snapshot_id: str
    symbol_count: int
    warnings: list[str] = Field(default_factory=list)
    message: str


class SearchHTTPRequest(BaseModel):
    """
    POST /search body.  Mirrors core SearchRequest but kept separate so the
    HTTP layer can evolve independently.
    """
    repo_id: str
    snapshot_id: str
    query: str = Field(min_length=1, max_length=500)
    filters: SearchFilters | None = None
    top_k: int = Field(default=20, ge=1, le=100)


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: dict = Field(default_factory=dict)


class ExplainHTTPRequest(BaseModel):
    """
    POST /explain and POST /ai/explain request body.
    """
    repo_id: str
    snapshot_id: str
    code: str | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    symbol_id: str | None = None
    question: str | None = None
    explanation_style: str = "technical"

