# CodePilot Documentation Guide

This directory holds the project specifications and engineering guide for **CodePilot — The Knowledge of Athena**.

## Specifications
1. `docs/specifications/SYSTEM_DESIGN_SPECIFICATION.md`: System Design Specification v1.1 (Scale, Latency, Reliability, 1000-user capacity model).
2. `docs/specifications/API_INTEGRATION_DATA_SPECIFICATION.md`: API, Integration & Data Specification v1.0 (98-endpoint catalogue, database DDL, Redis keys, Pydantic contracts).
3. `docs/specifications/MASTER_SPECIFICATION.md`: Master Architecture, Feature & Engineering Specification v2.1 (The 21 capabilities across Basic, Advanced, and Mastermind tiers).

## Current Phase: Authentication System
- GitHub OAuth Authentication
- Server-side Redis sessions (`cp_session`, HttpOnly, SameSite=Lax)
- Users and OAuth Connections in PostgreSQL with Alembic migrations
- FastAPI modular backend (`/api/v1/auth/*` and `/api/v1/integrations/github/*`)
- React + Vite + Tailwind CSS frontend with a professional CodePilot login page and protected dashboard placeholder
