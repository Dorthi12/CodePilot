"""
Tests for search filtering by symbol kind, programming language, and path prefix.
"""

import unittest

from AIservices.core.models import SearchFilters, SearchRequest, SupportedLanguage, SymbolKind
from AIservices.core.parser import index_repository
from AIservices.features.code_search import search


class TestSearchFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {
            "services/auth/login.py": """
import os

AUTH_LIMIT = 5

class LoginHandler:
    def execute(self):
        pass

def handle_login(username: str):
    pass
""",
            "services/billing/payment.ts": """
import { Stripe } from 'stripe';

export interface PaymentIntent {
    id: string;
    amount: number;
}

export class PaymentService {
    processPayment(): void {}
}

export function handle_payment(): void {}
""",
            "models/user.py": """
class User:
    pass

def get_user():
    pass
""",
        }
        cls.index = index_repository("filter-repo", "snap-1", cls.files)

    def test_filter_by_kind_function(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="handle",
            filters=SearchFilters(kinds=[SymbolKind.FUNCTION]),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        for r in resp.results:
            self.assertEqual(r.kind, SymbolKind.FUNCTION.value)

    def test_filter_by_kind_class(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="User",
            filters=SearchFilters(kinds=[SymbolKind.CLASS]),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        for r in resp.results:
            self.assertEqual(r.kind, SymbolKind.CLASS.value)

    def test_filter_by_multiple_kinds(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="Payment",
            filters=SearchFilters(kinds=[SymbolKind.CLASS, SymbolKind.INTERFACE]),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        allowed = {SymbolKind.CLASS.value, SymbolKind.INTERFACE.value}
        for r in resp.results:
            self.assertIn(r.kind, allowed)

    def test_filter_by_language_python(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="handle",
            filters=SearchFilters(languages=[SupportedLanguage.PYTHON]),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        for r in resp.results:
            self.assertEqual(r.language, SupportedLanguage.PYTHON.value)

    def test_filter_by_language_typescript(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="Payment",
            filters=SearchFilters(languages=[SupportedLanguage.TYPESCRIPT]),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        for r in resp.results:
            self.assertEqual(r.language, SupportedLanguage.TYPESCRIPT.value)

    def test_filter_by_path_prefix(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="handle",
            filters=SearchFilters(path_prefix="services/auth"),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        for r in resp.results:
            self.assertTrue(r.file_path.startswith("services/auth"))

    def test_filter_combined(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="handle",
            filters=SearchFilters(
                kinds=[SymbolKind.FUNCTION],
                languages=[SupportedLanguage.PYTHON],
                path_prefix="services/auth",
            ),
        )
        resp = search(req, self.index)
        self.assertGreater(resp.total, 0)
        for r in resp.results:
            self.assertEqual(r.kind, SymbolKind.FUNCTION.value)
            self.assertEqual(r.language, SupportedLanguage.PYTHON.value)
            self.assertTrue(r.file_path.startswith("services/auth"))

    def test_filter_matching_none(self):
        req = SearchRequest(
            repo_id="filter-repo",
            snapshot_id="snap-1",
            query="Login",
            filters=SearchFilters(
                path_prefix="non/existent/path",
            ),
        )
        resp = search(req, self.index)
        self.assertEqual(resp.total, 0)
        self.assertEqual(resp.results, [])
        self.assertTrue(any("No symbols match the applied filters" in w for w in resp.warnings))


if __name__ == "__main__":
    unittest.main()
