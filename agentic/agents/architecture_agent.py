"""Architecture Agent for detecting modularity, coupling, and dependency patterns."""

from datetime import datetime, timezone
from typing import Optional
from shared.types.agent import AgentRole, FindingSeverity, TaskStatus
from shared.types.findings import FindingEvidence
from agentic.agents.base_agent import BaseAgent
from agentic.schemas.agent import AgentMessage, AgentTask


class ArchitectureAgent(BaseAgent):
    role = AgentRole.ARCHITECTURE

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
                content="Architecture Agent initiated: analyzing module coupling, dependencies, and component boundaries.",
            )
        )

        try:
            # 1. Run static architecture analysis
            static_res = self.call_tool(
                task=task,
                snapshot_id=snapshot_id,
                tool_name="static_analysis",
                category="ARCHITECTURE",
                approved_scopes=approved_scopes,
                token_budget=token_budget,
            )

            for item in static_res.get("findings", []):
                # Verify source content via file_read
                evidence_list = []
                try:
                    file_res = self.call_tool(
                        task=task,
                        snapshot_id=snapshot_id,
                        tool_name="file_read",
                        file_path=item["file_path"],
                        line_start=item["line_start"],
                        line_end=item["line_end"],
                        approved_scopes=approved_scopes,
                        token_budget=token_budget,
                    )
                    evidence_list.append(
                        FindingEvidence(
                            file_path=item["file_path"],
                            line_start=item["line_start"],
                            line_end=item["line_end"],
                            snippet=file_res.get("snippet", item.get("snippet", "")),
                            snippet_hash=file_res.get("content_hash"),
                        )
                    )
                except Exception:
                    pass

                finding = self.create_finding(
                    snapshot_id=snapshot_id,
                    run_id=task.run_id,
                    category="ARCHITECTURE",
                    rule_id=item["rule_id"],
                    title=item["title"],
                    description=f"Architecture boundary concern: {item['title']}. May lead to tight coupling or cyclic references.",
                    file_path=item["file_path"],
                    line_start=item["line_start"],
                    line_end=item["line_end"],
                    severity=FindingSeverity(item.get("severity", "MEDIUM")),
                    remediation="Refactor shared dependencies into an independent core module or apply dependency inversion.",
                    evidence=evidence_list,
                )
                task.findings.append(finding)

            # 2. Graph relationship check
            graph_res = self.call_tool(
                task=task,
                snapshot_id=snapshot_id,
                tool_name="graph_query",
                relationship_types=["DEPENDS_ON", "IMPORTS"],
                approved_scopes=approved_scopes,
                token_budget=token_budget,
            )

            task.output = {
                "summary": f"Architecture analysis evaluated {len(graph_res.get('edges', []))} dependency edges and generated {len(task.findings)} findings.",
                "total_edges": len(graph_res.get("edges", [])),
                "total_findings": len(task.findings),
            }
            task.status = TaskStatus.COMPLETED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)

        task.ended_at = datetime.now(timezone.utc)
        return task
