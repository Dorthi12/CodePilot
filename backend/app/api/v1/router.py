"""API v1 master router unifying all feature endpoints."""

from fastapi import APIRouter

from backend.app.api.v1.agents import router as agents_router
from backend.app.api.v1.analysis import router as analysis_router
from backend.app.api.v1.fixes import router as fixes_router
from backend.app.api.v1.improvements import router as improvements_router
from backend.app.api.v1.investigations import router as investigations_router

api_router = APIRouter()

# Mount feature routers
api_router.include_router(agents_router)
api_router.include_router(analysis_router)
api_router.include_router(investigations_router)
api_router.include_router(improvements_router)
api_router.include_router(fixes_router)
