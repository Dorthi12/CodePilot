"""Patch artifacts and validation records for M4."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class PatchFile(BaseModel):
    path: str
    change_type: str
    additions: int = 0
    deletions: int = 0


class PatchApproval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    scope: str = "EXPORT"
    diff_sha256: str
    approver_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatchArtifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    base_commit_sha: Optional[str] = None
    finding_id: Optional[str] = None
    suggestion_id: Optional[str] = None
    source_task: Optional[str] = None
    unified_diff: str
    diff_sha256: str
    files: List[PatchFile] = Field(default_factory=list)
    rationale: str = ""
    status: str = "DRAFT"
    validation: List[Dict[str, Any]] = Field(default_factory=list)
    validation_policy: Dict[str, bool] = Field(default_factory=dict)
    approvals: List[PatchApproval] = Field(default_factory=list)
    parent_patch_id: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rejected_reason: Optional[str] = None
    generated_with: str = "deterministic-template-v1"

