"""GitHub Pull Request Adapter for fetching PR data and synchronizing PRs.

Specifications:
- Master Architecture Specification v2.1 §10 (M7)
- API and Data Specification v1.0 §3.4.15
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from shared.types.pull_requests import PullRequest, PRState


class GitHubPullRequestAdapter:
    """Adapter for interacting with GitHub Pull Request APIs."""

    @staticmethod
    def format_pr_from_github_api(payload: Dict[str, Any], repository_id: str) -> PullRequest:
        """Translate GitHub REST API response into internal PullRequest model."""
        number = payload.get("number", 1)
        title = payload.get("title", f"PR #{number}")
        author_login = payload.get("user", {}).get("login", "unknown")

        base_info = payload.get("base", {})
        head_info = payload.get("head", {})

        base_ref = base_info.get("ref", "main")
        base_sha = base_info.get("sha", "0" * 40)
        head_ref = head_info.get("ref", "feature")
        head_sha = head_info.get("sha", "1" * 40)

        base_repo_name = base_info.get("repo", {}).get("full_name")
        head_repo_name = head_info.get("repo", {}).get("full_name")
        is_fork = bool(head_repo_name and base_repo_name and (head_repo_name != base_repo_name))

        state_str = payload.get("state", "open").upper()
        if payload.get("merged", False):
            state = PRState.MERGED
        elif state_str == "CLOSED":
            state = PRState.CLOSED
        else:
            state = PRState.OPEN

        return PullRequest(
            repository_id=repository_id,
            number=number,
            title=title,
            author_login=author_login,
            base_ref=base_ref,
            head_ref=head_ref,
            head_repo_full_name=head_repo_name,
            base_sha=base_sha,
            head_sha=head_sha,
            state=state,
            is_fork=is_fork,
            draft=payload.get("draft", False),
            last_synced_at=datetime.now(timezone.utc),
        )
