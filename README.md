# CodePilot — The Knowledge of Athena

> An AI-powered codebase understanding and developer-assistance platform.

---

> [!IMPORTANT]
> ### 👥 Team Collaboration & Developer Onboarding
> If you are collaborating on this project or setting up your local developer environment, please consult:
> **👉 [TEAM_SETUP.md](TEAM_SETUP.md) — Team Setup & Safe Collaboration Guide**
> Contains step-by-step instructions for Docker, environment configuration, migrations without data loss, safe Git branching, and troubleshooting.

---

## Current Status: Phase 1 — Authentication System Complete

This repository contains the production-grade, secure authentication system for **CodePilot**, strictly adhering to the **CodePilot Master Architecture Specification (v2.1)** and **API, Integration & Data Specification (v1.0)**.

### Architecture Overview

- **Identity Provider**: GitHub OAuth 2.0 Web Application Flow.
- **Sessions**: Server-side sessions stored in **Redis** (`sess:{session_id}`) with:
  - 12-hour sliding idle timeout.
  - 7-day absolute lifetime cap.
  - Session ID rotation upon authentication (anti-session-fixation).
  - Stored in an `HttpOnly`, `SameSite=Lax` cookie named `cp_session`.
- **CSRF Protection**: Double-submit cookie pattern (`cp_csrf`) combined with server-side session token verification and `Origin`/`Referer` validation on all state-changing endpoints (`POST`, `PUT`, `PATCH`, `DELETE`).
- **Token Security**: GitHub OAuth access tokens are encrypted at rest with **AES-256-GCM** using a 256-bit derived key. Tokens are never exposed to the client browser or logged.
- **Database**: PostgreSQL 16 (persisted tables: `users`, `oauth_connections`) with Alembic version-controlled migrations.

---

## Technology Stack

### Backend (`apps/api`)
- **Language**: Python 3.12+
- **Framework**: FastAPI (modular routers, dependency injection, Pydantic v2 validation)
- **Database ORM**: SQLAlchemy 2.0 (asyncio + asyncpg / sqlite+aiosqlite fallback)
- **Migrations**: Alembic
- **Session & Caching**: Redis 7.0+ (redis-py async client + fakeredis for tests)
- **Cryptography**: `cryptography` (AES-256-GCM)

### Frontend (`apps/web`)
- **Framework**: React 18+ & TypeScript
- **Bundler**: Vite
- **Routing**: React Router v6
- **Styling**: Tailwind CSS (dark developer-tool aesthetic)
- **HTTP Client**: Axios with interceptors for credentials and CSRF tokens
- **Icons**: Lucide React

---

## Project Structure

```text
codepilot/
├── apps/
│   ├── api/                     # FastAPI backend application
│   │   ├── alembic/             # Database migrations
│   │   │   └── versions/        # Migration scripts (initial auth tables)
│   │   ├── src/
│   │   │   ├── api/             # API routes and dependencies
│   │   │   │   ├── deps.py      # Session and CSRF dependencies
│   │   │   │   └── v1/          # /api/v1 routers (auth, github)
│   │   │   ├── models/          # SQLAlchemy ORM models (User, OAuthConnection)
│   │   │   ├── schemas/         # Pydantic request/response schemas
│   │   │   ├── services/        # Business logic (Auth, GitHub, Session, Crypto)
│   │   │   ├── config.py        # Centralized Pydantic settings
│   │   │   ├── database.py      # Database engine and session factory
│   │   │   ├── main.py          # FastAPI application entrypoint
│   │   │   └── redis_client.py  # Async Redis client with resilient fallback
│   │   ├── tests/               # Automated test suite (19 tests)
│   │   ├── requirements.txt     # Production dependencies
│   │   └── requirements-dev.txt # Development & test dependencies
│   └── web/                     # React frontend application
│       ├── src/
│       │   ├── components/      # Navbar, ProtectedRoute
│       │   ├── context/         # AuthContext (state management)
│       │   ├── pages/           # LoginPage, DashboardPage
│       │   ├── services/        # Axios API client and auth service
│       │   ├── types/           # TypeScript interfaces (User, GitHubStatus)
│       │   ├── App.tsx          # Application routing
│       │   └── main.tsx         # React root
│       ├── index.html
│       ├── package.json
│       ├── tailwind.config.js
│       └── vite.config.ts
├── docs/
│   ├── specifications/          # SDS v1.1, AIDS v1.0, Master Spec v2.1
│   └── PROJECT_GUIDE.md
├── docker-compose.yml           # Local dev infrastructure (PostgreSQL 16 + Redis 7 AOF)
├── .env.example                 # Example environment variables
└── README.md
```

---

## API Endpoints Implemented

All endpoints are mounted under `/api/v1`:

| Method | Endpoint | Purpose | Security / Access |
|---|---|---|---|
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile | Requires active `cp_session` |
| `POST` | `/api/v1/auth/logout` | Invalidate Redis session and clear cookies | Requires active `cp_session` & `X-CSRF-Token` |
| `GET` | `/api/v1/integrations/github/start` | Initiate GitHub OAuth authorization | Public (stores state with 10m TTL in Redis) |
| `GET` | `/api/v1/integrations/github/callback` | Handle OAuth callback from GitHub | Validates state (single-use), exchanges code |
| `GET` | `/api/v1/integrations/github/status` | Check GitHub OAuth integration details | Requires active `cp_session` |
| `DELETE` | `/api/v1/integrations/github` | Disconnect GitHub integration | Requires active `cp_session` & `X-CSRF-Token` |
| `GET` | `/healthz` | Liveness health check | Operational |
| `GET` | `/readyz` | Readiness health check | Operational |

---

## Getting Started

### 1. Environment Setup

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

To enable live GitHub authentication, register an OAuth App on GitHub:
1. Navigate to **GitHub Settings -> Developer settings -> OAuth Apps -> New OAuth App**.
2. Set **Application Name**: `CodePilot`
3. Set **Homepage URL**: `http://localhost:5173`
4. Set **Authorization callback URL**: `http://localhost:8000/api/v1/integrations/github/callback`
5. Copy your **Client ID** and generate a **Client Secret**, then fill them in `.env`:
   ```dotenv
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   ```

### 2. Run with Docker Compose (Recommended)

Start PostgreSQL and Redis:
```bash
docker compose up -d postgres redis
```

Or start the full stack:
```bash
docker compose up -d
```

### 3. Local Development (Without Docker)

#### Backend Setup
```bash
cd apps/api
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start FastAPI dev server
uvicorn src.main:app --reload --port 8000
```
*Note: If PostgreSQL or Redis are not running locally, the development server automatically provides resilient in-memory fallback for immediate zero-friction local exploration.*

#### Frontend Setup
```bash
cd apps/web
npm install
npm run dev
```

Visit `http://localhost:5173` in your browser.

---

## Automated Tests

Run the backend test suite:
```bash
cd apps/api
.\.venv\Scripts\python -m pytest tests/ -v
```

The test suite validates:
- Unauthenticated vs authenticated access on `/auth/me`.
- Session creation, TTL expiration, 7-day absolute lifetime, and rotation.
- GitHub OAuth authorization URL generation with Redis state storage.
- Callback validation: missing parameters, invalid state, replayed state prevention.
- First-time user registration & existing user profile updates.
- AES-256-GCM token encryption and decryption.
- CSRF protection: missing token rejection, mismatched token rejection, untrusted origin rejection, and valid token acceptance.
- User logout and Redis session invalidation.

---

## Next Steps

Per the **CodePilot Master Architecture Specification**, the remaining 20 features (Repository Ingestion, Codebase Explorer, Knowledge Graph, Hybrid RAG, Multi-Agent Engine, etc.) will be implemented sequentially upon explicit direction.
