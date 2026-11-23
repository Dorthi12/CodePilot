"""Patch exporter: serializes unified diffs safely with attachment headers.

Specifications:
- Master Architecture Specification v2.1 §14.4 (Patch statuses and exports)
- API and Data Specification v1.0 §3.3 (E-083)
- Security & Testing Specification v1.0 §7.3.4 (SEC-API-09: Content-Disposition attachment)
"""

from typing import Dict, Tuple
from shared.types.patch import PatchArtifact
from backend.app.modules.patching.approval_binding import ApprovalBindingService


class PatchExporter:
    """Handles serialization and security headers for patch export."""

    @staticmethod
    def export_unified_diff(patch: PatchArtifact) -> Tuple[str, Dict[str, str]]:
        """Validate approval and export unified diff with secure download headers."""
        if patch.status != "APPROVED":
            raise ValueError(f"Cannot export patch with status '{patch.status}'. Must be 'APPROVED'.")

        current_hash = ApprovalBindingService.compute_diff_hash(patch.unified_diff)
        valid_approvals = [
            a for a in patch.approvals
            if ApprovalBindingService.verify_approval(a, patch.unified_diff, required_scope="EXPORT")
        ]

        if not valid_approvals:
            raise ValueError("EXPORT_APPROVAL_REQUIRED: No valid unexpired EXPORT approval bound to current diff hash.")

        filename = f"codepilot-fix-{patch.id[:8]}.diff"
        headers = {
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        }
        return patch.unified_diff, headers
