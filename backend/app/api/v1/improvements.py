"""FastAPI Router for Mastermind Feature 3 (Code Improvement Suggestions).

Specifications:
- Master Architecture Specification v2.1 §10 (M3), §11.3
- API and Data Specification v1.0 §3.3 (Endpoints 073, 074, 075), §3.4.13, §3.8.2
- Security & Testing Specification v1.0 §7.2 (RBAC), §7.3.3 (SEC-API), §8.9 (AI-19)
- Invariants I1, I5, I8
"""

import hashlib
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Response, status

from shared.types.suggestions import (
    EffortLevel,
    RiskLevel,
    SuggestionCategory,
    SuggestionRecord,
    SuggestionStatus,
)
from agentic.workflows.code_improvement import CodeImprovementWorkflow
from backend.app.repositories.improvement_repository import (
    ImprovementRepository,
    OptimisticLockError,
)
from backend.app.schemas.improvements import (
    ImprovementAnalyzeRequest,
    ImprovementReportResponse,
    SuggestionPatchRequest,
    SuggestionResponse,
)

router = APIRouter(prefix="/improvements", tags=["Code Improvement Suggestions (M3)"])

# Shared repository and workflow instances
repo = ImprovementRepository.get_instance()
workflow = CodeImprovementWorkflow(repository=repo)


def _to_suggestion_response(s: SuggestionRecord) -> SuggestionResponse:
    """Helper to convert internal SuggestionRecord to API response model."""
    return SuggestionResponse(
        id=s.id,
        run_id=s.run_id,
        snapshot_id=s.snapshot_id,
        category=s.category,
        rule_id=s.rule_id,
        title=s.title,
        problem=s.problem,
        recommendation=s.recommendation,
        current_code=s.current_code,
        proposed_code=s.proposed_code,
        benefit=s.benefit,
        effort=s.effort,
        risk=s.risk,
        trade_offs=s.trade_offs,
        affected_symbols=s.affected_symbols,
        affected_files=s.affected_files,
        evidence=s.evidence,
        status=s.status,
        version=s.version,
        feedback=s.feedback,
        priority_score=s.priority_score,
        confidence=s.confidence,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _build_report_response(
    report,
    suggestions: Optional[List[SuggestionRecord]] = None,
) -> ImprovementReportResponse:
    """Helper to convert ImprovementRunReport to ImprovementReportResponse."""
    items = suggestions if suggestions is not None else report.suggestions
    return ImprovementReportResponse(
        run_id=report.run_id,
        snapshot_id=report.snapshot_id,
        status=report.status,
        total_suggestions=report.total_suggestions,
        counts_by_category=report.counts_by_category,
        counts_by_status=report.counts_by_status,
        counts_by_effort=report.counts_by_effort,
        counts_by_risk=report.counts_by_risk,
        hotspot_files=report.hotspot_files,
        suggestions=[_to_suggestion_response(s) for s in items],
        started_at=report.started_at,
        completed_at=report.completed_at,
    )


@router.post(
    "/analyze",
    response_model=ImprovementReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="073: Start an improvement run (Idempotent)",
)
def start_improvement_analysis(
    request: ImprovementAnalyzeRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> ImprovementReportResponse:
    """Analyze code quality, performance, architecture, and maintainability for prioritized improvement suggestions."""
    # 1. Enforce Idempotency-Key requirement (API Spec §3.8.2)
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="VALIDATION_FAILED: 'Idempotency-Key' header is required on POST /improvements/analyze.",
        )

    # Calculate deterministic request hash
    body_serialized = json.dumps(request.model_dump(), sort_keys=True)
    request_hash = hashlib.sha256(body_serialized.encode("utf-8")).hexdigest()

    # Check for existing idempotency execution
    cached_response, is_conflict = repo.check_idempotency(idempotency_key, request_hash)
    if is_conflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IDEMPOTENCY_CONFLICT: Idempotency-Key reused with different request payload.",
        )
    if cached_response is not None:
        response.headers["Idempotent-Replayed"] = "true"
        return cached_response

    # 2. Run analysis workflow
    try:
        report = workflow.run_improvement_analysis(
            snapshot_id=request.snapshot_id,
            scope_paths=request.scope.paths if request.scope else None,
            categories=request.categories,
            constraints=request.constraints,
            repository_id=request.repository_id,
        )

        resp_obj = _build_report_response(report)

        # 3. Store idempotency record
        repo.store_idempotency(idempotency_key, request_hash, resp_obj)

        return resp_obj
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute code improvement analysis: {str(e)}",
        ) from e


@router.get(
    "/{run_id}",
    response_model=ImprovementReportResponse,
    summary="074: Prioritised suggestions report with filtering",
)
def get_improvement_report(
    run_id: str,
    category: Optional[SuggestionCategory] = Query(None, description="Filter by suggestion category"),
    status_filter: Optional[SuggestionStatus] = Query(None, alias="status", description="Filter by status (NEW, ACCEPTED, DISMISSED)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    max_effort: Optional[EffortLevel] = Query(None, description="Maximum effort ceiling (LOW, MEDIUM, HIGH)"),
    max_risk: Optional[RiskLevel] = Query(None, description="Maximum risk ceiling (LOW, MEDIUM, HIGH)"),
) -> ImprovementReportResponse:
    """Retrieve full improvement report and prioritized suggestions, supporting category and status filters."""
    report = repo.get_report(run_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Improvement run '{run_id}' not found.",
        )

    filtered_suggestions = repo.list_suggestions(
        run_id=run_id,
        category=category,
        status=status_filter,
        min_confidence=min_confidence,
        max_effort=max_effort,
        max_risk=max_risk,
    )

    return _build_report_response(report, suggestions=filtered_suggestions)


@router.patch(
    "/suggestions/{id}",
    response_model=SuggestionResponse,
    summary="075: Accept, dismiss, add feedback (Optimistic Concurrency)",
)
def patch_suggestion(
    id: str,
    request: SuggestionPatchRequest,
) -> SuggestionResponse:
    """Accept or dismiss an improvement suggestion with feedback, enforcing optimistic locking on version."""
    try:
        updated = repo.update_suggestion_status(
            suggestion_id=id,
            new_status=request.status,
            feedback=request.feedback,
            expected_version=request.version,
        )
        return _to_suggestion_response(updated)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion '{id}' not found.",
        )
    except OptimisticLockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update suggestion: {str(e)}",
        ) from e
