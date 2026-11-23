"""
Main entry point for the CodePilot AIservices FastAPI application.
Runs Feature 1: Basic Code Search and provides the REST API for the Node.js backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from AIservices.api.routes import router

app = FastAPI(
    title="CodePilot AI Services",
    version="1.0.0",
    description="Microservice providing repository indexing, code search (Feature 1), and AI code explanation (Feature 2) for CodePilot.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for local backend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("AIservices.main:app", host="127.0.0.1", port=8001, reload=True)