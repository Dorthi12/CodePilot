"""Code Quality Agent for analyzing maintainability, complexity, and smells."""

from datetime import datetime, timezone
from typing import Optional
from shared.types.agent import AgentRole, FindingSeverity, TaskStatus
from shared.types.findings import FindingEvidence
from agentic.agents.base_agent import BaseAgent
from agentic.schemas.agent import AgentMessage, AgentTask


class CodeQualityAgent(BaseAgent):
    role = AgentRole.CODE_QUALITY

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
                content="Code Quality Agent initiated: evaluating cyclomatic complexity, method length, and maintainability.",
            )
        )

        try:
            # 1. Run static checks for quality
            static_res = self.call_tool(
                task=task,
                snapshot_id=snapshot_id,
                tool_name="static_analysis",
                category="CODE_QUALITY",
                approved_scopes=approved_scopes,
                token_budget=token_budget,
            )

            for item in static_res.get("findings", []):
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
                    category="CODE_QUALITY",
                    rule_id=item["rule_id"],
                    title=item["title"],
                    description=f"Code quality concern: {item['title']}. Reduces readability and increases cognitive load.",
                    file_path=item["file_path"],
                    line_start=item["line_start"],
                    line_end=item["line_end"],
                    severity=FindingSeverity(item.get("severity", "MEDIUM")),
                    remediation="Decompose large routines into smaller single-responsibility functions.",
                    evidence=evidence_list,
                )
                task.findings.append(finding)

            task.output = {
                "summary": f"Code quality analysis completed with {len(task.findings)} maintainability findings.",
                "total_findings": len(task.findings),
            }
            task.status = TaskStatus.COMPLETED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)

        task.ended_at = datetime.now(timezone.utc)
        return task
