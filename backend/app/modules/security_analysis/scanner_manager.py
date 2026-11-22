"""Enterprise Security Scanner Manager for Mastermind Feature 6 (M6).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3, §14.2
- API and Data Specification v1.0 §3.3 (089, 090), §3.4.14, §4.6
- Security and Testing Specification v1.0 §7.3.3, §7.4, §8.9 (AI-10), UT-13, UT-26, IT-16, E2E-11
- Anti-tamper & Suppression Enforcement (ST-P04 / SEC-PI-08)
- Zero Raw Secrets Invariant (I9 / SEC-SECRET-01 / SEC-MAL-10)
- Read-only Dependency Manifest Inspection (SEC-DEP-09)
"""

import collections
import fnmatch
import hashlib
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from ai_service.security_analysis.risk_classifier import RiskClassifier
from ai_service.security_analysis.secret_detector import SecretScanner, redact_secrets
from backend.app.modules.security_analysis.dependency_audit import DependencyAuditor
from backend.app.modules.security_analysis.sast_adapter import SASTAdapter
from backend.app.modules.security_analysis.security_reporter import SecurityReporter
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.security_repository import SecurityRepository
from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus, RunStatus
from shared.types.findings import (
    AnalysisRunRecord,
    Finding,
    RuleMetadata,
    Suppression,
    ToolCoverage,
    ToolExecutionLog,
    compute_finding_fingerprint,
)
from shared.types.security import (
    DependencyInventoryItem,
    SecretFindingRecord,
    SecurityScanReport,
)

SEVERITY_RANKS = {
    FindingSeverity.INFO: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


class SecurityScannerManager:
    """Enterprise multi-scanner coordinator with caching, governance, and tamper resistance."""

    _instance: Optional["SecurityScannerManager"] = None
    _singleton_lock = threading.Lock()

    def __init__(
        self,
        security_repo: Optional[SecurityRepository] = None,
        findings_repo: Optional[FindingsRepository] = None,
        sast_adapter: Optional[SASTAdapter] = None,
        dependency_auditor: Optional[DependencyAuditor] = None,
        secret_scanner: Optional[SecretScanner] = None,
        risk_classifier: Optional[RiskClassifier] = None,
        reporter: Optional[SecurityReporter] = None,
    ) -> None:
        self.security_repo = security_repo or SecurityRepository.get_instance()
        self.findings_repo = findings_repo or FindingsRepository.get_instance()
        self.sast_adapter = sast_adapter or SASTAdapter()
        self.dependency_auditor = dependency_auditor or DependencyAuditor()
        self.secret_scanner = secret_scanner or SecretScanner()
        self.risk_classifier = risk_classifier or RiskClassifier()
        self.reporter = reporter or SecurityReporter()

        # Cache key: (file_path, content_hash, tool_name, profile)
        self._scan_cache: "collections.OrderedDict[Tuple[str, str, str, str], List[Finding]]" = collections.OrderedDict()
        self._cache_lock = threading.RLock()
        self._max_cache_entries = 10_000

    @classmethod
    def get_instance(cls) -> "SecurityScannerManager":
        if cls._instance is None:
            with cls._singleton_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear_cache(self) -> None:
        """Clear the incremental content-hash cache."""
        with self._cache_lock:
            self._scan_cache.clear()

    def run_security_scan(
        self,
        snapshot_id: str,
        scan_profile: str = "standard",
        languages: Optional[List[str]] = None,
        include_dependencies: bool = True,
        changed_files_only: bool = False,
        paths: Optional[List[str]] = None,
        changed_files: Optional[List[str]] = None,
        severity_threshold: FindingSeverity = FindingSeverity.LOW,
        repository_id: Optional[str] = None,
        simulate_dependency_failure: bool = False,
        job_id: Optional[str] = None,
        scan_id: Optional[str] = None,
    ) -> SecurityScanReport:
        """Execute end-to-end security vulnerability scan pinned to snapshot_id."""
        started_at = datetime.now(timezone.utc)
        scan_id = scan_id or str(uuid4())
        run_id = scan_id
        job_id_str = job_id or str(uuid4())

        if not SnapshotContextRegistry.contains(snapshot_id):
            raise KeyError(f"Snapshot '{snapshot_id}' is not loaded for security analysis.")

        context = SnapshotContextRegistry.get(snapshot_id)

        # 1. Resolve target files based on scope and changes
        target_files_map, target_paths = self._resolve_target_files(
            context=context,
            paths=paths,
            changed_files_only=changed_files_only,
            changed_files=changed_files,
        )

        tool_coverages: List[ToolCoverage] = []
        all_findings: List[Finding] = []
        all_secret_records: List[SecretFindingRecord] = []
        all_inventory: List[DependencyInventoryItem] = []
        warnings: List[str] = []
        not_checked_items: List[str] = []

        # 2. Secret Scanning (Invariant I9, SEC-SECRET-01, SEC-MAL-10)
        t_sec0 = time.perf_counter()
        try:
            sec_findings, sec_records = self._run_secret_scan(
                files=target_files_map,
                snapshot_id=snapshot_id,
                run_id=run_id,
                scan_profile=scan_profile,
            )
            dur_sec = round((time.perf_counter() - t_sec0) * 1000.0, 2)
            tc_sec = ToolCoverage(
                tool="secret_scanner",
                version="1.0.0",
                status="SUCCESS",
                duration_ms=dur_sec,
                files_scanned=len(target_files_map),
                rules_run=len(self.secret_scanner.patterns),
                findings_count=len(sec_findings),
            )
            tool_coverages.append(tc_sec)
            self.findings_repo.add_tool_execution_log(
                ToolExecutionLog(
                    run_id=run_id,
                    tool="secret_scanner",
                    tool_version="1.0.0",
                    status="SUCCESS",
                    duration_ms=dur_sec,
                    coverage={"files_scanned": len(target_files_map)},
                )
            )
            all_findings.extend(sec_findings)
            all_secret_records.extend(sec_records)
        except Exception as e:
            dur_sec = round((time.perf_counter() - t_sec0) * 1000.0, 2)
            tc_sec = ToolCoverage(
                tool="secret_scanner",
                version="1.0.0",
                status="FAILED",
                duration_ms=dur_sec,
                error=str(e),
            )
            tool_coverages.append(tc_sec)
            self.findings_repo.add_tool_execution_log(
                ToolExecutionLog(
                    run_id=run_id,
                    tool="secret_scanner",
                    tool_version="1.0.0",
                    status="FAILED",
                    duration_ms=dur_sec,
                    stderr_redacted=str(e),
                )
            )
            warnings.append(f"Secret scanner failed: {str(e)}")
            not_checked_items.append("Secret & credential scanning (tool failed)")

        # 3. Static Application Security Testing (SAST - AST & Taint Tracking)
        sast_findings, tc_sast, log_sast, sast_warns = self.sast_adapter.run_sast(
            files=target_files_map,
            snapshot_id=snapshot_id,
            run_id=run_id,
        )
        tool_coverages.append(tc_sast)
        self.findings_repo.add_tool_execution_log(log_sast)
        all_findings.extend(sast_findings)
        warnings.extend(sast_warns)

        # 4. Dependency Vulnerability Audit (SCA - SEC-DEP-09)
        if include_dependencies:
            inv_items, dep_findings, tc_dep, log_dep, dep_warns, dep_not_checked = self.dependency_auditor.run_audit(
                files=target_files_map,
                snapshot_id=snapshot_id,
                run_id=run_id,
                simulate_feed_failure=simulate_dependency_failure,
            )
            tool_coverages.append(tc_dep)
            self.findings_repo.add_tool_execution_log(log_dep)
            all_findings.extend(dep_findings)
            all_inventory.extend(inv_items)
            warnings.extend(dep_warns)
            not_checked_items.extend(dep_not_checked)
        else:
            not_checked_items.append("Dependency vulnerability audit (include_dependencies=False)")
            tool_coverages.append(
                ToolCoverage(
                    tool="dependency_audit",
                    version="1.0.0",
                    status="SKIPPED",
                    duration_ms=0.0,
                    files_scanned=0,
                )
            )

        # 5. Populate standard "What was NOT checked" disclosures (Acceptance Criteria M6)
        active_langs = [l.lower() for l in (languages or ["python"])]
        if "javascript" not in active_langs and "typescript" not in active_langs:
            not_checked_items.append("Client-side JavaScript / TypeScript deep SAST (language not selected)")
        if "go" not in active_langs:
            not_checked_items.append("Go source code analysis (language not selected)")
        if "java" not in active_langs:
            not_checked_items.append("Java bytecode / JVM taint analysis (language not selected)")

        not_checked_items.append("Dynamic Application Security Testing (DAST / runtime fuzzing not performed)")
        not_checked_items.append("Compiled binaries and archive contents excluded from analysis (SEC-MAL-07)")

        if paths:
            not_checked_items.append(f"Files outside path filter scope: {', '.join(paths)}")
        if changed_files_only:
            not_checked_items.append("Unchanged repository files excluded (changed_files_only=True)")

        # 6. Apply Governance: Anti-Tamper, Suppressions, Carry-Forward, Severity Filter
        processed_findings = self._apply_governance(
            raw_findings=all_findings,
            repository_id=repository_id,
            severity_threshold=severity_threshold,
        )

        # 7. Prioritize findings using RiskClassifier
        prioritized_findings = self.risk_classifier.prioritize_findings(processed_findings)

        # 8. Persist findings, secrets, inventory, and analysis runs
        self.findings_repo.save_findings(prioritized_findings, repository_id=repository_id)
        self.security_repo.save_secret_records(all_secret_records, run_id=run_id)
        if all_inventory:
            self.security_repo.save_dependency_inventory(snapshot_id, all_inventory)

        # Calculate counts
        sast_count = sum(1 for f in prioritized_findings if f.tool == "sast_analyzer")
        secret_count = sum(1 for f in prioritized_findings if f.tool == "secret_scanner")
        dep_count = sum(1 for f in prioritized_findings if f.tool == "dependency_audit")

        completed_at = datetime.now(timezone.utc)

        # 9. Build and persist SecurityScanReport
        report = self.reporter.build_report(
            scan_id=scan_id,
            run_id=run_id,
            job_id=job_id_str,
            snapshot_id=snapshot_id,
            scan_profile=scan_profile,
            tool_coverages=tool_coverages,
            not_checked_items=not_checked_items,
            findings=prioritized_findings,
            secret_findings_count=secret_count,
            dependency_findings_count=dep_count,
            sast_findings_count=sast_count,
            warnings=warnings,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.security_repo.save_report(report)

        # 10. Persist analysis_runs row (run_type="SECURITY") in FindingsRepository
        run_record = AnalysisRunRecord(
            id=run_id,
            snapshot_id=snapshot_id,
            run_type="SECURITY",
            status=report.status,
            job_id=job_id_str,
            tool_coverage=tool_coverages,
            counts_by_severity=report.counts_by_severity,
            counts_by_origin=report.counts_by_origin,
            total_findings=len(prioritized_findings),
            warnings=warnings,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.findings_repo.create_analysis_run(run_record)

        return report

    def _run_secret_scan(
        self,
        files: Dict[str, str],
        snapshot_id: str,
        run_id: str,
        scan_profile: str,
    ) -> Tuple[List[Finding], List[SecretFindingRecord]]:
        """Run secret detection with content-hash caching."""
        findings: List[Finding] = []
        secret_records: List[SecretFindingRecord] = []

        for file_path, content in files.items():
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            cache_key = (file_path, content_hash, "secret_scanner", scan_profile)

            cached = None
            with self._cache_lock:
                cached = self._scan_cache.get(cache_key)

            if cached is not None:
                findings.extend(cached)
            else:
                f_list, rec_list = self.secret_scanner.scan_file(
                    file_path=file_path,
                    content=content,
                    run_id=run_id,
                    snapshot_id=snapshot_id,
                )
                findings.extend(f_list)
                secret_records.extend(rec_list)
                with self._cache_lock:
                    self._scan_cache[cache_key] = f_list
                    if len(self._scan_cache) > self._max_cache_entries:
                        self._scan_cache.popitem(last=False)

        return findings, secret_records

    def _resolve_target_files(
        self,
        context: RepositorySnapshotContext,
        paths: Optional[List[str]],
        changed_files_only: bool,
        changed_files: Optional[List[str]],
    ) -> Tuple[Dict[str, str], Set[str]]:
        """Resolve targeted file paths according to scope constraints."""
        all_files = {
            p: (c.content if hasattr(c, "content") else str(c))
            for p, c in context.files.items()
        }
        target_paths: Set[str] = set()

        if changed_files_only:
            if not changed_files:
                raise ValueError("changed_files list is required when changed_files_only is true.")
            allowed_set = {f.replace("\\", "/").lstrip("/") for f in changed_files}
            all_files = {p: c for p, c in all_files.items() if p.replace("\\", "/").lstrip("/") in allowed_set}

        if paths:
            norm_paths = [p.replace("\\", "/").lstrip("/") for p in paths]
            filtered: Dict[str, str] = {}
            for p, c in all_files.items():
                np = p.replace("\\", "/").lstrip("/")
                if any(fnmatch.fnmatch(np, pat) or np.startswith(pat) for pat in norm_paths):
                    filtered[p] = c
            all_files = filtered

        target_paths = set(all_files.keys())
        return all_files, target_paths

    def _apply_governance(
        self,
        raw_findings: List[Finding],
        repository_id: Optional[str],
        severity_threshold: FindingSeverity,
    ) -> List[Finding]:
        """Apply anti-tamper, suppressions, carry-forward, and severity thresholds."""
        threshold_rank = SEVERITY_RANKS.get(severity_threshold, 0)
        suppressions: List[Suppression] = []
        if repository_id:
            suppressions = self.findings_repo.get_suppressions_for_repo(repository_id)

        processed: List[Finding] = []

        for f in raw_findings:
            # 1. Severity Threshold Filter
            f_rank = SEVERITY_RANKS.get(f.severity, 0)
            if f_rank < threshold_rank:
                continue

            # 2. Anti-tamper enforcement (ST-P04 / SEC-PI-08):
            # In-code comments trying to mark findings false positive or suppress are ignored.
            # Status defaults to OPEN.
            f.status = FindingStatus.OPEN

            # 3. Check repository-scoped suppressions (Audit-16 / SEC-PI-08)
            is_suppressed = any(s.matches(f) for s in suppressions)
            if is_suppressed:
                f.status = FindingStatus.ACKNOWLEDGED
                f.status_reason = "Suppressed by repository governance rule."
                f.status_updated_by = "governance_policy"
                f.status_updated_at = datetime.now(timezone.utc)

            # 4. Carry-Forward triage status from previous snapshot (UT-26)
            if not is_suppressed and repository_id:
                carried = self.findings_repo.get_carried_finding(
                    fingerprint=f.fingerprint,
                    repository_id=repository_id,
                )
                if carried and carried.status in (
                    FindingStatus.FALSE_POSITIVE,
                    FindingStatus.ACCEPTED_RISK,
                    FindingStatus.ACKNOWLEDGED,
                ):
                    f.status = carried.status
                    f.status_reason = carried.status_reason
                    f.status_updated_by = carried.status_updated_by
                    f.status_updated_at = carried.status_updated_at

            processed.append(f)

        return processed
