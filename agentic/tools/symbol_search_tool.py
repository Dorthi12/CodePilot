"""Tool for searching symbols within a repository snapshot."""

from typing import Any, Dict, List, Optional
from shared.types.agent import ToolPermissionLevel
from agentic.common.agent_context import SnapshotContextRegistry
from agentic.tools.base_tool import BaseAgentTool


class SymbolSearchTool(BaseAgentTool):
    name = "symbol_search"
    permission_level = ToolPermissionLevel.READ
    description = "Search AST symbols (functions, classes, variables, constants)"

    def execute(
        self,
        snapshot_id: str,
        query: str = "",
        kind: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ctx = SnapshotContextRegistry.get(snapshot_id)
        results: List[Dict[str, Any]] = []

        q_lower = query.lower()
        for sym in ctx.symbols:
            if query and q_lower not in sym.name.lower() and q_lower not in sym.qualified_name.lower():
                continue
            if kind and sym.kind.upper() != kind.upper():
                continue
            if file_path and sym.file_path != file_path.replace("\\", "/").lstrip("/"):
                continue

            results.append(
                {
                    "symbol_id": sym.id,
                    "name": sym.name,
                    "qualified_name": sym.qualified_name,
                    "kind": sym.kind,
                    "file_path": sym.file_path,
                    "line_start": sym.start_line,
                    "line_end": sym.end_line,
                    "complexity": sym.complexity,
                }
            )

            if len(results) >= limit:
                break

        return {
            "snapshot_id": snapshot_id,
            "query": query,
            "count": len(results),
            "symbols": results,
        }
