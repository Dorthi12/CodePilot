"""Finding models and types."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from shared.types.agent import FindingOrigin, FindingSeverity, FindingStatus


class FindingLocation(BaseModel):
    file_path: str
    line_start: int
    line_end: int
    symbol_id: Optional[str] = None


class FindingEvidence(BaseModel):
    source_ref_id: Optional[str] = None
    file_path: str
    line_start: int
    line_end: int
    snippet: str
    snippet_hash: Optional[str] = None
    role: str = "SUPPORTS"  # SUPPORTS or CONTRADICTS


class Finding(BaseModel):
    id: str
    snapshot_id: str
    analysis_run_id: str
    fingerprint: str
    origin: FindingOrigin = FindingOrigin.AI_HYPOTHESIS
    category: str  # SECURITY, CODE_QUALITY, ARCHITECTURE, PERFORMANCE, BUG
    rule_id: str
    tool: str
    tool_version: str = "1.0.0"
    severity: FindingSeverity = FindingSeverity.MEDIUM
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    cwe: Optional[str] = None
    owasp: Optional[str] = None
    title: str
    description: str
    remediation: Optional[str] = None
    file_path: str
    line_start: int
    line_end: int
    symbol_id: Optional[str] = None
    evidence: List[FindingEvidence] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.OPEN
    agent_role: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
