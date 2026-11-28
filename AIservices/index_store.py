"""
Root re-export of the AIservices index store.
Provides direct access to save_index, get_index, list_indexes, delete_index,
IndexStorageError, and Redis status helpers.
"""

from AIservices.api.index_store import (
    IndexStorageError,
    save_index,
    get_index,
    list_indexes,
    delete_index,
    get_redis_client,
    is_redis_available,
    clear_all_indexes,
    REDIS_URL,
    REDIS_KEY_PREFIX,
    CATALOG_KEY,
)

__all__ = [
    "IndexStorageError",
    "save_index",
    "get_index",
    "list_indexes",
    "delete_index",
    "get_redis_client",
    "is_redis_available",
    "clear_all_indexes",
    "REDIS_URL",
    "REDIS_KEY_PREFIX",
    "CATALOG_KEY",
]
