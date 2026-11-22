"""Approval binding and cryptographic integrity for CodePilot Patch Core.

Specifications:
- Master Architecture Specification v2.1 §14.4, §15
- Security & Testing Specification v1.0 §7.9 (Approval and Dangerous-Operation Controls), §7.9.4
- System Design Specification v1.0 §9.6
"""

from datetime import datetime, timezone, timedelta
import hashlib
from typing import Optional
from shared.types.patch import PatchApproval


class ApprovalBindingService:
    """Manages diff hash binding, approval scopes, and expiration logic."""

    DEFAULT_TTL_MINUTES = 30

    @staticmethod
    def compute_diff_hash(unified_diff: str) -> str:
        """Compute SHA256 of the unified diff string."""
        clean = unified_diff.strip() if unified_diff else ""
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    @staticmethod
    def create_approval(
        diff_sha256: str,
        approver_id: str,
        scope: str = "EXPORT",
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
    ) -> PatchApproval:
        """Create a cryptographic patch approval bound to diff_sha256 and scope."""
        now = datetime.now(timezone.utc)
        return PatchApproval(
            scope=scope,
            diff_sha256=diff_sha256,
            approver_id=approver_id,
            created_at=now,
        )

    @staticmethod
    def verify_approval(
        approval: PatchApproval,
        current_diff: str,
        required_scope: str = "EXPORT",
        max_age_minutes: int = DEFAULT_TTL_MINUTES,
    ) -> bool:
        """Verify that an approval is bound to the exact diff hash, matches scope, and has not expired."""
        current_hash = ApprovalBindingService.compute_diff_hash(current_diff)
        if approval.diff_sha256 != current_hash:
            return False

        if approval.scope != required_scope:
            return False

        now = datetime.now(timezone.utc)
        created_at = approval.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if (now - created_at) > timedelta(minutes=max_age_minutes):
            return False

        return True
