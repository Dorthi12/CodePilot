"""
Tests for AIservices REST API endpoints (routes.py).
"""

import unittest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from AIservices.api.index_store import delete_index, get_index
from AIservices.api.routes import (
    get_all_indexes,
    get_index_details,
    health_check,
    index_repo,
    remove_index,
    search_code,
)
from AIservices.api.schemas import IndexRequest, SearchHTTPRequest
from AIservices.core.models import SearchFilters, SymbolKind


class TestAPIRoutes(unittest.TestCase):
    def setUp(self):
        self.repo_id = "test-api-repo"
        self.snapshot_id = "snap-api-v1"
        self.files = {
            "app/auth.py": """
class TokenManager:
    def create_token(self, user: str) -> str:
        return "token_123"

def verify_token(token: str) -> bool:
    return True
""",
            "app/user.ts": """
export interface User {
    id: string;
    name: string;
}

export function fetchUser(id: string): User {
    return { id, name: "Alice" };
}
""",
        }

    def tearDown(self):
        delete_index(self.repo_id, self.snapshot_id)

    def test_health_check(self):
        res = health_check()
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["service"], "AIservices")

    def test_index_repo_success(self):
        req = IndexRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            files=self.files,
        )
        res = index_repo(req)
        self.assertEqual(res.repo_id, self.repo_id)
        self.assertEqual(res.snapshot_id, self.snapshot_id)
        self.assertGreater(res.symbol_count, 0)
        self.assertIn("Successfully indexed", res.message)

        # Verify index exists in store
        idx = get_index(self.repo_id, self.snapshot_id)
        self.assertIsNotNone(idx)
        self.assertEqual(len(idx.symbols), res.symbol_count)

    def test_index_repo_validation_empty_repo_id(self):
        req = IndexRequest(
            repo_id="   ",
            snapshot_id=self.snapshot_id,
            files=self.files,
        )
        with self.assertRaises(HTTPException) as ctx:
            index_repo(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("repo_id cannot be empty", ctx.exception.detail)

    def test_index_repo_validation_empty_snapshot_id(self):
        req = IndexRequest(
            repo_id=self.repo_id,
            snapshot_id="",
            files=self.files,
        )
        with self.assertRaises(HTTPException) as ctx:
            index_repo(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("snapshot_id cannot be empty", ctx.exception.detail)

    def test_search_code_success(self):
        # First index
        index_repo(IndexRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            files=self.files,
        ))

        # Search
        search_req = SearchHTTPRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            query="TokenManager",
        )
        res = search_code(search_req)
        self.assertGreater(res.total, 0)
        self.assertEqual(res.results[0].name, "TokenManager")
        self.assertEqual(res.results[0].kind, SymbolKind.CLASS.value)

    def test_search_code_with_filters(self):
        index_repo(IndexRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            files=self.files,
        ))

        search_req = SearchHTTPRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            query="fetchUser",
            filters=SearchFilters(kinds=[SymbolKind.FUNCTION]),
        )
        res = search_code(search_req)
        self.assertEqual(res.total, 1)
        self.assertEqual(res.results[0].name, "fetchUser")
        self.assertEqual(res.results[0].kind, SymbolKind.FUNCTION.value)

    def test_search_not_indexed_returns_404(self):
        search_req = SearchHTTPRequest(
            repo_id="unindexed-repo",
            snapshot_id="unindexed-snapshot",
            query="TokenManager",
        )
        res = search_code(search_req)
        self.assertIsInstance(res, JSONResponse)
        self.assertEqual(res.status_code, 404)

    def test_search_empty_query_raises_400(self):
        index_repo(IndexRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            files=self.files,
        ))
        search_req = SearchHTTPRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            query="   ",
        )
        with self.assertRaises(HTTPException) as ctx:
            search_code(search_req)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_indexes_crud_endpoints(self):
        index_repo(IndexRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            files=self.files,
        ))

        # List
        all_idx = get_all_indexes()
        self.assertTrue(any(i["repo_id"] == self.repo_id for i in all_idx["indexes"]))

        # Details
        details = get_index_details(self.repo_id, self.snapshot_id)
        self.assertEqual(details["repo_id"], self.repo_id)
        self.assertGreater(details["symbol_count"], 0)

        # Delete
        del_res = remove_index(self.repo_id, self.snapshot_id)
        self.assertTrue(del_res["deleted"])

        # Details after delete returns 404
        details_after = get_index_details(self.repo_id, self.snapshot_id)
        self.assertIsInstance(details_after, JSONResponse)
        self.assertEqual(details_after.status_code, 404)


if __name__ == "__main__":
    unittest.main()
