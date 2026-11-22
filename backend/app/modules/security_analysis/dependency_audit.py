"""Dependency vulnerability auditor adapter.

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §6.6
- Security and Testing Specification v1.0 §7.6 (SEC-DEP-09):
  Read from manifests without installing anything.
"""

import time
from typing import Dict, List, Optional, Tuple
from shared.types.findings import Finding, ToolCoverage, ToolExecutionLog
from shared.types.security import DependencyInventoryItem
from ai_service.security_analysis.dependency_scanner import DependencyScanner


class DependencyAuditor:
    """Coordinates manifest analysis and known advisory vulnerability scanning."""

    def __init__(self, scanner: Optional[DependencyScanner] = None) -> None:
        self.scanner = scanner or DependencyScanner()

    def run_audit(
        self,
        files: Dict[str, str],
        snapshot_id: str,
        run_id: str,
        simulate_feed_failure: bool = False,
    ) -> Tuple[List[DependencyInventoryItem], List[Finding], ToolCoverage, ToolExecutionLog, List[str], List[str]]:
        t0 = time.perf_counter()
        inventory: List[DependencyInventoryItem] = []
        findings: List[Finding] = []
        warnings: List[str] = []
        not_checked_items: List[str] = []

        if simulate_feed_failure:
            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            coverage = ToolCoverage(
                tool="dependency_audit",
                version="1.0.0",
                status="FAILED",
                duration_ms=dur_ms,
                files_scanned=0,
                error="Vulnerability advisory feed unavailable",
            )
            log = ToolExecutionLog(
                run_id=run_id,
                tool="dependency_audit",
                tool_version="1.0.0",
                status="FAILED",
                duration_ms=dur_ms,
                stderr_redacted="Vulnerability advisory feed unreachable",
            )
            not_checked_items.append("Dependency vulnerability advisories (feed unavailable)")
            warnings.append("Advisory feed unavailable: dependencies could not be evaluated for known CVEs.")
            return inventory, findings, coverage, log, warnings, not_checked_items

        try:
            inventory, findings, scan_warns = self.scanner.scan_manifests(
                snapshot_id=snapshot_id,
                run_id=run_id,
                files=files,
            )
            warnings.extend(scan_warns)

            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            manifest_files = [p for p in files.keys() if any(m in p.lower() for m in ("requirements", "pyproject.toml", "package.json"))]
            coverage = ToolCoverage(
                tool="dependency_audit",
                version="1.0.0",
                status="SUCCESS",
                duration_ms=dur_ms,
                files_scanned=len(manifest_files),
                rules_run=len(self.scanner.advisories),
                findings_count=len(findings),
            )
            log = ToolExecutionLog(
                run_id=run_id,
                tool="dependency_audit",
                tool_version="1.0.0",
                status="SUCCESS",
                duration_ms=dur_ms,
                coverage={"manifests_scanned": len(manifest_files), "packages_inventoried": len(inventory)},
            )
            return inventory, findings, coverage, log, warnings, not_checked_items

        except Exception as e:
            dur_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            coverage = ToolCoverage(
                tool="dependency_audit",
                version="1.0.0",
                status="FAILED",
                duration_ms=dur_ms,
                error=str(e),
            )
            log = ToolExecutionLog(
                run_id=run_id,
                tool="dependency_audit",
                tool_version="1.0.0",
                status="FAILED",
                duration_ms=dur_ms,
                stderr_redacted=str(e),
            )
            not_checked_items.append(f"Dependency vulnerability check failed: {str(e)}")
            warnings.append(f"Dependency audit failed: {str(e)}")
            return inventory, findings, coverage, log, warnings, not_checked_items
