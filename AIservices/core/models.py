"""
Core data models shared across all AIservices features.
Aligns with the CodePilot Master Architecture Specification v2.1.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations  (§6.1.1 of the Master Spec)
# ---------------------------------------------------------------------------

class SymbolKind(str, Enum):
    MODULE = "MODULE"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    ENUM = "ENUM"
    TYPE_ALIAS = "TYPE_ALIAS"
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    FIELD = "FIELD"
    ENUM_MEMBER = "ENUM_MEMBER"
    API_ENDPOINT = "API_ENDPOINT"
    TEST = "TEST"
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"


class SupportedLanguage(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    UNKNOWN = "unknown"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PROBABLE = "PROBABLE"
    UNRESOLVED = "UNRESOLVED"


# ---------------------------------------------------------------------------
# Symbol / Code-element model  (§6.1 — extracted entity)
# ---------------------------------------------------------------------------

class CodeSymbol(BaseModel):
    """A single code entity extracted from a source file."""

    # Identity
    symbol_id: str = Field(description="Deterministic id: sha256(repo_id|path|kind|qualified_name|start_line)")
    repo_id: str = Field(description="Opaque repository identifier supplied by the caller")
    snapshot_id: str = Field(description="Snapshot version identifier (e.g. commit SHA or UUID)")

    # Location
    file_path: str = Field(description="POSIX repo-relative path, e.g. app/auth/service.py")
    language: SupportedLanguage

    # Symbol metadata
    kind: SymbolKind
    name: str
    qualified_name: str = Field(description="Dot-separated fully qualified name")
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    signature: Optional[str] = None
    exported: bool = False

    # Snippet – the raw source text for this symbol
    snippet: str = Field(description="Extracted source lines for this symbol")

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# Search request / response models  (§11.3 — POST /search)
# ---------------------------------------------------------------------------

class SearchFilters(BaseModel):
    """Optional filters applied to a code-search query."""
    kinds: Optional[list[SymbolKind]] = Field(default=None, description="Filter by symbol kinds")
    languages: Optional[list[SupportedLanguage]] = Field(default=None, description="Filter by language")
    path_prefix: Optional[str] = Field(default=None, description="Restrict to files under this path prefix")


class SearchRequest(BaseModel):
    """Payload for a code-search request."""
    repo_id: str
    snapshot_id: str
    query: str = Field(min_length=1, max_length=500)
    filters: Optional[SearchFilters] = None
    top_k: int = Field(default=20, ge=1, le=100)


class SearchResultItem(BaseModel):
    """A single ranked search result."""
    source_id: str = Field(description="Same as CodeSymbol.symbol_id; stable citation anchor")
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
    score: float = Field(ge=0.0, le=1.0, description="Relevance score, higher is better")
    match_type: str = Field(description="exact | symbol | fuzzy")
    signature: Optional[str] = None


class SearchResponse(BaseModel):
    """Full response returned by the search endpoint."""
    repo_id: str
    snapshot_id: str
    query: str
    total: int
    results: list[SearchResultItem]
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Index snapshot model — what the indexer produces and the searcher consumes
# ---------------------------------------------------------------------------

class RepoIndex(BaseModel):
    """In-memory index for one repository snapshot."""
    repo_id: str
    snapshot_id: str
    symbols: list[CodeSymbol] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict, description="Map of file_path to source text")
    warnings: list[str] = Field(default_factory=list)
