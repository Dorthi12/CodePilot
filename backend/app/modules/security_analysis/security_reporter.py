"""Security reporter building comprehensive scan reports and disclosures.

Specifications:
- Master Architecture Specification v2.1 §10 (M6)
- Acceptance Criteria: Scan report includes coverage and explicitly states what was not checked.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from shared.types.agent import RunStatus
from shared.types.findings import Finding, ToolCoverage
from shared.types.security import SecurityScanReport


class SecurityReporter:
    """Builds consolidated security reports enforcing coverage disclosure."""

    def build_report(
        self,
        scan_id: str,
        run_id: str,
        job_id: str,
        snapshot_id: str,
        scan_profile: str,
        tool_coverages: List[ToolCoverage],
        not_checked_items: List[str],
        findings: List[Finding],
        secret_findings_count: int,
        dependency_findings_count: int,
        sast_findings_count: int,
        warnings: List[str],
        started_at: datetime,
        completed_at: Optional[datetime] = None,
    ) -> SecurityScanReport:
        counts_by_severity: Dict[str, int] = {}
        counts_by_origin: Dict[str, int] = {}

        for f in findings:
            s_val = f.severity.value
            counts_by_severity[s_val] = counts_by_severity.get(s_val, 0) + 1
            o_val = f.origin.value
            counts_by_origin[o_val] = counts_by_origin.get(o_val, 0) + 1

        # Partial status if any tool failed or timed out
        has_failed_tool = any(tc.status in ("FAILED", "TIMEOUT") for tc in tool_coverages)
        status = RunStatus.PARTIAL if has_failed_tool else RunStatus.COMPLETED

        # Ensure not_checked list is deduplicated while preserving order
        deduped_not_checked: List[str] = []
        for item in not_checked_items:
            if item not in deduped_not_checked:
                deduped_not_checked.append(item)

        return SecurityScanReport(
            scan_id=scan_id,
            run_id=run_id,
            job_id=job_id,
            snapshot_id=snapshot_id,
            run_type="SECURITY",
            status=status,
            scan_profile=scan_profile,
            tool_coverage=tool_coverages,
            not_checked=deduped_not_checked,
            total_findings=len(findings),
            counts_by_severity=counts_by_severity,
            counts_by_origin=counts_by_origin,
            sast_findings_count=sast_findings_count,
            secret_findings_count=secret_findings_count,
            dependency_findings_count=dependency_findings_count,
            warnings=warnings,
            started_at=started_at,
            completed_at=completed_at or datetime.now(timezone.utc),
        )
