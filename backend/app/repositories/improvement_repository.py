"""Repository for managing Code Improvement runs, suggestions, and idempotency states.

Specifications:
- Master Architecture Specification v2.1 §6.6, §10 (M3)
- API and Data Specification v1.0 §3.4.13, §3.8.2, §4.6
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.types.agent import RunStatus
from shared.types.findings import AnalysisRunRecord
from shared.types.suggestions import (
    EffortLevel,
    ImprovementRunReport,
    RiskLevel,
    SuggestionCategory,
    SuggestionRecord,
    SuggestionStatus,
)
from backend.app.repositories.findings_repository import FindingsRepository


class OptimisticLockError(Exception):
    """Raised when an update fails due to a conflicting version (optimistic locking)."""
    pass


class ImprovementRepository:
    """Thread-safe transactional repository for CodePilot Code Improvement Suggestions (M3)."""

    _instance: Optional["ImprovementRepository"] = None
    _lock = threading.Lock()

    def __init__(self, findings_repo: Optional[FindingsRepository] = None) -> None:
        self._suggestions: Dict[str, SuggestionRecord] = {}  # suggestion_id -> SuggestionRecord
        self._run_suggestions: Dict[str, List[str]] = {}     # run_id -> list of suggestion_ids
        self._reports: Dict[str, ImprovementRunReport] = {}  # run_id -> ImprovementRunReport
        self._idempotency_store: Dict[str, Dict[str, Any]] = {}  # key -> {request_hash, response, created_at}
        self._findings_repo = findings_repo or FindingsRepository.get_instance()

    @classmethod
    def get_instance(cls) -> "ImprovementRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear(self) -> None:
        """Reset repository state for isolated test execution."""
        with self._lock:
            self._suggestions.clear()
            self._run_suggestions.clear()
            self._reports.clear()
            self._idempotency_store.clear()

    # --- Idempotency Management (API Spec §3.8.2) ---

    def check_idempotency(self, key: str, request_hash: str) -> Tuple[Optional[Any], bool]:
        """Check if an idempotency key was previously processed.

        Returns:
            (cached_response, is_conflict):
            - If not found: (None, False)
            - If found with same hash: (cached_response, False)
            - If found with DIFFERENT hash: (None, True) -> 409 IDEMPOTENCY_CONFLICT
        """
        with self._lock:
            stored = self._idempotency_store.get(key)
            if not stored:
                return None, False
            if stored["request_hash"] == request_hash:
                return stored["response"], False
            return None, True

    def store_idempotency(self, key: str, request_hash: str, response_data: Any) -> None:
        """Store idempotency key record for 24h replay caching."""
        with self._lock:
            self._idempotency_store[key] = {
                "request_hash": request_hash,
                "response": response_data,
                "created_at": datetime.now(timezone.utc),
            }

    # --- Report and Run Management ---

    def save_report(self, report: ImprovementRunReport) -> ImprovementRunReport:
        """Persist an improvement report and sync with unified analysis_runs."""
        with self._lock:
            self._reports[report.run_id] = report
            self._run_suggestions[report.run_id] = [s.id for s in report.suggestions]
            for s in report.suggestions:
                self._suggestions[s.id] = s

            # Synchronize with unified analysis_runs in findings repository
            run_status = RunStatus.COMPLETED if report.completed_at else RunStatus.RUNNING
            run_record = AnalysisRunRecord(
                id=report.run_id,
                snapshot_id=report.snapshot_id,
                run_type="IMPROVEMENT",
                status=run_status,
                job_id=report.run_id,
                config={
                    "total_suggestions": report.total_suggestions,
                    "counts_by_category": report.counts_by_category,
                },
                started_at=report.started_at,
                completed_at=report.completed_at,
            )
            self._findings_repo.update_analysis_run(run_record)

            return report

    def get_report(self, run_id: str) -> Optional[ImprovementRunReport]:
        """Fetch an improvement report by run ID."""
        with self._lock:
            return self._reports.get(run_id)

    # --- Suggestion Operations ---

    def get_suggestion(self, suggestion_id: str) -> Optional[SuggestionRecord]:
        """Fetch a specific suggestion by ID."""
        with self._lock:
            return self._suggestions.get(suggestion_id)

    def list_suggestions(
        self,
        run_id: str,
        category: Optional[SuggestionCategory] = None,
        status: Optional[SuggestionStatus] = None,
        min_confidence: Optional[float] = None,
        max_effort: Optional[EffortLevel] = None,
        max_risk: Optional[RiskLevel] = None,
    ) -> List[SuggestionRecord]:
        """List suggestions belonging to a run with optional filtering."""
        with self._lock:
            suggestion_ids = self._run_suggestions.get(run_id, [])
            results = []

            # Mapping for comparison
            effort_order = {EffortLevel.LOW: 1, EffortLevel.MEDIUM: 2, EffortLevel.HIGH: 3}
            risk_order = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3}

            for sid in suggestion_ids:
                s = self._suggestions.get(sid)
                if not s:
                    continue
                if category and s.category != category:
                    continue
                if status and s.status != status:
                    continue
                if min_confidence is not None and s.confidence < min_confidence:
                    continue
                if max_effort and effort_order.get(s.effort, 9) > effort_order.get(max_effort, 9):
                    continue
                if max_risk and risk_order.get(s.risk, 9) > risk_order.get(max_risk, 9):
                    continue
                results.append(s)

            # Sort by priority_score descending
            results.sort(key=lambda item: item.priority_score, reverse=True)
            return results

    def update_suggestion_status(
        self,
        suggestion_id: str,
        new_status: SuggestionStatus,
        feedback: Optional[str] = None,
        expected_version: Optional[int] = None,
    ) -> SuggestionRecord:
        """Update suggestion status with optimistic concurrency control."""
        with self._lock:
            s = self._suggestions.get(suggestion_id)
            if not s:
                raise KeyError(f"Suggestion '{suggestion_id}' not found.")

            # Optimistic locking check
            if expected_version is not None and s.version != expected_version:
                raise OptimisticLockError(
                    f"Version conflict on suggestion '{suggestion_id}': "
                    f"current version is {s.version}, expected {expected_version}."
                )

            s.status = new_status
            if feedback is not None:
                s.feedback = feedback
            s.version += 1
            s.updated_at = datetime.now(timezone.utc)

            # Also update in report if present
            report = self._reports.get(s.run_id)
            if report:
                # Update status counts in report
                report.counts_by_status = {}
                for sid in self._run_suggestions.get(s.run_id, []):
                    item = self._suggestions.get(sid)
                    if item:
                        st = item.status.value
                        report.counts_by_status[st] = report.counts_by_status.get(st, 0) + 1

            return s
