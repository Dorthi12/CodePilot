"""
Tests for edge cases: empty repos, non-matching queries, malformed inputs, index store CRUD.
"""

import unittest

from AIservices.api.index_store import (
    delete_index,
    get_index,
    list_indexes,
    save_index,
)
from AIservices.core.models import RepoIndex, SearchRequest
from AIservices.core.parser import extract_symbols, index_repository
from AIservices.features.code_search import search


class TestEdgeCases(unittest.TestCase):
    def test_empty_repository(self):
        index = index_repository("empty-repo", "snap-0", {})
        self.assertEqual(len(index.symbols), 0)

        req = SearchRequest(repo_id="empty-repo", snapshot_id="snap-0", query="test")
        resp = search(req, index)
        self.assertEqual(resp.total, 0)
        self.assertEqual(resp.results, [])
        self.assertTrue(any("Repository index is empty" in w for w in resp.warnings))

    def test_repo_with_only_unsupported_files(self):
        files = {
            "README.md": "# Title",
            "data.csv": "col1,col2\n1,2",
            "logo.svg": "<svg></svg>",
        }
        index = index_repository("doc-repo", "snap-1", files)
        self.assertEqual(len(index.symbols), 0)
        self.assertGreaterEqual(len(index.warnings), 3)

    def test_comments_only_file(self):
        code = """
# This is a comment
# Another comment
\"\"\"
Docstring only
\"\"\"
"""
        syms, warns = extract_symbols(code, "empty_logic.py", "repo1", "snap1")
        # Should not crash; can return 0 symbols
        self.assertIsInstance(syms, list)
        self.assertIsInstance(warns, list)

    def test_index_store_crud(self):
        index = RepoIndex(
            repo_id="crud-repo",
            snapshot_id="v1",
            symbols=[],
            warnings=[],
        )
        save_index(index)

        # Retrieve
        retrieved = get_index("crud-repo", "v1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.repo_id, "crud-repo")

        # List
        all_idx = list_indexes()
        self.assertTrue(any(i["repo_id"] == "crud-repo" and i["snapshot_id"] == "v1" for i in all_idx))

        # Delete
        deleted = delete_index("crud-repo", "v1")
        self.assertTrue(deleted)
        self.assertIsNone(get_index("crud-repo", "v1"))

        # Delete non-existent
        deleted_again = delete_index("crud-repo", "v1")
        self.assertFalse(deleted_again)

    def test_multiple_snapshots_independent(self):
        f1 = {"main.py": "def version1(): pass"}
        f2 = {"main.py": "def version2(): pass"}

        idx1 = index_repository("repo-x", "snap-1", f1)
        idx2 = index_repository("repo-x", "snap-2", f2)

        save_index(idx1)
        save_index(idx2)

        s1 = search(SearchRequest(repo_id="repo-x", snapshot_id="snap-1", query="version1"), idx1)
        self.assertEqual(s1.total, 1)
        self.assertEqual(s1.results[0].name, "version1")

        s2 = search(SearchRequest(repo_id="repo-x", snapshot_id="snap-2", query="version2"), idx2)
        self.assertEqual(s2.total, 1)
        self.assertEqual(s2.results[0].name, "version2")


if __name__ == "__main__":
    unittest.main()
