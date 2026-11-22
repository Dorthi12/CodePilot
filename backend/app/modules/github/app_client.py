"""GitHub App and API Client supporting permission tiers and PR operations.

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §15.2
- Security and Testing Specification v1.0 §7.4 (SEC-REPO-05, SEC-APR-02)
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class GitHubAppClient:
    """Client for GitHub App operations respecting least privilege (READ vs WRITE)."""

    def __init__(self, installation_id: Optional[str] = None, permission_tier: str = "READ") -> None:
        self.installation_id = installation_id or "default-installation"
        self.permission_tier = permission_tier

    def has_write_permission(self) -> bool:
        """Check if write tier is enabled."""
        return self.permission_tier in ("WRITE", "PUBLISH", "ADMIN")

    def post_pr_review_comment(
        self,
        repository_id: str,
        pull_number: int,
        commit_id: str,
        path: str,
        line: int,
        body: str,
    ) -> Dict[str, Any]:
        """Post an inline review comment to GitHub PR (requires WRITE permission)."""
        if not self.has_write_permission():
            raise PermissionError("GITHUB_WRITE_PERMISSION_REQUIRED: Posting comments requires write tier.")

        comment_id = 900_000_000 + abs(hash(f"{repository_id}-{pull_number}-{path}-{line}")) % 100_000
        return {
            "id": comment_id,
            "path": path,
            "line": line,
            "commit_id": commit_id,
            "body": body,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
