"""PR Branch and Ref Manager: SHA validation, fork handling, and synchronization.

Specifications:
- Master Architecture Specification v2.1 §10 (M7), AUD-10
- API and Data Specification v1.0 §3.4.15, §3.10.3
- Security & Testing Specification v1.0 §7.3.10 (SEC-API-31)
"""

from typing import Optional, Tuple
from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.pull_requests import PullRequest


class PRBranchManager:
    """Manages PR branches, fork boundaries, and SHA verification."""

    def __init__(self, repo: Optional[PullRequestRepository] = None) -> None:
        self.repo = repo or PullRequestRepository.get_instance()

    def verify_head_sha(self, pull_request_id: str, expected_head_sha: str) -> Tuple[bool, Optional[str]]:
        """Verify whether expected_head_sha matches current PR head_sha.

        Returns (is_valid, current_head_sha).
        If author force-pushed, is_valid is False.
        """
        pr = self.repo.get_pull_request(pull_request_id)
        if not pr:
            return False, None

        is_match = (pr.head_sha == expected_head_sha)
        return is_match, pr.head_sha

    def is_fork_pr(self, pull_request: PullRequest) -> bool:
        """Check if PR originates from an external fork."""
        return bool(pull_request.is_fork or (
            pull_request.head_repo_full_name
            and "/" in pull_request.head_repo_full_name
        ))

    def update_head_on_synchronize(
        self,
        repository_id: str,
        pr_number: int,
        new_head_sha: str,
    ) -> Optional[PullRequest]:
        """Handle PR synchronize event (new commit or force-push).

        Updates head_sha, marks previous review runs stale.
        """
        pr = self.repo.get_pull_request_by_number(repository_id, pr_number)
        if not pr:
            return None

        pr.head_sha = new_head_sha
        pr.updated_at = pr.last_synced_at

        # Invalidate previous review runs for this PR
        self.repo.mark_review_runs_stale(pr.id)
        return pr
