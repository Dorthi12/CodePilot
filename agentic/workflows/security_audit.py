"""Security Audit Workflow for Mastermind Feature 6 (M6).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §13, §14
- API and Data Specification v1.0 §3.4.14, §4.6
- Security and Testing Specification v1.0 §7.3, §7.4, §8.9 (AI-10)
- Enforces Invariant I9 (Zero raw secrets stored)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agentic.common.agent_context import SnapshotContextRegistry
from backend.app.modules.security_analysis.scanner_manager import SecurityScannerManager
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.security_repository import SecurityRepository
from shared.types.agent import FindingSeverity
from shared.types.security import SecurityScanReport


class SecurityAuditWorkflow:
    """Coordinates end-to-end security audit, vulnerability scanning, and audit trails."""

    def __init__(
        self,
        scanner_manager: Optional[SecurityScannerManager] = None,
        security_repo: Optional[SecurityRepository] = None,
        findings_repo: Optional[FindingsRepository] = None,
    ) -> None:
        self.scanner_manager = scanner_manager or SecurityScannerManager.get_instance()
        self.security_repo = security_repo or SecurityRepository.get_instance()
        self.findings_repo = findings_repo or FindingsRepository.get_instance()

    def run_security_audit(
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
    ) -> SecurityScanReport:
        """Execute end-to-end security audit workflow on a repository snapshot."""
        if not SnapshotContextRegistry.contains(snapshot_id):
            raise KeyError(f"Snapshot '{snapshot_id}' not found in registry.")

        report = self.scanner_manager.run_security_scan(
            snapshot_id=snapshot_id,
            scan_profile=scan_profile,
            languages=languages,
            include_dependencies=include_dependencies,
            changed_files_only=changed_files_only,
            paths=paths,
            changed_files=changed_files,
            severity_threshold=severity_threshold,
            repository_id=repository_id,
        )
        return report
