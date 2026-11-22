"""FastAPI Router for Feature A3 (Bug and Code Smell Detection) and Findings Management."""

import fnmatch
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus
from shared.types.findings import Finding, Suppression
from agentic.common.agent_context import SnapshotContextRegistry
from backend.app.modules.code_analysis.engine import CodeQualityEngine
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.schemas.findings import (
    AnalysisRunResponse,
    CodeQualityRequest,
    CodeQualityResponse,
    FindingPatchRequest,
    FindingsListResponse,
    SuppressionCreateRequest,
)

router = APIRouter(tags=["Code Quality & Findings (A3)"])

# Shared engine and repository instances
repo = FindingsRepository.get_instance()
engine = CodeQualityEngine(repository=repo)


@router.post(
    "/analysis/code-quality",
    response_model=CodeQualityResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="043: Start a bug and code-smell analysis run",
)
def start_code_quality_analysis(
    request: CodeQualityRequest,
    background_tasks: BackgroundTasks,
) -> CodeQualityResponse:
    """Start an optimized code quality and smell detection analysis run on a snapshot."""
    try:
        if not SnapshotContextRegistry.contains(request.snapshot_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Snapshot was not found or is not available for analysis.",
            )
        paths = request.scope.paths if request.scope else None
        changed_only = request.scope.changed_files_only if request.scope else False
        if changed_only:
            changed_files = request.scope.changed_files if request.scope else None
            if not changed_files:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="scope.changed_files is required when changed_files_only is true.",
                )
            # A caller can narrow changed files with an additional path scope.
            paths = changed_files if not paths else [
                changed for changed in changed_files
                if any(
                    fnmatch.fnmatch(changed.replace("\\", "/"), scope.replace("\\", "/"))
                    for scope in paths
                )
            ]

        run = engine.create_pending_run(
            snapshot_id=request.snapshot_id,
            paths=paths,
            changed_files_only=changed_only,
            rule_pack=request.rule_pack,
            severity_threshold=request.severity_threshold,
            repository_id=request.repository_id,
        )
        background_tasks.add_task(
            engine.run_pending_analysis,
            snapshot_id=request.snapshot_id,
            paths=paths,
            changed_files_only=changed_only,
            rule_pack=request.rule_pack,
            severity_threshold=request.severity_threshold,
            repository_id=request.repository_id,
            job_id=run.job_id,
            run_id=run.id,
        )

        return CodeQualityResponse(
            run_id=run.id,
            job_id=run.job_id or run.id,
            status=run.status.value,
            snapshot_id=run.snapshot_id,
            message="Code quality analysis has been queued.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute code quality analysis: {str(e)}",
        ) from e


@router.get(
    "/analysis-runs/{run_id}",
    response_model=AnalysisRunResponse,
    summary="044: Run status, coverage and summary (all run types)",
)
def get_analysis_run(run_id: str) -> AnalysisRunResponse:
    """Retrieve detailed execution status, tool coverage, and severity breakdowns of an analysis run."""
    run = repo.get_analysis_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run '{run_id}' not found.",
        )

    return AnalysisRunResponse(
        run_id=run.id,
        snapshot_id=run.snapshot_id,
        run_type=run.run_type,
        status=run.status.value,
        tool_coverage=run.tool_coverage,
        counts_by_severity=run.counts_by_severity,
        counts_by_origin=run.counts_by_origin,
        total_findings=run.total_findings,
        warnings=run.warnings,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get(
    "/findings",
    response_model=FindingsListResponse,
    summary="045: List findings (quality and security) with filters",
)
def list_findings(
    snapshot_id: Optional[str] = Query(None, description="Filter by snapshot ID"),
    category: Optional[str] = Query(None, description="Filter by category (CODE_QUALITY, BUG, SECURITY, etc.)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)"),
    status: Optional[str] = Query(None, description="Filter by status (OPEN, ACKNOWLEDGED, FALSE_POSITIVE, etc.)"),
    origin: Optional[str] = Query(None, description="Filter by origin (STATIC_TOOL, GRAPH_RULE, AI_HYPOTHESIS, CONFIRMED)"),
    file_path: Optional[str] = Query(None, description="Filter by file path substring"),
    rule_id: Optional[str] = Query(None, description="Filter by rule ID"),
    limit: int = Query(100, ge=1, le=500, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Offset items"),
) -> FindingsListResponse:
    """Query findings across snapshots and repositories with multi-attribute filtering."""
    result = repo.query_findings(
        snapshot_id=snapshot_id,
        category=category,
        severity=severity,
        status=status,
        origin=origin,
        file_path=file_path,
        rule_id=rule_id,
        limit=limit,
        offset=offset,
    )

    return FindingsListResponse(
        items=result["items"],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        counts_by_severity=result["counts_by_severity"],
        counts_by_origin=result["counts_by_origin"],
    )


@router.get(
    "/findings/{id}",
    response_model=Finding,
    summary="046: Finding detail with evidence and citations",
)
def get_finding(id: str) -> Finding:
    """Retrieve full detail for a finding including code snippets and evidence references."""
    finding = repo.get_finding(id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{id}' was not found.",
        )
    return finding


@router.patch(
    "/findings/{id}",
    response_model=Finding,
    summary="047: Change status: acknowledge, false positive, accepted risk, reopen",
)
def update_finding(id: str, patch_data: FindingPatchRequest) -> Finding:
    """Update finding triage status with mandatory human justification for false positives."""
    if patch_data.status in (FindingStatus.FALSE_POSITIVE, FindingStatus.ACCEPTED_RISK) and not (patch_data.reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail="A justification 'reason' is required when marking a finding as FALSE_POSITIVE or ACCEPTED_RISK.",
        )

    try:
        updated = repo.update_finding_status(
            finding_id=id,
            new_status=patch_data.status,
            reason=patch_data.reason,
            user="authorized_user",
        )
        return updated
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding with ID '{id}' was not found.",
        )


@router.post(
    "/suppressions",
    response_model=Suppression,
    status_code=status.HTTP_201_CREATED,
    summary="Add a repository-scoped suppression",
)
def create_suppression(req: SuppressionCreateRequest) -> Suppression:
    """Create a persistent repository-scoped suppression that survives snapshot retirement."""
    if not req.fingerprint and not (req.rule_id and req.path_glob):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suppression must specify either a 'fingerprint' or both 'rule_id' and 'path_glob'.",
        )

    suppression = Suppression(
        repository_id=req.repository_id,
        fingerprint=req.fingerprint,
        rule_id=req.rule_id,
        path_glob=req.path_glob,
        reason=req.reason,
        expires_at=req.expires_at,
    )
    return repo.add_suppression(suppression)


@router.get(
    "/suppressions",
    response_model=List[Suppression],
    summary="List repository-scoped suppressions",
)
def list_suppressions(repository_id: str = Query(..., description="Repository ID")) -> List[Suppression]:
    """List all active suppressions registered for a repository."""
    return repo.get_suppressions_for_repo(repository_id)
