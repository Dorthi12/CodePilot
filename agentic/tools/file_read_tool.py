"""Tool for reading source code lines from a repository snapshot."""

from typing import Any, Dict, Optional
from shared.types.agent import ToolPermissionLevel
from agentic.common.agent_context import SnapshotContextRegistry
from agentic.tools.base_tool import BaseAgentTool


class FileReadTool(BaseAgentTool):
    name = "file_read"
    permission_level = ToolPermissionLevel.READ
    description = "Read file content from the snapshot workspace with line bounds"

    def execute(
        self,
        snapshot_id: str,
        file_path: str,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ctx = SnapshotContextRegistry.get(snapshot_id)
        norm_path = file_path.replace("\\", "/").lstrip("/")
        file_obj = ctx.get_file(norm_path)

        if not file_obj:
            raise FileNotFoundError(f"File '{norm_path}' not found in snapshot '{snapshot_id}'.")

        lines = file_obj.content.splitlines()
        total_lines = len(lines)

        start = max(1, line_start or 1)
        end = min(total_lines, line_end or total_lines)

        if start > total_lines:
            selected_lines = []
        else:
            selected_lines = lines[start - 1 : end]

        snippet = "\n".join(selected_lines)

        return {
            "file_path": norm_path,
            "line_start": start,
            "line_end": end,
            "total_lines": total_lines,
            "snippet": snippet,
            "content_hash": file_obj.content_hash,
            "language": file_obj.language,
        }
