"""Code Quality Engine for Feature A3 (Bug and Code Smell Detection).

Optimized orchestrator handling:
- Multi-analyzer coordination (AST Bug Detector, Graph Smell Detector)
- Sub-second incremental caching by (content_hash, tool_version, rule_pack)
- Fault-tolerant tool execution with ToolExecutionLog and ToolCoverage (IT-16)
- Finding deduplication, stable fingerprinting, and carry-forward (UT-26)
- Repository-scoped suppressions and anti-tamper security enforcement (SEC-PI-08 / ST-P04)
"""

import collections
import fnmatch
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import uuid4

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus, RunStatus
from shared.types.findings import (
    AnalysisRunRecord,
    Finding,
    RuleMetadata,
    Suppression,
    ToolCoverage,
    ToolExecutionLog,
)
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from ai_service.code_analysis.bug_detector import BugDetector
from ai_service.code_analysis.code_smell_detector import CodeSmellDetector, RulePackConfig
from backend.app.repositories.findings_repository import FindingsRepository

SEVERITY_RANKS = {
    FindingSeverity.INFO: 0,
    FindingSeverity.LOW: 1,
    FindingSeverity.MEDIUM: 2,
    FindingSeverity.HIGH: 3,
    FindingSeverity.CRITICAL: 4,
}


class CodeQualityEngine:
    """Enterprise code quality analyzer with caching and governance."""

    def __init__(self, repository: Optional[FindingsRepository] = None) -> None:
        self.repo = repository or FindingsRepository.get_instance()
        # File path matters: rules such as test-file assertions and findings
        # location are path-dependent even when file contents are identical.
        self._analysis_cache: "collections.OrderedDict[Tuple[str, str, str, str], List[Finding]]" = collections.OrderedDict()
        self._cache_lock = threading.RLock()
        self._max_cache_entries = 10_000

    def clear_cache(self) -> None:
        """Clear the incremental content-hash cache."""
        with self._cache_lock:
            self._analysis_cache.clear()

    def run_code_quality_analysis(
        self,
        snapshot_id: str,
        paths: Optional[List[str]] = None,
        changed_files_only: bool = False,
        rule_pack: str = "default",
        severity_threshold: FindingSeverity = FindingSeverity.LOW,
        repository_id: Optional[str] = None,
        job_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> AnalysisRunRecord:
        """Execute comprehensive code quality analysis pinned to snapshot_id."""
        if not SnapshotContextRegistry.contains(snapshot_id):
            raise ValueError(f"Snapshot '{snapshot_id}' is not loaded for analysis.")
        run_id = run_id or str(uuid4())
        job_id_str = job_id or str(uuid4())
        record = self.repo.get_analysis_run(run_id)
        if record is None:
            record = self.create_pending_run(
                snapshot_id=snapshot_id,
                paths=paths,
                changed_files_only=changed_files_only,
                rule_pack=rule_pack,
                severity_threshold=severity_threshold,
                repository_id=repository_id,
                job_id=job_id_str,
                run_id=run_id,
            )

        context = SnapshotContextRegistry.get(snapshot_id)
        target_files = self._resolve_target_files(context, paths)

        tool_coverages: List[ToolCoverage] = []
        raw_findings: List[Finding] = []
        warnings: List[str] = []

        # 1. Deterministic Bug & Security Analyzer
        t0 = time.perf_counter()
        try:
            bug_detector = BugDetector()
            bug_findings = self._run_cached_file_analysis(
                context=context,
                run_id=run_id,
                target_files=target_files,
                tool_name="bug_detector",
                rule_pack=rule_pack,
                analyzer_fn=lambda ctx, files: bug_detector.analyze(ctx, run_id, files),
            )
            dur_ms = (time.perf_counter() - t0) * 1000.0
            tool_coverages.append(
                ToolCoverage(
                    tool="bug_detector",
                    version="1.0.0",
                    status="SUCCESS",
                    duration_ms=round(dur_ms, 2),
                    files_scanned=len(target_files) if target_files is not None else len(context.files),
                    rules_run=8,
                    findings_count=len(bug_findings),
                )
            )
            self.repo.add_tool_execution_log(
                ToolExecutionLog(
                    run_id=run_id,
                    tool="bug_detector",
                    tool_version="1.0.0",
                    status="SUCCESS",
                    duration_ms=round(dur_ms, 2),
                    coverage={"files_scanned": len(target_files) if target_files is not None else len(context.files)},
                )
            )
            raw_findings.extend(bug_findings)
        except Exception as e:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            tool_coverages.append(
                ToolCoverage(
                    tool="bug_detector",
                    version="1.0.0",
                    status="FAILED",
                    duration_ms=round(dur_ms, 2),
                    error=str(e),
                )
            )
            self.repo.add_tool_execution_log(
                ToolExecutionLog(
                    run_id=run_id,
                    tool="bug_detector",
                    tool_version="1.0.0",
                    status="FAILED",
                    duration_ms=round(dur_ms, 2),
                    stderr_redacted=str(e),
                )
            )
            warnings.append(f"Tool bug_detector failed: {str(e)}")

        # 2. Graph & Smell Rule Pack Analyzer
        t1 = time.perf_counter()
        try:
            config = RulePackConfig.get_preset(rule_pack)
            smell_detector = CodeSmellDetector(config)
            smell_findings = smell_detector.analyze(context, run_id, target_files)
            dur_ms1 = (time.perf_counter() - t1) * 1000.0
            tool_coverages.append(
                ToolCoverage(
                    tool="code_smell_detector",
                    version="1.0.0",
                    status="SUCCESS",
                    duration_ms=round(dur_ms1, 2),
                    files_scanned=len(target_files) if target_files is not None else len(context.files),
                    rules_run=11,
                    findings_count=len(smell_findings),
                )
            )
            self.repo.add_tool_execution_log(
                ToolExecutionLog(
                    run_id=run_id,
                    tool="code_smell_detector",
                    tool_version="1.0.0",
                    status="SUCCESS",
                    duration_ms=round(dur_ms1, 2),
                    coverage={"files_scanned": len(target_files) if target_files is not None else len(context.files)},
                )
            )
            raw_findings.extend(smell_findings)
        except Exception as e:
            dur_ms1 = (time.perf_counter() - t1) * 1000.0
            tool_coverages.append(
                ToolCoverage(
                    tool="code_smell_detector",
                    version="1.0.0",
                    status="FAILED",
                    duration_ms=round(dur_ms1, 2),
                    error=str(e),
                )
            )
            self.repo.add_tool_execution_log(
                ToolExecutionLog(
                    run_id=run_id,
                    tool="code_smell_detector",
                    tool_version="1.0.0",
                    status="FAILED",
                    duration_ms=round(dur_ms1, 2),
                    stderr_redacted=str(e),
                )
            )
            warnings.append(f"Tool code_smell_detector failed: {str(e)}")

        # 3. Apply Governance: Carry-Forward, Suppressions, and Severity Filtering
        processed_findings = self._process_findings(
            raw_findings=raw_findings,
            repository_id=repository_id,
            severity_threshold=severity_threshold,
        )

        # 4. Save and index findings
        self.repo.save_findings(processed_findings, repository_id=repository_id)

        # 5. Summarize run results
        counts_by_severity: Dict[str, int] = {}
        counts_by_origin: Dict[str, int] = {}
        for f in processed_findings:
            counts_by_severity[f.severity.value] = counts_by_severity.get(f.severity.value, 0) + 1
            counts_by_origin[f.origin.value] = counts_by_origin.get(f.origin.value, 0) + 1

        has_failures = any(tc.status == "FAILED" for tc in tool_coverages)
        record.status = RunStatus.PARTIAL if has_failures else RunStatus.COMPLETED
        record.tool_coverage = tool_coverages
        record.counts_by_severity = counts_by_severity
        record.counts_by_origin = counts_by_origin
        record.total_findings = len(processed_findings)
        record.warnings = warnings
        record.completed_at = datetime.now(timezone.utc)

        self.repo.update_analysis_run(record)
        return record

    def create_pending_run(
        self,
        snapshot_id: str,
        paths: Optional[List[str]] = None,
        changed_files_only: bool = False,
        rule_pack: str = "default",
        severity_threshold: FindingSeverity = FindingSeverity.LOW,
        repository_id: Optional[str] = None,
        job_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> AnalysisRunRecord:
        """Persist a run record before scheduling the CPU-bound analysis."""
        if not SnapshotContextRegistry.contains(snapshot_id):
            raise ValueError(f"Snapshot '{snapshot_id}' is not loaded for analysis.")
        record = AnalysisRunRecord(
            id=run_id or str(uuid4()),
            snapshot_id=snapshot_id,
            run_type="QUALITY",
            status=RunStatus.RUNNING,
            job_id=job_id or str(uuid4()),
            config={
                "paths": paths,
                "changed_files_only": changed_files_only,
                "rule_pack": rule_pack,
                "severity_threshold": severity_threshold.value,
                "repository_id": repository_id,
            },
            model_and_tool_versions={
                "codepilot_engine": "1.0.0",
                "codepilot_ast": "1.0.0",
                "codepilot_secrets": "1.0.0",
                "codepilot_smells": "1.0.0",
            },
            started_at=datetime.now(timezone.utc),
        )
        return self.repo.create_analysis_run(record)

    def run_pending_analysis(self, **kwargs: Any) -> None:
        """Background-task boundary that ensures unexpected errors finalize the run."""
        run_id = kwargs.get("run_id")
        try:
            self.run_code_quality_analysis(**kwargs)
        except Exception as exc:
            record = self.repo.get_analysis_run(run_id) if run_id else None
            if record is None:
                return
            record.status = RunStatus.FAILED
            record.warnings = [f"Analysis failed ({type(exc).__name__})."]
            record.completed_at = datetime.now(timezone.utc)
            self.repo.update_analysis_run(record)

    def _resolve_target_files(
        self,
        context: RepositorySnapshotContext,
        paths: Optional[List[str]],
    ) -> Optional[Set[str]]:
        if paths is None:
            return None
        target_set: Set[str] = set()
        for p in paths:
            norm_p = p.replace("\\", "/").lstrip("/")
            for file_path in context.files.keys():
                if fnmatch.fnmatch(file_path, norm_p):
                    target_set.add(file_path)
        return target_set

    def _run_cached_file_analysis(
        self,
        context: RepositorySnapshotContext,
        run_id: str,
        target_files: Optional[Set[str]],
        tool_name: str,
        rule_pack: str,
        analyzer_fn: Any,
    ) -> List[Finding]:
        """Incremental cache helper using (content_hash, tool_name, rule_pack)."""
        files_to_scan = [
            f for path, f in context.files.items()
            if target_files is None or path in target_files
        ]

        uncached_files: Set[str] = set()
        cached_findings: List[Finding] = []

        for file_obj in files_to_scan:
            key = (file_obj.content_hash, file_obj.path, tool_name, rule_pack)
            with self._cache_lock:
                cache_hit = key in self._analysis_cache
                templates = self._analysis_cache.get(key, [])
                if cache_hit:
                    self._analysis_cache.move_to_end(key)
            if cache_hit:
                for cached_f in templates:
                    rebound = cached_f.model_copy(update={
                        "id": str(uuid4()),
                        "snapshot_id": context.snapshot_id,
                        "analysis_run_id": run_id,
                    }, deep=True)
                    for evidence in rebound.evidence:
                        evidence.id = str(uuid4())
                    cached_findings.append(rebound)
            else:
                uncached_files.add(file_obj.path)

        if uncached_files:
            fresh_findings = analyzer_fn(context, uncached_files)
            # Group fresh findings by file content hash and store in cache
            findings_by_path: Dict[str, List[Finding]] = collections.defaultdict(list)
            for f in fresh_findings:
                findings_by_path[f.file_path].append(f)

            for path in uncached_files:
                file_obj = context.files[path]
                key = (file_obj.content_hash, file_obj.path, tool_name, rule_pack)
                with self._cache_lock:
                    self._analysis_cache[key] = [
                        finding.model_copy(deep=True)
                        for finding in findings_by_path.get(path, [])
                    ]
                    self._analysis_cache.move_to_end(key)
                    while len(self._analysis_cache) > self._max_cache_entries:
                        self._analysis_cache.popitem(last=False)

            return cached_findings + fresh_findings

        return cached_findings

    def _process_findings(
        self,
        raw_findings: List[Finding],
        repository_id: Optional[str],
        severity_threshold: FindingSeverity,
    ) -> List[Finding]:
        """Apply Finding Carry-Forward (UT-26), Suppressions, and Severity Filtering."""
        min_rank = SEVERITY_RANKS.get(severity_threshold, 1)
        suppressions = self.repo.get_suppressions_for_repo(repository_id) if repository_id else []

        processed: List[Finding] = []
        for f in raw_findings:
            # 1. Severity threshold check
            if SEVERITY_RANKS.get(f.severity, 2) < min_rank:
                continue

            # 2. Finding Carry-Forward across snapshots (UT-26)
            carried = self.repo.get_carried_finding(f.fingerprint, repository_id=repository_id)
            if carried is not None:
                # If human had previously acknowledged or accepted risk or marked false positive, carry it forward
                if carried.status in (
                    FindingStatus.ACKNOWLEDGED,
                    FindingStatus.FALSE_POSITIVE,
                    FindingStatus.ACCEPTED_RISK,
                    FindingStatus.FIXED,
                ):
                    f.status = carried.status
                    f.status_reason = carried.status_reason
                    f.status_updated_by = carried.status_updated_by
                    f.status_updated_at = carried.status_updated_at

            # 3. Repository-scoped Suppressions
            for supp in suppressions:
                if supp.matches(f):
                    f.status = FindingStatus.FALSE_POSITIVE
                    f.status_reason = f"Suppressed by policy: {supp.reason}"
                    f.status_updated_by = supp.created_by
                    f.status_updated_at = supp.created_at
                    break

            processed.append(f)

        return processed
