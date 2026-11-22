"""Repository for managing AI Bug Investigation runs, hypotheses, evidence, and diagnostics.

Specifications:
- Master Architecture Specification v2.1 §6.6, §10 (M2)
- API and Data Specification v1.0 §3.4.13, §4.6
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.agent import RunStatus
from shared.types.findings import AnalysisRunRecord
from shared.types.investigation import (
    DiagnosticStep,
    Hypothesis,
    HypothesisStatus,
    InvestigationRecord,
    ReproductionStatus,
)
from backend.app.repositories.findings_repository import FindingsRepository


class InvestigationRepository:
    """Thread-safe transactional repository for CodePilot AI Bug Investigations (M2)."""

    _instance: Optional["InvestigationRepository"] = None
    _lock = threading.Lock()

    def __init__(self, findings_repo: Optional[FindingsRepository] = None) -> None:
        self._investigations: Dict[str, InvestigationRecord] = {}  # run_id -> InvestigationRecord
        self._findings_repo = findings_repo or FindingsRepository.get_instance()

    @classmethod
    def get_instance(cls) -> "InvestigationRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear(self) -> None:
        """Reset repository state for isolated test execution."""
        with self._lock:
            self._investigations.clear()

    def save_investigation(self, record: InvestigationRecord) -> InvestigationRecord:
        """Persist or update an investigation record and sync with analysis_runs."""
        with self._lock:
            self._investigations[record.run_id] = record

            # Synchronize with unified analysis_runs in findings repository
            run_status = RunStatus.COMPLETED if record.completed_at else RunStatus.RUNNING
            run_record = AnalysisRunRecord(
                id=record.run_id,
                snapshot_id=record.snapshot_id,
                run_type="INVESTIGATION",
                status=run_status,
                job_id=record.run_id,
                config={
                    "issue_description": record.issue_description,
                    "failing_test": record.failing_test,
                    "entrypoint": record.entrypoint,
                },
                started_at=record.started_at,
                completed_at=record.completed_at,
            )
            self._findings_repo.update_analysis_run(run_record)

            return record

    def get_investigation(self, run_id: str) -> Optional[InvestigationRecord]:
        """Fetch an investigation record by run ID."""
        with self._lock:
            return self._investigations.get(run_id)

    def list_investigations(
        self,
        snapshot_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InvestigationRecord]:
        """List stored investigations, optionally filtered by snapshot."""
        with self._lock:
            items = list(self._investigations.values())
            if snapshot_id:
                items = [inv for inv in items if inv.snapshot_id == snapshot_id]
            # Order by started_at desc
            items.sort(key=lambda inv: inv.started_at, reverse=True)
            return items[offset : offset + limit]

    def update_hypothesis_status(
        self,
        run_id: str,
        hypothesis_id: str,
        new_status: HypothesisStatus,
    ) -> Optional[Hypothesis]:
        """Update the status of a specific hypothesis within an investigation."""
        with self._lock:
            inv = self._investigations.get(run_id)
            if not inv:
                return None

            for hyp in inv.hypotheses:
                if hyp.id == hypothesis_id:
                    hyp.status = new_status
                    return hyp

            return None
