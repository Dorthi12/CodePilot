"""FastAPI Router for Mastermind Feature 6 (Security Vulnerability Detection).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3, §14.2, §14.3
- API and Data Specification v1.0 §3.3 (Endpoints 089, 090), §3.4.14, §3.8.2 (Idempotency), §4.6
- Security and Testing Specification v1.0 §7.3.3, §7.4, §8.9 (AI-10), UT-13, UT-26, IT-16, E2E-11
"""

import hashlib
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Response, status

from agentic.common.agent_context import SnapshotContextRegistry
from backend.app.modules.security_analysis.scanner_manager import SecurityScannerManager
from backend.app.repositories.security_repository import SecurityRepository
from backend.app.schemas.security import (
    SecurityScanRequest,
    SecurityScanResponse,
)
from shared.types.security import SecurityScanReport

router = APIRouter(tags=["Security Vulnerability Detection (M6)"])
manager = SecurityScannerManager.get_instance()
repo = SecurityRepository.get_instance()


def _build_response(report: SecurityScanReport, message: Optional[str] = None) -> SecurityScanResponse:
    """Helper converting SecurityScanReport to serialized SecurityScanResponse."""
    return SecurityScanResponse(
        scan_id=report.scan_id,
        run_id=report.run_id,
        job_id=report.job_id,
        snapshot_id=report.snapshot_id,
        status=report.status.value,
        scan_profile=report.scan_profile,
        tool_coverage=report.tool_coverage,
        not_checked=report.not_checked,
        total_findings=report.total_findings,
        counts_by_severity=report.counts_by_severity,
        counts_by_origin=report.counts_by_origin,
        sast_findings_count=report.sast_findings_count,
        secret_findings_count=report.secret_findings_count,
        dependency_findings_count=report.dependency_findings_count,
        warnings=report.warnings,
        message=message or "Security vulnerability scan completed.",
        started_at=report.started_at,
        completed_at=report.completed_at,
    )


@router.post(
    "/security/scans",
    response_model=SecurityScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="089: Start a security scan run",
)
def start_security_scan(
    request: SecurityScanRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> SecurityScanResponse:
    """Start a comprehensive security vulnerability scan on a snapshot.

    Enforces:
    - Idempotency-Key requirement (§3.8.2) with conflict detection and replay.
    - Snapshot availability check (404).
    - Scope validation for changed files (422).
    - Zero plaintext credential leakage (SEC-SECRET-01).
    - Explicit disclosure of tool coverage and what was not checked.
    """
    # 1. Enforce Idempotency-Key requirement (API Spec §3.8.2, Endpoint 089)
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="VALIDATION_FAILED: 'Idempotency-Key' header is required on POST /security/scans.",
        )

    # Calculate request hash
    body_serialized = json.dumps(request.model_dump(), sort_keys=True, default=str)
    request_hash = hashlib.sha256(body_serialized.encode("utf-8")).hexdigest()

    cached_response, is_conflict = repo.check_idempotency(idempotency_key, request_hash)
    if is_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IDEMPOTENCY_CONFLICT: Idempotency-Key reused with different request payload.",
        )
    if cached_response is not None:
        response.headers["Idempotent-Replayed"] = "true"
        return SecurityScanResponse(**cached_response)

    # 2. Verify snapshot context
    if not SnapshotContextRegistry.contains(request.snapshot_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot '{request.snapshot_id}' not found or is not available for analysis.",
        )

    # 3. Validate changed_files when changed_files_only is true
    if request.changed_files_only and not request.changed_files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="changed_files is required when changed_files_only is true.",
        )

    try:
        # 4. Execute security vulnerability detection
        report = manager.run_security_scan(
            snapshot_id=request.snapshot_id,
            scan_profile=request.scan_profile,
            languages=request.languages,
            include_dependencies=request.include_dependencies,
            changed_files_only=request.changed_files_only,
            paths=request.paths,
            changed_files=request.changed_files,
            severity_threshold=request.severity_threshold,
            repository_id=request.repository_id,
        )

        resp_obj = _build_response(report)

        # 5. Store idempotency record
        repo.store_idempotency(idempotency_key, request_hash, resp_obj.model_dump())

        return resp_obj

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Security scan failed: {str(e)}",
        )


@router.get(
    "/security/scans/{id}",
    response_model=SecurityScanResponse,
    status_code=status.HTTP_200_OK,
    summary="090: Scan status, coverage, and what was not checked",
)
def get_security_scan(id: str) -> SecurityScanResponse:
    """Retrieve security scan status, coverage details, and what was not checked (Acceptance Criteria M6)."""
    report = repo.get_report(id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Security scan run '{id}' was not found.",
        )

    return _build_response(report, message="Security scan report retrieved.")
