"""Shared types, enums, and data models for Mastermind Feature 3 (Code Improvement Suggestions).

Specifications:
- Master Architecture Specification v2.1 §10 (M3), §6.6
- API and Data Specification v1.0 §3.3 (Endpoints 073, 074, 075), §4.6, §4.10
- Security and Testing Specification v1.0 §7.2, §7.3, §7.8, §8.9 (AI-19)
- System Design Specification v1.0 §4, §5, §8, §9
"""

import hashlib
import posixpath
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from shared.types.investigation import EvidenceRef, EvidenceRole


class SuggestionCategory(str, Enum):
    """Categories of code improvement suggestions (Master Spec §10 M3)."""
    PERFORMANCE = "PERFORMANCE"
    MAINTAINABILITY = "MAINTAINABILITY"
    READABILITY = "READABILITY"
    ARCHITECTURE = "ARCHITECTURE"
    CODE_QUALITY = "CODE_QUALITY"


class SuggestionStatus(str, Enum):
    """Lifecycle status of an improvement suggestion (Master Spec §10 M3, API Spec §4.6)."""
    NEW = "NEW"
    ACCEPTED = "ACCEPTED"
    DISMISSED = "DISMISSED"


class EffortLevel(str, Enum):
    """Estimated effort required to implement the suggestion (LOW, MEDIUM, HIGH per API Spec §4.6)."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskLevel(str, Enum):
    """Estimated architectural/behavioral risk of applying the suggestion (LOW, MEDIUM, HIGH per API Spec §4.6)."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def compute_suggestion_fingerprint(
    rule_id: str,
    file_path: str,
    line_start: int,
    category: str,
    title: str,
) -> str:
    """Compute deterministic fingerprint for suggestion deduplication and carry-forward."""
    norm_path = posixpath.normpath(file_path.replace("\\", "/").strip()).lstrip("/")
    norm_rule = rule_id.strip().upper()
    norm_cat = category.strip().upper()
    norm_title = " ".join(title.strip().split()[:15])
    raw = f"{norm_rule}|{norm_cat}|{norm_path}|{line_start}|{norm_title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SuggestionRecord(BaseModel):
    """Comprehensive representation of an evidence-backed code improvement suggestion."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    snapshot_id: str
    tenant_id: str = "default-tenant"
    category: SuggestionCategory
    rule_id: str
    title: str
    problem: str
    recommendation: str
    current_code: Optional[str] = None
    proposed_code: Optional[str] = None
    benefit: str
    effort: EffortLevel = EffortLevel.LOW
    risk: RiskLevel = RiskLevel.LOW
    trade_offs: Optional[str] = None
    affected_symbols: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    status: SuggestionStatus = SuggestionStatus.NEW
    version: int = 1
    feedback: Optional[str] = None
    priority_score: float = 0.0
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    fingerprint: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.fingerprint and self.rule_id and self.affected_files:
            file_p = self.affected_files[0] if self.affected_files else "unknown"
            line_s = self.evidence[0].line_start if self.evidence else 1
            self.fingerprint = compute_suggestion_fingerprint(
                rule_id=self.rule_id,
                file_path=file_p,
                line_start=line_s,
                category=self.category.value,
                title=self.title,
            )


class ImprovementRunReport(BaseModel):
    """Aggregated report of an improvement run (Master Spec §10 M3, API Spec §3.4.13)."""
    run_id: str
    snapshot_id: str
    status: str
    total_suggestions: int = 0
    counts_by_category: Dict[str, int] = Field(default_factory=dict)
    counts_by_status: Dict[str, int] = Field(default_factory=dict)
    counts_by_effort: Dict[str, int] = Field(default_factory=dict)
    counts_by_risk: Dict[str, int] = Field(default_factory=dict)
    hotspot_files: List[Dict[str, Any]] = Field(default_factory=list)
    suggestions: List[SuggestionRecord] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
