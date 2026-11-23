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


@app.get("/healthz", tags=["Health"], summary="Liveness probe")
def liveness_check() -> dict:
    return {"status": "ok", "service": "codepilot-api", "version": "1.0.0"}


@app.get("/readyz", tags=["Health"], summary="Readiness probe")
def readiness_check() -> dict:
    return {"status": "ready", "service": "codepilot-api", "version": "1.0.0"}


@app.get("/metrics", tags=["Observability"], summary="Prometheus metrics")
def metrics() -> str:
    return "# HELP codepilot_up API status\n# TYPE codepilot_up gauge\ncodepilot_up 1\n"
