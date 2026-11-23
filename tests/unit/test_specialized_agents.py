"""Unit tests for specialized domain agents."""

import pytest
from shared.types.agent import AgentRole, FindingSeverity, TaskStatus
from agentic.agents.architecture_agent import ArchitectureAgent
from agentic.agents.code_quality_agent import CodeQualityAgent
from agentic.agents.performance_agent import PerformanceAgent
from agentic.agents.review_agent import ReviewAgent
from agentic.agents.security_agent import SecurityAgent
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry, SnapshotSymbol
from agentic.governance.policy_engine import AgentPolicyEngine
from agentic.schemas.agent import AgentTask
from agentic.tools.file_read_tool import FileReadTool
from agentic.tools.graph_query_tool import GraphQueryTool
from agentic.tools.static_analysis_tool import StaticAnalysisTool
from agentic.tools.symbol_search_tool import SymbolSearchTool


@pytest.fixture
def test_snapshot_context():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-test-001")

    # Seed vulnerable & smelly code
    auth_code = """import os

api_key = "secret_api_key_1234567890_abcdef"

def login_handler(username, password):
    query = f"SELECT * FROM users WHERE user = '{username}'"
    return execute_query(query)

def process_batch(items):
    for i in items:
        for j in items:
            do_work(i, j)
"""
    ctx.add_file("app/auth.py", auth_code, language="python")

    # Add symbols
    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-1",
            name="login_handler",
            qualified_name="app.auth.login_handler",
            kind="FUNCTION",
            file_path="app/auth.py",
            start_line=5,
            end_line=7,
            complexity=2,
        )
    )

    ctx.add_symbol(
        SnapshotSymbol(
            id="sym-2",
            name="giant_function",
            qualified_name="app.auth.giant_function",
            kind="FUNCTION",
            file_path="app/auth.py",
            start_line=9,
            end_line=70,  # >50 lines
            complexity=15,  # high complexity
        )
    )

    # Add cyclic edges
    ctx.add_edge("module_a.py", "module_b.py", "IMPORTS")
    ctx.add_edge("module_b.py", "module_a.py", "IMPORTS")

    SnapshotContextRegistry.register(ctx)
    return ctx


@pytest.fixture
def agent_tools():
    return {
        "file_read": FileReadTool(),
        "symbol_search": SymbolSearchTool(),
        "graph_query": GraphQueryTool(),
        "static_analysis": StaticAnalysisTool(),
    }


def test_security_agent(test_snapshot_context, agent_tools):
    policy = AgentPolicyEngine()
    agent = SecurityAgent(policy, agent_tools)

    task = AgentTask(run_id="run-1", agent_role=AgentRole.SECURITY)
    agent.run_analysis(task=task, snapshot_id="snap-test-001")

    assert task.status == TaskStatus.COMPLETED
    assert len(task.findings) >= 2

    # Check that secrets and SQL injection were detected
    secret_finding = next((f for f in task.findings if "SECRET" in f.rule_id), None)
    assert secret_finding is not None
    assert secret_finding.severity == FindingSeverity.CRITICAL
    assert secret_finding.cwe == "CWE-798"
    assert secret_finding.file_path == "app/auth.py"
    assert len(secret_finding.evidence) > 0

    sqli_finding = next((f for f in task.findings if "SQLI" in f.rule_id), None)
    assert sqli_finding is not None
    assert sqli_finding.severity == FindingSeverity.HIGH
    assert sqli_finding.cwe == "CWE-89"


def test_code_quality_agent(test_snapshot_context, agent_tools):
    policy = AgentPolicyEngine()
    agent = CodeQualityAgent(policy, agent_tools)

    task = AgentTask(run_id="run-1", agent_role=AgentRole.CODE_QUALITY)
    agent.run_analysis(task=task, snapshot_id="snap-test-001")

    assert task.status == TaskStatus.COMPLETED
    assert len(task.findings) >= 2

    length_finding = next((f for f in task.findings if "QUAL-LEN" in f.rule_id), None)
    assert length_finding is not None
    assert "giant_function" in length_finding.title

    complex_finding = next((f for f in task.findings if "QUAL-COMPLEX" in f.rule_id), None)
    assert complex_finding is not None
    assert complex_finding.severity == FindingSeverity.HIGH


def test_performance_agent(test_snapshot_context, agent_tools):
    policy = AgentPolicyEngine()
    agent = PerformanceAgent(policy, agent_tools)

    task = AgentTask(run_id="run-1", agent_role=AgentRole.PERFORMANCE)
    agent.run_analysis(task=task, snapshot_id="snap-test-001")

    assert task.status == TaskStatus.COMPLETED
    assert len(task.findings) >= 1

    perf_finding = next((f for f in task.findings if "PERF-LOOP" in f.rule_id), None)
    assert perf_finding is not None
    assert "Nested loop" in perf_finding.title


def test_architecture_agent(test_snapshot_context, agent_tools):
    policy = AgentPolicyEngine()
    agent = ArchitectureAgent(policy, agent_tools)

    task = AgentTask(run_id="run-1", agent_role=AgentRole.ARCHITECTURE)
    agent.run_analysis(task=task, snapshot_id="snap-test-001")

    assert task.status == TaskStatus.COMPLETED
    cycle_finding = next((f for f in task.findings if "ARCH-CYCLE" in f.rule_id), None)
    assert cycle_finding is not None
    assert "Circular dependency" in cycle_finding.title
