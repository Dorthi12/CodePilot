"""Pydantic schemas for Mastermind Feature 6 (Security Vulnerability Detection).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3
- API and Data Specification v1.0 §3.3 (089, 090), §3.4.14
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from shared.types.agent import FindingSeverity
from shared.types.findings import ToolCoverage
from shared.types.security import SecurityScanReport


class SecurityScanRequest(BaseModel):
    """089: Request to start a security scan run."""
    snapshot_id: str = Field(..., description="Target repository snapshot ID")
    scan_profile: Literal["fast", "standard", "deep"] = Field(
        default="standard", description="Scan profile (fast, standard, deep)"
    )
    languages: List[str] = Field(
        default_factory=lambda: ["python"], description="Languages to include in analysis"
    )
    include_dependencies: bool = Field(
        default=True, description="Whether to include dependency vulnerability audit (SCA)"
    )
    changed_files_only: bool = Field(
        default=False, description="Whether to restrict scan to changed files only"
    )
    paths: Optional[List[str]] = Field(
        default=None, description="Optional paths or glob filters to analyze"
    )
    changed_files: Optional[List[str]] = Field(
        default=None, description="List of changed file paths when changed_files_only is true"
    )
    severity_threshold: FindingSeverity = Field(
        default=FindingSeverity.LOW, description="Minimum severity threshold to report"
    )
    repository_id: Optional[str] = Field(
        default=None, description="Optional repository ID for suppressions and carry-forward"
    )


class SecurityScanResponse(BaseModel):
    """089/090: Security scan execution and status report."""
    scan_id: str
    run_id: str
    job_id: str
    snapshot_id: str
    status: str
    scan_profile: str
    tool_coverage: List[ToolCoverage] = Field(default_factory=list)
    not_checked: List[str] = Field(
        default_factory=list,
        description="Explicit list of what was NOT checked so a partial scan is never read as clean.",
    )
    total_findings: int = 0
    counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    counts_by_origin: Dict[str, int] = Field(default_factory=dict)
    sast_findings_count: int = 0
    secret_findings_count: int = 0
    dependency_findings_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    message: str = "Security scan completed successfully."
    started_at: datetime
    completed_at: Optional[datetime] = None
