"""Root-cause hypothesis generation and ranking engine for Mastermind Feature 2.

Specifications:
- Master Architecture Specification v2.1 §10 (M2)
- API and Data Specification v1.0 §3.4.13, §4.6
- Security and Testing Specification v1.0 §8.9 (AI-11), Appendix C.g (Case G0-I-004)
- System Design Specification v1.0 §7.36: Status stays UNCONFIRMED until reproduction/test.
"""

import hashlib
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.types.investigation import (
    EvidenceRef,
    EvidenceRole,
    Hypothesis,
    HypothesisStatus,
    InvestigationFrame,
    ParsedStackTrace,
)
from agentic.common.agent_context import SnapshotContextRegistry


def compute_snippet_hash(snippet: str) -> str:
    """Compute SHA256 hash of a snippet for evidence integrity verification."""
    return hashlib.sha256(snippet.encode("utf-8")).hexdigest()


class HypothesisEngine:
    """Formulates and ranks evidence-backed root cause hypotheses for investigated defects."""

    def generate_hypotheses(
        self,
        snapshot_id: str,
        run_id: str,
        issue_description: str,
        parsed_trace: ParsedStackTrace,
        failing_test: Optional[str] = None,
        entrypoint: Optional[str] = None,
    ) -> List[Hypothesis]:
        """Generate and rank hypotheses based on stack frames, code context, and error semantics."""
        ctx = SnapshotContextRegistry.get(snapshot_id)
        hypotheses: List[Hypothesis] = []

        mapped_frames = [f for f in parsed_trace.frames if f.is_mapped and f.mapped_file_path]
        error_class = parsed_trace.error_class or "Error"
        error_msg = parsed_trace.error_message or issue_description

        if mapped_frames:
            # We have stack frames!
            # The deepest mapped frame is the immediate failure site
            failure_frame = mapped_frames[-1]

            # Immediate caller frame (if any) is often the root cause caller introducing unhandled error
            caller_frame = mapped_frames[-2] if len(mapped_frames) > 1 else None

            # Entrypoint frame (top of user stack)
            entry_frame = mapped_frames[0] if len(mapped_frames) > 2 else None

            # 1. Caller Function Hypothesis (e.g. refresh_access_token in Case G0-I-004)
            # In many system defects, callee raises expected validation error (e.g. AuthError: token expired),
            # but the caller fails to catch or translate it for the API layer.
            if caller_frame:
                hyp_id = str(uuid4())
                file_path = caller_frame.mapped_file_path or caller_frame.raw_file_path
                func_name = caller_frame.function_name or "caller_function"
                line_start = caller_frame.line
                line_end = caller_frame.line + 3

                snippet = self._extract_snippet(ctx, file_path, line_start, line_end)
                evidence = [
                    EvidenceRef(
                        id=str(uuid4()),
                        owner_type="HYPOTHESIS",
                        owner_id=hyp_id,
                        file_path=file_path,
                        line_start=line_start,
                        line_end=line_end,
                        snippet=snippet,
                        snippet_hash=compute_snippet_hash(snippet),
                        role=EvidenceRole.SUPPORTS,
                    )
                ]

                hypotheses.append(
                    Hypothesis(
                        id=hyp_id,
                        run_id=run_id,
                        rank=1,
                        summary=f"Unhandled {error_class} in '{func_name}' ({file_path}:{line_start})",
                        confidence=0.88,
                        status=HypothesisStatus.UNCONFIRMED,
                        file_path=file_path,
                        function=func_name,
                        line_start=line_start,
                        line_end=line_end,
                        rationale=(
                            f"{error_class} raised by deeper call is not caught or translated in '{func_name}', "
                            f"allowing the exception to propagate unexpectedly to the caller."
                        ),
                        evidence=evidence,
                    )
                )

            # 2. Immediate Failure Site Hypothesis (where exception was raised)
            hyp_id = str(uuid4())
            file_path = failure_frame.mapped_file_path or failure_frame.raw_file_path
            func_name = failure_frame.function_name or "failure_site"
            line_start = failure_frame.line
            line_end = failure_frame.line

            snippet = self._extract_snippet(ctx, file_path, line_start, line_end)
            evidence = [
                EvidenceRef(
                    id=str(uuid4()),
                    owner_type="HYPOTHESIS",
                    owner_id=hyp_id,
                    file_path=file_path,
                    line_start=line_start,
                    line_end=line_end,
                    snippet=snippet,
                    snippet_hash=compute_snippet_hash(snippet),
                    role=EvidenceRole.SUPPORTS,
                )
            ]

            hypotheses.append(
                Hypothesis(
                    id=hyp_id,
                    run_id=run_id,
                    rank=2 if caller_frame else 1,
                    summary=f"Exception raised in '{func_name}' ({file_path}:{line_start}): {error_class}",
                    confidence=0.82 if caller_frame else 0.90,
                    status=HypothesisStatus.UNCONFIRMED,
                    file_path=file_path,
                    function=func_name,
                    line_start=line_start,
                    line_end=line_end,
                    rationale=f"Direct exception origin: {error_class} ('{error_msg}') was raised at this line.",
                    evidence=evidence,
                )
            )

            # 3. Entrypoint / Controller Hypothesis (missing boundary error translation)
            if entry_frame and entry_frame != caller_frame:
                hyp_id = str(uuid4())
                file_path = entry_frame.mapped_file_path or entry_frame.raw_file_path
                func_name = entry_frame.function_name or "entrypoint"
                line_start = entry_frame.line
                line_end = entry_frame.line

                snippet = self._extract_snippet(ctx, file_path, line_start, line_end)
                evidence = [
                    EvidenceRef(
                        id=str(uuid4()),
                        owner_type="HYPOTHESIS",
                        owner_id=hyp_id,
                        file_path=file_path,
                        line_start=line_start,
                        line_end=line_end,
                        snippet=snippet,
                        snippet_hash=compute_snippet_hash(snippet),
                        role=EvidenceRole.SUPPORTS,
                    )
                ]

                hypotheses.append(
                    Hypothesis(
                        id=hyp_id,
                        run_id=run_id,
                        rank=3,
                        summary=f"Missing API boundary error translation in '{func_name}' ({file_path}:{line_start})",
                        confidence=0.74,
                        status=HypothesisStatus.UNCONFIRMED,
                        file_path=file_path,
                        function=func_name,
                        line_start=line_start,
                        line_end=line_end,
                        rationale=(
                            f"Entrypoint '{func_name}' failed to convert internal domain error {error_class} "
                            f"into an appropriate API response or recovery workflow."
                        ),
                        evidence=evidence,
                    )
                )

        else:
            # No mapped stack frames (e.g. only issue_description or failing_test provided)
            target_path = None
            if failing_test:
                # Derive path from failing test e.g. "tests/test_auth.py::test_refresh"
                test_file = failing_test.split("::")[0].strip()
                target_path = test_file

            hyp_id = str(uuid4())
            file_path = target_path or "unknown"
            snippet = f"# Reported issue:\n# {issue_description}"

            evidence = [
                EvidenceRef(
                    id=str(uuid4()),
                    owner_type="HYPOTHESIS",
                    owner_id=hyp_id,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    snippet=snippet,
                    snippet_hash=compute_snippet_hash(snippet),
                    role=EvidenceRole.SUPPORTS,
                )
            ]

            hypotheses.append(
                Hypothesis(
                    id=hyp_id,
                    run_id=run_id,
                    rank=1,
                    summary=f"Defect reported: {issue_description[:100]}",
                    confidence=0.60,
                    status=HypothesisStatus.UNCONFIRMED,
                    file_path=file_path,
                    function=failing_test or entrypoint,
                    line_start=1,
                    line_end=1,
                    rationale=f"Reported issue description indicates defect: {issue_description}",
                    evidence=evidence,
                )
            )

        # Sort and re-rank cleanly
        hypotheses.sort(key=lambda h: (h.rank, -h.confidence))
        for r, h in enumerate(hypotheses, start=1):
            h.rank = r

        return hypotheses

    def _extract_snippet(
        self,
        ctx: Any,
        file_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """Extract lines safely from the snapshot context."""
        file_obj = ctx.get_file(file_path)
        if not file_obj:
            return f"# Source file '{file_path}' (lines {start_line}-{end_line})"

        lines = file_obj.content.splitlines()
        s = max(1, start_line)
        e = min(len(lines), max(start_line, end_line))
        return "\n".join(lines[s - 1 : e])
