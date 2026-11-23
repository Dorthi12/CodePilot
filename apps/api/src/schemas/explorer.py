import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class SnapshotResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    commit_sha: str
    branch: str
    status: str
    total_files: int
    total_lines: int
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileTreeItem(BaseModel):
    name: str
    path: str
    type: str  # "file" | "directory"
    language: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    summary: Optional[str] = None
    symbol_count: int = 0


class FileTreeResponse(BaseModel):
    current_path: str
    entries: List[FileTreeItem]
    snapshot: Optional[SnapshotResponse] = None


class SymbolResponse(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    name: str
    qualified_name: str
    kind: str
    scope: Optional[str] = None
    start_line: int
    end_line: int
    start_column: int = 0
    end_column: int = 0
    signature: Optional[str] = None
    docstring: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ImportResponse(BaseModel):
    id: uuid.UUID
    source_module: str
    imported_symbol: Optional[str] = None
    alias: Optional[str] = None
    line_number: int

    model_config = ConfigDict(from_attributes=True)


class CodeChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_type: str
    start_line: int
    end_line: int
    token_count: int
    content: str
    content_hash: str

    model_config = ConfigDict(from_attributes=True)


class FileDetailResponse(BaseModel):
    id: uuid.UUID
    snapshot_id: uuid.UUID
    path: str
    filename: str
    extension: Optional[str] = None
    language: Optional[str] = None
    content_hash: str
    size_bytes: int
    line_count: int
    summary: Optional[str] = None
    content: Optional[str] = None
    symbols: List[SymbolResponse] = Field(default_factory=list)
    imports: List[ImportResponse] = Field(default_factory=list)
    chunks: List[CodeChunkResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class FileSummaryItem(BaseModel):
    id: uuid.UUID
    snapshot_id: uuid.UUID
    path: str
    filename: str
    extension: Optional[str] = None
    language: Optional[str] = None
    size_bytes: int = 0
    line_count: int = 0
    summary: Optional[str] = None
    function_count: int = 0
    class_count: int = 0
    symbol_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class FileSummaryRequest(BaseModel):
    file_id: Optional[uuid.UUID] = None
    file_path: Optional[str] = None
    force: bool = False


class FileSummaryResponse(BaseModel):
    file_id: uuid.UUID
    path: str
    filename: str
    language: Optional[str] = None
    summary: str
    cached: bool = False
    content_hash: str

    model_config = ConfigDict(from_attributes=True)


class RepositoryOverviewResponse(BaseModel):
    repository_id: uuid.UUID
    total_files: int = 0
    total_lines: int = 0
    total_symbols: int = 0
    total_chunks: int = 0
    languages: Dict[str, int] = Field(default_factory=dict)
    latest_snapshot: Optional[SnapshotResponse] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    last_analyzed_at: Optional[datetime] = None
