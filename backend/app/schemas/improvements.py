"""Pydantic schemas for Mastermind Feature 3 (Code Improvement Suggestions) API.

Specifications:
- Master Architecture Specification v2.1 §10 (M3)
- API and Data Specification v1.0 §3.3 (Endpoints 073, 074, 075), §3.4.13
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from shared.types.agent import FindingSeverity
from shared.types.investigation import EvidenceRef
from shared.types.suggestions import (
    EffortLevel,
    RiskLevel,
    SuggestionCategory,
    SuggestionStatus,
)
from backend.app.schemas.findings import CodeQualityScope


class ImprovementAnalyzeRequest(BaseModel):
    """Request payload to initiate a code improvement analysis run (Endpoint 073)."""
    snapshot_id: str = Field(..., description="Target repository snapshot identifier")
    scope: Optional[CodeQualityScope] = Field(default_factory=CodeQualityScope, description="Scope filter")
    categories: Optional[List[SuggestionCategory]] = Field(
        default=None, description="Optional filter of improvement categories to evaluate"
    )
    constraints: Optional[List[str]] = Field(
        default_factory=list, description="Architectural or operational constraints"
    )
    severity_threshold: Optional[FindingSeverity] = Field(
        default=FindingSeverity.LOW, description="Minimum severity threshold"
    )
    repository_id: Optional[str] = Field(
        default=None, description="Optional repository ID for suppressions evaluation"
    )


class SuggestionResponse(BaseModel):
    """Detailed response for a single code improvement suggestion."""
    id: str
    run_id: str
    snapshot_id: str
    category: SuggestionCategory
    rule_id: str
    title: str
    problem: str
    recommendation: str
    current_code: Optional[str] = None
    proposed_code: Optional[str] = None
    benefit: str
    effort: EffortLevel
    risk: RiskLevel
    trade_offs: Optional[str] = None
    affected_symbols: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    status: SuggestionStatus
    version: int
    feedback: Optional[str] = None
    priority_score: float
    confidence: float
    created_at: datetime
    updated_at: Optional[datetime] = None


class ImprovementReportResponse(BaseModel):
    """Full improvement report returned by Endpoints 073 and 074."""
    run_id: str
    snapshot_id: str
    status: str
    total_suggestions: int
    counts_by_category: Dict[str, int] = Field(default_factory=dict)
    counts_by_status: Dict[str, int] = Field(default_factory=dict)
    counts_by_effort: Dict[str, int] = Field(default_factory=dict)
    counts_by_risk: Dict[str, int] = Field(default_factory=dict)
    hotspot_files: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[SuggestionResponse] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None


class SuggestionPatchRequest(BaseModel):
    """Payload to update suggestion status or feedback (Endpoint 075)."""
    status: SuggestionStatus = Field(..., description="Target status: ACCEPTED or DISMISSED")
    feedback: Optional[str] = Field(default=None, description="User justification or feedback")
    version: Optional[int] = Field(
        default=None, description="Expected resource version for optimistic concurrency control"
    )
