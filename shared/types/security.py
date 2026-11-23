"""Security types and data models for Mastermind Feature 6 (Security Vulnerability Detection).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3, §14.2
- API and Data Specification v1.0 §3.3 (Endpoints 089, 090), §3.4.14, §3.8.2, §4.6
- Security and Testing Specification v1.0 §7.3.3, §7.4, §8.9 (AI-10), UT-13, UT-26, IT-16, E2E-11
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus, RunStatus
from shared.types.findings import ToolCoverage


class SecretFindingRecord(BaseModel):
    """Repository-scoped secret finding metadata.

    Invariant I9 / SEC-SECRET-01:
    NO column may hold the raw secret value. Only the SHA256 fingerprint hash is stored.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    finding_id: str
    secret_type: str  # AWS_KEY, GITHUB_TOKEN, PRIVATE_KEY, JWT, AI_API_KEY, etc.
    fingerprint: str  # SHA-256 hash of secret value only
    file_path: str
    line: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DependencyInventoryItem(BaseModel):
    """Manifest-derived external dependency item without installing packages (SEC-DEP-09)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    module_id: Optional[str] = None
    ecosystem: str  # pypi, npm, go, maven, etc.
    package: str
    version_spec: str
    resolved_version: Optional[str] = None
    scope: str = "runtime"  # runtime, dev, test
    manifest_path: str
    advisory_ids: List[str] = Field(default_factory=list)


class VulnerabilityAdvisory(BaseModel):
    """Vulnerability advisory entry from CVE/GHSA feeds."""
    id: str  # e.g. CVE-2023-32681, GHSA-j8r2-6x86-q33q
    package: str
    ecosystem: str
    vulnerable_versions: str  # Semantic version constraint expression e.g. "< 2.31.0"
    fixed_version: Optional[str] = None
    severity: FindingSeverity = FindingSeverity.HIGH
    cvss_score: float = Field(default=7.5, ge=0.0, le=10.0)
    cwe: str = "CWE-1395"
    owasp: str = "A06:2021-Vulnerable and Outdated Components"
    title: str
    description: str
    remediation: str


class SecurityScanReport(BaseModel):
    """Comprehensive Security Scan Report (Endpoint 089/090, Acceptance Criteria M6)."""
    scan_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    run_type: str = "SECURITY"
    status: RunStatus = RunStatus.COMPLETED
    scan_profile: str = "standard"  # fast, standard, deep
    tool_coverage: List[ToolCoverage] = Field(default_factory=list)
    not_checked: List[str] = Field(
        default_factory=list,
        description="Explicit disclosure of what was NOT checked so a partial scan is never read as clean.",
    )
    total_findings: int = 0
    counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    counts_by_origin: Dict[str, int] = Field(default_factory=dict)
    sast_findings_count: int = 0
    secret_findings_count: int = 0
    dependency_findings_count: int = 0
    warnings: List[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
