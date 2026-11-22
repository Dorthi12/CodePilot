"""PR Review Comment Generator: formatting actionable comments with evidence and remediation.

Specifications:
- Master Architecture Specification v2.1 §10 (M7)
- API and Data Specification v1.0 §3.4.15, §4.6
- Security & Testing Specification v1.0 §8.9 (AI-16)
- System Design Specification v1.0 §7.19 (V6 Claim-support check)
"""

import hashlib
from typing import Any, Dict, List, Optional
from uuid import uuid4

from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry
from shared.types.agent import FindingSeverity
from shared.types.findings import Finding, FindingEvidence
from shared.types.pull_requests import ReviewComment, ReviewCommentStatus


class CommentGenerator:
    """Generates structured, grounded inline review comments from findings and diff hunks."""

    @staticmethod
    def create_comment_from_finding(
        finding: Finding,
        run_id: str,
        pull_request_id: str,
        snapshot_id: str,
        target_line: Optional[int] = None,
    ) -> ReviewComment:
        """Construct an inline review comment from a detected finding with cryptographic evidence."""
        ctx = SnapshotContextRegistry.get(snapshot_id)
        file_obj = ctx.get_file(finding.file_path)

        line = target_line or finding.line_start
        side = "RIGHT"

        # Format markdown body
        severity_badge = f"**[{finding.severity.value}]**"
        title = finding.title.strip()
        desc = finding.description.strip()
        remediation = (
            f"\n\n**Suggested Remediation:**\n```python\n{finding.remediation}\n```"
            if finding.remediation
            else ""
        )
        cwe_info = f" *(CWE: {finding.cwe})*" if finding.cwe else ""

        body = f"{severity_badge} {title}{cwe_info}\n\n{desc}{remediation}"

        # Extract authentic code snippet for evidence grounding
        evidence_list: List[FindingEvidence] = []
        if finding.evidence:
            evidence_list = list(finding.evidence)
        elif file_obj and file_obj.content:
            lines = file_obj.content.splitlines()
            start = max(1, line - 1)
            end = min(len(lines), line + 1)
            snippet = "\n".join(lines[start - 1 : end])
            snippet_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

            evidence_list.append(
                FindingEvidence(
                    file_path=finding.file_path,
                    line_start=start,
                    line_end=end,
                    snippet=snippet,
                    snippet_hash=snippet_hash,
                    role="SUPPORTS",
                )
            )

        return ReviewComment(
            run_id=run_id,
            pull_request_id=pull_request_id,
            file_path=finding.file_path,
            side=side,
            line=line,
            finding_id=finding.id,
            body=body,
            severity=finding.severity,
            status=ReviewCommentStatus.DRAFT,
            evidence=evidence_list,
        )

    @staticmethod
    def create_custom_comment(
        run_id: str,
        pull_request_id: str,
        file_path: str,
        line: int,
        title: str,
        description: str,
        severity: FindingSeverity = FindingSeverity.MEDIUM,
        remediation: Optional[str] = None,
        snippet: Optional[str] = None,
    ) -> ReviewComment:
        """Create a custom inline review comment."""
        body = f"**[{severity.value}]** {title}\n\n{description}"
        if remediation:
            body += f"\n\n**Suggested Remediation:**\n```python\n{remediation}\n```"

        evidence_list: List[FindingEvidence] = []
        if snippet:
            evidence_list.append(
                FindingEvidence(
                    file_path=file_path,
                    line_start=line,
                    line_end=line,
                    snippet=snippet,
                    snippet_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                    role="SUPPORTS",
                )
            )

        return ReviewComment(
            run_id=run_id,
            pull_request_id=pull_request_id,
            file_path=file_path,
            side="RIGHT",
            line=line,
            body=body,
            severity=severity,
            status=ReviewCommentStatus.DRAFT,
            evidence=evidence_list,
        )
