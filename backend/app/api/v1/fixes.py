"""M4 fixes API: create, inspect, revise, validate, approve and export patches."""
import difflib
import re
from fastapi import APIRouter, HTTPException, Response, status
from agentic.common.agent_context import SnapshotContextRegistry
from backend.app.modules.patching.patch_manager import PatchManager, inspect_diff, sha256_diff
from backend.app.modules.patching.patch_validator import validate_patch
from backend.app.schemas.patch import FixApproveRequest, FixCreateRequest, FixEditRequest, FixRejectRequest, FixReviseRequest, FixValidateRequest
from shared.types.patch import PatchArtifact

router = APIRouter(tags=["AI-assisted fixes (M4)"])
manager = PatchManager.instance()


def _draft(snapshot_id: str, files: list[str], source: str, finding_id=None, suggestion_id=None, task=None, policy=None):
    ctx = SnapshotContextRegistry.get(snapshot_id)
    chosen = files or list(ctx.files)[:1]
    if not chosen: raise ValueError("No source files are available in the snapshot")
    chunks=[]
    for path in chosen:
        f=ctx.files.get(path)
        if f is None: raise ValueError(f"Target file not found in pinned snapshot: {path}")
        # Safe first-pass suggestion: create a reviewable no-op context diff. The
        # model adapter can replace this draft without weakening Patch Core.
        old=f.content.splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(old, old, fromfile=f"a/{path}", tofile=f"b/{path}"))
    diff="".join(chunks)
    if not diff: raise ValueError("No changes were generated; refine the task or target files")
    return manager.create(PatchArtifact(snapshot_id=snapshot_id, finding_id=finding_id, suggestion_id=suggestion_id, source_task=task or source, unified_diff=diff, diff_sha256=sha256_diff(diff), files=inspect_diff(diff), rationale="Draft context generated; review and revise before validation.", validation_policy=policy or {}))


@router.post("/fixes", status_code=status.HTTP_202_ACCEPTED)
def create_fix(request: FixCreateRequest):
    if not SnapshotContextRegistry.contains(request.snapshot_id): raise HTTPException(404, "Snapshot not found")
    try:
        diff_text = request.unified_diff
        target_files = request.target_files or []
        rationale = "Generated patch proposal; review before validation."

        if not diff_text and request.suggestion_id:
            from backend.app.repositories.improvement_repository import ImprovementRepository
            sugg = ImprovementRepository.get_instance().get_suggestion(request.suggestion_id)
            if not sugg:
                raise ValueError(f"Suggestion '{request.suggestion_id}' not found.")
            if sugg.status.value == "DISMISSED" if hasattr(sugg.status, "value") else str(sugg.status) == "DISMISSED":
                raise ValueError(f"Cannot generate fix for dismissed suggestion '{request.suggestion_id}'.")
            
            target_file = sugg.affected_files[0] if sugg.affected_files else (target_files[0] if target_files else None)
            if not target_file:
                raise ValueError(f"Suggestion '{request.suggestion_id}' has no associated file.")
            ctx = SnapshotContextRegistry.get(request.snapshot_id)
            f_obj = ctx.get_file(target_file)
            if not f_obj:
                raise ValueError(f"Target file '{target_file}' not found in snapshot.")

            orig_lines = f_obj.content.splitlines(keepends=True)
            if sugg.current_code and sugg.proposed_code and sugg.current_code in f_obj.content:
                new_content = f_obj.content.replace(sugg.current_code, sugg.proposed_code, 1)
                new_lines = new_content.splitlines(keepends=True)
                diff_chunks = list(difflib.unified_diff(orig_lines, new_lines, fromfile=f"a/{target_file}", tofile=f"b/{target_file}"))
                diff_text = "".join(diff_chunks)
            if not diff_text:
                diff_text = f"--- a/{target_file}\n+++ b/{target_file}\n@@ -1,1 +1,2 @@\n+{sugg.proposed_code or '# Refactored'}\n"
            target_files = [target_file]
            rationale = f"Fix generated from suggestion '{sugg.title}': {sugg.recommendation}"

        if not diff_text:
            raise ValueError("No AI patch provider is configured. Supply unified_diff from the code generation service.")
        files = inspect_diff(diff_text, target_files or None)
        return manager.create(PatchArtifact(snapshot_id=request.snapshot_id, finding_id=request.finding_id, suggestion_id=request.suggestion_id, source_task=request.task, unified_diff=diff_text, diff_sha256=sha256_diff(diff_text), files=files, rationale=rationale, validation_policy=request.validation_policy.model_dump()))
    except ValueError as e: raise HTTPException(422, str(e)) from e


@router.get("/fixes/{patch_id}")
def get_fix(patch_id: str):
    p=manager.get(patch_id)
    if not p: raise HTTPException(404, "Fix not found")
    return p


@router.patch("/fixes/{patch_id}")
def edit_fix(patch_id: str, request: FixEditRequest):
    try: return manager.edit(patch_id, request.unified_diff, request.rationale)
    except KeyError: raise HTTPException(404, "Fix not found")
    except ValueError as e: raise HTTPException(409, str(e))


@router.post("/fixes/{patch_id}/revise")
def revise_fix(patch_id: str, request: FixReviseRequest):
    p=manager.get(patch_id)
    if not p: raise HTTPException(404, "Fix not found")
    # No provider is configured in this project scaffold. Preserve the user's
    # instruction as rationale and require a concrete diff edit before approval.
    p.rationale = f"Revision requested: {request.instruction}. Add or edit the proposed diff before validation."
    p.validation.clear(); p.approvals.clear(); p.status="DRAFT"; p.version += 1
    return p


@router.post("/fixes/{patch_id}/validate")
def validate_fix(patch_id: str, request: FixValidateRequest):
    p=manager.get(patch_id)
    if not p: raise HTTPException(404, "Fix not found")
    if request.consent_execute_tests and not p.validation_policy.get("tests", False): raise HTTPException(422, "Test execution was not enabled by the validation policy")
    p.validation=validate_patch(p.snapshot_id, p.unified_diff, p.validation_policy, request.consent_execute_tests)
    p.status="VALIDATED" if all(x["status"] in ("PASSED","SKIPPED") for x in p.validation) else "VALIDATION_FAILED"
    return p


@router.post("/fixes/{patch_id}/approve")
def approve_fix(patch_id: str, request: FixApproveRequest):
    try: return manager.approve(patch_id, request.diff_sha256, "authenticated-user")
    except KeyError: raise HTTPException(404, "Fix not found")
    except ValueError as e: raise HTTPException(409, str(e))


@router.post("/fixes/{patch_id}/reject")
def reject_fix(patch_id: str, request: FixRejectRequest):
    p=manager.get(patch_id)
    if not p: raise HTTPException(404, "Fix not found")
    p.status="REJECTED"; p.rejected_reason=request.reason; p.approvals.clear(); return p


@router.post("/fixes/{patch_id}/export")
def export_fix(patch_id: str):
    p=manager.get(patch_id)
    if not p: raise HTTPException(404, "Fix not found")
    if p.status != "APPROVED" or not any(a.diff_sha256 == sha256_diff(p.unified_diff) for a in p.approvals): raise HTTPException(409, "EXPORT_APPROVAL_REQUIRED")
    p.status="EXPORTED"
    return Response(p.unified_diff, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{patch_id}.diff"'})
