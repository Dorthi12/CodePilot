"""GitHub Webhook Handler: HMAC-SHA256 verification, delivery deduplication, and event processing.

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoint 091), §15.2
- API and Data Specification v1.0 §3.3 (091), §3.10 (Webhooks: §3.10.1, §3.10.2, §3.10.3)
- Security and Testing Specification v1.0 §7.3.10 (SEC-API-28..31), §7.4 (SEC-SECRET-03)
- System Design Specification v1.0 §9.7, §12.4
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from backend.app.modules.pull_requests.branch_manager import PRBranchManager
from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.pull_requests import (
    PRState,
    PullRequest,
    WebhookDeliveryStatus,
)

logger = logging.getLogger(__name__)

# Official test vector from GitHub docs (AIDS §3.10.2, UT-12, AT-12)
GITHUB_TEST_SECRET = "It's a Secret to Everybody"
GITHUB_TEST_BODY = b"Hello, World!"
GITHUB_TEST_EXPECTED_SIGNATURE = (
    "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"
)

# 26 MB body size limit (GitHub max is 25 MB)
MAX_WEBHOOK_BODY_BYTES = 26 * 1024 * 1024


class GitHubWebhookHandler:
    """Enterprise GitHub webhook verification and event dispatcher."""

    def __init__(
        self,
        primary_secret: Optional[str] = None,
        previous_secret: Optional[str] = None,
        repo: Optional[PullRequestRepository] = None,
    ) -> None:
        self.primary_secret = primary_secret or os.getenv("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
        self.previous_secret = previous_secret or os.getenv("WEBHOOK_SECRET_PREVIOUS")
        self.repo = repo or PullRequestRepository.get_instance()
        self.branch_mgr = PRBranchManager(self.repo)

    @staticmethod
    def verify_signature(
        raw_body: bytes,
        secret: str,
        signature_header: Optional[str],
    ) -> bool:
        """Verify GitHub HMAC-SHA256 signature using constant-time comparison (SEC-API-28)."""
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        if not secret:
            return False

        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature_header)

    def verify_request(
        self,
        raw_body: bytes,
        signature_header: Optional[str],
    ) -> bool:
        """Verify signature supporting two active secrets during rotation (SEC-API-30)."""
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            return False

        # Try primary secret
        if self.verify_signature(raw_body, self.primary_secret, signature_header):
            return True

        # Try previous secret if present during rotation
        if self.previous_secret and self.verify_signature(
            raw_body, self.previous_secret, signature_header
        ):
            return True

        return False

    def handle_webhook(
        self,
        delivery_id: str,
        event: str,
        raw_body: bytes,
        signature_header: Optional[str],
    ) -> Tuple[int, Dict[str, Any]]:
        """Process incoming webhook delivery.

        Returns (http_status_code, response_payload).
        """
        # 1. Enforce payload body size limit
        if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
            logger.warning("Webhook body exceeded size limit: %d bytes", len(raw_body))
            return 413, {"error": {"code": "PAYLOAD_TOO_LARGE", "message": "Body exceeds 26 MB limit."}}

        # 2. Verify signature with constant-time comparison
        if not self.verify_request(raw_body, signature_header):
            logger.warning("Webhook signature verification failed for delivery %s", delivery_id)
            return 401, {
                "error": {
                    "code": "WEBHOOK_SIGNATURE_INVALID",
                    "message": "HMAC-SHA256 signature verification failed.",
                }
            }

        # 3. Deduplicate: Replays return 200 immediately (AIDS §3.10.2 Step 3)
        delivery, is_duplicate = self.repo.record_webhook_delivery(
            delivery_id=delivery_id,
            event=event,
            status=WebhookDeliveryStatus.RECEIVED,
        )
        if is_duplicate:
            return 200, {
                "status": "REPLAY",
                "delivery_id": delivery_id,
                "event": event,
                "message": "Delivery already received; idempotently accepted.",
            }

        # 4. Parse payload JSON safely
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as e:
            self.repo.update_webhook_status(delivery_id, WebhookDeliveryStatus.FAILED)
            return 400, {"error": {"code": "INVALID_JSON", "message": f"Malformed JSON: {str(e)}"}}

        # 5. Route Event
        action = payload.get("action")
        repository_data = payload.get("repository", {})
        repo_id = str(repository_data.get("id", "unknown-repo"))

        try:
            if event == "pull_request":
                self._handle_pull_request_event(payload, repo_id, action)
                self.repo.update_webhook_status(delivery_id, WebhookDeliveryStatus.PROCESSED)
                return 202, {
                    "status": "ACCEPTED",
                    "delivery_id": delivery_id,
                    "event": event,
                    "action": action,
                    "message": f"PR event '{action}' processed successfully.",
                }
            elif event == "push":
                self._handle_push_event(payload, repo_id)
                self.repo.update_webhook_status(delivery_id, WebhookDeliveryStatus.PROCESSED)
                return 202, {
                    "status": "ACCEPTED",
                    "delivery_id": delivery_id,
                    "event": event,
                    "message": "Push event processed successfully.",
                }
            else:
                # Other events (ping, installation, etc.) are accepted and ignored (AIDS §3.10.3)
                self.repo.update_webhook_status(delivery_id, WebhookDeliveryStatus.IGNORED)
                return 200, {
                    "status": "IGNORED",
                    "delivery_id": delivery_id,
                    "event": event,
                    "message": f"Event '{event}' acknowledged.",
                }
        except Exception as e:
            logger.error("Error processing webhook %s: %s", delivery_id, str(e), exc_info=True)
            self.repo.update_webhook_status(delivery_id, WebhookDeliveryStatus.FAILED)
            return 500, {"error": {"code": "PROCESSING_FAILED", "message": str(e)}}

    def _handle_pull_request_event(
        self,
        payload: Dict[str, Any],
        repo_id: str,
        action: Optional[str],
    ) -> None:
        """Handle GitHub pull_request events: opened, reopened, synchronize, closed."""
        pr_data = payload.get("pull_request", {})
        number = pr_data.get("number", payload.get("number", 0))
        title = pr_data.get("title", f"Pull Request #{number}")
        author_login = pr_data.get("user", {}).get("login", "unknown")

        base_info = pr_data.get("base", {})
        head_info = pr_data.get("head", {})

        base_ref = base_info.get("ref", "main")
        base_sha = base_info.get("sha", "0" * 40)
        head_ref = head_info.get("ref", "head-branch")
        head_sha = head_info.get("sha", "1" * 40)

        # Check fork: head repo full name differs from base repo full name
        base_repo_name = base_info.get("repo", {}).get("full_name")
        head_repo_name = head_info.get("repo", {}).get("full_name")
        is_fork = bool(head_repo_name and base_repo_name and (head_repo_name != base_repo_name))

        draft = pr_data.get("draft", False)

        if action in ("opened", "reopened", "ready_for_review"):
            # Upsert PR record
            pr = PullRequest(
                repository_id=repo_id,
                number=number,
                title=title,
                author_login=author_login,
                base_ref=base_ref,
                head_ref=head_ref,
                head_repo_full_name=head_repo_name,
                base_sha=base_sha,
                head_sha=head_sha,
                state=PRState.OPEN,
                is_fork=is_fork,
                draft=draft,
                last_synced_at=datetime.now(timezone.utc),
            )
            self.repo.upsert_pull_request(pr)

        elif action == "synchronize":
            # Author pushed new commits or force-pushed
            existing_pr = self.repo.get_pull_request_by_number(repo_id, number)
            if existing_pr:
                existing_pr.head_sha = head_sha
                existing_pr.last_synced_at = datetime.now(timezone.utc)
                # Mark previous review runs stale
                self.repo.mark_review_runs_stale(existing_pr.id)
            else:
                pr = PullRequest(
                    repository_id=repo_id,
                    number=number,
                    title=title,
                    author_login=author_login,
                    base_ref=base_ref,
                    head_ref=head_ref,
                    head_repo_full_name=head_repo_name,
                    base_sha=base_sha,
                    head_sha=head_sha,
                    state=PRState.OPEN,
                    is_fork=is_fork,
                    draft=draft,
                    last_synced_at=datetime.now(timezone.utc),
                )
                self.repo.upsert_pull_request(pr)

        elif action == "closed":
            merged = pr_data.get("merged", False)
            existing_pr = self.repo.get_pull_request_by_number(repo_id, number)
            if existing_pr:
                existing_pr.state = PRState.MERGED if merged else PRState.CLOSED
                existing_pr.last_synced_at = datetime.now(timezone.utc)

    def _handle_push_event(self, payload: Dict[str, Any], repo_id: str) -> None:
        """Handle push event to a tracked branch (AIDS §3.10.3)."""
        ref = payload.get("ref", "")
        after_sha = payload.get("after")
        deleted = payload.get("deleted", False)

        if not deleted and after_sha:
            logger.info("Tracked push for repo %s on ref %s -> %s", repo_id, ref, after_sha)
