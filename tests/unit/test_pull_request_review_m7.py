"""Unit tests for Mastermind Feature 7: Pull Request Reviews (M7).

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoints 091–096)
- API and Data Specification v1.0 §3.3 (091–096), §3.4.15, §3.10
- Security and Testing Specification v1.0 §7.3.10 (SEC-API-28..31), §7.9, §8.9 (AI-16, UT-12, AT-12)
"""

import hashlib
import hmac
import json
import pytest
from datetime import datetime, timezone

from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from agentic.workflows.pull_request_review import PullRequestReviewWorkflow
from backend.app.modules.github.webhook_handler import (
    GITHUB_TEST_BODY,
    GITHUB_TEST_EXPECTED_SIGNATURE,
    GITHUB_TEST_SECRET,
    GitHubWebhookHandler,
)
from backend.app.modules.pull_requests.branch_manager import PRBranchManager
from backend.app.modules.pull_requests.comment_generator import CommentGenerator
from backend.app.modules.pull_requests.diff_analyzer import PRDiffAnalyzer
from backend.app.modules.pull_requests.publisher import PullRequestPublisher
from backend.app.modules.pull_requests.review_manager import PullRequestReviewManager
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.agent import FindingSeverity
from shared.types.findings import Finding
from shared.types.pull_requests import (
    PRState,
    PullRequest,
    ReviewCommentStatus,
)


@pytest.fixture(autouse=True)
def clean_repositories():
    """Reset repositories and snapshot registry before each test."""
    PullRequestRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()
    yield
    PullRequestRepository.get_instance().clear()
    FindingsRepository.get_instance().clear()
    SnapshotContextRegistry.clear()


# =====================================================================
# 1. Webhook Signature & Deduplication (SEC-API-28..31, UT-12, AT-12)
# =====================================================================

def test_github_conformance_test_vector():
    """Verify official GitHub docs test vector: secret, body, expected signature (AIDS §3.10.2)."""
    assert GitHubWebhookHandler.verify_signature(
        raw_body=GITHUB_TEST_BODY,
        secret=GITHUB_TEST_SECRET,
        signature_header=GITHUB_TEST_EXPECTED_SIGNATURE,
    )


def test_webhook_constant_time_verification_invalid_signatures():
    """Verify invalid or mismatched signatures are rejected."""
    secret = "my-secret-key"
    body = b'{"action": "opened"}'

    # Missing header
    assert not GitHubWebhookHandler.verify_signature(body, secret, None)
    # Malformed prefix
    assert not GitHubWebhookHandler.verify_signature(body, secret, "sha1=abcdef")
    # Wrong digest
    assert not GitHubWebhookHandler.verify_signature(body, secret, "sha256=wrongdigest1234567890")


def test_webhook_dual_secret_rotation():
    """Verify SEC-API-30: dual active secrets during rotation."""
    primary = "secret-v2"
    previous = "secret-v1"
    handler = GitHubWebhookHandler(primary_secret=primary, previous_secret=previous)

    body = b'{"hello": "world"}'

    # Valid with primary
    sig_primary = "sha256=" + hmac.new(primary.encode(), body, hashlib.sha256).hexdigest()
    assert handler.verify_request(body, sig_primary)

    # Valid with previous
    sig_previous = "sha256=" + hmac.new(previous.encode(), body, hashlib.sha256).hexdigest()
    assert handler.verify_request(body, sig_previous)

    # Invalid with third unknown secret
    sig_other = "sha256=" + hmac.new(b"secret-v0", body, hashlib.sha256).hexdigest()
    assert not handler.verify_request(body, sig_other)


def test_webhook_delivery_deduplication_replay():
    """Verify deduplication via X-GitHub-Delivery: duplicate delivery returns 200 replay."""
    handler = GitHubWebhookHandler(primary_secret="test-secret")
    payload = json.dumps({"action": "opened", "pull_request": {"number": 1, "title": "Test PR"}}).encode()
    sig = "sha256=" + hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()

    # First delivery
    status_1, resp_1 = handler.handle_webhook(
        delivery_id="delivery-guid-001",
        event="pull_request",
        raw_body=payload,
        signature_header=sig,
    )
    assert status_1 == 202
    assert resp_1["status"] == "ACCEPTED"

    # Second delivery (replay)
    status_2, resp_2 = handler.handle_webhook(
        delivery_id="delivery-guid-001",
        event="pull_request",
        raw_body=payload,
        signature_header=sig,
    )
    assert status_2 == 200
    assert resp_2["status"] == "REPLAY"


def test_webhook_body_size_limit():
    """Verify 26 MB body limit returns 413."""
    handler = GitHubWebhookHandler(primary_secret="test-secret")
    huge_body = b"x" * (26 * 1024 * 1024 + 1)
    status, resp = handler.handle_webhook(
        delivery_id="delivery-oversized",
        event="push",
        raw_body=huge_body,
        signature_header="sha256=irrelevant",
    )
    assert status == 413
    assert resp["error"]["code"] == "PAYLOAD_TOO_LARGE"


# =====================================================================
# 2. Diff Parsing, Hunk Extraction, and Line Tracking
# =====================================================================

SAMPLE_DIFF = """--- a/app/auth.py
+++ b/app/auth.py
@@ -10,4 +10,6 @@ def validate_token(token):
     if not token:
-        return False
+        raise AuthError("missing token")
+    user = get_user(token, items=[])
+    return user
"""

def test_pr_diff_analyzer_parse_diff():
    """Verify PR diff parser extracts changed files, hunk boundaries, and added lines."""
    pr_files = PRDiffAnalyzer.parse_diff(SAMPLE_DIFF, pull_request_id="pr-123")
    assert len(pr_files) == 1

    pf = pr_files[0]
    assert pf.path == "app/auth.py"
    assert pf.status == "modified"
    assert pf.additions == 3
    assert pf.deletions == 1
    assert len(pf.hunks) == 1

    hunk = pf.hunks[0]
    assert hunk.mod_start == 10
    # Added lines in head file: 11, 12, 13
    assert 11 in hunk.added_lines
    assert 12 in hunk.added_lines
    assert 13 in hunk.added_lines


def test_pr_diff_extract_changed_lines():
    """Verify changed line numbers mapping."""
    pr_files = PRDiffAnalyzer.parse_diff(SAMPLE_DIFF, pull_request_id="pr-123")
    changed_map = PRDiffAnalyzer.extract_changed_line_numbers(pr_files)

    assert "app/auth.py" in changed_map
    assert changed_map["app/auth.py"] == {11, 12, 13}


# =====================================================================
# 3. Line Anchor Verification (AI-16: comments anchor to changed lines)
# =====================================================================

def test_line_anchor_verification_discards_unchanged_lines():
    """Verify AI-16 invariant: comments on unchanged lines are discarded."""
    snap_id = "snap-test-anchors"
    ctx = RepositorySnapshotContext(snap_id)
    ctx.add_file(
        "app/service.py",
        """line_1 = 1
line_2 = 2
line_3 = 3
line_4 = 4
line_5 = 5
def compute(x, data=[]):
    return sum(data)
line_8 = 8
line_9 = 9
line_10 = 10
""",
    )
    SnapshotContextRegistry.register(ctx)

    # PR diff touches only line 6
    diff = """--- a/app/service.py
+++ b/app/service.py
@@ -5,3 +5,3 @@
 line_5 = 5
-def compute(x, data=None):
+def compute(x, data=[]):
     return sum(data)
"""
    pr = PullRequest(
        id="pr-anchor-test",
        repository_id="repo-1",
        number=42,
        title="Update compute",
        author_login="dev1",
        base_ref="main",
        head_ref="feat",
        base_sha="0000000000000000000000000000000000000000",
        head_sha="1111111111111111111111111111111111111111",
        head_snapshot_id=snap_id,
        base_snapshot_id=snap_id,
    )
    PullRequestRepository.get_instance().upsert_pull_request(pr)

    workflow = PullRequestReviewWorkflow()
    result = workflow.run_review(
        pull_request_id=pr.id,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
        diff_text=diff,
        head_snapshot_id=snap_id,
        base_snapshot_id=snap_id,
    )

    # Comment should anchor to line 6 (which is in the diff)
    assert len(result.comments) >= 1
    for c in result.comments:
        assert c.line == 6
        assert c.status == ReviewCommentStatus.DRAFT
        assert len(c.evidence) > 0
        assert c.evidence[0].snippet_hash is not None


# =====================================================================
# 4. Secret Detection in Diff (Zero Raw Secrets Invariant I9)
# =====================================================================

def test_secret_detection_in_pr_diff():
    """Verify secrets in PR diff are detected with critical severity and redacted fingerprints."""
    snap_id = "snap-test-secrets"
    ctx = RepositorySnapshotContext(snap_id)
    ctx.add_file(
        "app/config.py",
        """import os
API_KEY = "sk-1234567890abcdef1234567890abcdef"
""",
    )
    SnapshotContextRegistry.register(ctx)

    diff = """--- a/app/config.py
+++ b/app/config.py
@@ -1,1 +1,2 @@
 import os
+API_KEY = "sk-1234567890abcdef1234567890abcdef"
"""
    pr = PullRequest(
        id="pr-secret-test",
        repository_id="repo-sec",
        number=99,
        title="Add api key",
        author_login="leaker",
        base_ref="main",
        head_ref="leak-branch",
        base_sha="aaaa000000000000000000000000000000000000",
        head_sha="bbbb111111111111111111111111111111111111",
        head_snapshot_id=snap_id,
    )
    PullRequestRepository.get_instance().upsert_pull_request(pr)

    workflow = PullRequestReviewWorkflow()
    result = workflow.run_review(
        pull_request_id=pr.id,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
        diff_text=diff,
        head_snapshot_id=snap_id,
        base_snapshot_id=snap_id,
    )

    # Must contain critical secret comment
    secret_comments = [c for c in result.comments if c.severity == FindingSeverity.CRITICAL]
    assert len(secret_comments) >= 1
    sc = secret_comments[0]
    assert "Hardcoded credential" in sc.body or "API secret" in sc.body or "secret" in sc.body.lower()
    # Ensure raw secret is not in the comment title/snippet
    assert "sk-1234567890abcdef" not in sc.evidence[0].snippet
    assert "[REDACTED]" in sc.evidence[0].snippet or "REDACTED" in sc.evidence[0].snippet


# =====================================================================
# 5. Blast Radius & Impact Analysis
# =====================================================================

def test_blast_radius_and_tests_to_run():
    """Verify impact analysis traverses graph to identify impacted modules and tests."""
    snap_id = "snap-test-impact"
    ctx = RepositorySnapshotContext(snap_id)
    ctx.add_file("app/auth.py", "def authenticate(): pass\n")
    ctx.add_file("app/api.py", "from app.auth import authenticate\n")
    ctx.add_file("tests/test_auth.py", "def test_auth(): pass\n")

    # Add graph edges
    ctx.add_edge("app.api", "authenticate", "CALLS")
    ctx.add_edge("tests/test_auth.py", "app/auth.py", "TESTS")
    SnapshotContextRegistry.register(ctx)

    diff = """--- a/app/auth.py
+++ b/app/auth.py
@@ -1,1 +1,2 @@
+def authenticate(): return True
"""
    pr = PullRequest(
        id="pr-impact-test",
        repository_id="repo-imp",
        number=10,
        title="Update auth",
        author_login="alice",
        base_ref="main",
        head_ref="auth-update",
        base_sha="c000000000000000000000000000000000000000",
        head_sha="d000000000000000000000000000000000000000",
        head_snapshot_id=snap_id,
    )
    PullRequestRepository.get_instance().upsert_pull_request(pr)

    workflow = PullRequestReviewWorkflow()
    result = workflow.run_review(
        pull_request_id=pr.id,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
        diff_text=diff,
        head_snapshot_id=snap_id,
        base_snapshot_id=snap_id,
    )

    assert "app.auth" in result.impacted_modules
    assert "tests/test_auth.py" in result.tests_to_run


# =====================================================================
# 6. Force-Push Detection (returns 409 PR_HEAD_CHANGED)
# =====================================================================

def test_force_push_detection_raises_pr_head_changed():
    """Verify force-push between request and run invalidates run and raises PR_HEAD_CHANGED."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        id="pr-force-push-test",
        repository_id="repo-fp",
        number=7,
        title="Feature branch",
        author_login="bob",
        base_ref="main",
        head_ref="feature",
        base_sha="1111111111111111111111111111111111111111",
        head_sha="2222222222222222222222222222222222222222",
    )
    repo.upsert_pull_request(pr)

    manager = PullRequestReviewManager.get_instance()

    # Client requests review with stale head SHA (force-push changed head)
    with pytest.raises(ValueError, match="PR_HEAD_CHANGED"):
        manager.start_review_run(
            pull_request_id=pr.id,
            base_sha=pr.base_sha,
            head_sha="stale-old-head-sha",
        )


# =====================================================================
# 7. Comment Triage: Edit and Discard (Endpoint 095)
# =====================================================================

def test_comment_triage_edit_and_discard():
    """Verify human reviewer can edit comment text and discard unwanted comments."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        id="pr-triage",
        repository_id="repo-tr",
        number=1,
        title="PR Triage",
        author_login="dev",
        base_ref="main",
        head_ref="head",
        base_sha="0000000000000000000000000000000000000000",
        head_sha="1111111111111111111111111111111111111111",
    )
    repo.upsert_pull_request(pr)

    manager = PullRequestReviewManager.get_instance()

    # Pre-seed review run and comments
    run_dict = {
        "id": "run-triage-1",
        "pull_request_id": pr.id,
        "repository_id": pr.repository_id,
        "base_sha": pr.base_sha,
        "head_sha": pr.head_sha,
        "summary": "Initial summary",
    }
    from shared.types.pull_requests import ReviewRunRecord, ReviewComment
    run_rec = ReviewRunRecord(**run_dict)
    repo.create_review_run(run_rec)

    c1 = ReviewComment(
        id="comment-1",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/main.py",
        line=10,
        body="Original body 1",
    )
    c2 = ReviewComment(
        id="comment-2",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/main.py",
        line=20,
        body="Original body 2",
    )
    repo.add_comment(c1)
    repo.add_comment(c2)

    # 1. Edit comment 1
    updated_c1 = manager.edit_or_discard_comment(
        pull_request_id=pr.id,
        run_id=run_rec.id,
        comment_id="comment-1",
        body="Revised body by human reviewer",
    )
    assert updated_c1.status == ReviewCommentStatus.EDITED
    assert updated_c1.body == "Revised body by human reviewer"

    # 2. Discard comment 2
    discarded_c2 = manager.edit_or_discard_comment(
        pull_request_id=pr.id,
        run_id=run_rec.id,
        comment_id="comment-2",
        status="DISCARDED",
    )
    assert discarded_c2.status == ReviewCommentStatus.DISCARDED


# =====================================================================
# 8. Dangerous Operation Gate & Publish Review (Endpoint 096)
# =====================================================================

def test_publish_review_dangerous_operation_gate():
    """Verify publishing enforces authorization, omits discarded comments, and logs audit events."""
    repo = PullRequestRepository.get_instance()
    pr = PullRequest(
        id="pr-pub-test",
        repository_id="repo-pub",
        number=5,
        title="PR Publish Test",
        author_login="contributor",
        base_ref="main",
        head_ref="head",
        base_sha="0000000000000000000000000000000000000000",
        head_sha="1111111111111111111111111111111111111111",
    )
    repo.upsert_pull_request(pr)

    from shared.types.pull_requests import ReviewRunRecord, ReviewComment
    run_rec = ReviewRunRecord(
        id="run-pub-1",
        pull_request_id=pr.id,
        repository_id=pr.repository_id,
        base_sha=pr.base_sha,
        head_sha=pr.head_sha,
    )
    repo.create_review_run(run_rec)

    # c1 is DRAFT, c2 is EDITED, c3 is DISCARDED
    c1 = ReviewComment(
        id="c-draft",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/a.py",
        line=5,
        body="Draft comment",
        status=ReviewCommentStatus.DRAFT,
    )
    c2 = ReviewComment(
        id="c-edited",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/b.py",
        line=15,
        body="Edited comment",
        status=ReviewCommentStatus.EDITED,
    )
    c3 = ReviewComment(
        id="c-discarded",
        run_id=run_rec.id,
        pull_request_id=pr.id,
        file_path="app/c.py",
        line=25,
        body="Discarded comment",
        status=ReviewCommentStatus.DISCARDED,
    )
    repo.add_comment(c1)
    repo.add_comment(c2)
    repo.add_comment(c3)

    publisher = PullRequestPublisher(repo)

    # Unauthorized attempt without approval and not owner
    with pytest.raises(PermissionError, match="PUBLISH_APPROVAL_REQUIRED"):
        publisher.publish_review(
            pull_request_id=pr.id,
            run_id=run_rec.id,
            publish_approval_id=None,
            actor_role="VIEWER",
        )

    # Authorized publish
    pub_result = publisher.publish_review(
        pull_request_id=pr.id,
        run_id=run_rec.id,
        publish_approval_id="approval-token-xyz",
        actor_role="OWNER",
    )

    assert pub_result["status"] == "PUBLISHED"
    assert pub_result["published_count"] == 2  # c1 and c2, c3 discarded
    assert "c-draft" in pub_result["published_comment_ids"]
    assert "c-edited" in pub_result["published_comment_ids"]
    assert "c-discarded" not in pub_result["published_comment_ids"]

    # Verify audit event was logged
    audit_events = repo.list_audit_events(resource_type="PULL_REQUEST", resource_id=pr.id)
    assert len(audit_events) == 1
    assert audit_events[0].action == "PUBLISH_PR_REVIEW"
    assert audit_events[0].outcome == "SUCCESS"
    assert audit_events[0].metadata["published_count"] == 2
