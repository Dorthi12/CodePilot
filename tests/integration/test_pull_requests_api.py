"""Integration tests for Mastermind Feature 7: Pull Request Review API endpoints (091–096).

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoints 091–096)
- API and Data Specification v1.0 §3.3 (091–096), §3.4.15, §3.10
- Security & Testing Specification v1.0 §7.3.10 (SEC-API-28..31), §7.9, §8.9 (AI-16)
"""

import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient

from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from backend.app.main import app
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.pull_requests import PullRequest, PRState

client = TestClient(app)
WEBHOOK_SECRET = "test-webhook-secret"


@pytest.fixture(autouse=True)
def setup_snapshot_and_pr_repo():
    """Setup test snapshot with sample source files and reset repositories."""
    PullRequestRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()

    # Pre-register test snapshot context
    snap_id = "snap-pr-test"
    ctx = RepositorySnapshotContext(snap_id)
    ctx.add_file(
        "app/service.py",
        """class PaymentService:
    def process_payment(self, user_id, items=[]):
        if not user_id:
            raise ValueError("user_id required")
        return {"status": "success", "items": items}
""",
        language="python",
    )
    ctx.add_file(
        "tests/test_service.py",
        """from app.service import PaymentService

def test_payment():
    svc = PaymentService()
    res = svc.process_payment(1, ["apple"])
    assert res["status"] == "success"
""",
        language="python",
    )
    # Add graph edges
    ctx.add_edge("tests/test_service.py", "app/service.py", "TESTS")
    SnapshotContextRegistry.register(ctx)

    yield

    PullRequestRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()


def _compute_sig(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# =====================================================================
# Endpoint 091: POST /api/v1/github/webhooks
# =====================================================================

def test_endpoint_091_webhook_hmac_invalid():
    """Verify E-091: Invalid signature returns 401 WEBHOOK_SIGNATURE_INVALID."""
    body = b'{"action": "ping"}'
    headers = {
        "X-GitHub-Event": "ping",
        "X-GitHub-Delivery": "delivery-fail-001",
        "X-Hub-Signature-256": "sha256=invalidhex00000000000000000000000000000000",
    }
    resp = client.post("/api/v1/github/webhooks", content=body, headers=headers)
    assert resp.status_code == 401
    assert "signature" in resp.json()["detail"].lower()


def test_endpoint_091_webhook_pull_request_opened():
    """Verify E-091: Valid webhook creates PR record and returns 202 Accepted."""
    payload = {
        "action": "opened",
        "repository": {"id": 12345},
        "pull_request": {
            "number": 101,
            "title": "Add payment gateway",
            "user": {"login": "octocat"},
            "base": {
                "ref": "main",
                "sha": "1111111111111111111111111111111111111111",
                "repo": {"full_name": "org/repo"},
            },
            "head": {
                "ref": "feature/payments",
                "sha": "2222222222222222222222222222222222222222",
                "repo": {"full_name": "org/repo"},
            },
            "draft": False,
        },
    }
    raw_body = json.dumps(payload).encode()
    sig = _compute_sig(raw_body)
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-pr-101",
        "X-Hub-Signature-256": sig,
    }

    resp = client.post("/api/v1/github/webhooks", content=raw_body, headers=headers)
    assert resp.status_code == 202

    # Verify PR was stored in repository
    pr = PullRequestRepository.get_instance().get_pull_request_by_number("12345", 101)
    assert pr is not None
    assert pr.title == "Add payment gateway"
    assert pr.author_login == "octocat"
    assert pr.base_sha == "1111111111111111111111111111111111111111"
    assert pr.head_sha == "2222222222222222222222222222222222222222"
    assert not pr.is_fork


def test_endpoint_091_webhook_fork_pr():
    """Verify E-091: Webhook correctly flags fork PRs (different head_repo_full_name)."""
    payload = {
        "action": "opened",
        "repository": {"id": 12345},
        "pull_request": {
            "number": 102,
            "title": "Community contribution",
            "user": {"login": "external-contributor"},
            "base": {
                "ref": "main",
                "sha": "1111111111111111111111111111111111111111",
                "repo": {"full_name": "org/repo"},
            },
            "head": {
                "ref": "patch-1",
                "sha": "3333333333333333333333333333333333333333",
                "repo": {"full_name": "external-fork/repo"},
            },
            "draft": False,
        },
    }
    raw_body = json.dumps(payload).encode()
    sig = _compute_sig(raw_body)
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-pr-fork-102",
        "X-Hub-Signature-256": sig,
    }

    resp = client.post("/api/v1/github/webhooks", content=raw_body, headers=headers)
    assert resp.status_code == 202

    pr = PullRequestRepository.get_instance().get_pull_request_by_number("12345", 102)
    assert pr is not None
    assert pr.is_fork is True


# =====================================================================
# Endpoint 092: GET /api/v1/repositories/{id}/pull-requests
# =====================================================================

def test_endpoint_092_list_pull_requests():
    """Verify E-092: List PRs for repository with state filtering."""
    repo = PullRequestRepository.get_instance()
    pr1 = PullRequest(
        repository_id="repo-999",
        number=1,
        title="PR 1",
        author_login="user1",
        base_ref="main",
        head_ref="f1",
        base_sha="0" * 40,
        head_sha="1" * 40,
        state=PRState.OPEN,
    )
    pr2 = PullRequest(
        repository_id="repo-999",
        number=2,
        title="PR 2",
        author_login="user2",
        base_ref="main",
        head_ref="f2",
        base_sha="0" * 40,
        head_sha="2" * 40,
        state=PRState.MERGED,
    )
    repo.upsert_pull_request(pr1)
    repo.upsert_pull_request(pr2)

    # List all
    resp_all = client.get("/api/v1/repositories/repo-999/pull-requests")
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert data_all["total"] == 2

    # Filter state=OPEN
    resp_open = client.get("/api/v1/repositories/repo-999/pull-requests?state=OPEN")
    assert resp_open.status_code == 200
    data_open = resp_open.json()
    assert data_open["total"] == 1
    assert data_open["pull_requests"][0]["number"] == 1


# =====================================================================
# Endpoint 093 & 094: Start PR Review Run & Retrieve Draft Review
# =====================================================================

def test_endpoint_093_and_094_review_run_lifecycle():
    """Verify E-093 and E-094: Start review run, detect bugs on changed lines, anchor comments, get draft."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        repository_id="repo-service",
        number=20,
        title="Fix payments",
        author_login="alice",
        base_ref="main",
        head_ref="fix/payments",
        base_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        head_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        head_snapshot_id="snap-pr-test",
        base_snapshot_id="snap-pr-test",
    )
    repo.upsert_pull_request(pr)

    diff = """--- a/app/service.py
+++ b/app/service.py
@@ -1,4 +1,4 @@
 class PaymentService:
-    def process_payment(self, user_id, items=None):
+    def process_payment(self, user_id, items=[]):
         if not user_id:
"""

    # 1. Start review run (E-093)
    req_body = {
        "base_sha": pr.base_sha,
        "head_sha": pr.head_sha,
        "review_profile": "standard",
        "unified_diff": diff,
        "head_snapshot_id": "snap-pr-test",
        "base_snapshot_id": "snap-pr-test",
    }
    create_resp = client.post(f"/api/v1/pull-requests/{pr.id}/review-runs", json=req_body)
    assert create_resp.status_code == 202
    run_data = create_resp.json()

    assert run_data["run_id"] is not None
    assert run_data["pull_request_id"] == pr.id
    assert run_data["base_sha"] == pr.base_sha
    assert run_data["head_sha"] == pr.head_sha
    assert run_data["status"] == "COMPLETED"
    assert len(run_data["comments"]) >= 1

    # Check that comment caught the mutable default argument on line 2
    comment = run_data["comments"][0]
    assert comment["file_path"] == "app/service.py"
    assert comment["line"] == 2
    assert "Mutable default" in comment["body"] or "mutable" in comment["body"].lower()
    assert comment["status"] == "DRAFT"
    assert len(comment["evidence"]) > 0

    # Check blast radius and recommended tests
    assert "app.service" in run_data["impacted_modules"]
    assert "tests/test_service.py" in run_data["tests_to_run"]

    # 2. Get review draft (E-094)
    get_resp = client.get(f"/api/v1/pull-requests/{pr.id}/reviews/{run_data['run_id']}")
    assert get_resp.status_code == 200
    draft_data = get_resp.json()
    assert draft_data["run_id"] == run_data["run_id"]
    assert len(draft_data["comments"]) == len(run_data["comments"])


def test_endpoint_093_force_push_returns_409_pr_head_changed():
    """Verify E-093: If head SHA does not match current PR head, returns 409 PR_HEAD_CHANGED."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        repository_id="repo-fp",
        number=21,
        title="Feature",
        author_login="bob",
        base_ref="main",
        head_ref="feat",
        base_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        head_sha="current_latest_sha_1234567890abcdef1234",
    )
    repo.upsert_pull_request(pr)

    req_body = {
        "base_sha": pr.base_sha,
        "head_sha": "stale_old_sha_00000000000000000000000000",
        "review_profile": "standard",
    }
    resp = client.post(f"/api/v1/pull-requests/{pr.id}/review-runs", json=req_body)
    assert resp.status_code == 409
    assert "PR_HEAD_CHANGED" in resp.json()["detail"]


# =====================================================================
# Endpoint 095: PATCH /api/v1/pull-requests/{id}/reviews/{run_id}/comments/{comment_id}
# =====================================================================

def test_endpoint_095_edit_and_discard_comment():
    """Verify E-095: Edit draft comment text and discard unwanted comments."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        repository_id="repo-comments",
        number=30,
        title="Review triage",
        author_login="dev",
        base_ref="main",
        head_ref="branch",
        base_sha="0" * 40,
        head_sha="1" * 40,
    )
    repo.upsert_pull_request(pr)

    from shared.types.pull_requests import ReviewRunRecord, ReviewComment
    run_rec = ReviewRunRecord(
        id="run-comment-test",
        pull_request_id=pr.id,
        repository_id=pr.repository_id,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
    )
    repo.create_review_run(run_rec)

    comment = ReviewComment(
        id="c-1",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/service.py",
        line=2,
        body="Original draft text",
    )
    repo.add_comment(comment)

    # 1. Edit comment body
    patch_resp = client.patch(
        f"/api/v1/pull-requests/{pr.id}/reviews/{run_rec.id}/comments/{comment.id}",
        json={"body": "Human revised comment text"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["body"] == "Human revised comment text"
    assert patch_resp.json()["status"] == "EDITED"

    # 2. Discard comment
    discard_resp = client.patch(
        f"/api/v1/pull-requests/{pr.id}/reviews/{run_rec.id}/comments/{comment.id}",
        json={"status": "DISCARDED"},
    )
    assert discard_resp.status_code == 200
    assert discard_resp.json()["status"] == "DISCARDED"


# =====================================================================
# Endpoint 096: POST /api/v1/pull-requests/{id}/reviews/{run_id}/publish
# =====================================================================

def test_endpoint_096_publish_review_and_audit():
    """Verify E-096: Publish approved comments to GitHub, skip discarded comments, emit audit record."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        repository_id="repo-pub-api",
        number=50,
        title="PR Publish API Test",
        author_login="octocat",
        base_ref="main",
        head_ref="branch",
        base_sha="0" * 40,
        head_sha="1" * 40,
    )
    repo.upsert_pull_request(pr)

    from shared.types.pull_requests import ReviewRunRecord, ReviewComment, ReviewCommentStatus
    run_rec = ReviewRunRecord(
        id="run-pub-api",
        pull_request_id=pr.id,
        repository_id=pr.repository_id,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
    )
    repo.create_review_run(run_rec)

    # Active comment
    c1 = ReviewComment(
        id="c-active",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/service.py",
        line=2,
        body="Actionable comment",
        status=ReviewCommentStatus.DRAFT,
    )
    # Discarded comment
    c2 = ReviewComment(
        id="c-discarded",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/service.py",
        line=5,
        body="Discarded comment",
        status=ReviewCommentStatus.DISCARDED,
    )
    repo.add_comment(c1)
    repo.add_comment(c2)

    pub_resp = client.post(
        f"/api/v1/pull-requests/{pr.id}/reviews/{run_rec.id}/publish",
        json={"publish_approval_id": "appr-12345"},
    )
    assert pub_resp.status_code == 202
    data = pub_resp.json()

    assert data["status"] == "PUBLISHED"
    assert data["published_count"] == 1
    assert "c-active" in data["published_comment_ids"]
    assert "c-discarded" not in data["published_comment_ids"]
    assert len(data["github_comment_ids"]) == 1
    assert data["audit_event_id"] is not None

    # Verify audit event in repository
    audits = repo.list_audit_events(resource_type="PULL_REQUEST", resource_id=pr.id)
    assert len(audits) == 1
    assert audits[0].action == "PUBLISH_PR_REVIEW"
