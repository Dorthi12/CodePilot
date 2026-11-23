"""Finding models, types, and schemas matching CodePilot Specification (A3 & Shared)."""

import hashlib
import posixpath
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus, RunStatus


def compute_finding_fingerprint(
    rule_id: str,
    file_path: str,
    symbol_or_anchor: Optional[str] = None,
    snippet: Optional[str] = None,
) -> str:
    """Compute stable, snapshot-agnostic SHA256 fingerprint for finding deduplication and carry-forward."""
    # Repository paths are case-sensitive on common hosts. Normalize
    # separators and dot segments without folding case.
    norm_path = posixpath.normpath(file_path.replace("\\", "/").strip()).lstrip("/")
    norm_rule = rule_id.strip().upper()
    norm_symbol = (symbol_or_anchor or "").strip()
    norm_snippet = " ".join((snippet or "").strip().split()[:20])  # Normalize whitespace of first 20 tokens
    raw = f"{norm_rule}|{norm_path}|{norm_symbol}|{norm_snippet}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FindingLocation(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    symbol_id: Optional[str] = None


class FindingEvidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_ref_id: Optional[str] = None
    file_path: str
    line_start: int
    line_end: int
    snippet: str
    snippet_hash: Optional[str] = None
    role: str = "SUPPORTS"  # SUPPORTS or CONTRADICTS

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.snippet_hash and self.snippet:
            self.snippet_hash = hashlib.sha256(self.snippet.encode("utf-8")).hexdigest()


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    analysis_run_id: str
    fingerprint: str
    origin: FindingOrigin = FindingOrigin.STATIC_TOOL
    category: str = "CODE_QUALITY"  # CODE_QUALITY, BUG, SECURITY, PERFORMANCE, ARCHITECTURE
    rule_id: str
    tool: str
    tool_version: str = "1.0.0"
    severity: FindingSeverity = FindingSeverity.MEDIUM
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    cwe: Optional[str] = None
    owasp: Optional[str] = None
    title: str
    description: str = ""
    remediation: Optional[str] = None
    file_path: str
    line_start: int
    line_end: int
    symbol_id: Optional[str] = None
    evidence: List[FindingEvidence] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.OPEN
    version: int = 1
    status_reason: Optional[str] = None
    status_updated_by: Optional[str] = None
    status_updated_at: Optional[datetime] = None
    agent_role: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RuleMetadata(BaseModel):
    rule_id: str
    tool: str
    pack: str = "default"
    category: str = "CODE_QUALITY"
    default_severity: FindingSeverity = FindingSeverity.MEDIUM
    cwe: Optional[str] = None
    owasp: Optional[str] = None
    title: str
    description: str
    remediation: Optional[str] = None


class Suppression(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    repository_id: str
    fingerprint: Optional[str] = None
    rule_id: Optional[str] = None
    path_glob: Optional[str] = None
    reason: str
    created_by: str = "developer"
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def matches(self, finding: Finding) -> bool:
        """Check if this suppression matches the given finding."""
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        if self.fingerprint and finding.fingerprint == self.fingerprint:
            return True
        if self.rule_id and self.rule_id == finding.rule_id:
            if not self.path_glob:
                return True
            import fnmatch
            norm_file = finding.file_path.replace("\\", "/")
            norm_glob = self.path_glob.replace("\\", "/")
            return fnmatch.fnmatch(norm_file, norm_glob)
        return False


class ToolCoverage(BaseModel):
    tool: str
    version: str = "1.0.0"
    status: str = "SUCCESS"  # SUCCESS, PARTIAL, FAILED, TIMEOUT, SKIPPED
    duration_ms: float = 0.0
    files_scanned: int = 0
    rules_run: int = 0
    findings_count: int = 0
    error: Optional[str] = None


class ToolExecutionLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    tool: str
    tool_version: str
    status: str
    duration_ms: float
    coverage: Dict[str, Any] = Field(default_factory=dict)
    stderr_redacted: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalysisRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    run_type: str = "QUALITY"
    status: RunStatus = RunStatus.RUNNING
    job_id: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    model_and_tool_versions: Dict[str, str] = Field(default_factory=dict)
    cost_estimate: float = 0.0
    created_by: str = "developer"
    tool_coverage: List[ToolCoverage] = Field(default_factory=list)
    counts_by_severity: Dict[str, int] = Field(default_factory=dict)
    counts_by_origin: Dict[str, int] = Field(default_factory=dict)
    total_findings: int = 0
    warnings: List[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
