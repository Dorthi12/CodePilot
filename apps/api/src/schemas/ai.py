"""Pydantic request and response schemas for AI Code Intelligence endpoints."""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


def _validate_safe_relative_path(value: Optional[str]) -> Optional[str]:
    """Ensure path inputs are relative and cannot traverse outside the repository."""
    if value is None:
        return None
    cleaned = value.strip().replace("\\", "/")
    if not cleaned:
        return None
    if cleaned.startswith("/") or (len(cleaned) >= 2 and cleaned[1] == ":"):
        raise PydanticCustomError("unsafe_path", "Path must be relative to the repository root.")
    parts = PurePosixPath(cleaned).parts
    if ".." in parts:
        raise PydanticCustomError("unsafe_path", "Path traversal ('..') is not allowed.")
    return cleaned


class RepoIndexRequest(BaseModel):
    """Request payload for indexing a repository snapshot."""

    snapshot_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional completed snapshot UUID. Uses latest completed snapshot if omitted.",
    )
    force: bool = Field(
        default=False,
        description="Force re-indexing even if snapshot index is already cached.",
    )


class RepoIndexResponse(BaseModel):
    """Response payload after indexing a repository snapshot."""

    repo_id: str
    snapshot_id: str
    symbol_count: int
    file_count: int
    warnings: List[str] = Field(default_factory=list)
    cached: bool = False
    message: str


class CodeSearchFiltersRequest(BaseModel):
    """Optional filters for repository code search."""

    kinds: Optional[List[str]] = Field(
        default=None,
        description="Filter by symbol kinds (e.g. FUNCTION, CLASS, METHOD, INTERFACE).",
    )
    languages: Optional[List[str]] = Field(
        default=None,
        description="Filter by languages (python, javascript, typescript, java, go).",
    )
    path_prefix: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Restrict results to files under this repository-relative path prefix.",
    )

    @field_validator("path_prefix")
    @classmethod
    def validate_path_prefix(cls, v: Optional[str]) -> Optional[str]:
        return _validate_safe_relative_path(v)


class CodeSearchRequest(BaseModel):
    """Request payload for searching code symbols in a repository snapshot."""

    query: str = Field(..., min_length=1, max_length=500)
    snapshot_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional completed snapshot UUID. Uses latest completed snapshot if omitted.",
    )
    filters: Optional[CodeSearchFiltersRequest] = None
    top_k: int = Field(default=20, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_non_empty_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise PydanticCustomError("empty_query", "Search query cannot be empty or whitespace only.")
        return stripped


class CodeSearchResultItem(BaseModel):
    """Single ranked symbol match returned by code search."""

    source_id: str
    repo_id: str
    snapshot_id: str
    file_path: str
    language: str
    kind: str
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    match_type: str
    signature: Optional[str] = None


class CodeSearchResponse(BaseModel):
    """Response payload for repository code search."""

    repo_id: str
    snapshot_id: str
    query: str
    total: int
    results: List[CodeSearchResultItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CodeExplainRequest(BaseModel):
    """Request payload for AI code explanation."""

    snapshot_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Optional completed snapshot UUID. Uses latest completed snapshot if omitted.",
    )
    code: Optional[str] = Field(
        default=None,
        max_length=50000,
        description="Explicit selected code snippet to explain.",
    )
    file_path: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Repository-relative file path.",
    )
    start_line: Optional[int] = Field(default=None, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)
    symbol_id: Optional[str] = Field(default=None, max_length=256)
    question: Optional[str] = Field(default=None, max_length=1000)
    explanation_style: Literal["beginner", "technical", "deep"] = Field(
        default="technical",
        description="Target audience style: beginner | technical | deep.",
    )

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: Optional[str]) -> Optional[str]:
        return _validate_safe_relative_path(v)

    @model_validator(mode="after")
    def validate_target_and_lines(self) -> "CodeExplainRequest":
        has_code = bool(self.code and self.code.strip())
        has_file = bool(self.file_path and self.file_path.strip())
        has_symbol = bool(self.symbol_id and self.symbol_id.strip())
        if not (has_code or has_file or has_symbol):
            raise PydanticCustomError(
                "missing_target",
                "Provide at least one of 'code', 'file_path', or 'symbol_id'.",
            )
        if self.start_line is not None and self.end_line is not None and self.end_line < self.start_line:
            raise PydanticCustomError(
                "invalid_line_range",
                "'end_line' must be greater than or equal to 'start_line'.",
            )
        return self


class CitationItemResponse(BaseModel):
    """Reference citation pointing back to a repository file and line range."""

    source_id: str
    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    snippet: str


class RelatedSymbolContextResponse(BaseModel):
    """Cross-file symbol definition retrieved from repository context."""

    name: str
    kind: str
    file_path: str
    start_line: int
    end_line: int
    snippet: str
    relevance_reason: str


class CodeExplainResponse(BaseModel):
    """Structured AI code explanation response."""

    repo_id: str
    snapshot_id: str
    file_path: Optional[str] = None
    language: str
    selected_code: str
    question: Optional[str] = None
    explanation_style: str
    overview: str
    step_by_step: List[str] = Field(default_factory=list)
    inputs: Optional[str] = None
    outputs: Optional[str] = None
    important_symbols: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)
    edge_cases: List[str] = Field(default_factory=list)
    related_symbols: List[RelatedSymbolContextResponse] = Field(default_factory=list)
    citations: List[CitationItemResponse] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    raw_explanation: str
