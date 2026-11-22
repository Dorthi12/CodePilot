"""Pull Request Review Manager coordinating reviews, draft comments, and comment triage.

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoints 092–096)
- API and Data Specification v1.0 §3.3 (092–096), §3.4.15
- Security & Testing Specification v1.0 §7.9, §8.9 (AI-16)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agentic.workflows.pull_request_review import PullRequestReviewWorkflow
from backend.app.modules.pull_requests.branch_manager import PRBranchManager
from backend.app.modules.pull_requests.publisher import PullRequestPublisher
from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.pull_requests import (
    PRState,
    PullRequest,
    ReviewComment,
    ReviewCommentStatus,
    ReviewRunRecord,
)


class PullRequestReviewManager:
    """Manages PR reviews, SHA pinning, comment lifecycle, and publishing."""

    _instance: Optional["PullRequestReviewManager"] = None

    def __init__(
        self,
        repo: Optional[PullRequestRepository] = None,
        publisher: Optional[PullRequestPublisher] = None,
        branch_mgr: Optional[PRBranchManager] = None,
    ) -> None:
        self.repo = repo or PullRequestRepository.get_instance()
        self.publisher = publisher or PullRequestPublisher(self.repo)
        self.branch_mgr = branch_mgr or PRBranchManager(self.repo)
        self.workflow = PullRequestReviewWorkflow(pr_repo=self.repo)

    @classmethod
    def get_instance(cls) -> "PullRequestReviewManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def list_pull_requests(
        self,
        repository_id: str,
        state: Optional[str] = None,
    ) -> List[PullRequest]:
        """List pull requests for repository (Endpoint 092)."""
        pr_state = PRState(state.upper()) if state else None
        return self.repo.list_pull_requests(repository_id, pr_state)

    def start_review_run(
        self,
        pull_request_id: str,
        base_sha: str,
        head_sha: str,
        review_profile: str = "standard",
        unified_diff: Optional[str] = None,
        base_snapshot_id: Optional[str] = None,
        head_snapshot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a PR review run pinned to base/head SHAs (Endpoint 093)."""
        pr = self.repo.get_pull_request(pull_request_id)
        if not pr:
            raise KeyError(f"Pull request '{pull_request_id}' not found.")

        # Pinning check: If head_sha does not match PR head_sha (force-push occurred)
        # return 409 PR_HEAD_CHANGED (API Spec §3.4.15)
        if pr.head_sha != head_sha:
            self.repo.mark_review_runs_stale(pr.id)
            raise ValueError("PR_HEAD_CHANGED")

        # Execute workflow
        res_bundle = self.workflow.run_review(
            pull_request_id=pull_request_id,
            base_sha=base_sha,
            head_sha=head_sha,
            review_profile=review_profile,
            diff_text=unified_diff,
            base_snapshot_id=base_snapshot_id,
            head_snapshot_id=head_snapshot_id,
        )

        return res_bundle.__dict__

    def get_review_draft(
        self,
        pull_request_id: str,
        run_id: str,
    ) -> Dict[str, Any]:
        """Retrieve draft review summary, comments, and impact (Endpoint 094)."""
        pr = self.repo.get_pull_request(pull_request_id)
        if not pr:
            raise KeyError(f"Pull request '{pull_request_id}' not found.")

        run = self.repo.get_review_run(run_id)
        if not run:
            raise KeyError(f"Review run '{run_id}' not found.")

        comments = self.repo.list_comments_for_run(run_id, include_discarded=True)

        return {
            "run_id": run.id,
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "base_sha": run.base_sha,
            "head_sha": run.head_sha,
            "review_profile": run.review_profile,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "summary": run.summary,
            "impacted_modules": run.impacted_modules,
            "tests_to_run": run.tests_to_run,
            "comments": comments,
            "approval_state": run.approval_state,
            "stale": run.stale,
            "created_at": run.created_at,
            "completed_at": run.completed_at,
        }

    def edit_or_discard_comment(
        self,
        pull_request_id: str,
        run_id: str,
        comment_id: str,
        body: Optional[str] = None,
        status: Optional[str] = None,
    ) -> ReviewComment:
        """Edit or discard a draft comment before publish (Endpoint 095)."""
        pr = self.repo.get_pull_request(pull_request_id)
        if not pr:
            raise KeyError(f"Pull request '{pull_request_id}' not found.")

        run = self.repo.get_review_run(run_id)
        if not run:
            raise KeyError(f"Review run '{run_id}' not found.")

        comment = self.repo.get_comment(comment_id)
        if not comment or comment.run_id != run_id:
            raise KeyError(f"Review comment '{comment_id}' not found for run '{run_id}'.")

        # Cannot edit or discard if already published
        if comment.status == ReviewCommentStatus.PUBLISHED:
            raise ValueError("COMMENT_ALREADY_PUBLISHED: Cannot edit or discard an already published comment.")

        new_status = comment.status
        if status:
            new_status = ReviewCommentStatus(status.upper())
        elif body is not None and body != comment.body:
            new_status = ReviewCommentStatus.EDITED

        updated = self.repo.update_comment_status(
            comment_id=comment_id,
            status=new_status,
            body=body,
        )
        return updated or comment

    def publish_review(
        self,
        pull_request_id: str,
        run_id: str,
        publish_approval_id: Optional[str] = None,
        comment_ids: Optional[List[str]] = None,
        actor_id: str = "repo_owner",
        actor_role: str = "OWNER",
    ) -> Dict[str, Any]:
        """Publish approved comments to GitHub (Endpoint 096)."""
        return self.publisher.publish_review(
            pull_request_id=pull_request_id,
            run_id=run_id,
            publish_approval_id=publish_approval_id,
            selected_comment_ids=comment_ids,
            actor_id=actor_id,
            actor_role=actor_role,
        )
