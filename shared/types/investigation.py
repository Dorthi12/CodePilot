"""Shared types, enums, and data models for Mastermind Feature 2 (AI Bug Investigation).

Specifications:
- Master Architecture Specification v2.1 §10 (M2), §6.6
- API and Data Specification v1.0 §3.4.13, §4.6, §4.10
- Security and Testing Specification v1.0 §8.9 (AI-11), Appendix C.g (Case G0-I-004)
- System Design Specification v1.0 §7.36
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class HypothesisStatus(str, Enum):
    """Lifecycle status of a root cause hypothesis (Master Spec §10 M2, API Spec §4.6)."""
    UNCONFIRMED = "UNCONFIRMED"
    SUPPORTED = "SUPPORTED"
    REPRODUCED = "REPRODUCED"
    REFUTED = "REFUTED"


class ReproductionStatus(str, Enum):
    """Reproduction status of the reported issue."""
    NOT_REPRODUCED = "NOT_REPRODUCED"
    REPRODUCED = "REPRODUCED"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


class DiagnosticKind(str, Enum):
    """Type of diagnostic action for bug investigation."""
    SANDBOX_TEST = "SANDBOX_TEST"
    STATIC_CHECK = "STATIC_CHECK"
    CALL_GRAPH_INSPECTION = "CALL_GRAPH_INSPECTION"
    LOG_ANALYSIS = "LOG_ANALYSIS"


class DiagnosticStatus(str, Enum):
    """Status of a diagnostic step."""
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class EvidenceRole(str, Enum):
    """Role of an evidence reference (SUPPORTS or CONTRADICTS per API Spec §4.6)."""
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"


class StackTraceLanguage(str, Enum):
    """Supported stack trace formats (Master Spec §10 M2, AUD-11)."""
    PYTHON = "PYTHON"
    NODE = "NODE"
    JAVA = "JAVA"
    GO = "GO"
    UNKNOWN = "UNKNOWN"


class InvestigationFrame(BaseModel):
    """Parsed stack trace frame mapped to repository files via longest-suffix match."""
    frame_index: int
    raw_file_path: str
    mapped_file_path: Optional[str] = None
    line: int
    column: Optional[int] = None
    function_name: Optional[str] = None
    code_line: Optional[str] = None
    is_mapped: bool = False
    is_ambiguous: bool = False
    candidates: List[str] = Field(default_factory=list)
    symbol_id: Optional[str] = None


class ParsedStackTrace(BaseModel):
    """Complete parsed stack trace representation."""
    language: StackTraceLanguage = StackTraceLanguage.UNKNOWN
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    frames: List[InvestigationFrame] = Field(default_factory=list)
    raw_trace: str
    redacted_trace: str
    unmapped_frames_count: int = 0
    ambiguous_frames_count: int = 0


class EvidenceRef(BaseModel):
    """Polymorphic evidence reference model matching database table evidence_refs."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    owner_type: str = "HYPOTHESIS"  # FINDING, HYPOTHESIS, SUGGESTION, COMMENT
    owner_id: str
    source_ref_id: Optional[str] = None
    file_path: str
    line_start: int
    line_end: int
    snippet: str
    snippet_hash: str
    role: EvidenceRole = EvidenceRole.SUPPORTS
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Hypothesis(BaseModel):
    """Ranked root cause hypothesis."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    rank: int
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: HypothesisStatus = HypothesisStatus.UNCONFIRMED
    file_path: Optional[str] = None
    function: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    rationale: str
    evidence: List[EvidenceRef] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DiagnosticStep(BaseModel):
    """Diagnostic step (e.g. sandboxed test execution) requiring approval."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    hypothesis_id: Optional[str] = None
    kind: DiagnosticKind = DiagnosticKind.SANDBOX_TEST
    command_ref: str
    status: DiagnosticStatus = DiagnosticStatus.PENDING_APPROVAL
    result_ref: Optional[str] = None
    approved_by: Optional[str] = None
    limits: Dict[str, Any] = Field(default_factory=lambda: {
        "timeout_seconds": 60,
        "max_memory_mb": 2048,
        "network": "NONE",
    })
    test_results: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CallPathFrame(BaseModel):
    """Frame in the reconstructed call execution path."""
    order: int
    file_path: str
    line: int
    function: Optional[str] = None
    snippet: Optional[str] = None
    is_root_cause_candidate: bool = False
    is_entrypoint: bool = False


class InvestigationRecord(BaseModel):
    """Persisted record for an AI Bug Investigation run (Table investigations)."""
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    snapshot_id: str
    issue_description: str
    stack_trace_raw: Optional[str] = None
    stack_trace_redacted: Optional[str] = None
    parsed_frames: List[InvestigationFrame] = Field(default_factory=list)
    failing_test: Optional[str] = None
    entrypoint: Optional[str] = None
    environment_redacted: Dict[str, Any] = Field(default_factory=dict)
    reproduction_status: ReproductionStatus = ReproductionStatus.NOT_REPRODUCED
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    call_path: List[CallPathFrame] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    diagnostics: List[DiagnosticStep] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    problem_summary: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
