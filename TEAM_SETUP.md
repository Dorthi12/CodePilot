# CodePilot — Team Setup & Collaboration Guide

> **Important Notice for Teammates:**
> CodePilot is an active, collaborative project with multiple developers working on ongoing feature branches.
> **Do not treat this as a blank project or attempt to recreate the application from scratch.**
> This guide outlines how to configure your local developer environment, safely integrate your teammates' contributions, and collaborate without overwriting or losing code or data.

---

## Table of Contents

1. [System Requirements & Prerequisites](#1-system-requirements--prerequisites)
2. [First-Time Environment Setup](#2-first-time-environment-setup)
3. [Running with Docker Compose (Recommended)](#3-running-with-docker-compose-recommended)
4. [Running Services Locally (Native / Hybrid)](#4-running-services-locally-native--hybrid)
5. [Database Migrations & Data Preservation](#5-database-migrations--data-preservation)
6. [Application Verification & Health Checks](#6-application-verification--health-checks)
7. [Safe Git Collaboration Workflow (Windows PowerShell)](#7-safe-git-collaboration-workflow-windows-powershell)
8. [Strict Safety Rules (Preventing Data & Code Loss)](#8-strict-safety-rules-preventing-data--code-loss)
9. [Environment Variables Reference](#9-environment-variables-reference)
10. [Troubleshooting Common Issues](#10-troubleshooting-common-issues)

---

## 1. System Requirements & Prerequisites

Before setting up your environment, ensure you have the following installed:

| Tool | Recommended Version | Purpose |
|---|---|---|
| **Git** | `2.40+` | Version control |
| **Python** | `3.12+` | Backend runtime & testing |
| **Node.js** | `v20.x` or `v22.x` (LTS) | Frontend runtime |
| **npm** | `10.x+` | Frontend package manager |
| **Docker Desktop** | `24+` / Compose `v2+` | Containerized PostgreSQL, Redis, API, and Web |
| **PowerShell** | `7+` or `Windows PowerShell 5.1` | Terminal scripting (Windows) |

---

## 2. First-Time Environment Setup

### Step 2.1: Clone the Shared Repository

Clone the existing repository from the team's remote GitHub URL:

```powershell
# Clone the repository
git clone https://github.com/<your-org-or-user>/CodePilot.git
cd CodePilot
```

### Step 2.2: Configure Local Environment Variables

Every developer must maintain their own local `.env` file based on `.env.example`.
**Never commit `.env` or real credentials to Git.**

```powershell
# Copy the example environment file to .env in project root
Copy-Item .env.example .env

# Also create local copies inside apps/api and apps/web if running natively
Copy-Item apps/api/.env.example apps/api/.env
```

Open `.env` and fill in your developer settings:

```dotenv
# Environment Mode
ENVIRONMENT=development
APP_NAME="CodePilot — The Knowledge of Athena"

# Service Base URLs
APP_BASE_URL=http://localhost:8000
FRONTEND_BASE_URL=http://localhost:5173
VITE_API_URL=http://localhost:8000/api/v1

# PostgreSQL Connection (Port 5432)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codepilot
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5432/codepilot

# Redis Connection (Port 6379)
REDIS_URL=redis://localhost:6379/0

# GitHub OAuth Application Credentials (see Step 2.3)
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/integrations/github/callback
GITHUB_SCOPES=read:user,user:email,repo

# Cryptographic Keys (Must be 32+ characters)
SESSION_SECRET=dev-session-secret-key-must-be-at-least-32-chars-long
TOKEN_ENCRYPTION_KEY=dev-token-encryption-key-must-be-32-chars!

# Workspace & Cloned Repositories Storage
WORKSPACE_BASE_DIR=/workspaces
```

### Step 2.3: Configure Your Local GitHub OAuth App

To enable login and repository browsing:
1. Go to **GitHub -> Settings -> Developer settings -> OAuth Apps -> New OAuth App** ([https://github.com/settings/applications/new](https://github.com/settings/applications/new)).
2. Configure the application:
   - **Application Name:** `CodePilot Dev (Your Name)`
   - **Homepage URL:** `http://localhost:5173`
   - **Authorization callback URL:** `http://localhost:8000/api/v1/integrations/github/callback` *(Exact match is required!)*
3. Click **Register application**.
4. Copy the **Client ID**.
5. Click **Generate a new client secret** and copy it.
6. Paste both into your `.env` file under `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.

---

## 3. Running with Docker Compose (Recommended)

Docker Compose runs the entire CodePilot stack (PostgreSQL 16, Redis 7, FastAPI backend, and React frontend) with persistent volumes.

```powershell
# 1. Start all containers in detached mode
docker-compose up -d --build

# 2. Check container status
docker-compose ps
```

Expected output:
```text
NAME                 IMAGE                STATUS                  PORTS
codepilot-postgres   postgres:16-alpine   Up (healthy)            127.0.0.1:5432->5432/tcp
codepilot-redis      redis:7-alpine       Up (healthy)            127.0.0.1:6379->6379/tcp
codepilot-api        codepilot-api        Up                      0.0.0.0:8000->8000/tcp
codepilot-web        codepilot-web        Up                      0.0.0.0:5173->5173/tcp
```

To view live container logs:
```powershell
docker-compose logs -f api
docker-compose logs -f web
```

To stop containers **without losing database records or cloned workspaces**:
```powershell
# SAFE: stops containers while preserving volumes
docker-compose down
```

> [!CAUTION]
> **NEVER run `docker-compose down -v` or `docker volume prune`.**
> The `-v` flag permanently deletes the Docker volumes `postgres_data`, `redis_data`, and `workspace_data`, destroying all local databases and cloned repository workspaces!

---

## 4. Running Services Locally (Native / Hybrid)

If you prefer running Python and Node directly on your host while using Docker only for PostgreSQL and Redis:

### Step 4.1: Start Supporting Infrastructure
```powershell
# Run only PostgreSQL and Redis in Docker
docker-compose up -d postgres redis
```

### Step 4.2: Setup Backend (`apps/api`)
```powershell
cd apps/api

# Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# Run migrations
alembic upgrade head

# Start FastAPI development server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 4.3: Setup Frontend (`apps/web`)
Open a new PowerShell terminal:
```powershell
cd apps/web

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```

---

## 5. Database Migrations & Data Preservation

CodePilot uses Alembic for version-controlled database schema migrations.

### Applying Existing Migrations Safely
When setting up or pulling updates from teammates, apply pending migrations to bring your database schema up to date without deleting existing data:

```powershell
# Inside apps/api (with virtual environment active)
alembic upgrade head
```

Or via Docker:
```powershell
docker-compose exec api alembic upgrade head
```

### Creating New Migrations
When adding or modifying SQLAlchemy models:
1. Communicate with teammates to avoid conflicting migration heads.
2. Generate a new sequential migration script:
   ```powershell
   alembic revision -m "create_feature_xyz_table"
   ```
3. Edit the generated file in `apps/api/alembic/versions/`.
4. Apply and test both `upgrade` and `downgrade`:
   ```powershell
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

> [!IMPORTANT]
> If a merge conflict results in multiple Alembic heads (`Multiple head revisions are present`), **do not edit or delete older migration files**. Instead, run:
> ```powershell
> alembic merge heads -m "merge_conflicting_heads"
> alembic upgrade head
> ```

---

## 6. Application Verification & Health Checks

Once services are running, verify each component:

### Port Allocation
- **Frontend Web UI:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000`
- **PostgreSQL Database:** `localhost:5432`
- **Redis Cache & Session Store:** `localhost:6379`

### Health Check Verification
In PowerShell:
```powershell
# 1. Verify Backend Liveness
(Invoke-WebRequest -Uri http://localhost:8000/healthz -UseBasicParsing).Content
# Expected: {"status":"ok","app":"CodePilot — The Knowledge of Athena"}

# 2. Verify Backend Readiness
(Invoke-WebRequest -Uri http://localhost:8000/readyz -UseBasicParsing).Content
# Expected: {"status":"ready"}

# 3. Verify Frontend HTTP Server
(Invoke-WebRequest -Uri http://localhost:5173 -UseBasicParsing).StatusCode
# Expected: 200
```

### Running Test Suites
Before making any changes, verify that your environment passes all tests:

```powershell
# 1. Backend Pytest Suite (69 tests)
& apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests

# 2. Frontend Production Build Check (TypeScript + Vite)
npm --prefix apps/web run build
```

---

## 7. Safe Git Collaboration Workflow (Windows PowerShell)

Because multiple teammates are actively developing features on different branches, adhere strictly to this collaboration workflow.

### 7.1. Check Current Status Before Starting Work
```powershell
# Check what branch you are on and if you have uncommitted changes
git status
git branch -a
```

### 7.2. Always Work on Isolated Feature Branches
**Never commit directly to `main`.** Always create a descriptive branch:
```powershell
# Create and switch to a new branch from latest main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### 7.3. Preserving Local Uncommitted Work
If you need to switch branches or pull teammates' updates without losing your work:
```powershell
# Stash your modified and untracked files safely
git stash save "WIP: your description of current progress"

# Switch branches or pull updates
git checkout main
git pull origin main
git checkout feature/your-feature-name

# Restore your stashed changes
git stash pop
```

### 7.4. Integrating Shared Updates from Teammates
To keep your feature branch up-to-date with work merged into `main` by teammates:
```powershell
# Fetch all remote branches and commits
git fetch origin

# Rebase your feature branch on top of main
git rebase origin/main
```

### 7.5. Resolving Merge Conflicts Safely
If Git notifies you of conflicts during rebase or merge:
1. Open conflicting files in your editor (look for `<<<<<<<`, `=======`, `>>>>>>>`).
2. Review both your changes and your teammate's changes. **Do not blindly choose "accept theirs" or "accept ours".** Combine both logics.
3. Once resolved, mark the conflict as resolved and continue:
   ```powershell
   git add <resolved-file-path>
   git rebase --continue
   ```
   *(If you get stuck or make a mistake, abort safely without losing work: `git rebase --abort`)*

### 7.6. Verifying Before Pushing
Always run test suites before pushing your branch:
```powershell
& apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests
npm --prefix apps/web run build
```

### 7.7. Pushing and Opening a Pull Request
```powershell
# Push your feature branch to the remote repository
git push -u origin feature/your-feature-name
```
Open a Pull Request on GitHub for peer review. Only merge after tests pass and team approval is granted.

---

## 8. Strict Safety Rules (Preventing Data & Code Loss)

To protect your teammates' contributions and prevent accidental data loss:

1. **DO NOT run destructive Git resets:**
   - `git reset --hard` discards uncommitted work permanently.
   - `git clean -fd` deletes untracked files, which may include your `.env` or local test assets.
   - Always use `git stash` instead.

2. **DO NOT run destructive Docker volume commands:**
   - `docker-compose down -v` wipes all databases and cloned workspaces.
   - Use `docker-compose down` (without `-v`) to preserve data.

3. **DO NOT commit local configuration or secrets:**
   - `.env`, `.env.local`, `.venv`, and `node_modules` must remain in `.gitignore`.
   - Never hardcode API keys, client secrets, or cryptographic tokens in Python or TypeScript files.

4. **DO NOT delete or modify existing migration files:**
   - Once a migration is committed and pushed, it is immutable. Add a new migration to make further schema changes.

5. **DO NOT delete repositories on GitHub when testing:**
   - The CodePilot deletion action only removes local database records and workspace cache. It never calls GitHub's deletion API.

---

## 9. Environment Variables Reference

| Variable | Required | Default / Example | Purpose |
|---|---|---|---|
| `ENVIRONMENT` | Yes | `development` | Environment mode (`development`, `testing`, `production`) |
| `APP_BASE_URL` | Yes | `http://localhost:8000` | Backend base URL |
| `FRONTEND_BASE_URL` | Yes | `http://localhost:5173` | Frontend application URL |
| `VITE_API_URL` | Yes | `http://localhost:8000/api/v1` | Frontend API client base URL |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://...` | Async SQLAlchemy database URL |
| `DATABASE_URL_SYNC` | Yes | `postgresql://...` | Synchronous database URL used by Alembic |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis session and lock connection URL |
| `GITHUB_CLIENT_ID` | Yes | `your_client_id` | GitHub OAuth App Client ID |
| `GITHUB_CLIENT_SECRET` | Yes | `your_client_secret` | GitHub OAuth App Client Secret |
| `GITHUB_REDIRECT_URI` | Yes | `http://localhost:8000/api/v1/integrations/github/callback` | OAuth redirect callback URI |
| `SESSION_SECRET` | Yes | `32+ characters` | Signing secret for session data |
| `TOKEN_ENCRYPTION_KEY` | Yes | `32 characters` | AES-256-GCM token encryption key |
| `WORKSPACE_BASE_DIR` | Yes | `/workspaces` | Directory where repository workspaces are cloned |

---

## 10. Troubleshooting Common Issues

### Issue 1: Port Conflict (Port Already in Use)
- **Error:** `bind: address already in use` for `5432`, `6379`, `8000`, or `5173`.
- **Cause:** Another local PostgreSQL, Redis, or Node process is running on your machine.
- **Solution (PowerShell):**
  ```powershell
  # Find what process is holding port 5432 or 8000
  Get-NetTCPConnection -LocalPort 5432, 8000 -ErrorAction SilentlyContinue | Select-Object LocalPort, OwningProcess
  # Stop local native Postgres/Redis services if you want Docker to own the ports:
  Stop-Service -Name postgresql* -ErrorAction SilentlyContinue
  ```

### Issue 2: GitHub OAuth Redirect URI Mismatch
- **Error:** `redirect_uri_mismatch` during GitHub login.
- **Solution:** Verify that the callback URL configured in your GitHub OAuth App settings is exactly `http://localhost:8000/api/v1/integrations/github/callback`.

### Issue 3: Docker Daemon Not Running
- **Error:** `error during connect: ... open //./pipe/docker_engine: The system cannot find the file specified.`
- **Solution:** Ensure **Docker Desktop** is launched and running. In Docker Desktop Settings, verify that WSL 2 integration is enabled.

### Issue 4: Python Virtual Environment Path Conflicts
- **Error:** `Activate.ps1 cannot be loaded because running scripts is disabled on this system.`
- **Solution:**
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### Issue 5: Module Import Errors in Backend Tests
- **Solution:** Ensure you execute pytest with the virtual environment Python interpreter:
  ```powershell
  & apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests
  ```

---

*For further architectural questions or schema designs, consult [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md).*
