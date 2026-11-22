"""
In-memory index store.

Keeps one RepoIndex per (repo_id, snapshot_id) pair for the lifetime of the
process.  Other AIservices features that need repository data call
``get_index`` after the caller has POSTed to /index.

Replace this with a persistent store (Redis, PostgreSQL) when you graduate
from the in-process prototype.
"""

from __future__ import annotations

from AIservices.core.models import RepoIndex

_store: dict[tuple[str, str], RepoIndex] = {}


def save_index(index: RepoIndex) -> None:
    _store[(index.repo_id, index.snapshot_id)] = index


def get_index(repo_id: str, snapshot_id: str) -> RepoIndex | None:
    return _store.get((repo_id, snapshot_id))


def list_indexes() -> list[dict]:
    return [
        {"repo_id": k[0], "snapshot_id": k[1], "symbol_count": len(v.symbols)}
        for k, v in _store.items()
    ]


def delete_index(repo_id: str, snapshot_id: str) -> bool:
    key = (repo_id, snapshot_id)
    if key in _store:
        del _store[key]
        return True
    return False
