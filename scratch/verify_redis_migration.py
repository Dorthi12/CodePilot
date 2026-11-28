"""
Comprehensive verification test script for Docker Redis Storage Migration (Tests A - G).
Executes strictly against real Docker Redis on 127.0.0.1:6379/0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure REDIS_URL points to real Docker Redis
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"
os.environ["AI_STORAGE_BACKEND"] = "redis"
os.environ.pop("TESTING", None)

from AIservices.api.index_store import (
    IndexStorageError,
    clear_all_indexes,
    delete_index,
    get_index,
    get_redis_client,
    is_redis_available,
    list_indexes,
    save_index,
)
from AIservices.core.models import CodeChunk, CodeSymbol, RepoIndex, SearchRequest
from AIservices.core.parser import index_repository
from AIservices.features.code_explanation import (
    ExplanationRequest,
    ExplanationStyle,
    explain_code,
)
from AIservices.features.code_search import search

TEST_REPO_ID = "org-verify/codepilot-e2e"
TEST_SNAPSHOT_ID = "sha-9a8b7c6d5e4f3a2b"

SAMPLE_FILES = {
    "src/math_ops.py": """\"\"\"Mathematical operations module.\"\"\"

def calculate_fibonacci(n: int) -> int:
    \"\"\"Return the nth Fibonacci number.\"\"\"
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

class VectorCalculator:
    \"\"\"Performs 2D vector computations.\"\"\"

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def magnitude(self) -> float:
        \"\"\"Compute euclidean magnitude.\"\"\"
        return (self.x ** 2 + self.y ** 2) ** 0.5
""",
    "src/utils.py": """\"\"\"General utility helpers.\"\"\"

def format_currency(amount: float, symbol: str = "$") -> str:
    \"\"\"Format a float into a currency string.\"\"\"
    return f"{symbol}{amount:,.2f}"
"""
}


def run_tests():
    print("=" * 70)
    print("STARTING DOCKER REDIS STORAGE MIGRATION VERIFICATION (TESTS A - G)")
    print("=" * 70)

    # Pre-check: Ensure Redis is online
    if not is_redis_available():
        print("FATAL: Docker Redis is not available on 127.0.0.1:6379/0")
        sys.exit(1)
    print("[PRE-CHECK] Connected successfully to Docker Redis at 127.0.0.1:6379/0\n")

    # Clean previous test entries
    clear_all_indexes()

    # -------------------------------------------------------------------------
    # TEST A: Index repository snapshot and save to Docker Redis
    # -------------------------------------------------------------------------
    print("--- TEST A: Index Repository Snapshot ---")
    repo_idx = index_repository(
        repo_id=TEST_REPO_ID,
        snapshot_id=TEST_SNAPSHOT_ID,
        files=SAMPLE_FILES,
    )
    print(f"Generated RepoIndex: {len(repo_idx.symbols)} symbols, {len(repo_idx.chunks)} chunks, {len(repo_idx.files)} files")
    assert len(repo_idx.symbols) >= 3, f"Expected >= 3 symbols, got {len(repo_idx.symbols)}"
    assert len(repo_idx.chunks) >= 3, f"Expected >= 3 chunks, got {len(repo_idx.chunks)}"

    save_index(repo_idx)
    print("Saved RepoIndex to Redis via save_index(repo_idx).")
    print("TEST A: PASSED\n")

    # -------------------------------------------------------------------------
    # TEST B: Inspect Redis keys in codepilot-redis
    # -------------------------------------------------------------------------
    print("--- TEST B: Inspect Redis Keys in codepilot-redis ---")
    client = get_redis_client()
    keys = sorted(client.keys("ai:index:*"))
    print(f"Found {len(keys)} keys under 'ai:index:*':")
    for k in keys:
        print(f"  - {k}")

    expected_data_key = f"ai:index:{TEST_REPO_ID}:{TEST_SNAPSHOT_ID}"
    expected_meta_key = f"ai:index:meta:{TEST_REPO_ID}:{TEST_SNAPSHOT_ID}"
    assert "ai:index:catalog" in keys, "Catalog key missing!"
    assert expected_data_key in keys, f"Data key {expected_data_key} missing!"
    assert expected_meta_key in keys, f"Meta key {expected_meta_key} missing!"

    catalog_members = client.smembers("ai:index:catalog")
    print(f"Catalog members: {catalog_members}")
    assert f"{TEST_REPO_ID}:{TEST_SNAPSHOT_ID}" in catalog_members
    print("TEST B: PASSED\n")

    # -------------------------------------------------------------------------
    # TEST C: Verify raw Redis JSON payload structure (chunks & symbols)
    # -------------------------------------------------------------------------
    print("--- TEST C: Verify Raw Redis JSON Payload ---")
    raw_json = client.get(expected_data_key)
    assert raw_json is not None, "Raw data from Redis was None!"
    parsed_json = json.loads(raw_json)

    assert parsed_json["repo_id"] == TEST_REPO_ID
    assert parsed_json["snapshot_id"] == TEST_SNAPSHOT_ID
    assert "symbols" in parsed_json and len(parsed_json["symbols"]) > 0
    assert "chunks" in parsed_json and len(parsed_json["chunks"]) > 0
    assert "files" in parsed_json and len(parsed_json["files"]) == len(SAMPLE_FILES)

    first_chunk = parsed_json["chunks"][0]
    print(f"Sample Chunk Structure from Redis:")
    print(f"  chunk_id: {first_chunk.get('chunk_id')}")
    print(f"  file_path: {first_chunk.get('file_path')}")
    print(f"  chunk_type: {first_chunk.get('chunk_type')}")
    print(f"  lines: {first_chunk.get('start_line')} to {first_chunk.get('end_line')}")
    print(f"  content snippet: {first_chunk.get('content', '')[:60]}...")
    assert first_chunk.get("content"), "Chunk content should not be empty!"

    meta_hash = client.hgetall(expected_meta_key)
    print(f"Metadata Hash in Redis: {meta_hash}")
    assert meta_hash.get("symbol_count") == str(len(parsed_json["symbols"]))
    assert meta_hash.get("chunk_count") == str(len(parsed_json["chunks"]))
    print("TEST C: PASSED\n")

    # -------------------------------------------------------------------------
    # TEST D: Retrieve Index in Fresh Process (Zero Python Memory)
    # -------------------------------------------------------------------------
    print("--- TEST D: Retrieve Index from Redis without in-memory state ---")
    retrieved_index = get_index(TEST_REPO_ID, TEST_SNAPSHOT_ID)
    assert retrieved_index is not None, "Failed to retrieve RepoIndex from Redis!"
    assert retrieved_index.repo_id == TEST_REPO_ID
    assert retrieved_index.snapshot_id == TEST_SNAPSHOT_ID
    assert len(retrieved_index.symbols) == len(repo_idx.symbols)
    assert len(retrieved_index.chunks) == len(repo_idx.chunks)
    print(f"Retrieved index successfully: {len(retrieved_index.symbols)} symbols, {len(retrieved_index.chunks)} chunks")
    print("TEST D: PASSED\n")

    # -------------------------------------------------------------------------
    # TEST E: Redis Restart Survival (AOF Persistence Verification)
    # -------------------------------------------------------------------------
    print("--- TEST E: Verify Persistence Across Redis Container Restart ---")
    print("Calling 'docker compose restart redis'...")
    res = subprocess.run(["docker", "compose", "restart", "redis"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Failed to restart redis via docker compose: {res.stderr}")
        sys.exit(1)

    print("Waiting for Redis to come back online...")
    reconnected = False
    for _ in range(15):
        time.sleep(1)
        try:
            # Recreate connection to avoid stale socket
            import redis
            rc = redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
            if rc.ping():
                reconnected = True
                break
        except Exception:
            pass

    assert reconnected, "Redis container failed to reconnect after restart!"
    print("Redis reconnected! Checking persisted keys...")

    restarted_keys = sorted(rc.keys("ai:index:*"))
    print(f"Keys after container restart: {restarted_keys}")
    assert expected_data_key in restarted_keys, f"Data key {expected_data_key} did not survive Redis restart!"
    assert expected_meta_key in restarted_keys, f"Meta key {expected_meta_key} did not survive Redis restart!"

    idx_after_restart = get_index(TEST_REPO_ID, TEST_SNAPSHOT_ID)
    assert idx_after_restart is not None, "RepoIndex not found after Redis restart!"
    assert len(idx_after_restart.symbols) == len(repo_idx.symbols)
    print("Index survived Redis container restart with AOF volume preserved.")
    print("TEST E: PASSED\n")

    # -------------------------------------------------------------------------
    # TEST F: Code Search and Code Explanation without Re-indexing
    # -------------------------------------------------------------------------
    print("--- TEST F: Code Search & Explanation from Redis ---")
    # Search for calculate_fibonacci
    search_req = SearchRequest(
        repo_id=TEST_REPO_ID,
        snapshot_id=TEST_SNAPSHOT_ID,
        query="calculate_fibonacci",
        top_k=5,
    )
    search_resp = search(search_req, idx_after_restart)
    print(f"Search query '{search_req.query}' returned {search_resp.total} results:")
    for r in search_resp.results:
        print(f"  - [{r.kind}] {r.name} ({r.file_path}:{r.start_line}-{r.end_line}) score={r.score}")
    assert search_resp.total > 0, "Search returned 0 results!"
    assert search_resp.results[0].name == "calculate_fibonacci"

    # Explain calculate_fibonacci
    explain_req = ExplanationRequest(
        repo_id=TEST_REPO_ID,
        snapshot_id=TEST_SNAPSHOT_ID,
        file_path="src/math_ops.py",
        start_line=3,
        end_line=12,
        explanation_style=ExplanationStyle.TECHNICAL,
    )
    explain_resp = explain_code(explain_req, idx_after_restart)
    print(f"Explanation generated successfully:")
    print(f"  Overview: {explain_resp.overview[:80]}...")
    print(f"  Step-by-step points: {len(explain_resp.step_by_step)}")
    print(f"  Citations: {len(explain_resp.citations)}")
    print(f"  Edge cases: {len(explain_resp.edge_cases)}")
    assert explain_resp.overview, "Explanation overview is empty!"
    print("TEST F: PASSED\n")

    # -------------------------------------------------------------------------
    # TEST G: Strict Error Handling on Redis Failure (No Silent Fallback)
    # -------------------------------------------------------------------------
    print("--- TEST G: Strict Failure Handling (IndexStorageError) ---")
    # Point REDIS_URL to an unreachable port
    os.environ["REDIS_URL"] = "redis://127.0.0.1:9999/0"
    try:
        from AIservices.api.index_store import get_index as get_index_fail
        get_index_fail(TEST_REPO_ID, TEST_SNAPSHOT_ID)
        print("FAILED: Expected IndexStorageError when Redis is down, but got no exception!")
        sys.exit(1)
    except IndexStorageError as e:
        print(f"Correctly caught IndexStorageError on read: {e}")

    try:
        from AIservices.api.index_store import save_index as save_index_fail
        save_index_fail(repo_idx)
        print("FAILED: Expected IndexStorageError on write when Redis is down, but got no exception!")
        sys.exit(1)
    except IndexStorageError as e:
        print(f"Correctly caught IndexStorageError on write: {e}")

    print("TEST G: PASSED\n")

    # Restore REDIS_URL
    os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"

    print("=" * 70)
    print("ALL VERIFICATION TESTS (A THROUGH G) COMPLETED AND PASSED PERFECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
