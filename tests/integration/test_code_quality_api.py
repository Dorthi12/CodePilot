"""Integration tests for Feature A3 Code Quality & Findings Endpoints (043 - 047)."""

import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.repositories.findings_repository import FindingsRepository


@pytest.fixture(autouse=True)
def setup_quality_context():
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()

    ctx = RepositorySnapshotContext("snap-quality-api")
    ctx.add_file(
        "app/api_endpoints.py",
        """def bad_handler(request, cache_store=[]):
    try:
        eval(request.data)
    except:
        pass
    return True
""",
        language="python",
    )
    SnapshotContextRegistry.register(ctx)


def test_code_quality_api_end_to_end_flow():
    client = TestClient(app)

    # 1. POST /api/v1/analysis/code-quality (043)
    start_payload = {
        "snapshot_id": "snap-quality-api",
        "rule_pack": "default",
        "severity_threshold": "LOW",
        "repository_id": "repo-api-test",
    }
    resp = client.post("/api/v1/analysis/code-quality", json=start_payload)
    assert resp.status_code == 202
    data = resp.json()
    run_id = data["run_id"]
    assert data["status"] in ("COMPLETED", "RUNNING")
    assert data["snapshot_id"] == "snap-quality-api"

    # 2. GET /api/v1/analysis-runs/{run_id} (044)
    run_resp = client.get(f"/api/v1/analysis-runs/{run_id}")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["run_id"] == run_id
    assert run_data["status"] == "COMPLETED"
    assert len(run_data["tool_coverage"]) >= 1
    assert run_data["total_findings"] >= 2
    assert "counts_by_severity" in run_data
    assert "counts_by_origin" in run_data

    # 3. GET /api/v1/findings (045)
    findings_resp = client.get("/api/v1/findings?snapshot_id=snap-quality-api")
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert findings_data["total"] >= 2
    assert len(findings_data["items"]) >= 2
    assert "STATIC_TOOL" in findings_data["counts_by_origin"]

    first_finding = findings_data["items"][0]
    finding_id = first_finding["id"]

    # Test filtering by category
    sec_resp = client.get("/api/v1/findings?snapshot_id=snap-quality-api&category=SECURITY")
    assert sec_resp.status_code == 200
    assert all(item["category"] == "SECURITY" for item in sec_resp.json()["items"])

    # 4. GET /api/v1/findings/{id} (046)
    detail_resp = client.get(f"/api/v1/findings/{finding_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == finding_id
    assert detail["fingerprint"]
    assert detail["file_path"] == "app/api_endpoints.py"
    assert len(detail["evidence"]) >= 1

    # 5. PATCH /api/v1/findings/{id} (047)
    # Marking FALSE_POSITIVE requires reason
    patch_no_reason = client.patch(
        f"/api/v1/findings/{finding_id}",
        json={"status": "FALSE_POSITIVE"},
    )
    assert patch_no_reason.status_code == 422

    # Successful PATCH with reason
    patch_resp = client.patch(
        f"/api/v1/findings/{finding_id}",
        json={
            "status": "FALSE_POSITIVE",
            "reason": "Input is validated and sanitized upstream in reverse proxy.",
        },
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["status"] == "FALSE_POSITIVE"
    assert patched["status_reason"] == "Input is validated and sanitized upstream in reverse proxy."
    assert patched["version"] == 2


def test_suppressions_api():
    client = TestClient(app)

    # 1. Create suppression
    supp_payload = {
        "repository_id": "repo-api-test",
        "rule_id": "SEC-CODEI-001",
        "path_glob": "legacy/*",
        "reason": "Sandboxed internal utility script",
    }
    create_resp = client.post("/api/v1/suppressions", json=supp_payload)
    assert create_resp.status_code == 201
    supp_data = create_resp.json()
    assert supp_data["repository_id"] == "repo-api-test"
    assert supp_data["rule_id"] == "SEC-CODEI-001"

    # 2. List suppressions
    list_resp = client.get("/api/v1/suppressions?repository_id=repo-api-test")
    assert list_resp.status_code == 200
    supp_list = list_resp.json()
    assert len(supp_list) == 1
    assert supp_list[0]["id"] == supp_data["id"]


def test_not_found_errors():
    client = TestClient(app)

    res1 = client.get("/api/v1/analysis-runs/non-existent-run")
    assert res1.status_code == 404

    res2 = client.get("/api/v1/findings/non-existent-finding")
    assert res2.status_code == 404

    res3 = client.patch(
        "/api/v1/findings/non-existent-finding",
        json={"status": "ACKNOWLEDGED", "reason": "Acknowledged"},
    )
    assert res3.status_code == 404
