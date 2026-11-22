"""Schemas for Multi-Agent Code Analysis (M1)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

from shared.types.agent import (
    AgentRole,
    FindingSeverity,
    FindingStatus,
    RunStatus,
    TaskStatus,
    ToolPermissionLevel,
    VerificationCheck,
)
from shared.types.findings import Finding, FindingEvidence


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    task_id: str
    tool: str
    permission_level: ToolPermissionLevel
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    output_ref: Optional[str] = None
    status: str = "SUCCESS"  # SUCCESS, FAILED, DENIED
    policy_decision: str = "ALLOW"  # ALLOW, DENY, NEEDS_APPROVAL
    approval_request_id: Optional[str] = None
    reason: Optional[str] = None
    duration_ms: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    task_id: str
    role: AgentRole
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    agent_role: AgentRole
    status: TaskStatus = TaskStatus.PENDING
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    tokens: int = 0
    findings: List[Finding] = Field(default_factory=list)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    messages: List[AgentMessage] = Field(default_factory=list)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class VerificationResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    finding_id: str
    check: VerificationCheck
    passed: bool
    detail: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisPlanStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    agent_role: AgentRole
    title: str
    description: str
    permission_level: ToolPermissionLevel = ToolPermissionLevel.READ
    requires_approval: bool = False
    dependencies: List[str] = Field(default_factory=list)
    estimated_tokens: int = 2000


class AnalysisPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    title: str
    steps: List[AnalysisPlanStep] = Field(default_factory=list)
    requires_human_approval: bool = False
    approval_reason: Optional[str] = None
    estimated_total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class ConsensusFinding(BaseModel):
    fingerprint: str
    category: str
    title: str
    severity: FindingSeverity
    file_path: str
    line_start: int
    line_end: int
    supporting_agents: List[AgentRole] = Field(default_factory=list)
    consensus_confidence: float = 0.9
    synthesized_remediation: str


class DisagreementItem(BaseModel):
    topic: str
    file_path: str
    affected_symbol: Optional[str] = None
    agents_involved: List[AgentRole]
    positions: Dict[str, str] = Field(
        description="Map of agent role string to its evaluated perspective or recommendation"
    )
    conflicting_aspect: str = "RECOMMENDATION"  # SEVERITY, RECOMMENDATION, TRADE_OFF
    trade_off_analysis: str


class MultiAgentReport(BaseModel):
    run_id: str
    snapshot_id: str
    total_findings: int = 0
    findings_by_severity: Dict[str, int] = Field(default_factory=dict)
    findings_by_category: Dict[str, int] = Field(default_factory=dict)
    consensus_findings: List[ConsensusFinding] = Field(default_factory=list)
    disagreements: List[DisagreementItem] = Field(default_factory=list)
    all_findings: List[Finding] = Field(default_factory=list)
    verification_summary: Dict[str, Any] = Field(default_factory=dict)
    agent_summaries: Dict[str, str] = Field(default_factory=dict)
    execution_metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentRunCreateRequest(BaseModel):
    snapshot_id: str
    repository_id: Optional[str] = None
    scope: str = "full"  # full, directory, file, changed_files
    target_paths: List[str] = Field(default_factory=list)
    agents: List[AgentRole] = Field(
        default_factory=lambda: [
            AgentRole.ARCHITECTURE,
            AgentRole.SECURITY,
            AgentRole.CODE_QUALITY,
            AgentRole.PERFORMANCE,
        ]
    )
    require_plan_approval: bool = False
    token_budget: int = 50000
    timeout_seconds: int = 300
    policy_profile: str = "standard"


class AgentRunApproveRequest(BaseModel):
    step_id: Optional[str] = None
    scope: str = "PLAN"  # PLAN, EXECUTE, WRITE, PUBLISH
    comment: Optional[str] = None


class AgentRunResponse(BaseModel):
    run_id: str
    snapshot_id: str
    status: RunStatus
    plan: Optional[AnalysisPlan] = None
    tasks: List[AgentTask] = Field(default_factory=list)
    total_findings: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
