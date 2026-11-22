"""Integration tests for Mastermind Feature 2 (AI Bug Investigation) REST API endpoints.

Specifications:
- Master Architecture Specification v2.1 §10 (M2)
- API and Data Specification v1.0 §3.3 (Endpoints 070, 071, 072), §3.4.13
"""

import pytest
from fastapi.testclient import TestClient

from agentic.common.agent_context import (
    RepositorySnapshotContext,
    SnapshotContextRegistry,
)
from backend.app.main import app
from backend.app.repositories.investigation_repository import InvestigationRepository


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_snapshot_and_repo() -> None:
    InvestigationRepository.get_instance().clear()
    SnapshotContextRegistry.clear()

    snapshot_id = "snap-api-test"
    ctx = RepositorySnapshotContext(snapshot_id)

    ctx.add_file(
        "app/api/routes.py",
        """from fastapi import APIRouter
from app.auth.service import refresh_access_token

router = APIRouter()

@router.post("/refresh")
def refresh(token: str):
    return refresh_access_token(token)
""",
    )

    ctx.add_file(
        "app/auth/service.py",
        """class AuthError(Exception):
    pass

def validate_token(token: str):
    raise AuthError("token expired")

def refresh_access_token(token: str):
    return validate_token(token)
""",
    )

    SnapshotContextRegistry.register(ctx)


def test_post_debug_investigations_success(client: TestClient) -> None:
    payload = {
        "snapshot_id": "snap-api-test",
        "issue_description": "Token refresh fails unexpectedly for expired tokens",
        "stack_trace": """Traceback (most recent call last):
  File "app/api/routes.py", line 8, in refresh
    return refresh_access_token(token)
  File "app/auth/service.py", line 10, in refresh_access_token
    return validate_token(token)
  File "app/auth/service.py", line 5, in validate_token
    raise AuthError("token expired")
AuthError: token expired with secret_key=sk-1234567890abcdef1234567890""",
        "failing_test": "tests/test_auth.py::test_refresh",
        "entrypoint": "POST /refresh",
        "environment": {
            "python": "3.12",
            "API_KEY": "sk-secret1234567890abcdef",
        },
    }

    response = client.post("/api/v1/debug/investigations", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "investigation_id" in data
    assert data["snapshot_id"] == "snap-api-test"
    assert data["reproduction_status"] == "NOT_REPRODUCED"

    # Verify secret redaction in response (AUD-11)
    assert "sk-1234567890abcdef" not in data["stack_trace_redacted"]
    assert "[REDACTED]" in data["stack_trace_redacted"]

    # Verify ranked root cause hypotheses
    assert len(data["root_causes"]) >= 2
    for rc in data["root_causes"]:
        assert rc["status"] == "UNCONFIRMED"
        assert 0.0 <= rc["confidence"] <= 1.0

    # Top hypothesis should be caller or failure site
    top_rc = data["root_causes"][0]
    assert top_rc["rank"] == 1
    assert "app/auth/service.py" in top_rc["file_path"]

    # Verify call path
    assert len(data["call_path"]) == 3
    assert data["call_path"][0]["file_path"] == "app/api/routes.py"
    assert data["call_path"][0]["is_entrypoint"] is True

    # Verify evidence
    assert len(data["evidence"]) > 0
    assert data["evidence"][0]["snippet_hash"] is not None

    # Verify diagnostics created
    assert len(data["diagnostics"]) >= 1
    assert data["diagnostics"][0]["kind"] == "SANDBOX_TEST"
    assert data["diagnostics"][0]["status"] == "PENDING_APPROVAL"


def test_get_debug_investigations_success_and_404(client: TestClient) -> None:
    # 404 for unknown
    res_404 = client.get("/api/v1/debug/investigations/unknown-id")
    assert res_404.status_code == 404

    # Create one first
    create_payload = {
        "snapshot_id": "snap-api-test",
        "issue_description": "Service unreachable",
    }
    create_res = client.post("/api/v1/debug/investigations", json=create_payload)
    assert create_res.status_code == 201
    inv_id = create_res.json()["investigation_id"]

    # Retrieve
    get_res = client.get(f"/api/v1/debug/investigations/{inv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["investigation_id"] == inv_id


def test_post_debug_investigations_diagnostics_execute_gate(client: TestClient) -> None:
    # Create investigation
    create_payload = {
        "snapshot_id": "snap-api-test",
        "issue_description": "Auth error in token refresh",
        "failing_test": "tests/test_auth.py::test_refresh",
    }
    create_res = client.post("/api/v1/debug/investigations", json=create_payload)
    inv_id = create_res.json()["investigation_id"]
    diag_id = create_res.json()["diagnostics"][0]["id"]

    # 1. Deny execution without consent (Gate: EXECUTE opt-in)
    denied_res = client.post(
        f"/api/v1/debug/investigations/{inv_id}/diagnostics",
        json={
            "diagnostic_id": diag_id,
            "consent": {"execute": False},
        },
    )
    assert denied_res.status_code == 403
    assert "EXECUTE opt-in approval is required" in denied_res.json()["detail"]

    # 2. Allow execution with explicit consent
    allow_res = client.post(
        f"/api/v1/debug/investigations/{inv_id}/diagnostics",
        json={
            "diagnostic_id": diag_id,
            "consent": {"execute": True, "approver_id": "admin_qa"},
            "simulate_outcome": "REPRODUCED",
        },
    )
    assert allow_res.status_code == 200
    diag_data = allow_res.json()
    assert diag_data["status"] == "COMPLETED"
    assert diag_data["reproduction_status"] == "REPRODUCED"

    # 3. Verify get reflects updated reproduction status
    inv_res = client.get(f"/api/v1/debug/investigations/{inv_id}")
    assert inv_res.json()["reproduction_status"] == "REPRODUCED"
    assert inv_res.json()["root_causes"][0]["status"] == "REPRODUCED"


def test_unified_analysis_run_sync(client: TestClient) -> None:
    create_payload = {
        "snapshot_id": "snap-api-test",
        "issue_description": "Integration test check for unified run",
    }
    create_res = client.post("/api/v1/debug/investigations", json=create_payload)
    run_id = create_res.json()["run_id"]

    # Check analysis-runs endpoint reflects the investigation
    run_res = client.get(f"/api/v1/analysis-runs/{run_id}")
    assert run_res.status_code == 200
    assert run_res.json()["run_type"] == "INVESTIGATION"
