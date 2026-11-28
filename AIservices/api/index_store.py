"""
Authoritative Redis-backed index store for CodePilot AIservices.

Keeps RepoIndex per (repo_id, snapshot_id) pair backed strictly by Redis.
No silent in-memory fallback. Docker Redis is the primary and authoritative storage layer.

Keys:
- ai:index:{repo_id}:{snapshot_id}      -> Full serialized RepoIndex JSON
- ai:index:meta:{repo_id}:{snapshot_id} -> Hash with repository metadata
- ai:index:catalog                      -> Set of "repo_id:snapshot_id" members
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import sys
from typing import Any, Optional

from AIservices.core.models import RepoIndex

logger = logging.getLogger(__name__)


class IndexStorageError(RuntimeError):
    """Raised when repository index cannot be stored or retrieved from Redis."""
    pass


# Redis configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_KEY_PREFIX = os.getenv("AI_INDEX_KEY_PREFIX", "ai:index")
CATALOG_KEY = f"{REDIS_KEY_PREFIX}:catalog"

_fake_redis_instance: Optional[Any] = None
_real_redis_client: Optional[Any] = None
_connected_url: Optional[str] = None


def is_test_environment() -> bool:
    """Returns True if explicitly configured for testing with fakeredis."""
    backend = os.getenv("AI_STORAGE_BACKEND", "").lower()
    testing = os.getenv("TESTING", "").lower()
    return backend == "fakeredis" or testing in ("true", "1", "yes")


def _make_data_key(repo_id: str, snapshot_id: str) -> str:
    return f"{REDIS_KEY_PREFIX}:{repo_id}:{snapshot_id}"


def _make_meta_key(repo_id: str, snapshot_id: str) -> str:
    return f"{REDIS_KEY_PREFIX}:meta:{repo_id}:{snapshot_id}"


def get_redis_client() -> Any:
    """
    Returns the authoritative Redis client.
    In test environments (AI_STORAGE_BACKEND=fakeredis or TESTING=true), returns FakeRedis.
    In production environments, connects strictly to real Redis and verifies connectivity.
    Raises IndexStorageError if real Redis is unreachable.
    """
    global _fake_redis_instance, _real_redis_client, _connected_url

    if is_test_environment():
        if _fake_redis_instance is None:
            import fakeredis
            _fake_redis_instance = fakeredis.FakeRedis(decode_responses=True)
            logger.info("Using FakeRedis for unit test environment")
        return _fake_redis_instance

    target_url = os.getenv("REDIS_URL", REDIS_URL)

    if _real_redis_client is not None and _connected_url == target_url:
        try:
            _real_redis_client.ping()
            return _real_redis_client
        except Exception:
            _real_redis_client = None
            _connected_url = None

    try:
        import redis
        client = redis.from_url(
            target_url,
            decode_responses=True,
            socket_timeout=3.0,
            socket_connect_timeout=3.0,
        )
        client.ping()
        _real_redis_client = client
        _connected_url = target_url
        return _real_redis_client
    except Exception as exc:
        _real_redis_client = None
        _connected_url = None
        error_msg = f"Redis is unreachable at {target_url}: {exc}"
        logger.error(error_msg)
        raise IndexStorageError(error_msg) from exc


def is_redis_available() -> bool:
    """Checks whether Redis is reachable without raising an exception."""
    try:
        client = get_redis_client()
        return bool(client.ping())
    except Exception:
        return False


def _serialize_index(index: RepoIndex) -> str:
    """Serialize RepoIndex to JSON text, supporting Pydantic v1 and v2."""
    if hasattr(index, "model_dump_json"):
        return index.model_dump_json()
    return index.json()


def _deserialize_index(raw_data: str) -> RepoIndex:
    """Deserialize RepoIndex from JSON text, supporting Pydantic v1 and v2."""
    if hasattr(RepoIndex, "model_validate_json"):
        return RepoIndex.model_validate_json(raw_data)
    return RepoIndex.parse_raw(raw_data)


def save_index(index: RepoIndex) -> None:
    """
    Persists a repository snapshot index strictly into Redis.
    Never falls back to Python RAM.
    Raises IndexStorageError if Redis is unavailable or the write fails.
    """
    repo_id = str(index.repo_id)
    snapshot_id = str(index.snapshot_id)
    data_key = _make_data_key(repo_id, snapshot_id)
    meta_key = _make_meta_key(repo_id, snapshot_id)
    catalog_member = f"{repo_id}:{snapshot_id}"

    client = get_redis_client()

    try:
        payload = _serialize_index(index)
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_mapping = {
            "repo_id": repo_id,
            "snapshot_id": snapshot_id,
            "symbol_count": str(len(index.symbols)),
            "chunk_count": str(len(index.chunks)),
            "file_count": str(len(index.files)),
            "warnings_count": str(len(index.warnings)),
            "updated_at": now_iso,
        }

        pipe = client.pipeline()
        pipe.set(data_key, payload)
        pipe.hset(meta_key, mapping=meta_mapping)
        pipe.sadd(CATALOG_KEY, catalog_member)
        pipe.execute()
        logger.info(
            "Persisted RepoIndex to Redis for %s:%s (%d symbols, %d chunks, %d files)",
            repo_id,
            snapshot_id,
            len(index.symbols),
            len(index.chunks),
            len(index.files),
        )
    except IndexStorageError:
        raise
    except Exception as exc:
        error_msg = f"Failed to persist index ({repo_id}, {snapshot_id}) to Redis: {exc}"
        logger.error(error_msg)
        raise IndexStorageError(error_msg) from exc


def get_index(repo_id: str, snapshot_id: str) -> RepoIndex | None:
    """
    Retrieves a repository snapshot index directly from Redis.
    Returns None if the key does not exist.
    Raises IndexStorageError if Redis is unreachable or fails.
    """
    r_id = str(repo_id)
    s_id = str(snapshot_id)
    client = get_redis_client()

    try:
        data_key = _make_data_key(r_id, s_id)
        raw_data = client.get(data_key)
        if not raw_data:
            return None
        return _deserialize_index(raw_data)
    except IndexStorageError:
        raise
    except Exception as exc:
        error_msg = f"Failed to retrieve index ({r_id}, {s_id}) from Redis: {exc}"
        logger.error(error_msg)
        raise IndexStorageError(error_msg) from exc


def list_indexes() -> list[dict]:
    """
    Lists all indexed repository snapshots with their metadata from Redis.
    Returns: [{"repo_id": str, "snapshot_id": str, "symbol_count": int, "chunk_count": int, "file_count": int}, ...]
    Raises IndexStorageError if Redis is unreachable.
    """
    client = get_redis_client()

    try:
        members = client.smembers(CATALOG_KEY)
        if not members:
            return []

        pipe = client.pipeline()
        member_list = sorted(list(members))
        for member in member_list:
            pipe.hgetall(f"{REDIS_KEY_PREFIX}:meta:{member}")
        meta_results = pipe.execute()

        results: list[dict] = []
        for member, meta in zip(member_list, meta_results):
            if meta and "repo_id" in meta and "snapshot_id" in meta:
                r_id = meta["repo_id"]
                s_id = meta["snapshot_id"]
                try:
                    s_count = int(meta.get("symbol_count", 0))
                except (ValueError, TypeError):
                    s_count = 0
                try:
                    c_count = int(meta.get("chunk_count", 0))
                except (ValueError, TypeError):
                    c_count = 0
                try:
                    f_count = int(meta.get("file_count", 0))
                except (ValueError, TypeError):
                    f_count = 0

                results.append({
                    "repo_id": r_id,
                    "snapshot_id": s_id,
                    "symbol_count": s_count,
                    "chunk_count": c_count,
                    "file_count": f_count,
                    "updated_at": meta.get("updated_at"),
                })
            else:
                parts = member.split(":", 1)
                if len(parts) == 2:
                    results.append({
                        "repo_id": parts[0],
                        "snapshot_id": parts[1],
                        "symbol_count": 0,
                        "chunk_count": 0,
                        "file_count": 0,
                    })
        return results
    except IndexStorageError:
        raise
    except Exception as exc:
        error_msg = f"Failed to list indexes from Redis: {exc}"
        logger.error(error_msg)
        raise IndexStorageError(error_msg) from exc


def delete_index(repo_id: str, snapshot_id: str) -> bool:
    """
    Deletes a repository snapshot index from Redis.
    Returns True if the index was found and deleted, False otherwise.
    Raises IndexStorageError if Redis is unreachable.
    """
    r_id = str(repo_id)
    s_id = str(snapshot_id)
    client = get_redis_client()

    try:
        data_key = _make_data_key(r_id, s_id)
        meta_key = _make_meta_key(r_id, s_id)
        catalog_member = f"{r_id}:{s_id}"

        pipe = client.pipeline()
        pipe.exists(data_key)
        pipe.sismember(CATALOG_KEY, catalog_member)
        pipe.delete(data_key, meta_key)
        pipe.srem(CATALOG_KEY, catalog_member)
        results = pipe.execute()

        has_data_key = bool(results[0])
        is_in_catalog = bool(results[1])
        return has_data_key or is_in_catalog
    except IndexStorageError:
        raise
    except Exception as exc:
        error_msg = f"Failed to delete index ({r_id}, {s_id}) from Redis: {exc}"
        logger.error(error_msg)
        raise IndexStorageError(error_msg) from exc


def clear_all_indexes() -> int:
    """
    Removes all AI indexes from Redis.
    Useful for test cleanup and isolation.
    """
    client = get_redis_client()

    try:
        members = client.smembers(CATALOG_KEY)
        count = len(members)
        if count > 0:
            pipe = client.pipeline()
            for member in members:
                pipe.delete(f"{REDIS_KEY_PREFIX}:{member}")
                pipe.delete(f"{REDIS_KEY_PREFIX}:meta:{member}")
            pipe.delete(CATALOG_KEY)
            pipe.execute()
        return count
    except IndexStorageError:
        raise
    except Exception as exc:
        error_msg = f"Failed to clear indexes from Redis: {exc}"
        logger.error(error_msg)
        raise IndexStorageError(error_msg) from exc
