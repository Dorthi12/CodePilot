"""Unit and integration tests for Mastermind Feature 4: AI-Assisted Code Fixes (M4).

Covers:
- Endpoints E-076 to E-084: Create, Inspect, Edit, Revise, Validate, Approve, Reject, Export, Pull Request
- Security Invariant I8: diff edits reset validation and approvals
- Fail-closed validation (Apply, Syntax, Lint, Security, Sandbox tests with EXECUTE gate)
- Approval binding to diff SHA256 and rejection on hash mismatch
- Pull request publishing under 'codepilot/' branch namespace
"""

import pytest
from fastapi.testclient import TestClient
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.main import app
from backend.app.modules.patching.patch_manager import PatchManager, sha256_diff
from backend.app.modules.patching.diff_generator import DiffGenerator
from backend.app.modules.patching.approval_binding import ApprovalBindingService
from backend.app.repositories.findings_repository import FindingsRepository
from shared.types.findings import Finding
from shared.types.agent import FindingOrigin, FindingSeverity

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_snapshot_and_repo():
    """Setup test snapshot with sample source files."""
    SnapshotContextRegistry.clear()
    PatchManager.instance().clear()
    FindingsRepository.get_instance().clear()

    ctx = RepositorySnapshotContext("snap-fix-test")
    ctx.add_file(
        "app/auth.py",
        "def login(user, items=[]):\n    if not user:\n        raise AuthError(\"token expired\")\n    return True\n",
        language="python",
    )
    ctx.add_file(
        "app/db.py",
        "def get_user(uid):\n    query = f\"SELECT * FROM users WHERE id = {uid}\"\n    return query\n",
        language="python",
    )
    SnapshotContextRegistry.register(ctx)

    yield

    SnapshotContextRegistry.clear()
    PatchManager.instance().clear()
    FindingsRepository.get_instance().clear()


def test_create_fix_with_patch_generator():
    """Verify E-076: AI Patch generation creates unified diff, calculates sha256, sets status to DRAFT."""
    payload = {
        "snapshot_id": "snap-fix-test",
        "task": "Fix mutable default argument in login function",
        "target_files": ["app/auth.py"],
        "validation_policy": {"syntax": True, "security": True, "tests": False},
    }
    response = client.post("/api/v1/fixes", json=payload)
    assert response.status_code == 202
    data = response.json()

    assert data["id"] is not None
    assert data["snapshot_id"] == "snap-fix-test"
    assert data["status"] == "DRAFT"
    assert data["diff_sha256"] is not None
    assert len(data["diff_sha256"]) == 64
    assert len(data["files"]) == 1
    assert data["files"][0]["path"] == "app/auth.py"
    assert "None" in data["unified_diff"]


def test_get_fix():
    """Verify E-077: Retrieve patch detail by ID."""
    # First create
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Fix SQL injection",
            "target_files": ["app/db.py"],
        },
    )
    patch_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/fixes/{patch_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == patch_id
    assert get_res.json()["status"] == "DRAFT"


def test_edit_fix_resets_validation_and_approvals_invariant_i8():
    """Verify E-078 & Invariant I8: Diff edits recalculate SHA256, clear validation and approvals."""
    # 1. Create patch
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Fix mutable default",
            "target_files": ["app/auth.py"],
        },
    )
    patch_id = create_res.json()["id"]
    orig_hash = create_res.json()["diff_sha256"]

    # 2. Validate patch
    val_res = client.post(f"/api/v1/fixes/{patch_id}/validate", json={"consent_execute_tests": False})
    assert val_res.status_code == 200
    assert val_res.json()["status"] == "VALIDATED"

    # 3. Approve patch
    appr_res = client.post(
        f"/api/v1/fixes/{patch_id}/approve",
        json={"scope": "EXPORT", "diff_sha256": orig_hash},
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"
    assert len(appr_res.json()["approvals"]) == 1

    # 4. User edits diff -> Must trigger Invariant I8
    new_diff = (
        "--- a/app/auth.py\n"
        "+++ b/app/auth.py\n"
        "@@ -1,4 +1,4 @@\n"
        "-def login(user, items=[]):\n"
        "+def login(user, items=None):\n"
        "     if not user:\n"
        "         return False\n"
    )
    edit_res = client.patch(
        f"/api/v1/fixes/{patch_id}",
        json={"unified_diff": new_diff, "rationale": "Manual correction"},
    )
    assert edit_res.status_code == 200
    edited = edit_res.json()
    assert edited["status"] == "DRAFT"
    assert edited["version"] == 2
    assert edited["diff_sha256"] != orig_hash
    assert len(edited["validation"]) == 0
    assert len(edited["approvals"]) == 0


def test_revise_fix():
    """Verify E-079: Revise patch with instruction updates diff and resets approvals."""
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Handle expired token",
            "target_files": ["app/auth.py"],
        },
    )
    patch_id = create_res.json()["id"]

    rev_res = client.post(
        f"/api/v1/fixes/{patch_id}/revise",
        json={"instruction": "Add comments explaining the token fix"},
    )
    assert rev_res.status_code == 202
    revised = rev_res.json()
    assert revised["status"] == "DRAFT"
    assert "Revision applied" in revised["rationale"]


def test_validate_fix_fail_closed_and_security_scan():
    """Verify E-080: Validation checks syntax, secrets, and apply cleanly."""
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Fix mutable default",
            "target_files": ["app/auth.py"],
            "validation_policy": {"syntax": True, "lint": True, "security": True, "tests": False},
        },
    )
    patch_id = create_res.json()["id"]

    val_res = client.post(f"/api/v1/fixes/{patch_id}/validate", json={"consent_execute_tests": False})
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["status"] == "VALIDATED"
    kinds = [v["kind"] for v in val_data["validation"]]
    assert "APPLY" in kinds
    assert "SYNTAX" in kinds
    assert "LINT" in kinds
    assert "SECURITY" in kinds

    # Test security failure if diff contains private key or secret token
    bad_diff = (
        "--- a/app/auth.py\n"
        "+++ b/app/auth.py\n"
        "@@ -1,2 +1,3 @@\n"
        "+ghp_secret_token_1234567890abcdef\n"
        " def login(user, items=[]):\n"
    )
    client.patch(f"/api/v1/fixes/{patch_id}", json={"unified_diff": bad_diff})
    bad_val = client.post(f"/api/v1/fixes/{patch_id}/validate", json={"consent_execute_tests": False})
    assert bad_val.json()["status"] == "VALIDATION_FAILED"
    sec_item = next(x for x in bad_val.json()["validation"] if x["kind"] == "SECURITY")
    assert sec_item["status"] == "FAILED"


def test_approve_and_export_fix():
    """Verify E-081 & E-083: Approval binding and attachment export."""
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Fix mutable default",
            "target_files": ["app/auth.py"],
        },
    )
    patch_id = create_res.json()["id"]
    correct_hash = create_res.json()["diff_sha256"]

    # Validate first
    client.post(f"/api/v1/fixes/{patch_id}/validate", json={"consent_execute_tests": False})

    # Approve with wrong hash -> must fail with 409
    wrong_hash = "0" * 64
    appr_fail = client.post(
        f"/api/v1/fixes/{patch_id}/approve",
        json={"scope": "EXPORT", "diff_sha256": wrong_hash},
    )
    assert appr_fail.status_code == 409

    # Approve with correct hash -> succeeds
    appr_ok = client.post(
        f"/api/v1/fixes/{patch_id}/approve",
        json={"scope": "EXPORT", "diff_sha256": correct_hash},
    )
    assert appr_ok.status_code == 200
    assert appr_ok.json()["status"] == "APPROVED"

    # Export unified diff
    export_res = client.post(f"/api/v1/fixes/{patch_id}/export")
    assert export_res.status_code == 200
    assert "attachment;" in export_res.headers["Content-Disposition"]
    assert "nosniff" in export_res.headers["X-Content-Type-Options"]
    assert "def login" in export_res.text


def test_reject_fix():
    """Verify E-082: Rejecting a patch transitions to REJECTED."""
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Fix mutable default",
            "target_files": ["app/auth.py"],
        },
    )
    patch_id = create_res.json()["id"]

    rej_res = client.post(
        f"/api/v1/fixes/{patch_id}/reject",
        json={"reason": "Alternative architectural redesign preferred"},
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "REJECTED"
    assert rej_res.json()["rejected_reason"] == "Alternative architectural redesign preferred"


def test_publish_pull_request_d3_gate():
    """Verify E-084: Create PR for approved patch with codepilot/ branch namespace."""
    create_res = client.post(
        "/api/v1/fixes",
        json={
            "snapshot_id": "snap-fix-test",
            "task": "Fix SQL injection",
            "target_files": ["app/db.py"],
        },
    )
    patch_id = create_res.json()["id"]
    diff_hash = create_res.json()["diff_sha256"]

    # Validate and approve
    client.post(f"/api/v1/fixes/{patch_id}/validate", json={"consent_execute_tests": False})
    client.post(f"/api/v1/fixes/{patch_id}/approve", json={"scope": "EXPORT", "diff_sha256": diff_hash})

    # Publish PR
    pr_res = client.post(
        f"/api/v1/fixes/{patch_id}/pull-request",
        json={
            "publish_approval_id": "appr-12345",
            "branch_name": "fix-sql-vuln",
            "title": "Fix SQL injection vulnerability in db.py",
            "body": "Replaces string format with parameterized query.",
        },
    )
    assert pr_res.status_code == 202
    pr_data = pr_res.json()
    assert pr_data["pull_request_number"] == 42
    assert pr_data["branch_name"] == "codepilot/fix-sql-vuln"
    assert pr_data["diff_sha256"] == diff_hash
