"""Thread-safe Repository for Mastermind Feature 7: Pull Requests, Review Runs, and Webhooks.

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §6.5, §6.6
- API and Data Specification v1.0 §3.3, §3.10, §4.5, §4.6
- Security and Testing Specification v1.0 §7.3.10, §7.9, §8.9 (AI-16)
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.pull_requests import (
    AuditEventRecord,
    PRFile,
    PRState,
    PullRequest,
    ReviewComment,
    ReviewCommentStatus,
    ReviewRunRecord,
    WebhookDelivery,
    WebhookDeliveryStatus,
)


class PullRequestRepository:
    """Thread-safe in-memory and transactional repository for PR review operations."""

    _instance: Optional["PullRequestRepository"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._pull_requests: Dict[str, PullRequest] = {}  # id -> PullRequest
        self._pr_by_repo_num: Dict[tuple[str, int], str] = {}  # (repo_id, number) -> id
        self._pr_files: Dict[str, List[PRFile]] = {}  # pr_id -> list[PRFile]
        self._review_runs: Dict[str, ReviewRunRecord] = {}  # run_id -> ReviewRunRecord
        self._review_comments: Dict[str, ReviewComment] = {}  # comment_id -> ReviewComment
        self._comments_by_run: Dict[str, List[str]] = {}  # run_id -> list[comment_id]
        self._webhook_deliveries: Dict[str, WebhookDelivery] = {}  # delivery_id -> WebhookDelivery
        self._audit_events: List[AuditEventRecord] = []

    @classmethod
    def get_instance(cls) -> "PullRequestRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear(self) -> None:
        """Reset repository state for isolated tests."""
        with self._lock:
            self._pull_requests.clear()
            self._pr_by_repo_num.clear()
            self._pr_files.clear()
            self._review_runs.clear()
            self._review_comments.clear()
            self._comments_by_run.clear()
            self._webhook_deliveries.clear()
            self._audit_events.clear()

    # --- Pull Requests ---

    def upsert_pull_request(self, pr: PullRequest) -> PullRequest:
        with self._lock:
            existing_id = self._pr_by_repo_num.get((pr.repository_id, pr.number))
            if existing_id:
                # Update existing
                existing = self._pull_requests[existing_id]
                existing.title = pr.title
                existing.author_login = pr.author_login
                existing.base_ref = pr.base_ref
                existing.head_ref = pr.head_ref
                existing.head_repo_full_name = pr.head_repo_full_name
                existing.base_sha = pr.base_sha
                existing.head_sha = pr.head_sha
                existing.base_snapshot_id = pr.base_snapshot_id or existing.base_snapshot_id
                existing.head_snapshot_id = pr.head_snapshot_id or existing.head_snapshot_id
                existing.state = pr.state
                existing.is_fork = pr.is_fork
                existing.draft = pr.draft
                existing.last_synced_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
                return existing

            self._pull_requests[pr.id] = pr
            self._pr_by_repo_num[(pr.repository_id, pr.number)] = pr.id
            return pr

    def get_pull_request(self, pr_id: str) -> Optional[PullRequest]:
        with self._lock:
            return self._pull_requests.get(pr_id)

    def get_pull_request_by_number(self, repository_id: str, number: int) -> Optional[PullRequest]:
        with self._lock:
            pr_id = self._pr_by_repo_num.get((repository_id, number))
            if pr_id:
                return self._pull_requests.get(pr_id)
            return None

    def list_pull_requests(
        self,
        repository_id: str,
        state: Optional[PRState] = None,
    ) -> List[PullRequest]:
        with self._lock:
            res = [
                pr for pr in self._pull_requests.values()
                if pr.repository_id == repository_id
            ]
            if state:
                res = [pr for pr in res if pr.state == state]
            # Order descending by number
            return sorted(res, key=lambda x: x.number, reverse=True)

    # --- PR Files ---

    def save_pr_files(self, pr_id: str, files: List[PRFile]) -> None:
        with self._lock:
            self._pr_files[pr_id] = files

    def get_pr_files(self, pr_id: str) -> List[PRFile]:
        with self._lock:
            return list(self._pr_files.get(pr_id, []))

    # --- Review Runs ---

    def create_review_run(self, run: ReviewRunRecord) -> ReviewRunRecord:
        with self._lock:
            self._review_runs[run.id] = run
            # Update PR latest_review_run_id
            pr = self._pull_requests.get(run.pull_request_id)
            if pr:
                pr.latest_review_run_id = run.id
            return run

    def get_review_run(self, run_id: str) -> Optional[ReviewRunRecord]:
        with self._lock:
            run = self._review_runs.get(run_id)
            if run:
                # Refresh comments from comments store
                comment_ids = self._comments_by_run.get(run_id, [])
                run.comments = [
                    self._review_comments[cid] for cid in comment_ids
                    if cid in self._review_comments
                ]
            return run

    def mark_review_runs_stale(self, pr_id: str) -> int:
        """Mark existing review runs for a PR as stale (e.g. on new commit / synchronize)."""
        count = 0
        with self._lock:
            for run in self._review_runs.values():
                if run.pull_request_id == pr_id and not run.stale:
                    run.stale = True
                    run.approval_state = "STALE"
                    count += 1
        return count

    # --- Review Comments ---

    def add_comment(self, comment: ReviewComment) -> ReviewComment:
        with self._lock:
            self._review_comments[comment.id] = comment
            self._comments_by_run.setdefault(comment.run_id, []).append(comment.id)
            return comment

    def get_comment(self, comment_id: str) -> Optional[ReviewComment]:
        with self._lock:
            return self._review_comments.get(comment_id)

    def update_comment_status(
        self,
        comment_id: str,
        status: ReviewCommentStatus,
        body: Optional[str] = None,
        github_comment_id: Optional[int] = None,
    ) -> Optional[ReviewComment]:
        with self._lock:
            comment = self._review_comments.get(comment_id)
            if not comment:
                return None
            comment.status = status
            if body is not None:
                comment.body = body
            if github_comment_id is not None:
                comment.github_comment_id = github_comment_id
            comment.version += 1
            comment.updated_at = datetime.now(timezone.utc)
            return comment

    def list_comments_for_run(
        self,
        run_id: str,
        include_discarded: bool = True,
    ) -> List[ReviewComment]:
        with self._lock:
            comment_ids = self._comments_by_run.get(run_id, [])
            res = [
                self._review_comments[cid] for cid in comment_ids
                if cid in self._review_comments
            ]
            if not include_discarded:
                res = [c for c in res if c.status != ReviewCommentStatus.DISCARDED]
            return res

    # --- Webhook Deliveries (Deduplication) ---

    def record_webhook_delivery(
        self,
        delivery_id: str,
        event: str,
        repository_id: Optional[str] = None,
        status: WebhookDeliveryStatus = WebhookDeliveryStatus.RECEIVED,
    ) -> tuple[WebhookDelivery, bool]:
        """Record a webhook delivery. Returns (delivery, is_duplicate).

        If delivery_id already exists, returns (existing, True) for replay idempotency.
        """
        with self._lock:
            if delivery_id in self._webhook_deliveries:
                return self._webhook_deliveries[delivery_id], True

            delivery = WebhookDelivery(
                delivery_id=delivery_id,
                event=event,
                repository_id=repository_id,
                status=status,
            )
            self._webhook_deliveries[delivery_id] = delivery
            return delivery, False

    def update_webhook_status(self, delivery_id: str, status: WebhookDeliveryStatus) -> None:
        with self._lock:
            if delivery_id in self._webhook_deliveries:
                self._webhook_deliveries[delivery_id].status = status

    def get_webhook_delivery(self, delivery_id: str) -> Optional[WebhookDelivery]:
        with self._lock:
            return self._webhook_deliveries.get(delivery_id)

    # --- Audit Events ---

    def record_audit_event(self, event: AuditEventRecord) -> AuditEventRecord:
        with self._lock:
            self._audit_events.append(event)
            return event

    def list_audit_events(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> List[AuditEventRecord]:
        with self._lock:
            res = list(self._audit_events)
            if resource_type:
                res = [e for e in res if e.resource_type == resource_type]
            if resource_id:
                res = [e for e in res if e.resource_id == resource_id]
            return res
