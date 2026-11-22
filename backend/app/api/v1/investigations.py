"""FastAPI Router for Mastermind Feature 2 (AI Bug Investigation).

Specifications:
- Master Architecture Specification v2.1 §10 (M2), §11.3
- API and Data Specification v1.0 §3.3 (Endpoints 070, 071, 072), §3.4.13
- Security & Testing Specification v1.0 §7.3.3 (SEC-API-05, SEC-API-06), §8.9 (AI-11), Appendix C.g
"""

from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status

from agentic.workflows.bug_investigation import BugInvestigationWorkflow
from backend.app.repositories.investigation_repository import InvestigationRepository
from backend.app.schemas.investigations import (
    CallPathResponse,
    DiagnosticExecuteRequest,
    DiagnosticExecuteResponse,
    DiagnosticStepResponse,
    InvestigationCreateRequest,
    InvestigationReportResponse,
    RootCauseResponse,
)
from sandbox.runner.diagnostic_sandbox import ExecutionConsentRequiredError

router = APIRouter(prefix="/debug", tags=["AI Bug Investigation (M2)"])

# Shared repository and workflow instances
repo = InvestigationRepository.get_instance()
workflow = BugInvestigationWorkflow(repository=repo)


def _build_report_response(inv) -> InvestigationReportResponse:
    """Helper to convert InvestigationRecord to InvestigationReportResponse."""
    root_causes = [
        RootCauseResponse(
            id=h.id,
            rank=h.rank,
            summary=h.summary,
            confidence=h.confidence,
            status=h.status,
            file_path=h.file_path,
            function=h.function,
            line_start=h.line_start,
            line_end=h.line_end,
            rationale=h.rationale,
        )
        for h in inv.hypotheses
    ]

    call_path = [
        CallPathResponse(
            order=cp.order,
            file_path=cp.file_path,
            line=cp.line,
            function=cp.function,
            snippet=cp.snippet,
            is_root_cause_candidate=cp.is_root_cause_candidate,
            is_entrypoint=cp.is_entrypoint,
        )
        for cp in inv.call_path
    ]

    diagnostics = [
        DiagnosticStepResponse(
            id=d.id,
            kind=d.kind,
            command_ref=d.command_ref,
            status=d.status,
            result_ref=d.result_ref,
            approved_by=d.approved_by,
            limits=d.limits,
            test_results=d.test_results,
        )
        for d in inv.diagnostics
    ]

    return InvestigationReportResponse(
        investigation_id=inv.run_id,
        run_id=inv.run_id,
        snapshot_id=inv.snapshot_id,
        problem_summary=inv.problem_summary,
        root_causes=root_causes,
        call_path=call_path,
        evidence=inv.evidence,
        reproduction_status=inv.reproduction_status,
        diagnostics=diagnostics,
        next_steps=inv.next_steps,
        stack_trace_redacted=inv.stack_trace_redacted,
        started_at=inv.started_at,
        completed_at=inv.completed_at,
    )


@router.post(
    "/investigations",
    response_model=InvestigationReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="070: Start an investigation (issue, stack trace, failing test)",
)
def create_investigation(request: InvestigationCreateRequest) -> InvestigationReportResponse:
    """Start an AI-powered bug investigation from an issue description, stack trace, or failing test."""
    try:
        record = workflow.start_investigation(
            snapshot_id=request.snapshot_id,
            issue_description=request.issue_description,
            stack_trace=request.stack_trace,
            failing_test=request.failing_test,
            entrypoint=request.entrypoint,
            environment=request.environment,
        )
        return _build_report_response(record)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initiate bug investigation: {str(e)}",
        ) from e


@router.get(
    "/investigations/{id}",
    response_model=InvestigationReportResponse,
    summary="071: Report: call path, ranked hypotheses, evidence",
)
def get_investigation(id: str) -> InvestigationReportResponse:
    """Retrieve full investigation report including call path, ranked hypotheses, and supporting evidence."""
    record = repo.get_investigation(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{id}' not found.",
        )
    return _build_report_response(record)


@router.post(
    "/investigations/{id}/diagnostics",
    response_model=DiagnosticExecuteResponse,
    summary="072: Request an approved diagnostic (sandbox)",
)
def execute_investigation_diagnostic(
    id: str,
    request: DiagnosticExecuteRequest,
) -> DiagnosticExecuteResponse:
    """Execute an approved diagnostic step in the isolated sandbox, enforcing the EXECUTE opt-in gate."""
    # Check investigation exists
    inv = repo.get_investigation(id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{id}' not found.",
        )

    # Check explicit EXECUTE consent gate
    if not request.consent.execute:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Execution denied: explicit EXECUTE opt-in approval is required for sandbox execution.",
        )

    try:
        diag_step = workflow.execute_diagnostic(
            run_id=id,
            consent_execute=request.consent.execute,
            diagnostic_id=request.diagnostic_id,
            approver_id=request.consent.approver_id,
            simulate_outcome=request.simulate_outcome,
        )

        updated_inv = repo.get_investigation(id)
        reproduction_status = updated_inv.reproduction_status if updated_inv else inv.reproduction_status

        return DiagnosticExecuteResponse(
            diagnostic_id=diag_step.id,
            run_id=id,
            status=diag_step.status,
            reproduction_status=reproduction_status,
            test_results=diag_step.test_results,
            message="Diagnostic executed successfully in sandbox",
        )
    except ExecutionConsentRequiredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute diagnostic: {str(e)}",
        ) from e
