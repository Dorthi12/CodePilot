"""FastAPI Router for Mastermind Feature 5 (Unit Test Generation).

Specifications:
- Master Architecture Specification v2.1 §10 (M5), §11.3, §14.2, §14.3
- API and Data Specification v1.0 §3.3 (Endpoints 085, 086, 087, 088), §3.4.14, §4.6
- Security & Testing Specification v1.0 §7.3.3 (SEC-API-05), §8.9 (AI-15), IT-11, RT-16
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Response, status

from agentic.common.agent_context import SnapshotContextRegistry
from backend.app.modules.testing.test_execution import ExecutionConsentRequiredError
from backend.app.modules.testing.test_manager import TestManager
from backend.app.repositories.test_repository import TestRepository
from backend.app.schemas.tests import (
    TestExecuteRequest,
    TestExportRequest,
    TestExportResponse,
    TestGenerateRequest,
    TestGenerationReportResponse,
)
from shared.types.testing import TestGenerationRunRecord

router = APIRouter(tags=["Unit Test Generation (M5)"])
manager = TestManager.instance()
repo = TestRepository.get_instance()


def _build_report_response(record: TestGenerationRunRecord) -> TestGenerationReportResponse:
    """Helper to convert TestGenerationRunRecord into serialized TestGenerationReportResponse."""
    return TestGenerationReportResponse(
        run_id=record.run_id,
        snapshot_id=record.snapshot_id,
        status=record.status,
        target=record.target,
        target_symbol_name=record.target_symbol_name,
        target_file_path=record.target_file_path,
        framework=record.framework,
        test_type=record.test_type,
        test_artifact=record.test_artifact,
        test_cases=record.test_cases,
        fixtures=record.fixtures,
        assumptions=record.assumptions,
        vacuous_assertions_detected=record.vacuous_assertions_detected,
        execution=record.test_run,
        test_results=record.test_results,
        coverage=record.coverage,
        patch_id=record.patch_id,
        created_at=record.created_at,
        completed_at=record.completed_at,
        error=record.error,
    )


@router.post(
    "/tests/generate",
    response_model=TestGenerationReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="085: Generate candidate tests",
)
def generate_tests(request: TestGenerateRequest) -> TestGenerationReportResponse:
    """Synthesize candidate tests covering happy paths, edge cases, and boundary conditions."""
    if not SnapshotContextRegistry.contains(request.snapshot_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot '{request.snapshot_id}' not found.",
        )

    try:
        record = manager.generate_tests(
            snapshot_id=request.snapshot_id,
            target_file=request.target.file_path,
            symbol_id=request.target.symbol_id,
            framework=request.framework,
            test_type=request.test_type,
            target_edge_cases=request.target_edge_cases,
            existing_test_paths=request.existing_test_paths,
        )
        return _build_report_response(record)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get(
    "/tests/{run_id}",
    response_model=TestGenerationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="086: Retrieve tests, assumptions, execution, and coverage",
)
def get_tests(run_id: str) -> TestGenerationReportResponse:
    """Retrieve full details of a test generation run by run_id."""
    record = repo.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test generation run '{run_id}' not found.",
        )
    return _build_report_response(record)


@router.post(
    "/tests/{run_id}/execute",
    response_model=TestGenerationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="087: Run tests in the sandbox (explicit opt-in)",
)
def execute_tests(run_id: str, request: TestExecuteRequest) -> TestGenerationReportResponse:
    """Execute candidate tests in the isolated sandbox, enforcing the EXECUTE opt-in gate."""
    # Enforce EXECUTE opt-in security gate
    if not request.consent.execute:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="EXECUTE_OPT_IN_REQUIRED: Explicit user opt-in is required to run tests in the sandbox (Master §13.3, §14.2).",
        )

    record = repo.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test generation run '{run_id}' not found.",
        )

    try:
        updated_record = manager.execute_tests(
            run_id=run_id,
            consent_execute=request.consent.execute,
            install_scripts=request.consent.install_scripts,
            approver_id=request.consent.approver_id,
        )
        return _build_report_response(updated_record)
    except ExecutionConsentRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/tests/{run_id}/export",
    response_model=TestExportResponse,
    status_code=status.HTTP_200_OK,
    summary="088: Export the test patch",
)
def export_tests(
    run_id: str,
    response: Response,
    request: Optional[TestExportRequest] = None,
) -> TestExportResponse:
    """Export generated test suite as a unified diff patch integrated into M4 Patch Core."""
    record = repo.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test generation run '{run_id}' not found.",
        )

    try:
        target_path = request.target_path if request else None
        patch, unified_diff = manager.export_patch(run_id=run_id, target_path=target_path)

        filename = f"codepilot-test-{run_id[:8]}.diff"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["X-Content-Type-Options"] = "nosniff"

        return TestExportResponse(
            run_id=run_id,
            patch_id=patch.id,
            snapshot_id=record.snapshot_id,
            file_path=record.test_artifact.file_path if record.test_artifact else "tests/test_generated.py",
            diff_sha256=patch.diff_sha256,
            unified_diff=unified_diff,
            status=patch.status,
            message="Test suite patch exported successfully; ready for M4 review and application.",
        )
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
