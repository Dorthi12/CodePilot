"""Security Repository managing security scan runs, secret findings, and dependency inventory.

Specifications:
- Master Architecture Specification v2.1 §6.6, §10 (M6)
- API and Data Specification v1.0 §3.3 (089, 090), §3.8.2 (Idempotency), §4.6
- Security and Testing Specification v1.0 §7.4 (SEC-SECRET-01, Invariant I9)
"""

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.types.security import (
    DependencyInventoryItem,
    SecretFindingRecord,
    SecurityScanReport,
)
from backend.app.repositories.findings_repository import FindingsRepository


class SecurityRepository:
    """Thread-safe transactional repository for CodePilot Security Vulnerability Detection (M6)."""

    _instance: Optional["SecurityRepository"] = None
    _lock = threading.Lock()

    def __init__(self, findings_repo: Optional[FindingsRepository] = None) -> None:
        self._reports: Dict[str, SecurityScanReport] = {}  # scan_id -> SecurityScanReport
        self._run_to_scan: Dict[str, str] = {}             # run_id -> scan_id
        self._secret_findings: Dict[str, SecretFindingRecord] = {}  # finding_id -> SecretFindingRecord
        self._secret_findings_by_run: Dict[str, List[SecretFindingRecord]] = {}
        self._dependency_inventory: Dict[str, List[DependencyInventoryItem]] = {}  # snapshot_id -> items
        self._idempotency_store: Dict[str, Dict[str, Any]] = {}  # key -> {request_hash, response, created_at}
        self._findings_repo = findings_repo or FindingsRepository.get_instance()

    @classmethod
    def get_instance(cls) -> "SecurityRepository":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def clear(self) -> None:
        """Reset repository state for isolated test execution."""
        with self._lock:
            self._reports.clear()
            self._run_to_scan.clear()
            self._secret_findings.clear()
            self._secret_findings_by_run.clear()
            self._dependency_inventory.clear()
            self._idempotency_store.clear()

    # --- Idempotency Management (API Spec §3.8.2) ---

    def check_idempotency(self, key: str, request_hash: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """Check for existing idempotency key.

        Returns (cached_response, is_conflict).
        """
        with self._lock:
            if key in self._idempotency_store:
                entry = self._idempotency_store[key]
                if entry["request_hash"] != request_hash:
                    return None, True
                return entry["response"], False
            return None, False

    def store_idempotency(self, key: str, request_hash: str, response_payload: Dict[str, Any]) -> None:
        """Store idempotent request response for 24 hours."""
        with self._lock:
            self._idempotency_store[key] = {
                "request_hash": request_hash,
                "response": response_payload,
                "created_at": datetime.now(timezone.utc),
            }

    # --- Security Scan Reports ---

    def save_report(self, report: SecurityScanReport) -> SecurityScanReport:
        with self._lock:
            self._reports[report.scan_id] = report
            self._run_to_scan[report.run_id] = report.scan_id
            return report

    def get_report(self, scan_id_or_run_id: str) -> Optional[SecurityScanReport]:
        with self._lock:
            if scan_id_or_run_id in self._reports:
                return self._reports[scan_id_or_run_id]
            if scan_id_or_run_id in self._run_to_scan:
                scan_id = self._run_to_scan[scan_id_or_run_id]
                return self._reports.get(scan_id)
            return None

    # --- Secret Findings (Fingerprints Only - Invariant I9) ---

    def save_secret_records(self, records: List[SecretFindingRecord], run_id: Optional[str] = None) -> None:
        with self._lock:
            for rec in records:
                self._secret_findings[rec.finding_id] = rec
                if run_id:
                    if run_id not in self._secret_findings_by_run:
                        self._secret_findings_by_run[run_id] = []
                    self._secret_findings_by_run[run_id].append(rec)

    def get_secret_records(self, run_id: str) -> List[SecretFindingRecord]:
        with self._lock:
            return list(self._secret_findings_by_run.get(run_id, []))

    def get_secret_record_by_finding(self, finding_id: str) -> Optional[SecretFindingRecord]:
        with self._lock:
            return self._secret_findings.get(finding_id)

    # --- Dependency Inventory (SEC-DEP-09) ---

    def save_dependency_inventory(self, snapshot_id: str, items: List[DependencyInventoryItem]) -> None:
        with self._lock:
            if snapshot_id not in self._dependency_inventory:
                self._dependency_inventory[snapshot_id] = []
            self._dependency_inventory[snapshot_id].extend(items)

    def get_dependency_inventory(self, snapshot_id: str) -> List[DependencyInventoryItem]:
        with self._lock:
            return list(self._dependency_inventory.get(snapshot_id, []))
