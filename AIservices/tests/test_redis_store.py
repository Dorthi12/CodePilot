"""
Unit tests for the Redis-backed persistent index store.
Tests persistence, serialization, catalog metadata indexing, and fallback behavior.
"""

import unittest
from AIservices.core.models import (
    CodeSymbol,
    RepoIndex,
    SupportedLanguage,
    SymbolKind,
)
from AIservices.api.index_store import (
    save_index,
    get_index,
    list_indexes,
    delete_index,
    clear_all_indexes,
    is_redis_available,
    get_redis_client,
)
import AIservices.index_store as root_store


class TestRedisIndexStore(unittest.TestCase):
    def setUp(self):
        clear_all_indexes()

    def tearDown(self):
        clear_all_indexes()

    def _create_sample_index(self, repo_id: str = "redis-repo", snapshot_id: str = "main") -> RepoIndex:
        sym = CodeSymbol(
            symbol_id="sym-001",
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            file_path="src/service.py",
            language=SupportedLanguage.PYTHON,
            kind=SymbolKind.CLASS,
            name="AuthService",
            qualified_name="src.service.AuthService",
            start_line=10,
            end_line=50,
            snippet="class AuthService:\n    pass\n",
            exported=True,
        )
        return RepoIndex(
            repo_id=repo_id,
            snapshot_id=snapshot_id,
            symbols=[sym],
            files={"src/service.py": "class AuthService:\n    pass\n"},
            warnings=["Test warning"],
        )

    def test_save_and_retrieve_index(self):
        sample = self._create_sample_index()
        save_index(sample)

        retrieved = get_index(sample.repo_id, sample.snapshot_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.repo_id, sample.repo_id)
        self.assertEqual(retrieved.snapshot_id, sample.snapshot_id)
        self.assertEqual(len(retrieved.symbols), 1)
        self.assertEqual(retrieved.symbols[0].name, "AuthService")
        self.assertEqual(retrieved.symbols[0].kind, SymbolKind.CLASS)
        self.assertIn("src/service.py", retrieved.files)
        self.assertEqual(retrieved.warnings, ["Test warning"])

    def test_list_indexes_metadata(self):
        idx1 = self._create_sample_index("repo-a", "v1.0")
        idx2 = self._create_sample_index("repo-b", "v2.0")
        save_index(idx1)
        save_index(idx2)

        indexes = list_indexes()
        self.assertEqual(len(indexes), 2)

        repo_a_meta = next((i for i in indexes if i["repo_id"] == "repo-a"), None)
        self.assertIsNotNone(repo_a_meta)
        self.assertEqual(repo_a_meta["snapshot_id"], "v1.0")
        self.assertEqual(repo_a_meta["symbol_count"], 1)

        repo_b_meta = next((i for i in indexes if i["repo_id"] == "repo-b"), None)
        self.assertIsNotNone(repo_b_meta)
        self.assertEqual(repo_b_meta["snapshot_id"], "v2.0")
        self.assertEqual(repo_b_meta["symbol_count"], 1)

    def test_delete_index(self):
        sample = self._create_sample_index()
        save_index(sample)

        self.assertIsNotNone(get_index(sample.repo_id, sample.snapshot_id))
        deleted = delete_index(sample.repo_id, sample.snapshot_id)
        self.assertTrue(deleted)

        self.assertIsNone(get_index(sample.repo_id, sample.snapshot_id))
        self.assertEqual(len(list_indexes()), 0)

        # Deleting again returns False
        deleted_again = delete_index(sample.repo_id, sample.snapshot_id)
        self.assertFalse(deleted_again)

    def test_root_index_store_alias(self):
        sample = self._create_sample_index("alias-repo", "v1")
        root_store.save_index(sample)

        retrieved = root_store.get_index("alias-repo", "v1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.repo_id, "alias-repo")

        all_idx = root_store.list_indexes()
        self.assertTrue(any(i["repo_id"] == "alias-repo" for i in all_idx))

        self.assertTrue(root_store.delete_index("alias-repo", "v1"))

    def test_multiple_snapshots_same_repo(self):
        idx1 = self._create_sample_index("multi-snap-repo", "commit-1")
        idx2 = self._create_sample_index("multi-snap-repo", "commit-2")
        idx2.symbols.append(
            CodeSymbol(
                symbol_id="sym-002",
                repo_id="multi-snap-repo",
                snapshot_id="commit-2",
                file_path="src/utils.py",
                language=SupportedLanguage.PYTHON,
                kind=SymbolKind.FUNCTION,
                name="helper",
                qualified_name="src.utils.helper",
                start_line=1,
                end_line=5,
                snippet="def helper(): pass",
            )
        )

        save_index(idx1)
        save_index(idx2)

        res1 = get_index("multi-snap-repo", "commit-1")
        res2 = get_index("multi-snap-repo", "commit-2")
        self.assertEqual(len(res1.symbols), 1)
        self.assertEqual(len(res2.symbols), 2)

        # Deleting one snapshot leaves the other intact
        delete_index("multi-snap-repo", "commit-1")
        self.assertIsNone(get_index("multi-snap-repo", "commit-1"))
        self.assertIsNotNone(get_index("multi-snap-repo", "commit-2"))


if __name__ == "__main__":
    unittest.main()
