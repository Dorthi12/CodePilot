"""Agent governance policy engine enforcing authorization and safety invariants."""

from dataclasses import dataclass
from typing import Optional, Set
from shared.types.agent import AgentRole, ToolPermissionLevel
from agentic.governance.tool_permissions import ToolPermissionRegistry


@dataclass
class PolicyEvaluationResult:
    allowed: bool
    decision: str  # ALLOW, DENY, NEEDS_APPROVAL
    reason: Optional[str] = None
    approval_scope: Optional[str] = None


class AgentPolicyEngine:
    """Evaluates agent tool requests according to security policies and safety gates."""

    def __init__(
        self,
        registry: Optional[ToolPermissionRegistry] = None,
        kill_switches: Optional[Set[str]] = None,
    ) -> None:
        self.registry = registry or ToolPermissionRegistry()
        self.kill_switches: Set[str] = kill_switches or set()

    def set_kill_switch(self, switch_name: str, active: bool = True) -> None:
        if active:
            self.kill_switches.add(switch_name)
        else:
            self.kill_switches.discard(switch_name)

    def evaluate_tool_request(
        self,
        agent_role: AgentRole,
        tool_name: str,
        approved_scopes: Optional[Set[str]] = None,
        current_tokens_used: int = 0,
        token_budget: int = 50000,
    ) -> PolicyEvaluationResult:
        approved_scopes = approved_scopes or set()

        # 1. Kill switches check
        if "disable_agents" in self.kill_switches:
            return PolicyEvaluationResult(
                allowed=False,
                decision="DENY",
                reason="KILL_SWITCH_ACTIVE: Agent execution is globally disabled.",
            )

        if "disable_execute" in self.kill_switches and tool_name == "sandbox_test_runner":
            return PolicyEvaluationResult(
                allowed=False,
                decision="DENY",
                reason="KILL_SWITCH_ACTIVE: Execution sandbox is disabled.",
            )

        # 2. Tool registration check
        if not self.registry.is_registered(tool_name):
            return PolicyEvaluationResult(
                allowed=False,
                decision="DENY",
                reason=f"UNREGISTERED_TOOL: Tool '{tool_name}' does not exist in registry.",
            )

        tool_def = self.registry.get_tool(tool_name)

        # 3. Agent role permission check
        if agent_role not in tool_def.allowed_roles:
            return PolicyEvaluationResult(
                allowed=False,
                decision="DENY",
                reason=f"ROLE_DENIED: Agent '{agent_role.value}' is not authorized to call tool '{tool_name}'.",
            )

        # 4. Budget check
        if current_tokens_used >= token_budget:
            return PolicyEvaluationResult(
                allowed=False,
                decision="DENY",
                reason=f"BUDGET_EXCEEDED: Token budget {token_budget} reached ({current_tokens_used} used).",
            )

        # 5. Dangerous operations & approval gate
        if tool_def.permission_level in (
            ToolPermissionLevel.EXECUTE,
            ToolPermissionLevel.WRITE,
            ToolPermissionLevel.PUBLISH,
        ):
            scope = tool_def.permission_level.value
            if scope not in approved_scopes:
                return PolicyEvaluationResult(
                    allowed=False,
                    decision="NEEDS_APPROVAL",
                    reason=f"APPROVAL_REQUIRED: Tool '{tool_name}' requires human {scope} authorization.",
                    approval_scope=scope,
                )

        # 6. Three-Property Rule & Egress constraint
        if tool_def.egress_allowed:
            return PolicyEvaluationResult(
                allowed=False,
                decision="DENY",
                reason="THREE_PROPERTY_VIOLATION: Untrusted repository analysis agents cannot have network egress.",
            )

        return PolicyEvaluationResult(allowed=True, decision="ALLOW")
