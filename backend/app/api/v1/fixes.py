"""M4 fixes API: create, inspect, revise, validate, approve, export, and publish patches.

Specifications:
- Master Architecture Specification v2.1 §10 (M4), §11.3 (Endpoints 076–084)
- API and Data Specification v1.0 §3.3 (Fixes Endpoints 076–084), §3.4.14
- Security & Testing Specification v1.0 §7.9 (Approval and Dangerous-Operation Controls), §7.9.5, §7.9.6
"""

from fastapi import APIRouter, HTTPException, Response, status
from agentic.common.agent_context import SnapshotContextRegistry
from ai_service.generation.patch_generator import PatchGenerator
from backend.app.modules.patching.patch_exporter import PatchExporter
from backend.app.modules.patching.patch_manager import PatchManager, inspect_diff, sha256_diff
from backend.app.modules.patching.patch_validator import validate_patch
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.schemas.patch import (
    FixApproveRequest,
    FixCreateRequest,
    FixEditRequest,
    FixPullRequestCreate,
    FixRejectRequest,
    FixReviseRequest,
    FixValidateRequest,
)
from shared.types.patch import PatchArtifact

router = APIRouter(tags=["AI-assisted fixes (M4)"])
manager = PatchManager.instance()
findings_repo = FindingsRepository.get_instance()


@router.post("/fixes", status_code=status.HTTP_202_ACCEPTED, summary="076: Generate a patch from finding, suggestion or task")
def create_fix(request: FixCreateRequest):
    """Generate or register a patch proposal for a finding, suggestion, or task description."""
    if not SnapshotContextRegistry.contains(request.snapshot_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")

    finding_data = None
    if request.finding_id:
        f = findings_repo.get_finding(request.finding_id)
        if f:
            finding_data = {
                "id": f.id,
                "rule_id": f.rule_id,
                "file_path": f.file_path,
                "line_start": f.line_start,
                "line_end": f.line_end,
                "title": f.title,
            }

    # Generate unified diff using PatchGenerator if not explicitly supplied
    diff = request.unified_diff
    rationale = "Generated patch proposal; review and validate before approval."
    if not diff:
        try:
            issue_desc = request.task or (finding_data.get("title") if finding_data else "Resolve code issue")
            diff, gen_rationale = PatchGenerator.generate_fix_diff(
                snapshot_id=request.snapshot_id,
                target_files=request.target_files,
                issue_or_task=issue_desc,
                finding_details=finding_data,
            )
            rationale = gen_rationale
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        files = inspect_diff(diff, request.target_files or None)
        patch = PatchArtifact(
            snapshot_id=request.snapshot_id,
            finding_id=request.finding_id,
            suggestion_id=request.suggestion_id,
            source_task=request.task,
            unified_diff=diff,
            diff_sha256=sha256_diff(diff),
            files=files,
            rationale=rationale,
            validation_policy=request.validation_policy.model_dump(),
        )
        return manager.create(patch)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/fixes/{patch_id}", summary="077: Patch, diff, rationale, validation, approval state")
def get_fix(patch_id: str):
    """Get patch artifact by ID."""
    p = manager.get(patch_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fix not found")
    return p


@router.patch("/fixes/{patch_id}", summary="078: User edits the diff (clears validation and approval)")
def edit_fix(patch_id: str, request: FixEditRequest):
    """User directly edits the diff text. Enforces Invariant I8: resets validation and approvals."""
    try:
        return manager.edit(patch_id, request.unified_diff, request.rationale)
    except KeyError:
        raise HTTPException(status_code=404, detail="Fix not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/fixes/{patch_id}/revise", status_code=status.HTTP_202_ACCEPTED, summary="079: Ask the model for a revision")
def revise_fix(patch_id: str, request: FixReviseRequest):
    """Ask AI service to revise the patch diff given an instruction, resetting validation and approvals."""
    p = manager.get(patch_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fix not found")

    try:
        new_diff, rationale = PatchGenerator.generate_fix_diff(
            snapshot_id=p.snapshot_id,
            target_files=[f.path for f in p.files],
            issue_or_task=p.source_task or "Revision",
            instruction=request.instruction,
        )
        return manager.revise(patch_id, new_diff, f"Revision applied: {request.instruction}. {rationale}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/fixes/{patch_id}/validate", summary="080: Apply, syntax, lint, test, security, impact checks")
def validate_fix(patch_id: str, request: FixValidateRequest):
    """Run fail-closed validation checks (apply, syntax, lint, security, tests, impact)."""
    p = manager.get(patch_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fix not found")

    if request.consent_execute_tests and not p.validation_policy.get("tests", False):
        raise HTTPException(status_code=422, detail="Test execution was not enabled by the validation policy")

    p.validation = validate_patch(
        snapshot_id=p.snapshot_id,
        diff=p.unified_diff,
        policy=p.validation_policy,
        execute_tests=request.consent_execute_tests,
    )
    p.status = "VALIDATED" if all(x["status"] in ("PASSED", "SKIPPED") for x in p.validation) else "VALIDATION_FAILED"
    return p


@router.post("/fixes/{patch_id}/approve", summary="081: Approve export (bound to diff_sha256)")
def approve_fix(patch_id: str, request: FixApproveRequest):
    """Approve patch, verifying cryptographic binding to the diff SHA256 and passed validation."""
    try:
        return manager.approve(patch_id, request.diff_sha256, approver_id="authenticated_admin", scope=request.scope)
    except KeyError:
        raise HTTPException(status_code=404, detail="Fix not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/fixes/{patch_id}/reject", summary="082: Reject the patch")
def reject_fix(patch_id: str, request: FixRejectRequest):
    """Reject patch proposal with a reason, resetting approvals."""
    p = manager.get(patch_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fix not found")
    p.status = "REJECTED"
    p.rejected_reason = request.reason
    p.approvals.clear()
    return p


@router.post("/fixes/{patch_id}/export", summary="083: Download unified diff")
def export_fix(patch_id: str):
    """Export approved unified diff as an attachment file."""
    p = manager.get(patch_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fix not found")

    try:
        diff_content, headers = PatchExporter.export_unified_diff(p)
        p.status = "EXPORTED"
        return Response(content=diff_content, media_type=headers["Content-Type"], headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/fixes/{patch_id}/pull-request", status_code=status.HTTP_202_ACCEPTED, summary="084: Create branch/PR; separate PUBLISH approval")
def create_pull_request_for_fix(patch_id: str, request: FixPullRequestCreate):
    """Create branch and PR on GitHub for approved patch. Enforces D3 publish gate and branch namespacing."""
    p = manager.get(patch_id)
    if not p:
        raise HTTPException(status_code=404, detail="Fix not found")

    try:
        pr_result = manager.publish_pull_request(
            patch_id=patch_id,
            publish_approval_id=request.publish_approval_id,
            branch_name=request.branch_name,
            title=request.title,
            body=request.body or "",
            approver_id="owner_user",
        )
        return pr_result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
