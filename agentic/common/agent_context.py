"""Agent repository context providing access to files, symbols, and graph data."""

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SnapshotFile:
    path: str
    content: str
    language: str
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass
class SnapshotSymbol:
    id: str
    name: str
    qualified_name: str
    kind: str  # FUNCTION, CLASS, VARIABLE, CONSTANT, etc.
    file_path: str
    start_line: int
    end_line: int
    complexity: int = 1


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str  # CALLS, IMPORTS, DEPENDS_ON, REFERENCES
    confidence: str = "RESOLVED"


class RepositorySnapshotContext:
    """In-memory and filesystem snapshot representation for agent analysis."""

    def __init__(self, snapshot_id: str) -> None:
        self.snapshot_id = snapshot_id
        self.files: Dict[str, SnapshotFile] = {}
        self.symbols: List[SnapshotSymbol] = []
        self.edges: List[GraphEdge] = []

    def add_file(self, path: str, content: str, language: str = "python") -> SnapshotFile:
        norm_path = path.replace("\\", "/").lstrip("/")
        file_obj = SnapshotFile(path=norm_path, content=content, language=language)
        self.files[norm_path] = file_obj
        return file_obj

    def add_symbol(self, symbol: SnapshotSymbol) -> None:
        self.symbols.append(symbol)

    def add_edge(self, source: str, target: str, relationship: str) -> None:
        self.edges.append(GraphEdge(source=source, target=target, relationship=relationship))

    def get_file(self, path: str) -> Optional[SnapshotFile]:
        norm_path = path.replace("\\", "/").lstrip("/")
        return self.files.get(norm_path)


class SnapshotContextRegistry:
    """Global or request-scoped registry of loaded snapshot contexts."""

    _instances: Dict[str, RepositorySnapshotContext] = {}

    @classmethod
    def register(cls, context: RepositorySnapshotContext) -> None:
        cls._instances[context.snapshot_id] = context

    @classmethod
    def get(cls, snapshot_id: str) -> RepositorySnapshotContext:
        if snapshot_id not in cls._instances:
            # Create a default context if not pre-seeded
            ctx = RepositorySnapshotContext(snapshot_id)
            cls._instances[snapshot_id] = ctx
        return cls._instances[snapshot_id]

    @classmethod
    def contains(cls, snapshot_id: str) -> bool:
        """Return whether a snapshot context was explicitly loaded and registered."""
        return snapshot_id in cls._instances

    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()
