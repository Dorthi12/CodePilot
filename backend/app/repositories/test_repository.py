"""Repository for managing Mastermind Feature 5 (Unit Test Generation) runs, artifacts, and execution reports.

Specifications:
- Master Architecture Specification v2.1 §6.6, §10 (M5)
- API and Data Specification v1.0 §3.4.14, §4.6
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.agent import RunStatus
from shared.types.findings import AnalysisRunRecord
from shared.types.testing import (
    CoverageReportRecord,
    TestArtifact,
    TestGenerationRunRecord,
    TestResultRecord,
    TestRunRecord,
)
from backend.app.repositories.findings_repository import FindingsRepository


class TestRepository:
    """Thread-safe transactional repository for CodePilot Unit Test Generation (M5)."""

    __test__ = False
    _instance: Optional["TestRepository"] = None
    _lock = threading.Lock()

    def __init__(self, findings_repo: Optional[FindingsRepository] = None) -> None:
        self._runs: Dict[str, TestGenerationRunRecord] = {}  # run_id -> TestGenerationRunRecord
        self._artifacts: Dict[str, TestArtifact] = {}  # artifact_id -> TestArtifact
        self._test_runs: Dict[str, TestRunRecord] = {}  # test_run_id -> TestRunRecord
        self._coverages: Dict[str, CoverageReportRecord] = {}  # coverage_id -> CoverageReportRecord
        self._findings_repo = findings_repo or FindingsRepository.get_instance()

    @classmethod
    def get_instance(cls) -> "TestRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear(self) -> None:
        """Reset repository state for isolated test execution."""
        with self._lock:
            self._runs.clear()
            self._artifacts.clear()
            self._test_runs.clear()
            self._coverages.clear()

    def save_run(self, record: TestGenerationRunRecord) -> TestGenerationRunRecord:
        """Persist or update a test generation run record and sync with analysis_runs."""
        with self._lock:
            self._runs[record.run_id] = record

            if record.test_artifact:
                self._artifacts[record.test_artifact.id] = record.test_artifact
            if record.test_run:
                self._test_runs[record.test_run.id] = record.test_run
            if record.coverage:
                self._coverages[record.coverage.id] = record.coverage

            # Synchronize with unified analysis_runs in findings repository
            run_status = RunStatus.COMPLETED if record.completed_at else RunStatus.RUNNING
            run_record = AnalysisRunRecord(
                id=record.run_id,
                snapshot_id=record.snapshot_id,
                run_type="TEST_GEN",
                status=run_status,
                job_id=record.run_id,
                config={
                    "target": record.target,
                    "framework": record.framework,
                    "test_type": record.test_type,
                    "target_edge_cases": record.target_edge_cases,
                },
                started_at=record.created_at,
                completed_at=record.completed_at,
            )
            self._findings_repo.update_analysis_run(run_record)

            return record

    def get_run(self, run_id: str) -> Optional[TestGenerationRunRecord]:
        """Retrieve a test generation run record by run_id."""
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self, snapshot_id: Optional[str] = None) -> List[TestGenerationRunRecord]:
        """List test generation runs, optionally filtered by snapshot_id."""
        with self._lock:
            if snapshot_id:
                return [r for r in self._runs.values() if r.snapshot_id == snapshot_id]
            return list(self._runs.values())

    def get_artifact(self, artifact_id: str) -> Optional[TestArtifact]:
        """Retrieve test artifact by ID."""
        with self._lock:
            return self._artifacts.get(artifact_id)

    def get_test_run(self, test_run_id: str) -> Optional[TestRunRecord]:
        """Retrieve sandbox test run by ID."""
        with self._lock:
            return self._test_runs.get(test_run_id)

    def get_coverage(self, coverage_id: str) -> Optional[CoverageReportRecord]:
        """Retrieve coverage report by ID."""
        with self._lock:
            return self._coverages.get(coverage_id)
