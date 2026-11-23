"""End-to-End Integration Tests for all Mastermind REST/SSE Endpoints (M1 to M7).

Verifies that all 33 Mastermind endpoints (#064 through #096) + operational endpoints
are fully implemented, registered with FastAPI, and functional end-to-end.
"""

import hashlib
import hmac
import json
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.modules.patching.patch_manager import PatchManager
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.improvement_repository import ImprovementRepository
from backend.app.repositories.investigation_repository import InvestigationRepository
from backend.app.repositories.pull_request_repository import PullRequestRepository
from backend.app.repositories.security_repository import SecurityRepository
from backend.app.repositories.test_repository import TestRepository


@pytest.fixture(autouse=True)
def setup_snapshot_and_registries():
    """Setup shared snapshot context and clear state."""
    SnapshotContextRegistry.clear()
    PatchManager.instance().clear()
    FindingsRepository.get_instance().clear()
    ImprovementRepository.get_instance().clear()
    InvestigationRepository.get_instance().clear()
    PullRequestRepository.get_instance().clear()
    SecurityRepository.get_instance().clear()
    TestRepository.get_instance().clear()

    ctx = RepositorySnapshotContext("snap-mm-all")
    ctx.add_file(
        "app/calculator.py",
        "def calculate_total(prices, tax_rate=0.05):\n"
        "    total = 0\n"
        "    for p in prices:\n"
        "        total += p\n"
        "    return total * (1 + tax_rate)\n",
        language="python",
    )
    ctx.add_file(
        "app/auth.py",
        "import os\n"
        "JWT_SECRET = 'super_secret_jwt_key_12345'\n"
        "def authenticate(token):\n"
        "    return token == JWT_SECRET\n",
        language="python",
    )
    SnapshotContextRegistry.register(ctx)

    yield

    SnapshotContextRegistry.clear()
    PatchManager.instance().clear()
    FindingsRepository.get_instance().clear()
    ImprovementRepository.get_instance().clear()
    InvestigationRepository.get_instance().clear()
    PullRequestRepository.get_instance().clear()
    SecurityRepository.get_instance().clear()
    TestRepository.get_instance().clear()


@pytest.fixture
def client():
    return TestClient(app)


# ----------------------------------------------------------------------
# Operational Endpoints
# ----------------------------------------------------------------------

def test_operational_endpoints(client):
    """Test health, healthz, readyz, metrics, openapi.json."""
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"

    res = client.get("/metrics")
    assert res.status_code == 200
    assert "codepilot_up" in res.text

    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    openapi = res.json()
    assert "paths" in openapi
    assert "/api/v1/agents/analysis-runs" in openapi["paths"]
    assert "/api/v1/fixes" in openapi["paths"]
    assert "/api/v1/tests/generate" in openapi["paths"]
    assert "/api/v1/security/scans" in openapi["paths"]
    assert "/api/v1/debug/investigations" in openapi["paths"]


# ----------------------------------------------------------------------
# M1: Multi-Agent Code Analysis (064 - 069)
# ----------------------------------------------------------------------

def test_m1_endpoints_064_to_069(client):
    # 064: POST /api/v1/agents/analysis-runs
    create_res = client.post(
        "/api/v1/agents/analysis-runs",
        json={
            "snapshot_id": "snap-mm-all",
            "agents": ["SECURITY", "CODE_QUALITY"],
            "require_plan_approval": True,
        },
    )
    assert create_res.status_code == 201
    run_data = create_res.json()
    run_id = run_data["run_id"]
    assert run_data["status"] == "WAITING_APPROVAL"

    # 065: GET /api/v1/agents/analysis-runs/{id}
    get_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == run_id

    # 068: GET /api/v1/agents/analysis-runs/{id}/events (SSE)
    events_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}/events")
    assert events_res.status_code == 200
    assert "text/event-stream" in events_res.headers["content-type"]

    # 066: POST /api/v1/agents/analysis-runs/{id}/approve
    approve_res = client.post(
        f"/api/v1/agents/analysis-runs/{run_id}/approve",
        json={"scope": "PLAN", "comment": "Approved by reviewer"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "COMPLETED"

    # 069: GET /api/v1/agents/analysis-runs/{id}/report
    report_res = client.get(f"/api/v1/agents/analysis-runs/{run_id}/report")
    assert report_res.status_code == 200
    assert "verification_summary" in report_res.json()

    # 067: POST /api/v1/agents/analysis-runs/{id}/cancel
    # Create another run to test cancel
    create_res2 = client.post(
        "/api/v1/agents/analysis-runs",
        json={"snapshot_id": "snap-mm-all", "require_plan_approval": True},
    )
    run_id2 = create_res2.json()["run_id"]
    cancel_res = client.post(f"/api/v1/agents/analysis-runs/{run_id2}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


# ----------------------------------------------------------------------
# M2: AI Bug Investigation (070 - 072)
# ----------------------------------------------------------------------

def test_m2_endpoints_070_to_072(client):
    # 070: POST /api/v1/debug/investigations
    inv_res = client.post(
        "/api/v1/debug/investigations",
        json={
            "snapshot_id": "snap-mm-all",
            "issue_description": "calculate_total raises TypeError with null prices",
            "stack_trace": (
                'Traceback (most recent call last):\n'
                '  File "app/calculator.py", line 4, in calculate_total\n'
                '    for p in prices:\n'
                'TypeError: \'NoneType\' object is not iterable\n'
            ),
        },
    )
    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    inv_id = inv_data["investigation_id"]
    assert len(inv_data["call_path"]) > 0

    # 071: GET /api/v1/debug/investigations/{id}
    get_res = client.get(f"/api/v1/debug/investigations/{inv_id}")
    assert get_res.status_code == 200
    assert get_res.json()["investigation_id"] == inv_id

    # 072: POST /api/v1/debug/investigations/{id}/diagnostics
    diag_res = client.post(
        f"/api/v1/debug/investigations/{inv_id}/diagnostics",
        json={
            "kind": "REPRODUCE_TEST",
            "command": "pytest app/test_calc.py",
            "consent_execute": True,
            "approver_id": "lead_eng",
        },
    )
    assert diag_res.status_code == 200
    assert diag_res.json()["status"] in ("EXECUTED", "COMPLETED")


# ----------------------------------------------------------------------
# M3: Code Improvement Suggestions (073 - 075)
# ----------------------------------------------------------------------

def test_m3_endpoints_073_to_075(client):
    # 073: POST /api/v1/improvements/analyze (Requires Idempotency-Key)
    analyze_res = client.post(
        "/api/v1/improvements/analyze",
        headers={"Idempotency-Key": "test-idem-m3-001"},
        json={
            "snapshot_id": "snap-mm-all",
            "categories": ["MAINTAINABILITY", "PERFORMANCE"],
        },
    )
    assert analyze_res.status_code == 201
    report_data = analyze_res.json()
    run_id = report_data["run_id"]
    assert report_data["status"] == "COMPLETED"

    # 074: GET /api/v1/improvements/{run_id}
    get_res = client.get(f"/api/v1/improvements/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == run_id

    # 075: PATCH /api/v1/improvements/suggestions/{id}
    if report_data["suggestions"]:
        sug_id = report_data["suggestions"][0]["id"]
        patch_res = client.patch(
            f"/api/v1/improvements/suggestions/{sug_id}",
            json={
                "status": "ACCEPTED",
                "feedback": "LGTM, apply in next release",
                "expected_version": 1,
            },
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["status"] == "ACCEPTED"


# ----------------------------------------------------------------------
# M4: AI-Assisted Code Fixes (076 - 084)
# ----------------------------------------------------------------------

def test_m4_endpoints_076_to_084(client):
    # 076: POST /api/v1/fixes
    diff_text = (
        "--- a/app/calculator.py\n"
        "+++ b/app/calculator.py\n"
        "@@ -1,4 +1,5 @@\n"
        " def calculate_total(prices, tax_rate=0.05):\n"
        "+    prices = prices or []\n"
        "     total = 0\n"
        "     for p in prices:\n"
    )
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-mm-all",
            "task": "Fix NoneType error in calculate_total",
            "target_files": ["app/calculator.py"],
            "unified_diff": diff_text,
            "validation_policy": {"syntax": True, "lint": False, "tests": False, "security": True},
        },
    )
    assert create_res.status_code == 202
    patch_data = create_res.json()
    patch_id = patch_data["id"]
    diff_sha = patch_data["diff_sha256"]

    # 077: GET /api/v1/fixes/{id}
    get_res = client.get(f"/api/v1/fixes/{patch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == patch_id

    # 078: PATCH /api/v1/fixes/{id}
    edited_diff = diff_text + "         total += p\n"
    edit_res = client.patch(
        f"/api/v1/fixes/{patch_id}",
        json={"unified_diff": edited_diff, "rationale": "Manual edit"},
    )
    assert edit_res.status_code == 200
    new_sha = edit_res.json()["diff_sha256"]

    # 079: POST /api/v1/fixes/{id}/revise
    revise_res = client.post(
        f"/api/v1/fixes/{patch_id}/revise",
        json={"instruction": "Ensure type checking for elements"},
    )
    assert revise_res.status_code == 202
    revised_data = revise_res.json()
    revised_sha = revised_data["diff_sha256"]

    # 080: POST /api/v1/fixes/{id}/validate
    val_res = client.post(
        f"/api/v1/fixes/{patch_id}/validate",
        json={"consent_execute_tests": False},
    )
    assert val_res.status_code == 200
    assert val_res.json()["status"] == "VALIDATED"

    # 081: POST /api/v1/fixes/{id}/approve
    approve_res = client.post(
        f"/api/v1/fixes/{patch_id}/approve",
        json={"diff_sha256": revised_sha, "scope": "FULL"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # 083: POST /api/v1/fixes/{id}/export
    export_res = client.post(f"/api/v1/fixes/{patch_id}/export")
    assert export_res.status_code == 200
    assert "text/x-diff" in export_res.headers["content-type"]

    # 084: POST /api/v1/fixes/{id}/pull-request
    pr_res = client.post(
        f"/api/v1/fixes/{patch_id}/pull-request",
        json={
            "publish_approval_id": "appr-pub-001",
            "branch_name": "codepilot/fix-calculator-null",
            "title": "Fix calculator null issue",
            "body": "Automated fix by CodePilot Mastermind",
        },
    )
    assert pr_res.status_code == 202
    assert "pull_request" in pr_res.json() or "branch" in pr_res.json()

    # 082: POST /api/v1/fixes/{id}/reject
    # Create another fix to test reject
    fix2 = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-mm-all",
            "unified_diff": diff_text,
            "validation_policy": {},
        },
    ).json()
    reject_res = client.post(
        f"/api/v1/fixes/{fix2['id']}/reject",
        json={"reason": "Not needed"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"


# ----------------------------------------------------------------------
# M5: Unit Test Generation (085 - 088)
# ----------------------------------------------------------------------

def test_m5_endpoints_085_to_088(client):
    # 085: POST /api/v1/tests/generate
    gen_res = client.post(
        "/api/v1/tests/generate",
        json={
            "snapshot_id": "snap-mm-all",
            "target": {"file_path": "app/calculator.py"},
            "framework": "PYTEST",
            "test_type": "UNIT",
        },
    )
    assert gen_res.status_code == 201
    test_run = gen_res.json()
    run_id = test_run["run_id"]
    assert test_run["test_artifact"] is not None

    # 086: GET /api/v1/tests/{run_id}
    get_res = client.get(f"/api/v1/tests/{run_id}")
    assert get_res.status_code == 200
    assert get_res.json()["run_id"] == run_id

    # 087: POST /api/v1/tests/{run_id}/execute
    exec_res = client.post(
        f"/api/v1/tests/{run_id}/execute",
        json={
            "consent": {
                "execute": True,
                "install_scripts": False,
                "approver_id": "qa_lead",
            }
        },
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["execution"] is not None

    # 088: POST /api/v1/tests/{run_id}/export
    exp_res = client.post(
        f"/api/v1/tests/{run_id}/export",
        json={"target_path": "tests/test_calculator_generated.py"},
    )
    assert exp_res.status_code == 200
    assert exp_res.json()["patch_id"] is not None


# ----------------------------------------------------------------------
# M6: Security Vulnerability Detection (089 - 090)
# ----------------------------------------------------------------------

def test_m6_endpoints_089_to_090(client):
    # 089: POST /api/v1/security/scans (Requires Idempotency-Key)
    scan_res = client.post(
        "/api/v1/security/scans",
        headers={"Idempotency-Key": "test-idem-m6-001"},
        json={
            "snapshot_id": "snap-mm-all",
            "scan_profile": "STANDARD",
        },
    )
    assert scan_res.status_code == 202
    scan_data = scan_res.json()
    scan_id = scan_data["scan_id"]
    assert scan_data["total_findings"] >= 1  # Should catch JWT_SECRET

    # 090: GET /api/v1/security/scans/{id}
    get_res = client.get(f"/api/v1/security/scans/{scan_id}")
    assert get_res.status_code == 200
    assert get_res.json()["scan_id"] == scan_id


# ----------------------------------------------------------------------
# M7: Pull Request Reviews (091 - 096)
# ----------------------------------------------------------------------

def test_m7_endpoints_091_to_096(client):
    # Setup PR in repository
    pr_repo = PullRequestRepository.get_instance()
    pr_repo.upsert_pull_request({
        "id": "pr-mm-001",
        "repository_id": "repo-test-1",
        "number": 42,
        "title": "Add tax calculation feature",
        "author_login": "contributor",
        "base_ref": "main",
        "head_ref": "feature/tax",
        "head_repo_full_name": "org/repo-test-1",
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "base_snapshot_id": "snap-mm-all",
        "head_snapshot_id": "snap-mm-all",
        "state": "OPEN",
    })

    # 092: GET /api/v1/repositories/{id}/pull-requests
    list_res = client.get("/api/v1/repositories/repo-test-1/pull-requests")
    assert list_res.status_code == 200
    assert list_res.json()["total"] >= 1

    # 093: POST /api/v1/pull-requests/{id}/review-runs
    run_res = client.post(
        "/api/v1/pull-requests/pr-mm-001/review-runs",
        json={
            "base_sha": "a" * 40,
            "head_sha": "b" * 40,
            "review_profile": "SECURITY_AND_QUALITY",
            "unified_diff": (
                "--- a/app/auth.py\n"
                "+++ b/app/auth.py\n"
                "@@ -1,3 +1,3 @@\n"
                "-JWT_SECRET = 'super_secret_jwt_key_12345'\n"
                "+JWT_SECRET = os.getenv('JWT_SECRET')\n"
            ),
        },
    )
    assert run_res.status_code == 202
    review_data = run_res.json()
    review_run_id = review_data["id"]

    # 094: GET /api/v1/pull-requests/{id}/reviews/{run_id}
    draft_res = client.get(f"/api/v1/pull-requests/pr-mm-001/reviews/{review_run_id}")
    assert draft_res.status_code == 200
    assert draft_res.json()["id"] == review_run_id

    # 095: PATCH /api/v1/pull-requests/{id}/reviews/{run_id}/comments/{comment_id}
    # Add a mock comment to draft if none present
    if not draft_res.json()["comments"]:
        pr_repo.add_comment(
            review_run_id,
            {
                "id": "cm-001",
                "run_id": review_run_id,
                "file_path": "app/auth.py",
                "line": 2,
                "body": "Ensure environment variable is verified on startup.",
                "status": "DRAFT",
            },
        )
    comment_res = client.patch(
        f"/api/v1/pull-requests/pr-mm-001/reviews/{review_run_id}/comments/cm-001",
        json={"body": "Updated comment text: Ensure env var is verified."},
    )
    assert comment_res.status_code == 200
    assert "Updated comment text" in comment_res.json()["body"]

    # 096: POST /api/v1/pull-requests/{id}/reviews/{run_id}/publish
    pub_res = client.post(
        f"/api/v1/pull-requests/pr-mm-001/reviews/{review_run_id}/publish",
        json={"publish_approval_id": "appr-pub-pr-01"},
    )
    assert pub_res.status_code == 202
    assert pub_res.json()["status"] == "PUBLISHED"

    # 091: POST /api/v1/github/webhooks (HMAC verified, deduplicated)
    secret = b"webhook_test_secret"
    webhook_payload = json.dumps({
        "action": "synchronize",
        "pull_request": {
            "id": 101,
            "number": 42,
            "head": {"sha": "c" * 40},
            "base": {"sha": "a" * 40},
        },
        "repository": {"id": 999, "full_name": "org/repo-test-1"},
    }).encode("utf-8")
    sig = "sha256=" + hmac.new(secret, webhook_payload, hashlib.sha256).hexdigest()

    wh_res = client.post(
        "/api/v1/github/webhooks",
        content=webhook_payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-uuid-999",
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )
    # 202 accepted or 200 depending on verification
    assert wh_res.status_code in (200, 202)
