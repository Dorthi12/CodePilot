"""Tool permissions and registry for agent governance."""

from dataclasses import dataclass, field
from typing import Dict, List, Set
from shared.types.agent import AgentRole, ToolPermissionLevel


@dataclass
class ToolDefinition:
    name: str
    permission_level: ToolPermissionLevel
    description: str
    allowed_roles: Set[AgentRole]
    dangerous: bool = False
    requires_approval: bool = False
    egress_allowed: bool = False


class ToolPermissionRegistry:
    """Registry mapping tools to their required permission levels and allowed roles."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.register(
            ToolDefinition(
                name="file_read",
                permission_level=ToolPermissionLevel.READ,
                description="Read source code files from the pinned repository snapshot",
                allowed_roles={
                    AgentRole.ORCHESTRATOR,
                    AgentRole.ARCHITECTURE,
                    AgentRole.SECURITY,
                    AgentRole.CODE_QUALITY,
                    AgentRole.PERFORMANCE,
                    AgentRole.TESTING,
                    AgentRole.REVIEW,
                },
                dangerous=False,
                requires_approval=False,
            )
        )
        self.register(
            ToolDefinition(
                name="symbol_search",
                permission_level=ToolPermissionLevel.READ,
                description="Search AST symbols (functions, classes, variables, constants)",
                allowed_roles={
                    AgentRole.ORCHESTRATOR,
                    AgentRole.ARCHITECTURE,
                    AgentRole.SECURITY,
                    AgentRole.CODE_QUALITY,
                    AgentRole.PERFORMANCE,
                    AgentRole.TESTING,
                    AgentRole.REVIEW,
                },
                dangerous=False,
                requires_approval=False,
            )
        )
        self.register(
            ToolDefinition(
                name="graph_query",
                permission_level=ToolPermissionLevel.READ,
                description="Query relationships (CALLS, IMPORTS, DEPENDS_ON) in graph",
                allowed_roles={
                    AgentRole.ORCHESTRATOR,
                    AgentRole.ARCHITECTURE,
                    AgentRole.SECURITY,
                    AgentRole.CODE_QUALITY,
                    AgentRole.PERFORMANCE,
                    AgentRole.TESTING,
                    AgentRole.REVIEW,
                },
                dangerous=False,
                requires_approval=False,
            )
        )
        self.register(
            ToolDefinition(
                name="static_analysis",
                permission_level=ToolPermissionLevel.ANALYZE,
                description="Run deterministic static linting and heuristic checks",
                allowed_roles={
                    AgentRole.SECURITY,
                    AgentRole.CODE_QUALITY,
                    AgentRole.PERFORMANCE,
                    AgentRole.ARCHITECTURE,
                },
                dangerous=False,
                requires_approval=False,
            )
        )
        self.register(
            ToolDefinition(
                name="sandbox_test_runner",
                permission_level=ToolPermissionLevel.EXECUTE,
                description="Execute tests inside an isolated ephemeral sandbox",
                allowed_roles={AgentRole.TESTING, AgentRole.PERFORMANCE},
                dangerous=True,
                requires_approval=True,
                egress_allowed=False,
            )
        )
        self.register(
            ToolDefinition(
                name="patch_workspace_writer",
                permission_level=ToolPermissionLevel.WRITE,
                description="Generate patch draft in temporary workspace",
                allowed_roles={AgentRole.REVIEW},
                dangerous=True,
                requires_approval=True,
                egress_allowed=False,
            )
        )

    def register(self, tool_def: ToolDefinition) -> None:
        self._tools[tool_def.name] = tool_def

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered in the ToolPermissionRegistry.")
        return self._tools[name]

    def is_registered(self, name: str) -> bool:
        return name in self._tools
