"""
Persistent and in-memory index store for AIservices.

Keeps active RepoIndex models in memory for fast retrieval, and persists them
to disk as JSON so that repository indexes survive service restarts.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from AIservices.core.models import RepoIndex

logger = logging.getLogger(__name__)

# Default storage directory: AIservices/data/indexes
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "indexes"
STORAGE_DIR = Path(os.environ.get("INDEX_STORAGE_DIR", str(_DEFAULT_STORAGE_DIR)))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_store: dict[tuple[str, str], RepoIndex] = {}


def _safe_filename(repo_id: str, snapshot_id: str) -> str:
    """Create a safe, deterministic filename from repo_id and snapshot_id."""
    clean_repo = re.sub(r"[^\w\-.]", "_", repo_id)
    clean_snap = re.sub(r"[^\w\-.]", "_", snapshot_id)
    return f"{clean_repo}__{clean_snap}.json"


def _index_file_path(repo_id: str, snapshot_id: str) -> Path:
    return STORAGE_DIR / _safe_filename(repo_id, snapshot_id)


def save_index(index: RepoIndex) -> None:
    """Store index in memory and persist to disk."""
    key = (index.repo_id, index.snapshot_id)
    _store[key] = index

    try:
        file_path = _index_file_path(index.repo_id, index.snapshot_id)
        # Write to temporary file first then replace for atomicity
        temp_path = file_path.with_suffix(".tmp")
        temp_path.write_text(index.model_dump_json(), encoding="utf-8")
        temp_path.replace(file_path)
        logger.info("Persisted index for (%s, %s) to %s", index.repo_id, index.snapshot_id, file_path)
    except Exception as exc:
        logger.warning("Could not persist index to disk for (%s, %s): %s", index.repo_id, index.snapshot_id, exc)


def get_index(repo_id: str, snapshot_id: str) -> RepoIndex | None:
    """Retrieve index from in-memory cache or restore from disk."""
    key = (repo_id, snapshot_id)
    if key in _store:
        return _store[key]

    # Check disk persistence
    file_path = _index_file_path(repo_id, snapshot_id)
    if file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8")
            index = RepoIndex.model_validate_json(content)
            _store[key] = index
            logger.info("Restored index for (%s, %s) from disk", repo_id, snapshot_id)
            return index
        except Exception as exc:
            logger.error("Failed to restore index from %s: %s", file_path, exc)

    return None


def list_indexes() -> list[dict]:
    """List all available indexes across memory and persisted storage."""
    results: dict[tuple[str, str], int] = {
        k: len(v.symbols) for k, v in _store.items()
    }

    # Also discover any on disk not loaded into memory
    if STORAGE_DIR.exists():
        for f in STORAGE_DIR.glob("*__*.json"):
            try:
                stem = f.stem
                repo_part, snap_part = stem.split("__", 1)
                k = (repo_part, snap_part)
                if k not in results:
                    idx = get_index(repo_part, snap_part)
                    if idx:
                        results[k] = len(idx.symbols)
            except Exception:
                pass

    return [
        {"repo_id": k[0], "snapshot_id": k[1], "symbol_count": count}
        for k, count in results.items()
    ]


def delete_index(repo_id: str, snapshot_id: str) -> bool:
    """Delete index from both memory and disk."""
    key = (repo_id, snapshot_id)
    deleted = False

    if key in _store:
        del _store[key]
        deleted = True

    file_path = _index_file_path(repo_id, snapshot_id)
    if file_path.exists():
        try:
            file_path.unlink()
            deleted = True
            logger.info("Deleted persisted index file %s", file_path)
        except Exception as exc:
            logger.warning("Failed to delete index file %s: %s", file_path, exc)

    return deleted
