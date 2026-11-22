"""Multi-Agent Orchestrator managing analysis plans, agent execution, and governance."""

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Set
from uuid import uuid4

from shared.types.agent import AgentRole, RunStatus, TaskStatus, ToolPermissionLevel
from shared.types.findings import Finding
from agentic.agents.architecture_agent import ArchitectureAgent
from agentic.agents.code_quality_agent import CodeQualityAgent
from agentic.agents.performance_agent import PerformanceAgent
from agentic.agents.review_agent import ReviewAgent
from agentic.agents.security_agent import SecurityAgent
from agentic.common.result_aggregator import MultiAgentResultAggregator
from agentic.evaluators.evidence_validator import EvidenceValidator
from agentic.governance.policy_engine import AgentPolicyEngine
from agentic.governance.tool_permissions import ToolPermissionRegistry
from agentic.schemas.agent import (
    AgentRunApproveRequest,
    AgentRunCreateRequest,
    AgentRunResponse,
    AgentTask,
    AnalysisPlan,
    AnalysisPlanStep,
    MultiAgentReport,
)
from agentic.tools.file_read_tool import FileReadTool
from agentic.tools.graph_query_tool import GraphQueryTool
from agentic.tools.static_analysis_tool import StaticAnalysisTool
from agentic.tools.symbol_search_tool import SymbolSearchTool


class MultiAgentOrchestrator:
    """Orchestrates multi-agent analysis runs according to CodePilot M1 specifications."""

    def __init__(self, policy_engine: Optional[AgentPolicyEngine] = None) -> None:
        self.registry = ToolPermissionRegistry()
        self.policy_engine = policy_engine or AgentPolicyEngine(registry=self.registry)

        # Initialize shared tools
        self.tools = {
            "file_read": FileReadTool(),
            "symbol_search": SymbolSearchTool(),
            "graph_query": GraphQueryTool(),
            "static_analysis": StaticAnalysisTool(),
        }

        # Wire specialist agents
        self.agents = {
            AgentRole.ARCHITECTURE: ArchitectureAgent(self.policy_engine, self.tools),
            AgentRole.SECURITY: SecurityAgent(self.policy_engine, self.tools),
            AgentRole.CODE_QUALITY: CodeQualityAgent(self.policy_engine, self.tools),
            AgentRole.PERFORMANCE: PerformanceAgent(self.policy_engine, self.tools),
            AgentRole.REVIEW: ReviewAgent(self.policy_engine, self.tools),
        }

        self.validator = EvidenceValidator()
        self.aggregator = MultiAgentResultAggregator()

        # In-memory run stores
        self._runs: Dict[str, Dict[str, Any]] = {}
        self._reports: Dict[str, MultiAgentReport] = {}
        self._event_subscribers: Dict[str, List[asyncio.Queue]] = {}

    def create_analysis_run(self, req: AgentRunCreateRequest) -> AgentRunResponse:
        run_id = str(uuid4())
        created_at = datetime.utcnow()

        # 1. Build Analysis Plan
        steps: List[AnalysisPlanStep] = []
        requires_approval = req.require_plan_approval

        for role in req.agents:
            steps.append(
                AnalysisPlanStep(
                    agent_role=role,
                    title=f"Analyze {role.value.replace('_', ' ').title()}",
                    description=f"Specialist inspection for {role.value.lower()} concerns",
                    permission_level=ToolPermissionLevel.ANALYZE if role != AgentRole.REVIEW else ToolPermissionLevel.READ,
                    requires_approval=False,
                    estimated_tokens=3000,
                )
            )

        # Always append final synthesis review step
        steps.append(
            AnalysisPlanStep(
                agent_role=AgentRole.REVIEW,
                title="Consolidate Findings & Disagreements",
                description="Synthesize consensus items and document cross-domain trade-offs",
                permission_level=ToolPermissionLevel.READ,
                requires_approval=False,
                dependencies=[s.step_id for s in steps],
                estimated_tokens=2000,
            )
        )

        plan = AnalysisPlan(
            run_id=run_id,
            title=f"Multi-Agent Code Analysis for Snapshot {req.snapshot_id[:8]}",
            steps=steps,
            requires_human_approval=requires_approval,
            approval_reason="User requested explicit plan approval before agent execution."
            if requires_approval
            else None,
            estimated_total_tokens=sum(s.estimated_tokens for s in steps),
            estimated_cost_usd=round(sum(s.estimated_tokens for s in steps) * 0.000003, 4),
        )

        # 2. Determine initial status
        initial_status = RunStatus.WAITING_APPROVAL if requires_approval else RunStatus.RUNNING

        run_state: Dict[str, Any] = {
            "run_id": run_id,
            "snapshot_id": req.snapshot_id,
            "repository_id": req.repository_id,
            "status": initial_status,
            "plan": plan,
            "tasks": [],
            "approved_scopes": set(),
            "token_budget": req.token_budget,
            "created_at": created_at,
            "started_at": created_at if not requires_approval else None,
            "completed_at": None,
            "error_message": None,
            "findings": [],
            "verification_results": [],
        }

        self._runs[run_id] = run_state
        self._emit_event(run_id, {"type": "run_state_changed", "status": initial_status.value})

        # 3. If auto-starting, trigger execution
        if initial_status == RunStatus.RUNNING:
            self._execute_run_sync(run_id)

        return self.get_run_response(run_id)

    def approve_run(self, run_id: str, req: AgentRunApproveRequest) -> AgentRunResponse:
        run = self._get_run_raw(run_id)
        if run["status"] != RunStatus.WAITING_APPROVAL:
            raise ValueError(f"Run {run_id} is in status '{run['status'].value}', not WAITING_APPROVAL.")

        run["approved_scopes"].add(req.scope)
        run["plan"].approved_by = "user_approval"
        run["plan"].approved_at = datetime.utcnow()
        run["status"] = RunStatus.RUNNING
        run["started_at"] = datetime.utcnow()

        self._emit_event(run_id, {"type": "run_approved", "scope": req.scope})
        self._emit_event(run_id, {"type": "run_state_changed", "status": RunStatus.RUNNING.value})

        self._execute_run_sync(run_id)
        return self.get_run_response(run_id)

    def cancel_run(self, run_id: str) -> AgentRunResponse:
        run = self._get_run_raw(run_id)
        run["status"] = RunStatus.CANCELLED
        run["completed_at"] = datetime.utcnow()
        self._emit_event(run_id, {"type": "run_cancelled"})
        self._emit_event(run_id, {"type": "run_state_changed", "status": RunStatus.CANCELLED.value})
        return self.get_run_response(run_id)

    def _execute_run_sync(self, run_id: str) -> None:
        run = self._get_run_raw(run_id)
        snapshot_id = run["snapshot_id"]
        plan: AnalysisPlan = run["plan"]

        all_findings: List[Finding] = []
        agent_summaries: Dict[str, str] = {}

        try:
            # Execute specialist agent tasks
            for step in plan.steps:
                if run["status"] == RunStatus.CANCELLED:
                    break

                if step.agent_role == AgentRole.REVIEW:
                    continue  # Run review at the end

                agent = self.agents.get(step.agent_role)
                if not agent:
                    continue

                task = AgentTask(
                    run_id=run_id,
                    agent_role=step.agent_role,
                    input={"scope": "full", "step_id": step.step_id},
                )
                run["tasks"].append(task)
                self._emit_event(
                    run_id,
                    {
                        "type": "task_started",
                        "task_id": task.id,
                        "agent": step.agent_role.value,
                    },
                )

                # Execute agent
                agent.run_analysis(
                    task=task,
                    snapshot_id=snapshot_id,
                    approved_scopes=run["approved_scopes"],
                    token_budget=run["token_budget"],
                )

                all_findings.extend(task.findings)
                if task.output and "summary" in task.output:
                    agent_summaries[step.agent_role.value] = task.output["summary"]

                self._emit_event(
                    run_id,
                    {
                        "type": "task_completed",
                        "task_id": task.id,
                        "agent": step.agent_role.value,
                        "status": task.status.value,
                        "findings_count": len(task.findings),
                    },
                )

            # Verification Stage
            run["status"] = RunStatus.VERIFYING
            self._emit_event(run_id, {"type": "run_state_changed", "status": RunStatus.VERIFYING.value})

            verif_results = self.validator.verify_findings(
                snapshot_id=snapshot_id,
                run_id=run_id,
                findings=all_findings,
            )
            run["verification_results"] = verif_results

            # Execute Review Agent
            review_agent = self.agents[AgentRole.REVIEW]
            review_task = AgentTask(
                run_id=run_id,
                agent_role=AgentRole.REVIEW,
                input={"findings": all_findings},
            )
            run["tasks"].append(review_task)
            review_agent.run_analysis(
                task=review_task,
                snapshot_id=snapshot_id,
                approved_scopes=run["approved_scopes"],
                token_budget=run["token_budget"],
            )

            # Consensus & Disagreements Aggregation
            consensus, disagreements = self.aggregator.aggregate(all_findings)

            # Severity counts
            severity_counts: Dict[str, int] = {}
            category_counts: Dict[str, int] = {}
            for f in all_findings:
                severity_counts[f.severity.value] = severity_counts.get(f.severity.value, 0) + 1
                category_counts[f.category] = category_counts.get(f.category, 0) + 1

            passed_verifs = sum(1 for v in verif_results if v.passed)
            verif_summary = {
                "total_checks": len(verif_results),
                "passed_checks": passed_verifs,
                "validity_percentage": round(
                    (passed_verifs / max(1, len(verif_results))) * 100.0, 1
                ),
            }

            # Build Consolidated Multi-Agent Report
            report = MultiAgentReport(
                run_id=run_id,
                snapshot_id=snapshot_id,
                total_findings=len(all_findings),
                findings_by_severity=severity_counts,
                findings_by_category=category_counts,
                consensus_findings=consensus,
                disagreements=disagreements,
                all_findings=all_findings,
                verification_summary=verif_summary,
                agent_summaries=agent_summaries,
                execution_metrics={
                    "total_tasks": len(run["tasks"]),
                    "total_tokens": sum(t.tokens for t in run["tasks"]),
                    "total_tool_calls": sum(len(t.tool_calls) for t in run["tasks"]),
                },
            )
            self._reports[run_id] = report

            run["status"] = RunStatus.COMPLETED
            run["completed_at"] = datetime.utcnow()
            run["findings"] = all_findings

            self._emit_event(
                run_id,
                {
                    "type": "run_completed",
                    "total_findings": len(all_findings),
                    "consensus_count": len(consensus),
                    "disagreements_count": len(disagreements),
                },
            )
            self._emit_event(run_id, {"type": "run_state_changed", "status": RunStatus.COMPLETED.value})

        except Exception as e:
            run["status"] = RunStatus.FAILED
            run["error_message"] = str(e)
            run["completed_at"] = datetime.utcnow()
            self._emit_event(run_id, {"type": "run_failed", "error": str(e)})

    def get_run_response(self, run_id: str) -> AgentRunResponse:
        run = self._get_run_raw(run_id)
        return AgentRunResponse(
            run_id=run["run_id"],
            snapshot_id=run["snapshot_id"],
            status=run["status"],
            plan=run.get("plan"),
            tasks=run.get("tasks", []),
            total_findings=len(run.get("findings", [])),
            created_at=run["created_at"],
            started_at=run.get("started_at"),
            completed_at=run.get("completed_at"),
            error_message=run.get("error_message"),
        )

    def get_report(self, run_id: str) -> MultiAgentReport:
        if run_id not in self._reports:
            run = self._get_run_raw(run_id)
            if run["status"] != RunStatus.COMPLETED:
                raise ValueError(f"Run {run_id} is in status '{run['status'].value}', report not ready.")
            raise KeyError(f"Report for run {run_id} not found.")
        return self._reports[run_id]

    def _get_run_raw(self, run_id: str) -> Dict[str, Any]:
        if run_id not in self._runs:
            raise KeyError(f"Analysis run '{run_id}' not found.")
        return self._runs[run_id]

    def _emit_event(self, run_id: str, event_data: Dict[str, Any]) -> None:
        if run_id in self._event_subscribers:
            event_data["timestamp"] = datetime.utcnow().isoformat()
            for q in self._event_subscribers[run_id]:
                try:
                    q.put_nowait(event_data)
                except Exception:
                    pass

    async def subscribe_events(self, run_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        self._get_run_raw(run_id)  # validate existence
        q: asyncio.Queue = asyncio.Queue()
        if run_id not in self._event_subscribers:
            self._event_subscribers[run_id] = []
        self._event_subscribers[run_id].append(q)

        try:
            while True:
                event = await q.get()
                yield event
                if event.get("type") in ("run_completed", "run_failed", "run_cancelled"):
                    break
        finally:
            if run_id in self._event_subscribers and q in self._event_subscribers[run_id]:
                self._event_subscribers[run_id].remove(q)
