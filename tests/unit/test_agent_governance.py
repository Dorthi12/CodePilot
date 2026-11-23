"""Unit tests for agent governance, tool permissions, and policy engine."""

import pytest
from shared.types.agent import AgentRole, ToolPermissionLevel
from agentic.governance.policy_engine import AgentPolicyEngine
from agentic.governance.tool_permissions import ToolDefinition, ToolPermissionRegistry


def test_tool_permission_registry_defaults():
    registry = ToolPermissionRegistry()
    assert registry.is_registered("file_read")
    assert registry.is_registered("symbol_search")
    assert registry.is_registered("graph_query")
    assert registry.is_registered("static_analysis")
    assert registry.is_registered("sandbox_test_runner")

    file_tool = registry.get_tool("file_read")
    assert file_tool.permission_level == ToolPermissionLevel.READ
    assert AgentRole.SECURITY in file_tool.allowed_roles

    sandbox_tool = registry.get_tool("sandbox_test_runner")
    assert sandbox_tool.permission_level == ToolPermissionLevel.EXECUTE
    assert sandbox_tool.dangerous is True
    assert sandbox_tool.requires_approval is True


def test_policy_engine_allow_read_tool():
    engine = AgentPolicyEngine()
    result = engine.evaluate_tool_request(
        agent_role=AgentRole.SECURITY,
        tool_name="file_read",
    )
    assert result.allowed is True
    assert result.decision == "ALLOW"


def test_policy_engine_denies_unregistered_tool():
    engine = AgentPolicyEngine()
    result = engine.evaluate_tool_request(
        agent_role=AgentRole.SECURITY,
        tool_name="unknown_tool_xyz",
    )
    assert result.allowed is False
    assert result.decision == "DENY"
    assert "UNREGISTERED_TOOL" in result.reason


def test_policy_engine_denies_unauthorized_role():
    engine = AgentPolicyEngine()
    # ReviewAgent is not authorized for static_analysis (only analyze agents are)
    result = engine.evaluate_tool_request(
        agent_role=AgentRole.REVIEW,
        tool_name="static_analysis",
    )
    assert result.allowed is False
    assert result.decision == "DENY"
    assert "ROLE_DENIED" in result.reason


def test_policy_engine_gates_execute_tools_until_approved():
    engine = AgentPolicyEngine()
    # sandbox_test_runner requires EXECUTE scope
    result = engine.evaluate_tool_request(
        agent_role=AgentRole.TESTING,
        tool_name="sandbox_test_runner",
        approved_scopes=set(),
    )
    assert result.allowed is False
    assert result.decision == "NEEDS_APPROVAL"
    assert result.approval_scope == "EXECUTE"

    # Once approved, tool is allowed
    approved_result = engine.evaluate_tool_request(
        agent_role=AgentRole.TESTING,
        tool_name="sandbox_test_runner",
        approved_scopes={"EXECUTE"},
    )
    assert approved_result.allowed is True
    assert approved_result.decision == "ALLOW"


def test_policy_engine_budget_limit():
    engine = AgentPolicyEngine()
    result = engine.evaluate_tool_request(
        agent_role=AgentRole.ARCHITECTURE,
        tool_name="file_read",
        current_tokens_used=50000,
        token_budget=50000,
    )
    assert result.allowed is False
    assert result.decision == "DENY"
    assert "BUDGET_EXCEEDED" in result.reason


def test_policy_engine_kill_switch():
    engine = AgentPolicyEngine()
    engine.set_kill_switch("disable_agents", active=True)

    result = engine.evaluate_tool_request(
        agent_role=AgentRole.SECURITY,
        tool_name="file_read",
    )
    assert result.allowed is False
    assert result.decision == "DENY"
    assert "KILL_SWITCH_ACTIVE" in result.reason

    engine.set_kill_switch("disable_agents", active=False)
    unlocked = engine.evaluate_tool_request(
        agent_role=AgentRole.SECURITY,
        tool_name="file_read",
    )
    assert unlocked.allowed is True


def test_policy_engine_three_property_rule_blocks_egress():
    registry = ToolPermissionRegistry()
    registry.register(
        ToolDefinition(
            name="external_http_fetcher",
            permission_level=ToolPermissionLevel.READ,
            description="Fetches external web links",
            allowed_roles={AgentRole.SECURITY},
            egress_allowed=True,
        )
    )
    engine = AgentPolicyEngine(registry=registry)
    result = engine.evaluate_tool_request(
        agent_role=AgentRole.SECURITY,
        tool_name="external_http_fetcher",
    )
    assert result.allowed is False
    assert result.decision == "DENY"
    assert "THREE_PROPERTY_VIOLATION" in result.reason
