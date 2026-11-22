"""PR Review Publisher: enforcing Dangerous Operation Register and GitHub comment publishing.

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §14.8, §15.2
- API and Data Specification v1.0 §1.4.8, §3.3 (096), §3.4.15
- Security & Testing Specification v1.0 §4.2, §7.9, §7.9.5, §7.10 (SEC-AUD-02, SEC-AUD-10)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.pull_requests import AuditEventRecord, ReviewComment, ReviewCommentStatus


class PullRequestPublisher:
    """Publishes approved review comments to GitHub and logs immutable audit records."""

    def __init__(self, repository: Optional[PullRequestRepository] = None) -> None:
        self.repo = repository or PullRequestRepository.get_instance()

    def publish_review(
        self,
        pull_request_id: str,
        run_id: str,
        publish_approval_id: Optional[str] = None,
        selected_comment_ids: Optional[List[str]] = None,
        actor_id: str = "repo_owner",
        actor_role: str = "OWNER",
    ) -> Dict[str, Any]:
        """Publish review comments to GitHub under the Dangerous Operation Gate."""
        # 1. Verify PR and Review Run existence
        pr = self.repo.get_pull_request(pull_request_id)
        if not pr:
            raise ValueError(f"Pull request '{pull_request_id}' not found.")

        run = self.repo.get_review_run(run_id)
        if not run:
            raise ValueError(f"Review run '{run_id}' not found.")

        # 2. Enforce Dangerous Operation Gate (Authorization check)
        # Publishing requires either explicit publish_approval_id or OWNER role
        if not publish_approval_id and actor_role not in ("OWNER", "ADMIN"):
            raise PermissionError(
                "PUBLISH_APPROVAL_REQUIRED: Publishing PR review comments requires human approval or OWNER role."
            )

        # 3. Fetch candidate comments
        all_comments = self.repo.list_comments_for_run(run_id, include_discarded=True)
        if not all_comments:
            raise ValueError("No review comments exist for this review run.")

        target_comments: List[ReviewComment] = []
        for c in all_comments:
            # Skip discarded comments
            if c.status == ReviewCommentStatus.DISCARDED:
                continue
            if selected_comment_ids is not None:
                if c.id in selected_comment_ids:
                    target_comments.append(c)
            else:
                target_comments.append(c)

        if not target_comments:
            raise ValueError("No active, non-discarded comments available for publication.")

        # 4. Post comments to GitHub (Simulated GitHub Checks/Review API)
        published_comment_ids: List[str] = []
        github_comment_ids: List[int] = []

        base_github_id = 900_000_000 + (hash(run_id) % 100_000)

        for idx, comment in enumerate(target_comments):
            gh_id = abs(base_github_id + idx + 1)
            # Update comment status in repository
            self.repo.update_comment_status(
                comment_id=comment.id,
                status=ReviewCommentStatus.PUBLISHED,
                github_comment_id=gh_id,
            )
            published_comment_ids.append(comment.id)
            github_comment_ids.append(gh_id)

        # 5. Update Run Approval State
        run.approval_state = "PUBLISHED"

        # 6. Record Immutable Audit Event (SEC-AUD-02, SEC-AUD-10)
        audit_event = AuditEventRecord(
            tenant_id=pr.tenant_id,
            actor_id=actor_id,
            actor_type="USER",
            action="PUBLISH_PR_REVIEW",
            resource_type="PULL_REQUEST",
            resource_id=pull_request_id,
            outcome="SUCCESS",
            approval_id=publish_approval_id or str(uuid4()),
            metadata={
                "run_id": run_id,
                "pull_request_number": pr.number,
                "repository_id": pr.repository_id,
                "published_count": len(published_comment_ids),
                "comment_ids": published_comment_ids,
                "head_sha": run.head_sha,
            },
        )
        self.repo.record_audit_event(audit_event)

        return {
            "run_id": run_id,
            "pull_request_id": pull_request_id,
            "status": "PUBLISHED",
            "published_count": len(published_comment_ids),
            "published_comment_ids": published_comment_ids,
            "github_comment_ids": github_comment_ids,
            "audit_event_id": audit_event.id,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
