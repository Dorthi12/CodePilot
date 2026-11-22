"""FastAPI application entrypoint for CodePilot - The Knowledge of Athena."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router

app = FastAPI(
    title="CodePilot API",
    description="Enterprise Multi-Agent & Code Intelligence Platform (The Knowledge of Athena)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS middleware allowlist
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 Routers
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    return {"status": "ok", "service": "codepilot-api", "version": "1.0.0"}
