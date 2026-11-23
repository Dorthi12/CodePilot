"""Base tool class for CodePilot agentic capabilities."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict
from shared.types.agent import ToolPermissionLevel


class BaseAgentTool(ABC):
    """Abstract base class for all agent tools."""

    name: str
    permission_level: ToolPermissionLevel
    description: str

    @abstractmethod
    def execute(self, snapshot_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Execute the tool logic against the target snapshot."""
        pass

    def run(self, snapshot_id: str, **kwargs: Any) -> Dict[str, Any]:
        """Executes tool and captures execution metrics and error handling."""
        start_time = time.perf_counter()
        try:
            result = self.execute(snapshot_id=snapshot_id, **kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "SUCCESS",
                "result": result,
                "duration_ms": round(duration_ms, 2),
            }
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "ERROR",
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
            }
