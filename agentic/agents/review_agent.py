"""Review Agent for consolidating specialist outputs and compiling final synthesis."""

from datetime import datetime, timezone
from typing import List, Optional
from shared.types.agent import AgentRole, TaskStatus
from shared.types.findings import Finding
from agentic.agents.base_agent import BaseAgent
from agentic.common.result_aggregator import MultiAgentResultAggregator
from agentic.schemas.agent import AgentMessage, AgentTask


class ReviewAgent(BaseAgent):
    role = AgentRole.REVIEW

    def run_analysis(
        self,
        task: AgentTask,
        snapshot_id: str,
        approved_scopes: Optional[set] = None,
        token_budget: int = 50000,
    ) -> AgentTask:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        task.messages.append(
            AgentMessage(
                run_id=task.run_id,
                task_id=task.id,
                role=self.role,
                content="Review Agent initiated: aggregating multi-agent findings, resolving consensus, and compiling disagreements.",
            )
        )

        all_findings: List[Finding] = task.input.get("findings", [])
        aggregator = MultiAgentResultAggregator()
        consensus, disagreements = aggregator.aggregate(all_findings)

        task.output = {
            "summary": f"Review completed: consolidated {len(all_findings)} findings across domains into {len(consensus)} consensus items and {len(disagreements)} cross-domain trade-offs.",
            "consensus_count": len(consensus),
            "disagreement_count": len(disagreements),
        }
        task.status = TaskStatus.COMPLETED
        task.ended_at = datetime.now(timezone.utc)
        return task
