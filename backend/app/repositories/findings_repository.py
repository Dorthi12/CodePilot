"""Repository for managing Analysis Runs, Findings, Suppressions, and Tool Logs."""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus, RunStatus
from shared.types.findings import (
    AnalysisRunRecord,
    Finding,
    RuleMetadata,
    Suppression,
    ToolCoverage,
    ToolExecutionLog,
)


class FindingsRepository:
    """In-memory and transactional repository for CodePilot findings and quality analysis runs."""

    _instance: Optional["FindingsRepository"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._runs: Dict[str, AnalysisRunRecord] = {}
        self._findings: Dict[str, Finding] = {}
        self._rules: Dict[str, RuleMetadata] = {}
        self._suppressions: Dict[str, List[Suppression]] = {}  # repository_id -> list[Suppression]
        self._tool_logs: Dict[str, List[ToolExecutionLog]] = {}  # run_id -> list[ToolExecutionLog]
        # Carry-forward is scoped to a repository. A matching fingerprint from
        # another tenant/repository must never inherit triage state.
        self._fingerprint_index: Dict[tuple[Optional[str], str], Finding] = {}
        self._finding_repositories: Dict[str, Optional[str]] = {}

    @classmethod
    def get_instance(cls) -> "FindingsRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear(self) -> None:
        """Reset repository state (primarily for isolated test fixtures)."""
        with self._lock:
            self._runs.clear()
            self._findings.clear()
            self._rules.clear()
            self._suppressions.clear()
            self._tool_logs.clear()
            self._fingerprint_index.clear()
            self._finding_repositories.clear()

    # --- Analysis Runs ---

    def create_analysis_run(self, run: AnalysisRunRecord) -> AnalysisRunRecord:
        with self._lock:
            self._runs[run.id] = run
            return run

    def get_analysis_run(self, run_id: str) -> Optional[AnalysisRunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def update_analysis_run(self, run: AnalysisRunRecord) -> AnalysisRunRecord:
        with self._lock:
            self._runs[run.id] = run
            return run

    # --- Findings ---

    def save_findings(self, findings: List[Finding], repository_id: Optional[str] = None) -> None:
        with self._lock:
            for f in findings:
                self._findings[f.id] = f
                self._finding_repositories[f.id] = repository_id
                self._fingerprint_index[(repository_id, f.fingerprint)] = f

    def get_finding(self, finding_id: str) -> Optional[Finding]:
        with self._lock:
            return self._findings.get(finding_id)

    def query_findings(
        self,
        snapshot_id: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        origin: Optional[str] = None,
        file_path: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self._lock:
            results = list(self._findings.values())

            if snapshot_id:
                results = [f for f in results if f.snapshot_id == snapshot_id]
            if category:
                results = [f for f in results if f.category.upper() == category.upper()]
            if severity:
                results = [f for f in results if f.severity.value.upper() == severity.upper()]
            if status:
                results = [f for f in results if f.status.value.upper() == status.upper()]
            if origin:
                results = [f for f in results if f.origin.value.upper() == origin.upper()]
            if file_path:
                norm_query = file_path.replace("\\", "/").lower()
                results = [f for f in results if norm_query in f.file_path.replace("\\", "/").lower()]
            if rule_id:
                results = [f for f in results if f.rule_id.upper() == rule_id.upper()]

            # Stable ordering keeps offset-based pagination deterministic when
            # newer findings are inserted between requests.
            results.sort(key=lambda f: (f.created_at, f.id), reverse=True)

            total = len(results)

            # Calculate counts
            counts_by_severity: Dict[str, int] = {}
            counts_by_origin: Dict[str, int] = {}
            for f in results:
                s_key = f.severity.value
                counts_by_severity[s_key] = counts_by_severity.get(s_key, 0) + 1
                o_key = f.origin.value
                counts_by_origin[o_key] = counts_by_origin.get(o_key, 0) + 1

            # Apply pagination
            paginated = results[offset : offset + limit]

            return {
                "items": paginated,
                "total": total,
                "limit": limit,
                "offset": offset,
                "counts_by_severity": counts_by_severity,
                "counts_by_origin": counts_by_origin,
            }

    def update_finding_status(
        self,
        finding_id: str,
        new_status: FindingStatus,
        reason: Optional[str] = None,
        user: str = "developer",
    ) -> Finding:
        with self._lock:
            if finding_id not in self._findings:
                raise KeyError(f"Finding with id '{finding_id}' not found")

            finding = self._findings[finding_id]
            finding.status = new_status
            finding.status_reason = reason
            finding.status_updated_by = user
            finding.status_updated_at = datetime.now(timezone.utc)
            finding.version += 1

            # Update index
            repository_id = self._finding_repositories.get(finding_id)
            self._fingerprint_index[(repository_id, finding.fingerprint)] = finding
            return finding

    def get_carried_finding(
        self, fingerprint: str, repository_id: Optional[str] = None
    ) -> Optional[Finding]:
        """Fetch previously recorded finding by fingerprint for carry-forward (UT-26)."""
        with self._lock:
            return self._fingerprint_index.get((repository_id, fingerprint))

    # --- Suppressions (Repository-scoped: survives snapshot retirement) ---

    def add_suppression(self, suppression: Suppression) -> Suppression:
        with self._lock:
            repo_id = suppression.repository_id
            if repo_id not in self._suppressions:
                self._suppressions[repo_id] = []
            self._suppressions[repo_id].append(suppression)
            return suppression

    def get_suppressions_for_repo(self, repository_id: str) -> List[Suppression]:
        with self._lock:
            return list(self._suppressions.get(repository_id, []))

    # --- Tool Execution Logs ---

    def add_tool_execution_log(self, log: ToolExecutionLog) -> None:
        with self._lock:
            if log.run_id not in self._tool_logs:
                self._tool_logs[log.run_id] = []
            self._tool_logs[log.run_id].append(log)

    def get_tool_execution_logs(self, run_id: str) -> List[ToolExecutionLog]:
        with self._lock:
            return list(self._tool_logs.get(run_id, []))
