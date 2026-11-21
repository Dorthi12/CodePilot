from fastapi import APIRouter
from src.api.v1.auth import router as auth_router
from src.api.v1.github import router as github_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(github_router)
