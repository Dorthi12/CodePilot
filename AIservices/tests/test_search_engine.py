"""
Tests for search engine ranking, scoring, de-duplication, and result formatting.
"""

import unittest

from AIservices.core.models import SearchFilters, SearchRequest, SymbolKind
from AIservices.core.parser import index_repository
from AIservices.features.code_search import search


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.files = {
            "services/auth_service.py": """
import hashlib

SECRET_TOKEN = "jwt-secret"

class AuthService:
    def authenticate_user(self, username: str, password_hash: str) -> bool:
        return True

    def generate_token(self, user_id: str) -> str:
        return hashlib.sha256(user_id.encode()).hexdigest()

def verify_token(token: str) -> bool:
    return len(token) > 0
""",
            "models/user.ts": """
export interface UserRecord {
    id: string;
    username: string;
}

export function getUserRecord(id: string): UserRecord {
    return { id, username: "admin" };
}
""",
        }
        self.index = index_repository("repo-test", "snap-123", self.files)

    def test_exact_name_match(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="AuthService",
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        top = resp.results[0]
        self.assertEqual(top.name, "AuthService")
        self.assertEqual(top.match_type, "exact")
        self.assertEqual(top.score, 1.0)
        self.assertEqual(top.file_path, "services/auth_service.py")
        self.assertEqual(top.source_id, top.source_id)
        self.assertGreaterEqual(top.start_line, 1)
        self.assertIn("class AuthService", top.snippet)

    def test_prefix_exact_match(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="Auth",
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        top = resp.results[0]
        self.assertEqual(top.match_type, "exact")
        self.assertGreaterEqual(top.score, 0.8)

    def test_symbol_word_boundary_match(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="authenticate_user",
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        names = [r.name for r in resp.results]
        self.assertIn("authenticate_user", names)

    def test_fuzzy_search(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="user token sha256",
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        # Should match generate_token or authenticate_user via snippet/path tokens
        match_types = {r.match_type for r in resp.results}
        self.assertTrue("fuzzy" in match_types or "symbol" in match_types)

    def test_ranking_precedence(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="UserRecord",
        )
        resp = search(req, self.index)
        self.assertGreaterEqual(resp.total, 1)
        # Exact match for UserRecord should be ranked first
        self.assertEqual(resp.results[0].name, "UserRecord")
        self.assertEqual(resp.results[0].match_type, "exact")

    def test_top_k_limit(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="user",
            top_k=2,
        )
        resp = search(req, self.index)
        self.assertLessEqual(len(resp.results), 2)
        self.assertEqual(resp.total, len(resp.results))

    def test_deduplication(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="token",
        )
        resp = search(req, self.index)
        ids = [r.source_id for r in resp.results]
        self.assertEqual(len(ids), len(set(ids)), "Search results must be de-duplicated by source_id")

    def test_repository_id_mismatch_validation(self):
        req = SearchRequest(
            repo_id="wrong-repo",
            snapshot_id="snap-123",
            query="AuthService",
        )
        with self.assertRaises(ValueError) as ctx:
            search(req, self.index)
        self.assertIn("does not match", str(ctx.exception))

    def test_snapshot_id_mismatch_validation(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="wrong-snapshot",
            query="AuthService",
        )
        with self.assertRaises(ValueError) as ctx:
            search(req, self.index)
        self.assertIn("does not match", str(ctx.exception))

    def test_no_results_graceful_handling(self):
        req = SearchRequest(
            repo_id="repo-test",
            snapshot_id="snap-123",
            query="NonExistentSymbolxyz123456789",
        )
        resp = search(req, self.index)
        self.assertEqual(resp.total, 0)
        self.assertEqual(resp.results, [])
        self.assertTrue(any("No symbols matched" in w for w in resp.warnings))


if __name__ == "__main__":
    unittest.main()
