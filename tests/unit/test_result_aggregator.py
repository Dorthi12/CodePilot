"""Unit tests for consensus aggregation and cross-domain disagreement detection."""

from shared.types.agent import AgentRole, FindingSeverity
from shared.types.findings import Finding
from agentic.common.result_aggregator import MultiAgentResultAggregator


def test_aggregator_detects_disagreements():
    aggregator = MultiAgentResultAggregator()

    # Create simultaneous Security and Performance findings on the same file
    f_sec = Finding(
        id="f1",
        snapshot_id="snap-1",
        analysis_run_id="run-1",
        fingerprint="fp1",
        category="SECURITY",
        rule_id="SEC-001",
        tool="agent_security",
        severity=FindingSeverity.HIGH,
        title="Unsanitized query in auth module",
        description="Requires regex checking on every token",
        file_path="app/auth.py",
        line_start=10,
        line_end=15,
        agent_role=AgentRole.SECURITY.value,
    )

    f_perf = Finding(
        id="f2",
        snapshot_id="snap-1",
        analysis_run_id="run-1",
        fingerprint="fp2",
        category="PERFORMANCE",
        rule_id="PERF-001",
        tool="agent_performance",
        severity=FindingSeverity.MEDIUM,
        title="Excessive regex checking causes latency regression",
        description="Hot path loop in auth needs bypass",
        file_path="app/auth.py",
        line_start=12,
        line_end=18,
        agent_role=AgentRole.PERFORMANCE.value,
    )

    consensus, disagreements = aggregator.aggregate([f_sec, f_perf])

    assert len(disagreements) >= 1
    d = disagreements[0]
    assert d.file_path == "app/auth.py"
    assert AgentRole.SECURITY in d.agents_involved
    assert AgentRole.PERFORMANCE in d.agents_involved
    assert "Security Validation vs Latency Trade-off" in d.topic
    assert len(d.trade_off_analysis) > 0


def test_aggregator_builds_consensus():
    aggregator = MultiAgentResultAggregator()

    f1 = Finding(
        id="f1",
        snapshot_id="snap-1",
        analysis_run_id="run-1",
        fingerprint="fp-shared",
        category="CODE_QUALITY",
        rule_id="QUAL-001",
        tool="agent_code_quality",
        severity=FindingSeverity.MEDIUM,
        title="Oversized god class",
        description="Module has too many concerns",
        file_path="app/monolith.py",
        line_start=1,
        line_end=200,
        agent_role=AgentRole.CODE_QUALITY.value,
    )

    f2 = Finding(
        id="f2",
        snapshot_id="snap-1",
        analysis_run_id="run-1",
        fingerprint="fp-shared",
        category="CODE_QUALITY",
        rule_id="QUAL-001",
        tool="agent_architecture",
        severity=FindingSeverity.MEDIUM,
        title="Oversized god class",
        description="Module has too many concerns",
        file_path="app/monolith.py",
        line_start=1,
        line_end=200,
        agent_role=AgentRole.ARCHITECTURE.value,
    )

    consensus, _ = aggregator.aggregate([f1, f2])
    assert len(consensus) == 1
    c = consensus[0]
    assert c.file_path == "app/monolith.py"
    assert AgentRole.CODE_QUALITY in c.supporting_agents
    assert AgentRole.ARCHITECTURE in c.supporting_agents
    assert c.consensus_confidence > 0.8
