"""Integration tests for the Agent API endpoints."""

import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry


@pytest.fixture(autouse=True)
def setup_api_context():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-api-test")
    ctx.add_file("app/main.py", "api_key = 'sk_test_1234567890_abcdef'\n", language="python")
    SnapshotContextRegistry.register(ctx)


def test_api_create_and_get_run():
    client = TestClient(app)

    # 1. Create run
    payload = {
        "snapshot_id": "snap-api-test",
        "agents": ["SECURITY", "CODE_QUALITY"],
        "require_plan_approval": False,
    }
    response = client.post("/api/v1/agents/analysis-runs", json=payload)
    assert response.status_code == 201
    data = response.json()
    run_id = data["run_id"]
    assert data["status"] == "COMPLETED"
    assert data["total_findings"] >= 1

    # 2. Get run
    get_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == run_id

    # 3. Get report
    report_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}/report")
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["total_findings"] >= 1
    assert "verification_summary" in report_data


def test_api_approval_flow():
    client = TestClient(app)

    payload = {
        "snapshot_id": "snap-api-test",
        "agents": ["SECURITY"],
        "require_plan_approval": True,
    }
    res = client.post("/api/v1/agents/analysis-runs", json=payload)
    assert res.status_code == 201
    run_id = res.json()["run_id"]
    assert res.json()["status"] == "WAITING_APPROVAL"

    # Report before approval should be 409 Conflict
    report_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}/report")
    assert report_res.status_code == 409

    # Approve
    approve_res = client.post(
        f"/api/v1/agents/analysis-runs/{run_id}/approve",
        json={"scope": "PLAN", "comment": "Approved by developer"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "COMPLETED"


def test_api_cancel_run():
    client = TestClient(app)

    payload = {
        "snapshot_id": "snap-api-test",
        "require_plan_approval": True,
    }
    res = client.post("/api/v1/agents/analysis-runs", json=payload)
    run_id = res.json()["run_id"]

    cancel_res = client.post(f"/api/v1/agents/analysis-runs/{run_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


def test_api_not_found():
    client = TestClient(app)
    res = client.get("/api/v1/agents/analysis-runs/non-existent-id")
    assert res.status_code == 404


def test_api_sse_events():
    client = TestClient(app)

    payload = {
        "snapshot_id": "snap-api-test",
        "agents": ["SECURITY"],
        "require_plan_approval": False,
    }
    res = client.post("/api/v1/agents/analysis-runs", json=payload)
    assert res.status_code == 201
    run_id = res.json()["run_id"]

    # Stream events via SSE
    events_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}/events")
    assert events_res.status_code == 200
    assert "text/event-stream" in events_res.headers.get("content-type", "")
    assert "data: " in events_res.text
