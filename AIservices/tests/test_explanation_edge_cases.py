"""
Tests for edge cases, error conditions, and provider failure fallback in Feature 2.
"""

import unittest
from unittest.mock import patch

from AIservices.core.parser import index_repository
from AIservices.features.code_explanation import (
    ExplanationRequest,
    explain_code,
)
from AIservices.features.code_explanation.llm_provider import BaseLLMProvider


class FailingMockProvider(BaseLLMProvider):
    def generate_explanation(self, *args, **kwargs):
        raise RuntimeError("Simulated remote LLM API network connection failure")


class TestExplanationEdgeCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {
            "main.py": "def hello():\n    return 'world'\n",
        }
        cls.index = index_repository("edge-repo", "snap-e1", cls.files)

    def test_empty_code_raises_value_error(self):
        req = ExplanationRequest(
            repo_id="edge-repo",
            snapshot_id="snap-e1",
            code="    \n   \t  ",
        )
        with self.assertRaises(ValueError) as ctx:
            explain_code(req, self.index)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_no_code_or_coordinates_raises_value_error(self):
        req = ExplanationRequest(
            repo_id="edge-repo",
            snapshot_id="snap-e1",
        )
        with self.assertRaises(ValueError) as ctx:
            explain_code(req, self.index)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_repo_id_mismatch_raises_value_error(self):
        req = ExplanationRequest(
            repo_id="wrong-repo",
            snapshot_id="snap-e1",
            code="def test(): pass",
        )
        with self.assertRaises(ValueError) as ctx:
            explain_code(req, self.index)
        self.assertIn("does not match", str(ctx.exception))

    def test_snapshot_id_mismatch_raises_value_error(self):
        req = ExplanationRequest(
            repo_id="edge-repo",
            snapshot_id="wrong-snapshot",
            code="def test(): pass",
        )
        with self.assertRaises(ValueError) as ctx:
            explain_code(req, self.index)
        self.assertIn("does not match", str(ctx.exception))

    def test_nonexistent_file_path_raises_value_error(self):
        req = ExplanationRequest(
            repo_id="edge-repo",
            snapshot_id="snap-e1",
            file_path="does_not_exist.py",
            start_line=1,
            end_line=5,
        )
        with self.assertRaises(ValueError) as ctx:
            explain_code(req, self.index)
        self.assertIn("could not be resolved", str(ctx.exception).lower())

    def test_llm_provider_failure_graceful_fallback(self):
        req = ExplanationRequest(
            repo_id="edge-repo",
            snapshot_id="snap-e1",
            code="def hello():\n    return 'world'\n",
        )

        with patch(
            "AIservices.features.code_explanation.explanation_engine.get_llm_provider",
            return_value=FailingMockProvider(),
        ):
            # Should not raise exception; must gracefully fall back to static analysis
            resp = explain_code(req, self.index)
            self.assertIsNotNone(resp)
            self.assertIn("hello", resp.overview)
            self.assertGreater(len(resp.step_by_step), 0)


if __name__ == "__main__":
    unittest.main()
