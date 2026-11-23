"""Base agent implementation with governance, tool execution, and tracing."""

import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.agent import AgentRole, FindingOrigin, FindingSeverity, FindingStatus, TaskStatus
from shared.types.findings import Finding, FindingEvidence
from agentic.governance.policy_engine import AgentPolicyEngine
from agentic.schemas.agent import AgentMessage, AgentTask, ToolCall
from agentic.tools.base_tool import BaseAgentTool


class BaseAgent(ABC):
    """Abstract base class for all specialized analysis agents."""

    role: AgentRole

    def __init__(
        self,
        policy_engine: AgentPolicyEngine,
        tools: Dict[str, BaseAgentTool],
    ) -> None:
        self.policy_engine = policy_engine
        self.tools = tools

    def call_tool(
        self,
        task: AgentTask,
        snapshot_id: str,
        tool_name: str,
        approved_scopes: Optional[set] = None,
        token_budget: int = 50000,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Calls a tool through the governance policy engine and records audit trail."""
        eval_result = self.policy_engine.evaluate_tool_request(
            agent_role=self.role,
            tool_name=tool_name,
            approved_scopes=approved_scopes,
            current_tokens_used=task.tokens,
            token_budget=token_budget,
        )

        tool_call = ToolCall(
            run_id=task.run_id,
            task_id=task.id,
            tool=tool_name,
            permission_level=self.policy_engine.registry.get_tool(tool_name).permission_level if self.policy_engine.registry.is_registered(tool_name) else None,
            input=kwargs,
            policy_decision=eval_result.decision,
            reason=eval_result.reason,
        )

        if not eval_result.allowed:
            tool_call.status = "DENIED"
            task.tool_calls.append(tool_call)
            raise PermissionError(f"Policy denied tool call '{tool_name}': {eval_result.reason}")

        tool = self.tools.get(tool_name)
        if not tool:
            tool_call.status = "FAILED"
            tool_call.reason = f"Tool '{tool_name}' not wired to agent."
            task.tool_calls.append(tool_call)
            raise RuntimeError(tool_call.reason)

        exec_res = tool.run(snapshot_id=snapshot_id, **kwargs)
        tool_call.status = exec_res["status"]
        tool_call.duration_ms = exec_res["duration_ms"]
        tool_call.output = exec_res.get("result")
        tool_call.reason = exec_res.get("error")
        task.tool_calls.append(tool_call)

        # Increment simulated tokens for retrieval
        task.tokens += 150

        if exec_res["status"] != "SUCCESS":
            raise RuntimeError(f"Tool '{tool_name}' execution failed: {exec_res.get('error')}")

        return exec_res["result"]

    def create_finding(
        self,
        snapshot_id: str,
        run_id: str,
        category: str,
        rule_id: str,
        title: str,
        description: str,
        file_path: str,
        line_start: int,
        line_end: int,
        severity: FindingSeverity = FindingSeverity.MEDIUM,
        confidence: float = 0.85,
        remediation: Optional[str] = None,
        cwe: Optional[str] = None,
        owasp: Optional[str] = None,
        evidence: Optional[List[FindingEvidence]] = None,
    ) -> Finding:
        """Helper to create a validated finding record with deterministic fingerprint."""
        raw_fingerprint = f"{rule_id}:{file_path}:{line_start}:{line_end}"
        fingerprint = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()

        return Finding(
            id=str(uuid4()),
            snapshot_id=snapshot_id,
            analysis_run_id=run_id,
            fingerprint=fingerprint,
            origin=FindingOrigin.AI_HYPOTHESIS,
            category=category,
            rule_id=rule_id,
            tool=f"agent_{self.role.value.lower()}",
            tool_version="1.0.0",
            severity=severity,
            confidence=confidence,
            cwe=cwe,
            owasp=owasp,
            title=title,
            description=description,
            remediation=remediation,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            evidence=evidence or [],
            status=FindingStatus.OPEN,
            agent_role=self.role.value,
        )

    @abstractmethod
    def run_analysis(
        self,
        task: AgentTask,
        snapshot_id: str,
        approved_scopes: Optional[set] = None,
        token_budget: int = 50000,
    ) -> AgentTask:
        """Execute specialist analysis and generate findings."""
        pass
