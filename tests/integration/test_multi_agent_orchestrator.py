"""Integration tests for the Multi-Agent Orchestrator."""

import asyncio
import pytest
from shared.types.agent import AgentRole, RunStatus, TaskStatus
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from agentic.orchestrator.orchestrator import MultiAgentOrchestrator
from agentic.schemas.agent import AgentRunApproveRequest, AgentRunCreateRequest


@pytest.fixture(autouse=True)
def setup_snapshot():
    SnapshotContextRegistry.clear()
    ctx = RepositorySnapshotContext("snap-orch-100")
    code = """def calc_stats(data):
    api_key = "secret_key_1234567890_abcdef"
    for x in data:
        for y in data:
            compute(x, y)
    return True
"""
    ctx.add_file("service/compute.py", code, language="python")
    SnapshotContextRegistry.register(ctx)


def test_orchestrator_auto_start_run():
    orchestrator = MultiAgentOrchestrator()

    req = AgentRunCreateRequest(
        snapshot_id="snap-orch-100",
        agents=[AgentRole.ARCHITECTURE, AgentRole.SECURITY, AgentRole.PERFORMANCE],
        require_plan_approval=False,
    )

    resp = orchestrator.create_analysis_run(req)
    assert resp.status == RunStatus.COMPLETED
    assert resp.total_findings > 0

    # Retrieve and verify report
    report = orchestrator.get_report(resp.run_id)
    assert report.run_id == resp.run_id
    assert report.total_findings > 0
    assert report.verification_summary["validity_percentage"] == 100.0
    assert len(report.consensus_findings) > 0


def test_orchestrator_gated_approval_flow():
    orchestrator = MultiAgentOrchestrator()

    # Create run with human approval required
    req = AgentRunCreateRequest(
        snapshot_id="snap-orch-100",
        agents=[AgentRole.SECURITY, AgentRole.CODE_QUALITY],
        require_plan_approval=True,
    )

    resp = orchestrator.create_analysis_run(req)
    assert resp.status == RunStatus.WAITING_APPROVAL
    assert resp.plan is not None
    assert resp.plan.requires_human_approval is True

    # Report cannot be fetched yet
    with pytest.raises(ValueError, match="not ready"):
        orchestrator.get_report(resp.run_id)

    # Human approves run
    approve_req = AgentRunApproveRequest(scope="PLAN", comment="Approved for execution")
    approved_resp = orchestrator.approve_run(resp.run_id, approve_req)
    assert approved_resp.status == RunStatus.COMPLETED
    assert approved_resp.total_findings > 0

    report = orchestrator.get_report(resp.run_id)
    assert report is not None
    assert report.total_findings > 0


def test_orchestrator_cancellation():
    orchestrator = MultiAgentOrchestrator()
    req = AgentRunCreateRequest(
        snapshot_id="snap-orch-100",
        require_plan_approval=True,
    )
    resp = orchestrator.create_analysis_run(req)
    assert resp.status == RunStatus.WAITING_APPROVAL

    cancelled = orchestrator.cancel_run(resp.run_id)
    assert cancelled.status == RunStatus.CANCELLED


@pytest.mark.asyncio
async def test_orchestrator_event_subscription():
    orchestrator = MultiAgentOrchestrator()
    req = AgentRunCreateRequest(
        snapshot_id="snap-orch-100",
        agents=[AgentRole.SECURITY],
        require_plan_approval=True,
    )
    resp = orchestrator.create_analysis_run(req)

    events_received = []

    async def event_collector():
        async for ev in orchestrator.subscribe_events(resp.run_id):
            events_received.append(ev)

    task = asyncio.create_task(event_collector())
    await asyncio.sleep(0.05)

    # Approve to trigger execution events
    orchestrator.approve_run(resp.run_id, AgentRunApproveRequest(scope="PLAN"))
    await asyncio.sleep(0.1)

    assert len(events_received) >= 2
    types = [e["type"] for e in events_received]
    assert "run_approved" in types
    assert "run_completed" in types

    task.cancel()
