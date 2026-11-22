"""Findings and Code Quality schemas for API serialization and request validation."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus, RunStatus
from shared.types.findings import (
    Finding,
    FindingEvidence,
    FindingLocation,
    RuleMetadata,
    Suppression,
    ToolCoverage,
)


class CodeQualityScope(BaseModel):
    paths: Optional[List[str]] = Field(default=None, description="Paths or path globs to analyze")
    changed_files: Optional[List[str]] = Field(default=None, description="Changed file paths supplied by the caller")
    changed_files_only: bool = Field(default=False, description="Scan only changed or modified files")


class CodeQualityRequest(BaseModel):
    snapshot_id: str = Field(..., description="Target repository snapshot ID")
    scope: Optional[CodeQualityScope] = Field(default_factory=CodeQualityScope, description="Scope filter")
    rule_pack: Literal["default", "strict", "lenient"] = Field(
        default="default", description="Rule pack identifier"
    )
    severity_threshold: FindingSeverity = Field(
        default=FindingSeverity.LOW, description="Minimum severity to include in report"
    )
    repository_id: Optional[str] = Field(default=None, description="Optional repository ID for suppressions scoping")


class CodeQualityResponse(BaseModel):
    run_id: str
    job_id: str
    status: str
    snapshot_id: str
    message: str = "Code quality analysis run started"


class AnalysisRunResponse(BaseModel):
    run_id: str
    snapshot_id: str
    run_type: str = "QUALITY"
    status: str
    tool_coverage: List[ToolCoverage] = Field(default_factory=list)
    counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    counts_by_origin: Dict[str, int] = Field(default_factory=dict)
    total_findings: int = 0
    warnings: List[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None


class FindingPatchRequest(BaseModel):
    status: FindingStatus = Field(..., description="Target finding status")
    reason: Optional[str] = Field(None, description="User justification for status change (mandatory for false positives)")


class SuppressionCreateRequest(BaseModel):
    repository_id: str
    fingerprint: Optional[str] = None
    rule_id: Optional[str] = None
    path_glob: Optional[str] = None
    reason: str
    expires_at: Optional[datetime] = None


class FindingsListResponse(BaseModel):
    items: List[Finding]
    total: int
    limit: int
    offset: int
    counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    counts_by_origin: Dict[str, int] = Field(default_factory=dict)
