"""Reconstruction of call execution path and graph traversal for bug investigation.

Specifications:
- Master Architecture Specification v2.1 §10 (M2)
- API and Data Specification v1.0 §3.4.13
"""

import hashlib
from typing import Any, Dict, List, Optional
from shared.types.investigation import CallPathFrame, InvestigationFrame
from agentic.common.agent_context import RepositorySnapshotContext, SnapshotContextRegistry


class CallPathTracer:
    """Traces and reconstructs call paths using parsed frames and the repository code graph."""

    def trace_call_path(
        self,
        snapshot_id: str,
        frames: List[InvestigationFrame],
        entrypoint: Optional[str] = None,
        context_radius: int = 3,
    ) -> List[CallPathFrame]:
        """Build an ordered execution call path with snippets and entrypoint/root-cause tags."""
        ctx = SnapshotContextRegistry.get(snapshot_id)
        call_path: List[CallPathFrame] = []

        mapped_frames = [f for f in frames if f.is_mapped and f.mapped_file_path]
        if not mapped_frames:
            return call_path

        total_mapped = len(mapped_frames)

        for idx, frame in enumerate(mapped_frames):
            file_path = frame.mapped_file_path or frame.raw_file_path
            file_obj = ctx.get_file(file_path)

            snippet = None
            if file_obj:
                lines = file_obj.content.splitlines()
                start = max(1, frame.line - context_radius)
                end = min(len(lines), frame.line + context_radius)
                snippet_lines = lines[start - 1 : end]
                snippet = "\n".join(snippet_lines)
            elif frame.code_line:
                snippet = frame.code_line

            # Determine if entrypoint: either matches specified entrypoint or is the earliest mapped caller
            is_entry = False
            if entrypoint and entrypoint.lower() in file_path.lower():
                is_entry = True
            elif idx == 0:
                is_entry = True

            # Candidate root cause: typically deepest frame (failure site) or its immediate caller
            is_root_cause = (idx == total_mapped - 1) or (idx == total_mapped - 2)

            call_path.append(
                CallPathFrame(
                    order=idx + 1,
                    file_path=file_path,
                    line=frame.line,
                    function=frame.function_name,
                    snippet=snippet,
                    is_root_cause_candidate=is_root_cause,
                    is_entrypoint=is_entry,
                )
            )

        return call_path
