"""Tool for querying relationships and paths in the repository property graph."""

from typing import Any, Dict, List, Optional
from shared.types.agent import ToolPermissionLevel
from agentic.common.agent_context import SnapshotContextRegistry
from agentic.tools.base_tool import BaseAgentTool


class GraphQueryTool(BaseAgentTool):
    name = "graph_query"
    permission_level = ToolPermissionLevel.READ
    description = "Query relationships (CALLS, IMPORTS, DEPENDS_ON) in graph"

    def execute(
        self,
        snapshot_id: str,
        node_id: Optional[str] = None,
        relationship_types: Optional[List[str]] = None,
        direction: str = "OUTGOING",  # OUTGOING, INCOMING, BOTH
        max_depth: int = 2,
        limit: int = 50,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        ctx = SnapshotContextRegistry.get(snapshot_id)
        matched_edges: List[Dict[str, Any]] = []

        rel_filter = set(r.upper() for r in (relationship_types or []))

        for edge in ctx.edges:
            if rel_filter and edge.relationship.upper() not in rel_filter:
                continue

            match = False
            if not node_id:
                match = True
            elif direction == "OUTGOING" and edge.source == node_id:
                match = True
            elif direction == "INCOMING" and edge.target == node_id:
                match = True
            elif direction == "BOTH" and (edge.source == node_id or edge.target == node_id):
                match = True

            if match:
                matched_edges.append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relationship": edge.relationship,
                        "confidence": edge.confidence,
                    }
                )

            if len(matched_edges) >= limit:
                break

        return {
            "snapshot_id": snapshot_id,
            "node_id": node_id,
            "count": len(matched_edges),
            "edges": matched_edges,
        }
