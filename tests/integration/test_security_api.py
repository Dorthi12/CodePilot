"""Integration tests for Mastermind Feature 6 (M6) Security Vulnerability Detection Endpoints (089 & 090).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3
- API and Data Specification v1.0 §3.3 (089, 090), §3.4.14, §3.8.2 (Idempotency)
- Security and Testing Specification v1.0 §7.3.3, §7.4, §8.8 (IT-16), E2E-11
"""

import uuid
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.security_repository import SecurityRepository

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_security_api_context():
    SecurityRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()

    ctx = RepositorySnapshotContext("snap-sec-api-01")
    # File 1: Hardcoded API key
    ctx.add_file(
        "app/secrets.py",
        'OPENAI_API_KEY = "sk-123456789012345678901234567890abcdef"\n',
        language="python",
    )
    # File 2: Command injection
    ctx.add_file(
        "app/terminal.py",
        """import os

def run_command(request):
    cmd = request.args.get("cmd")
    os.system(cmd)
""",
        language="python",
    )
    # File 3: Insecure dependency
    ctx.add_file(
        "requirements.txt",
        "django==4.1.2\n",
        language="text",
    )
    SnapshotContextRegistry.register(ctx)


def test_endpoint_089_security_scan_requires_idempotency_key():
    """Endpoint 089 requires Idempotency-Key header (§3.8.2); returns 422 if omitted."""
    payload = {"snapshot_id": "snap-sec-api-01"}
    resp = client.post("/api/v1/security/scans", json=payload)
    assert resp.status_code == 422
    assert "Idempotency-Key" in resp.json()["detail"]


def test_endpoint_089_snapshot_not_found():
    """Non-existent snapshot returns 404."""
    payload = {"snapshot_id": "snap-does-not-exist"}
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    resp = client.post("/api/v1/security/scans", json=payload, headers=headers)
    assert resp.status_code == 404


def test_endpoint_089_changed_files_validation():
    """changed_files_only=True without changed_files returns 422."""
    payload = {
        "snapshot_id": "snap-sec-api-01",
        "changed_files_only": True,
    }
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    resp = client.post("/api/v1/security/scans", json=payload, headers=headers)
    assert resp.status_code == 422


def test_security_scans_end_to_end_flow_and_idempotency():
    """End-to-end integration flow: 089 start, 090 get, unified /findings, and idempotency replay/conflict."""
    idempotency_key = str(uuid.uuid4())
    headers = {"Idempotency-Key": idempotency_key}

    start_payload = {
        "snapshot_id": "snap-sec-api-01",
        "scan_profile": "standard",
        "languages": ["python"],
        "include_dependencies": True,
        "repository_id": "repo-sec-integ",
    }

    # 1. POST /api/v1/security/scans (089)
    resp = client.post("/api/v1/security/scans", json=start_payload, headers=headers)
    assert resp.status_code == 202
    data = resp.json()

    scan_id = data["scan_id"]
    run_id = data["run_id"]
    assert data["status"] == "COMPLETED"
    assert data["total_findings"] >= 3
    assert data["secret_findings_count"] >= 1
    assert data["sast_findings_count"] >= 1
    assert data["dependency_findings_count"] >= 1
    assert len(data["not_checked"]) >= 1

    # 2. Idempotency Replay (same key + same body -> cached response with Idempotent-Replayed: true)
    replay_resp = client.post("/api/v1/security/scans", json=start_payload, headers=headers)
    assert replay_resp.status_code == 202
    assert replay_resp.headers.get("Idempotent-Replayed") == "true"
    assert replay_resp.json()["scan_id"] == scan_id

    # 3. Idempotency Conflict (same key + different body -> 409 conflict)
    conflict_payload = {
        "snapshot_id": "snap-sec-api-01",
        "scan_profile": "deep",
    }
    conflict_resp = client.post("/api/v1/security/scans", json=conflict_payload, headers=headers)
    assert conflict_resp.status_code == 409
    assert "IDEMPOTENCY_CONFLICT" in conflict_resp.json()["detail"]

    # 4. GET /api/v1/security/scans/{id} (090)
    get_resp = client.get(f"/api/v1/security/scans/{scan_id}")
    assert get_resp.status_code == 200
    scan_report = get_resp.json()
    assert scan_report["scan_id"] == scan_id
    assert scan_report["status"] == "COMPLETED"
    assert len(scan_report["tool_coverage"]) >= 3
    assert len(scan_report["not_checked"]) >= 1

    # 5. GET /api/v1/findings?category=SECURITY (Unified findings resource)
    findings_resp = client.get("/api/v1/findings?category=SECURITY&snapshot_id=snap-sec-api-01")
    assert findings_resp.status_code == 200
    sec_findings = findings_resp.json()["items"]
    assert len(sec_findings) >= 3

    # Check secret finding does NOT leak plaintext
    secret_finding = next(f for f in sec_findings if "SECRET" in f["rule_id"])
    assert "sk-1234567890" not in secret_finding["evidence"][0]["snippet"]
    assert "[REDACTED]" in secret_finding["evidence"][0]["snippet"]

    # 6. GET /api/v1/findings/{id}
    finding_id = secret_finding["id"]
    detail_resp = client.get(f"/api/v1/findings/{finding_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == finding_id
    assert detail["remediation"] is not None

    # 7. PATCH /api/v1/findings/{id}
    patch_resp = client.patch(
        f"/api/v1/findings/{finding_id}",
        json={
            "status": "FALSE_POSITIVE",
            "reason": "Test dummy fixture key used in integration test suite.",
        },
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "FALSE_POSITIVE"

    # 8. Unified /analysis-runs/{run_id} returns the SECURITY run
    run_resp = client.get(f"/api/v1/analysis-runs/{run_id}")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["run_type"] == "SECURITY"
    assert run_data["status"] == "COMPLETED"
