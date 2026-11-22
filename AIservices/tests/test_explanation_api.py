"""
Tests for Feature 2 REST API endpoints (/explain and /ai/explain).
"""

import unittest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from AIservices.api.index_store import delete_index
from AIservices.api.routes import explain_code_endpoint, index_repo
from AIservices.api.schemas import ExplainHTTPRequest, IndexRequest


class TestExplanationAPI(unittest.TestCase):
    def setUp(self):
        self.repo_id = "test-api-explain-repo"
        self.snapshot_id = "snap-api-v2"
        self.files = {
            "services/payment.py": """
def charge_customer(customer_id: str, amount: float) -> bool:
    if amount <= 0:
        raise ValueError("Invalid charge amount")
    return True
""",
        }
        index_repo(IndexRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            files=self.files,
        ))

    def tearDown(self):
        delete_index(self.repo_id, self.snapshot_id)

    def test_explain_endpoint_success(self):
        req = ExplainHTTPRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            code="""def charge_customer(customer_id: str, amount: float) -> bool:
    if amount <= 0:
        raise ValueError("Invalid charge amount")
    return True""",
            question="What does this function do?",
            explanation_style="technical",
        )
        resp = explain_code_endpoint(req)
        self.assertEqual(resp.repo_id, self.repo_id)
        self.assertIn("charge_customer", resp.overview)
        self.assertGreater(len(resp.step_by_step), 0)
        self.assertIsNotNone(resp.inputs)
        self.assertIsNotNone(resp.outputs)
        self.assertGreater(len(resp.raw_explanation), 0)

    def test_explain_unindexed_repo_returns_404(self):
        req = ExplainHTTPRequest(
            repo_id="unindexed-repo",
            snapshot_id="unindexed-snapshot",
            code="def foo(): pass",
        )
        resp = explain_code_endpoint(req)
        self.assertIsInstance(resp, JSONResponse)
        self.assertEqual(resp.status_code, 404)

    def test_explain_empty_repo_id_raises_400(self):
        req = ExplainHTTPRequest(
            repo_id="   ",
            snapshot_id=self.snapshot_id,
            code="def foo(): pass",
        )
        with self.assertRaises(HTTPException) as ctx:
            explain_code_endpoint(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("repo_id cannot be empty", ctx.exception.detail)

    def test_explain_empty_snapshot_id_raises_400(self):
        req = ExplainHTTPRequest(
            repo_id=self.repo_id,
            snapshot_id="",
            code="def foo(): pass",
        )
        with self.assertRaises(HTTPException) as ctx:
            explain_code_endpoint(req)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("snapshot_id cannot be empty", ctx.exception.detail)

    def test_explain_missing_code_and_coordinates_raises_400(self):
        req = ExplainHTTPRequest(
            repo_id=self.repo_id,
            snapshot_id=self.snapshot_id,
            code="  ",
        )
        with self.assertRaises(HTTPException) as ctx:
            explain_code_endpoint(req)
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
