"""FastAPI Router for M1 Multi-Agent Code Analysis Endpoints."""

import json
from typing import Any, AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agentic.orchestrator.orchestrator import MultiAgentOrchestrator
from agentic.schemas.agent import (
    AgentRunApproveRequest,
    AgentRunCreateRequest,
    AgentRunResponse,
    MultiAgentReport,
)

router = APIRouter(prefix="/agents", tags=["Multi-Agent Code Analysis (M1)"])

# Shared orchestrator instance
orchestrator = MultiAgentOrchestrator()


@router.post(
    "/analysis-runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and start a multi-agent analysis run",
)
def create_analysis_run(request: AgentRunCreateRequest) -> AgentRunResponse:
    try:
        return orchestrator.create_analysis_run(request)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/analysis-runs/{id}",
    response_model=AgentRunResponse,
    summary="Get multi-agent analysis run status and plan",
)
def get_analysis_run(id: str) -> AgentRunResponse:
    try:
        return orchestrator.get_run_response(id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run '{id}' not found.",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post(
    "/analysis-runs/{id}/approve",
    response_model=AgentRunResponse,
    summary="Approve an analysis plan or gated execution step",
)
def approve_analysis_run(id: str, request: AgentRunApproveRequest) -> AgentRunResponse:
    try:
        return orchestrator.approve_run(id, request)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run '{id}' not found.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/analysis-runs/{id}/cancel",
    response_model=AgentRunResponse,
    summary="Cancel an active multi-agent analysis run",
)
def cancel_analysis_run(id: str) -> AgentRunResponse:
    try:
        return orchestrator.cancel_run(id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run '{id}' not found.",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get(
    "/analysis-runs/{id}/events",
    summary="Stream real-time agent execution progress events via SSE",
)
async def stream_analysis_run_events(id: str) -> StreamingResponse:
    try:
        orchestrator.get_run_response(id)  # validate existence
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis run '{id}' not found.",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in orchestrator.subscribe_events(id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/analysis-runs/{id}/report",
    response_model=MultiAgentReport,
    summary="Retrieve the consolidated multi-agent report with consensus and disagreements",
)
def get_analysis_run_report(id: str) -> MultiAgentReport:
    try:
        return orchestrator.get_report(id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report or analysis run '{id}' not found.",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
