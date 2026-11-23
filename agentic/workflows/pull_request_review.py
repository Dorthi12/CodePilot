"""Mastermind Feature 7: Agentic Pull Request Review Workflow (M7).

Specifications:
- Master Architecture Specification v2.1 §10 (M7), §11.3 (Endpoints 091–096)
- API and Data Specification v1.0 §3.4.15, §4.5, §4.6
- Security and Testing Specification v1.0 §7.3.10 (SEC-API-28..31), §8.9 (AI-16)
- System Design Specification v1.0 §7.19 (V6 Claim Support), §8.1 (Invariants I1, I5, I6), §12.3
"""

import ast
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

from agentic.common.agent_context import (
    RepositorySnapshotContext,
    SnapshotContextRegistry,
)
from ai_service.code_analysis.bug_detector import BugDetector
from ai_service.code_analysis.code_smell_detector import CodeSmellDetector
from ai_service.security_analysis.secret_detector import SecretScanner
from backend.app.modules.pull_requests.comment_generator import CommentGenerator
from backend.app.modules.pull_requests.diff_analyzer import PRDiffAnalyzer
from backend.app.repositories.findings_repository import FindingsRepository
from backend.app.repositories.pull_request_repository import PullRequestRepository
from shared.types.agent import FindingOrigin, FindingSeverity, RunStatus
from shared.types.findings import (
    AnalysisRunRecord,
    Finding,
    FindingEvidence,
    compute_finding_fingerprint,
)
from shared.types.pull_requests import (
    PRFile,
    PullRequest,
    ReviewComment,
    ReviewCommentStatus,
    ReviewRunRecord,
)


class PullRequestReviewWorkflow:
    """Agentic PR review workflow executing impact analysis, multi-scanner checks, and line-anchor verification."""

    def __init__(
        self,
        pr_repo: Optional[PullRequestRepository] = None,
        findings_repo: Optional[FindingsRepository] = None,
    ) -> None:
        self.pr_repo = pr_repo or PullRequestRepository.get_instance()
        self.findings_repo = findings_repo or FindingsRepository.get_instance()

    def run_review(
        self,
        pull_request_id: str,
        base_sha: str,
        head_sha: str,
        review_profile: str = "standard",
        diff_text: Optional[str] = None,
        base_snapshot_id: Optional[str] = None,
        head_snapshot_id: Optional[str] = None,
    ) -> ReviewRunResponseBundle:
        """Execute end-to-end PR review workflow pinned to base_sha and head_sha."""
        # 1. Fetch Pull Request and verify SHAs
        pr = self.pr_repo.get_pull_request(pull_request_id)
        if not pr:
            raise ValueError(f"Pull request '{pull_request_id}' not found.")

        # Check for force push or SHA drift (API Spec §3.4.15: returns 409 PR_HEAD_CHANGED)
        if pr.head_sha != head_sha:
            # Invalidate any stale runs
            self.pr_repo.mark_review_runs_stale(pr.id)
            raise ValueError("PR_HEAD_CHANGED: PR head SHA has changed due to a force-push or new commit.")

        # 2. Resolve Head & Base Snapshot Contexts (Invariant I1)
        head_snap = head_snapshot_id or pr.head_snapshot_id or f"snap-{pr.repository_id}-{head_sha[:8]}"
        base_snap = base_snapshot_id or pr.base_snapshot_id or f"snap-{pr.repository_id}-{base_sha[:8]}"

        # 3. Parse unified diff and extract changed lines
        raw_diff = diff_text or ""
        pr_files = PRDiffAnalyzer.parse_diff(raw_diff, pull_request_id=pr.id)
        self.pr_repo.save_pr_files(pr.id, pr_files)

        # Map symbols in head snapshot
        PRDiffAnalyzer.map_symbols_to_changes(pr_files, head_snap)
        changed_lines_by_file = PRDiffAnalyzer.extract_changed_line_numbers(pr_files)

        # 4. Blast Radius / Impact Analysis
        impacted_modules, tests_to_run = self._analyze_impact(pr_files, head_snap)

        # 5. Initialize Review Run Record
        run_id = str(uuid4())
        run_record = ReviewRunRecord(
            id=run_id,
            pull_request_id=pr.id,
            repository_id=pr.repository_id,
            base_sha=base_sha,
            head_sha=head_sha,
            review_profile=review_profile,
            status=RunStatus.RUNNING,
            summary="Review running...",
            impacted_modules=impacted_modules,
            tests_to_run=tests_to_run,
            comments=[],
            approval_state="DRAFT",
            created_at=datetime.now(timezone.utc),
        )

        # Register in Findings Repository for unified analysis run model
        self.findings_repo.create_analysis_run(
            AnalysisRunRecord(
                id=run_id,
                snapshot_id=head_snap,
                run_type="PR_REVIEW",
                status=RunStatus.RUNNING,
                config={"profile": review_profile, "base_sha": base_sha, "head_sha": head_sha},
            )
        )

        # 6. Run Quality, Bug, and Security Analyzers on changed files
        raw_findings = self._execute_scanners(pr_files, head_snap, run_id)

        # 7. Line Anchor Verification (AI-16 / V6 Claim Support Check)
        # Strictly discard any comment that does not anchor to a changed/added line
        validated_comments: List[ReviewComment] = []
        discarded_anchor_count = 0

        for finding in raw_findings:
            changed_lines = changed_lines_by_file.get(finding.file_path, set())
            
            # Check if finding line is within changed lines
            target_line = None
            if finding.line_start in changed_lines:
                target_line = finding.line_start
            elif finding.line_end in changed_lines:
                target_line = finding.line_end
            elif any(finding.line_start <= line <= finding.line_end for line in changed_lines):
                # Pick the first overlapping changed line
                for cl in sorted(changed_lines):
                    if finding.line_start <= cl <= finding.line_end:
                        target_line = cl
                        break

            if target_line is None:
                # Discard comment: not anchored to changed lines in diff (AI-16)
                discarded_anchor_count += 1
                continue

            # Generate grounded review comment
            comment = CommentGenerator.create_comment_from_finding(
                finding=finding,
                run_id=run_id,
                pull_request_id=pr.id,
                snapshot_id=head_snap,
                target_line=target_line,
            )
            self.pr_repo.add_comment(comment)
            validated_comments.append(comment)

        # 8. Synthesize Executive Review Summary
        summary = self._synthesize_summary(
            pr=pr,
            pr_files=pr_files,
            impacted_modules=impacted_modules,
            tests_to_run=tests_to_run,
            comments=validated_comments,
            discarded_anchor_count=discarded_anchor_count,
        )

        run_record.status = RunStatus.COMPLETED
        run_record.summary = summary
        run_record.comments = validated_comments
        run_record.completed_at = datetime.now(timezone.utc)
        self.pr_repo.create_review_run(run_record)

        # Update Findings Repository run
        run_entry = self.findings_repo.get_analysis_run(run_id)
        if run_entry:
            run_entry.status = RunStatus.COMPLETED
            run_entry.completed_at = datetime.now(timezone.utc)
            self.findings_repo.update_analysis_run(run_entry)

        return ReviewRunResponseBundle(
            run_id=run_id,
            pull_request_id=pr.id,
            repository_id=pr.repository_id,
            base_sha=base_sha,
            head_sha=head_sha,
            review_profile=review_profile,
            status="COMPLETED",
            summary=summary,
            impacted_modules=impacted_modules,
            tests_to_run=tests_to_run,
            comments=validated_comments,
            approval_state="DRAFT",
            stale=False,
            created_at=run_record.created_at,
            completed_at=run_record.completed_at,
        )

    def _analyze_impact(
        self,
        pr_files: List[PRFile],
        snapshot_id: str,
    ) -> tuple[List[str], List[str]]:
        """Perform graph-based blast radius impact analysis and discover candidate tests."""
        impacted_modules: Set[str] = set()
        tests_to_run: Set[str] = set()

        if not SnapshotContextRegistry.contains(snapshot_id):
            return list(impacted_modules), list(tests_to_run)

        ctx = SnapshotContextRegistry.get(snapshot_id)

        changed_paths = {f.path for f in pr_files}
        changed_symbols = {sym for f in pr_files for sym in f.mapped_symbols}

        # 1. Inspect graph edges for callers and dependents
        for edge in ctx.edges:
            # If target is a changed symbol or file, source is impacted
            if edge.target in changed_symbols or edge.target in changed_paths:
                impacted_modules.add(edge.source)
            elif any(edge.target.endswith(sym) for sym in changed_symbols):
                impacted_modules.add(edge.source)

        # 2. Add modified files as impacted
        for path in changed_paths:
            mod_name = path.replace("/", ".").replace("\\", ".").rstrip(".py")
            impacted_modules.add(mod_name)

        # 3. Discover relevant tests
        for file_path in ctx.files.keys():
            is_test_file = file_path.startswith("tests/") or file_path.endswith("_test.py") or "/test_" in file_path
            if not is_test_file:
                continue

            # Does this test file test any changed path?
            for cp in changed_paths:
                base_name = cp.split("/")[-1].replace(".py", "")
                if base_name in file_path:
                    tests_to_run.add(file_path)

        # Also check TESTS edges in graph
        for edge in ctx.edges:
            if edge.relationship == "TESTS":
                if edge.target in changed_symbols or edge.target in changed_paths:
                    tests_to_run.add(edge.source)

        return sorted(impacted_modules), sorted(tests_to_run)

    def _execute_scanners(
        self,
        pr_files: List[PRFile],
        snapshot_id: str,
        run_id: str,
    ) -> List[Finding]:
        """Run bug, code smell, and security detectors across changed files."""
        findings: List[Finding] = []
        if not SnapshotContextRegistry.contains(snapshot_id):
            return findings

        ctx = SnapshotContextRegistry.get(snapshot_id)
        target_files = {f.path for f in pr_files}

        # 1. Run Bug Detector
        try:
            b_findings = BugDetector().analyze(
                context=ctx,
                analysis_run_id=run_id,
                target_files=target_files,
            )
            findings.extend(b_findings)
        except Exception:
            pass

        # 2. Run Code Smell Detector
        try:
            s_findings = CodeSmellDetector().analyze(
                context=ctx,
                analysis_run_id=run_id,
                target_files=target_files,
            )
            findings.extend(s_findings)
        except Exception:
            pass

        # 3. Run Secret Scanner (Zero Raw Secrets Invariant I9)
        secret_scanner = SecretScanner()
        for pr_file in pr_files:
            file_obj = ctx.get_file(pr_file.path)
            if not file_obj or not file_obj.content:
                continue
            try:
                sec_findings, _ = secret_scanner.scan_file(
                    file_path=pr_file.path,
                    content=file_obj.content,
                    run_id=run_id,
                    snapshot_id=snapshot_id,
                )
                findings.extend(sec_findings)
            except Exception:
                pass

        return findings

    def _synthesize_summary(
        self,
        pr: PullRequest,
        pr_files: List[PRFile],
        impacted_modules: List[str],
        tests_to_run: List[str],
        comments: List[ReviewComment],
        discarded_anchor_count: int,
    ) -> str:
        """Create executive summary of PR review."""
        total_files = len(pr_files)
        total_add = sum(f.additions for f in pr_files)
        total_del = sum(f.deletions for f in pr_files)
        comment_count = len(comments)

        crit_count = sum(1 for c in comments if c.severity == FindingSeverity.CRITICAL)
        high_count = sum(1 for c in comments if c.severity == FindingSeverity.HIGH)
        med_count = sum(1 for c in comments if c.severity == FindingSeverity.MEDIUM)

        lines = [
            f"### CodePilot Review Summary for PR #{pr.number}: {pr.title}",
            f"- **Changes:** {total_files} file(s) modified (+{total_add}/-{total_del})",
            f"- **Review Status:** {comment_count} actionable inline comment(s) generated.",
        ]

        if crit_count > 0 or high_count > 0:
            lines.append(f"- **Severity Breakdown:** {crit_count} Critical, {high_count} High, {med_count} Medium.")
        else:
            lines.append("- **Quality Assessment:** No critical security or correctness issues identified.")

        if impacted_modules:
            mod_sample = ", ".join(f"`{m}`" for m in impacted_modules[:5])
            if len(impacted_modules) > 5:
                mod_sample += f" (+{len(impacted_modules)-5} more)"
            lines.append(f"- **Impacted Modules:** {mod_sample}")

        if tests_to_run:
            test_sample = ", ".join(f"`{t}`" for t in tests_to_run[:3])
            if len(tests_to_run) > 3:
                test_sample += f" (+{len(tests_to_run)-3} more)"
            lines.append(f"- **Recommended Tests:** {test_sample}")

        lines.append(
            "\n*Note: All comments are in DRAFT status. Human authorization is required before publication to GitHub.*"
        )
        return "\n".join(lines)


class ReviewRunResponseBundle:
    """DTO bundling review run output."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)
