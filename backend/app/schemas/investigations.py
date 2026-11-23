"""Pydantic schemas for Mastermind Feature 2 (AI Bug Investigation) API serialization.

Specifications:
- Master Architecture Specification v2.1 §10 (M2)
- API and Data Specification v1.0 §3.3 (Endpoints 070, 071, 072), §3.4.13
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from shared.types.investigation import (
    CallPathFrame,
    DiagnosticKind,
    DiagnosticStatus,
    EvidenceRef,
    HypothesisStatus,
    InvestigationFrame,
    ReproductionStatus,
)


class DiagnosticConsent(BaseModel):
    """User authorization payload enforcing the EXECUTE opt-in gate."""
    execute: bool = Field(..., description="Explicit user opt-in granting execution permissions")
    approver_id: Optional[str] = Field(default=None, description="Identifier of the approving user")


class InvestigationCreateRequest(BaseModel):
    """Request payload to start an AI bug investigation (Endpoint 070)."""
    snapshot_id: str = Field(..., description="Target repository snapshot identifier")
    issue_description: str = Field(..., description="Detailed description of the bug or observed error")
    stack_trace: Optional[str] = Field(default=None, description="Raw stack trace or traceback")
    failing_test: Optional[str] = Field(default=None, description="Specific failing test identifier (e.g. tests/test_auth.py::test_refresh)")
    entrypoint: Optional[str] = Field(default=None, description="Entrypoint function or route (e.g. POST /login)")
    environment: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Redacted environment metadata")


class RootCauseResponse(BaseModel):
    """Ranked root cause hypothesis returned in the investigation report."""
    id: str
    rank: int
    summary: str
    confidence: float
    status: HypothesisStatus
    file_path: Optional[str] = None
    function: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    rationale: str


class CallPathResponse(BaseModel):
    """Reconstructed call path frame."""
    order: int
    file_path: str
    line: int
    function: Optional[str] = None
    snippet: Optional[str] = None
    is_root_cause_candidate: bool = False
    is_entrypoint: bool = False


class DiagnosticStepResponse(BaseModel):
    """Diagnostic step details."""
    id: str
    kind: DiagnosticKind
    command_ref: str
    status: DiagnosticStatus
    result_ref: Optional[str] = None
    approved_by: Optional[str] = None
    limits: Dict[str, Any] = Field(default_factory=dict)
    test_results: Optional[Dict[str, Any]] = None


class InvestigationReportResponse(BaseModel):
    """Investigation report matching CodePilot API Spec §3.4.13."""
    investigation_id: str
    run_id: str
    snapshot_id: str
    problem_summary: str
    root_causes: List[RootCauseResponse] = Field(default_factory=list)
    call_path: List[CallPathResponse] = Field(default_factory=list)
    evidence: List[EvidenceRef] = Field(default_factory=list)
    reproduction_status: ReproductionStatus
    diagnostics: List[DiagnosticStepResponse] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    stack_trace_redacted: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class DiagnosticExecuteRequest(BaseModel):
    """Request payload to request an approved diagnostic in the sandbox (Endpoint 072)."""
    diagnostic_id: Optional[str] = Field(default=None, description="Specific diagnostic step ID to execute")
    consent: DiagnosticConsent = Field(..., description="Explicit EXECUTE opt-in consent")
    simulate_outcome: Optional[str] = Field(default=None, description="Simulation override for test isolation ('REPRODUCED', 'PASSED', 'ERROR')")


class DiagnosticExecuteResponse(BaseModel):
    """Response returned upon running a diagnostic step."""
    diagnostic_id: str
    run_id: str
    status: DiagnosticStatus
    reproduction_status: ReproductionStatus
    test_results: Optional[Dict[str, Any]] = None
    message: str = "Diagnostic executed in isolated sandbox"
