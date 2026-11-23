"""Security Agent for detecting vulnerabilities, secrets, and injection risks."""

from datetime import datetime, timezone
from typing import Optional
from shared.types.agent import AgentRole, FindingSeverity, TaskStatus
from shared.types.findings import FindingEvidence
from agentic.agents.base_agent import BaseAgent
from agentic.schemas.agent import AgentMessage, AgentTask
from ai_service.security_analysis.secret_detector import redact_secrets


class SecurityAgent(BaseAgent):
    role = AgentRole.SECURITY

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
                content="Security Agent initiated: auditing codebase for OWASP Top 10, credential leaks, and injection patterns.",
            )
        )

        try:
            static_res = self.call_tool(
                task=task,
                snapshot_id=snapshot_id,
                tool_name="static_analysis",
                category="SECURITY",
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
                    raw_snippet = file_res.get("snippet", item.get("snippet", ""))
                    sanitized_snippet = redact_secrets(raw_snippet)
                    evidence_list.append(
                        FindingEvidence(
                            file_path=item["file_path"],
                            line_start=item["line_start"],
                            line_end=item["line_end"],
                            snippet=sanitized_snippet,
                            snippet_hash=file_res.get("content_hash"),
                        )
                    )
                except Exception:
                    pass

                severity = FindingSeverity(item.get("severity", "HIGH"))
                remediation = "Rotate credentials and inject via environment variables or secret manager." if "SECRET" in item["rule_id"] else "Use parameterized queries or bound arguments."

                finding = self.create_finding(
                    snapshot_id=snapshot_id,
                    run_id=task.run_id,
                    category="SECURITY",
                    rule_id=item["rule_id"],
                    title=item["title"],
                    description=f"Security risk: {item['title']}. Identified at {item['file_path']}:{item['line_start']}.",
                    file_path=item["file_path"],
                    line_start=item["line_start"],
                    line_end=item["line_end"],
                    severity=severity,
                    cwe=item.get("cwe"),
                    owasp="A01:2021-Broken Access Control" if "SECRET" in item["rule_id"] else "A03:2021-Injection",
                    remediation=remediation,
                    evidence=evidence_list,
                )
                task.findings.append(finding)

            task.output = {
                "summary": f"Security audit completed with {len(task.findings)} vulnerability and risk findings.",
                "total_findings": len(task.findings),
            }
            task.status = TaskStatus.COMPLETED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)

        task.ended_at = datetime.now(timezone.utc)
        return task
