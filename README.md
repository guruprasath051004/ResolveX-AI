# ResolveX AI

**Autonomous Unified Service Management (USM) Platform**

> Six LangGraph agents triage, retrieve knowledge, run simulated diagnostics, recommend resolutions, and manage IT incidents — with human approval for sensitive operations.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites & Environment Configuration](#prerequisites--environment-configuration)
3. [Database Migrations & Demo Seeding](#database-migrations--demo-seeding)
4. [Knowledge Base Document Ingestion (RAG)](#knowledge-base-document-ingestion-rag)
5. [Starting the Platform Services](#starting-the-platform-services)
6. [Docker Compose (Single Command Start)](#docker-compose-single-command-start)
7. [Demo Roles & Credentials](#demo-roles--credentials)
8. [Acceptance Scenarios Walkthrough](#acceptance-scenarios-walkthrough)
9. [Running Test Suites](#running-test-suites)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Platform Screenshots](#platform-screenshots)
12. [Documentation Index](#documentation-index)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (React 18 + TypeScript + Vite + Tailwind CSS)     │
│  Login │ AI Chat │ Dashboard │ Incidents │ Approvals │ ...   │
└───────────────────────┬──────────────────────────────────────┘
                        │ REST API & SSE Streams
┌───────────────────────▼──────────────────────────────────────┐
│  Backend (FastAPI + SQLAlchemy 2.x + JWT authentication/RBAC)│
│  ┌─────────────────────────────────────────────────────┐     │
│  │  LangGraph Multi-Agent Workflow (Supervisor)        │     │
│  │  Triage → Knowledge → Diagnostic → Resolution → Ticket│    │
│  └────┬──────────┬───────────────────────────────────────┘    │
│       │          │                                            │
│  ┌────▼───┐ ┌────▼──────────────────────────────────┐        │
│  │ChromaDB│ │ In-process MCP tool client/registry   │        │
│  │  (RAG) │ │ Role checks · DB call audit records  │        │
│  └────────┘ └───────────────────────────────────────┘        │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│  PostgreSQL 16 (Relational Database)                         │
└──────────────────────────────────────────────────────────────┘
```

---

## Prerequisites & Environment Configuration

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 16 (or Docker)

### Environment Configuration (`.env`)
If you do not already have a `.env` file, create one:
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
If `.env` already exists, merge the missing variable names from `.env.example` without replacing your existing values. Compose requires the `POSTGRES_*`, `JWT_SECRET_KEY`, and `DEMO_*_PASSWORD` variables.

| Key | Description | Default |
|-----|-------------|---------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | PostgreSQL credentials and database name | Set in `.env` |
| `DATABASE_URL` | PostgreSQL connection string for local backend processes | Set in `.env` |
| `JWT_SECRET_KEY` | JWT signing key | Set a unique value in `.env` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | `60` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated browser origins permitted to call the API | Local Vite origins |
| `DEMO_*_PASSWORD` | Password for each demo role account | Set in `.env` |
| `LLM_PROVIDER` | LLM engine (`demo`, `anthropic`, `openai`, `gemini`) | `demo` |
| `MCP_SERVER_URL` | Reserved for the separate MCP transport integration; the current backend client does not use it | `http://localhost:8001` |
| `CHROMA_PERSIST_DIR` | ChromaDB vector store directory | `./chroma_data` |

---

## Database Migrations & Demo Seeding

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Apply Alembic migrations:**
   ```bash
   alembic upgrade head
   ```

3. **Demo role accounts:** Demo users are created at backend startup. Configure their passwords with the `DEMO_*_PASSWORD` variables in `.env`.

---

## Knowledge Base Document Ingestion (RAG)

Ingest runbooks into ChromaDB (`resolvex_docs` collection) from `./documents/`:
```bash
python -m backend.rag.ingest --source ./documents --collection resolvex_docs
```
Supported formats: `.md`, `.pdf`, `.docx`, `.txt`.

---

## Starting the Platform Services

Before starting the application services, make sure PostgreSQL is running and apply the schema:
```bash
python -m alembic upgrade head
```

### Terminal 1: FastAPI Backend (Port 8000)
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --env-file .env --reload
```

### Terminal 2: React Frontend (Port 3000)
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser.

---

## Docker Compose (Single Command Start)

Build and run all 5 microservices in isolated containers:
```bash
docker compose up --build
```

| Service | Port | Description |
|---------|------|-------------|
| `frontend` | 3000 | React SPA served via Nginx |
| `backend` | 8000 | FastAPI REST API and SSE streaming |
| `mcp-server` | 8001 | Standalone Model Context Protocol server |
| `postgres` | 5432 | PostgreSQL 16 database |
| `chroma` | 8100 | ChromaDB vector database |

---

## Demo Roles & Credentials

Select a role on the login screen, then use the matching account email and password configured in `.env`:

| Role | Email | Access Capabilities |
|------|-------|----------------------|
| **Employee** | `employee@resolvex.ai` | Employee AI chat, report issues, view ticket status |
| **Support Engineer** | `support@resolvex.ai` | Triage inspection, diagnostic review, pending approvals |
| **Administrator** | `admin@resolvex.ai` | Full access, CMDB asset management, knowledge admin |

Use the configured passwords in `.env` for each demo account. If `.env` already existed, merge the required variables from `.env.example` rather than overwriting it.
Login returns a short-lived access token. Protected API routes enforce role permissions, and employee portal routes scope records to the authenticated user. The browser keeps the token in memory for the active session.

The login opens a role-specific panel: employees land on their database-backed dashboard with AI Support, ticket history, service requests, approvals, notifications, profile, and assigned assets; support engineers get a database-backed operations dashboard, filterable incident queue, assignment/resolution controls, read-only AI investigation, MCP tool execution, approvals, SLA risk, and per-incident audit history; administrators get the Administrator Dashboard and knowledge administration.

Employee catalog submissions create rows in the shared service-request and approval tables. Approval decisions, ticket updates, comments, and employee profile changes are audited and generate notifications where applicable.

**Known employee-portal limitations:** AI chat continues the active conversation thread in the browser, but the workflow does not yet ask dynamic clarification questions. SLA deadlines are displayed when a matching policy is configured; there is no background SLA alert/escalation worker. Announcements can be created through the admin API; there is no announcements management page.

**Known support-workspace limitations:** The backend MCP client currently invokes the registered tool server in-process; the separate Streamable HTTP endpoint is not wired into agent/API calls. Infrastructure diagnostics are simulated and labelled. The investigation workflow is read-only for incident lifecycle changes; recommendations require an engineer to apply/verify them. Escalations are queued for administrator approval, but no background SLA escalation worker is configured. Agent-linked resolution metrics do not prove autonomous resolution.

---

## Acceptance Scenarios Walkthrough

1. **Wi-Fi / Company Portal Connectivity:**
   - *Message:* `"My laptop is connected to Wi-Fi, but the company portal is not opening."`
   - *Result:* Triage classifies as `network`, retrieves connectivity runbook, runs `check_network_status` MCP diagnostic (Simulated badge), and sets ticket status to `in_progress`.
2. **Corporate VPN Failure:**
   - *Message:* `"I cannot connect to the corporate VPN."`
   - *Result:* Triage classifies as `vpn`, retrieves VPN runbook, checks network status, and returns certificate renewal guidance.
3. **Software Installation Request (Approval Workflow):**
   - *Message:* `"I need Python installed on my company laptop."`
   - *Result:* Triage classifies as `service_request:software`, searches employee assets, flags sensitive action, registers a `PENDING` approval, pauses workflow checkpoint, and waits for Support Engineer authorization.
4. **Production Outage (Critical Escalation):**
   - *Message:* `"The production application is unavailable."`
   - *Result:* Critical `P1` priority assigned and server health checked through the simulated diagnostic tool. An engineer must request escalation; execution waits for administrator approval.

---

## Running Test Suites

```bash
# 1. Full Backend Test Suite (pytest)
python -m pytest backend/tests/ -v

# 2. End-to-End Acceptance Smoke Test (All 4 scenarios + DB integrity)
python -m pytest backend/tests/test_e2e_smoke.py -v

# 3. Frontend Unit & Smoke Tests (Vitest)
cd frontend && npm test

# 4. Interactive Page Walkthrough Verification
python frontend/src/test/verify_all_pages.py
```

---

## Troubleshooting Guide

1. **PostgreSQL Connection Error:**
   - *Symptom:* `psycopg2.OperationalError: could not connect to server`.
   - *Fix:* Ensure PostgreSQL is running and `DATABASE_URL` matches the database settings in `.env`. The backend fails at startup instead of silently switching databases.
2. **MCP tools unavailable:**
   - *Symptom:* The in-process MCP tool registry cannot list or execute tools.
   - *Fix:* Check backend logs and database availability. The current backend client does not connect to `MCP_SERVER_URL`.
3. **ChromaDB File Lock on Windows:**
   - *Symptom:* `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
   - *Fix:* Avoid running multiple concurrent test suites accessing `./chroma_data` at the same instant.
4. **Frontend API Proxy Error:**
   - *Symptom:* Network calls to `http://localhost:8000/api` fail.
   - *Fix:* Ensure the FastAPI backend is running and CORS is enabled (enabled by default in `backend/main.py`).

---

## Platform Screenshots

The screenshot capture script automatically generates full-page previews:
```bash
pip install playwright && playwright install chromium
python scripts/capture_screenshots.py --url http://localhost:3000 --output docs/screenshots/
```

| Screenshot File | Page Name | Description |
|-----------------|-----------|-------------|
| `docs/screenshots/01_login_page.png` | **Login Page** | Role selection cards (Employee, Support Engineer, Admin) |
| `docs/screenshots/02_employee_chat.png` | **Employee AI Chat** | Multi-agent trace cards, RAG citations, MCP diagnostics (Simulated badge), feedback buttons |
| `docs/screenshots/03_usm_dashboard.png` | **USM Dashboard** | 8 SQL aggregate KPIs, Recharts volume trend, priority distribution, category breakdown |
| `docs/screenshots/04_incidents_queue.png` | **Incident Operations** | Filterable incident queue, assignment, investigation, resolution checks, and audit history |
| `docs/screenshots/05_pending_approvals.png` | **Approval Review** | Request context, reviewer comments, approval decision, and execution result |
| `docs/screenshots/06_agent_command_center.png` | **Agent Command Center** | Workflow map and persisted execution steps |
| `docs/screenshots/07_mcp_monitor.png` | **MCP Tool Monitor** | In-process tool registry and persisted call audit log |
| `docs/screenshots/08_sla_compliance.png` | **SLA Compliance** | Configured policy targets and timestamp-derived risk/compliance records |
| `docs/screenshots/09_asset_cmdb.png` | **Asset CMDB** | Hardware asset inventory, serial numbers, assignments, and device health |
| `docs/screenshots/10_knowledge_base.png` | **Knowledge Base Admin** | Runbook document library, category filters, upload, delete, and re-indexing |

---

## Documentation Index

- [Architecture & Diagrams (`docs/ARCHITECTURE.md`)](docs/ARCHITECTURE.md)
- [API Reference Specification (`docs/API.md`)](docs/API.md)
- [Testing Strategy & Test Suites (`docs/TESTING.md`)](docs/TESTING.md)
- [HCLTech Interview Demo Guide (`docs/INTERVIEW_DEMO.md`)](docs/INTERVIEW_DEMO.md)
- [Design Contracts & Rules (`docs/CONTRACTS.md`)](docs/CONTRACTS.md)
