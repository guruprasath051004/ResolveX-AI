# ResolveX AI – Testing Strategy & Test Guide

> Verification methodology, test suites, execution commands, and gate criteria.

---

## 1. Test Strategy Overview

ResolveX AI enforces a multi-tiered testing strategy ensuring each layer passes strict verification gates before integration:

```
┌────────────────────────────────────────────────────────┐
│  Tier 4: End-to-End Smoke Acceptance (4 Scenarios)     │
│  test_e2e_smoke.py                                     │
├────────────────────────────────────────────────────────┤
│  Tier 3: Frontend Component & Page Tests               │
│  Vitest + React Testing Library (including metrics/SLA) │
├────────────────────────────────────────────────────────┤
│  Tier 2: Auth, DB, Agents, MCP, Employee & Support   │
│  test_auth.py, test_database.py, portal and agent tests│
├────────────────────────────────────────────────────────┤
│  Tier 1: Knowledge & RAG Retrieval Tests               │
│  test_rag.py (isolated temporary Chroma collection)    │
└────────────────────────────────────────────────────────┘
```

---

## 2. Running Test Suites

### Complete Backend Test Suite
Runs all unit, integration, and E2E acceptance tests via `pytest`:
```bash
.\.venv311\Scripts\python.exe -m pytest backend\tests -q
```

### End-to-End Acceptance Smoke Suite
Validates the 4 core portfolio acceptance scenarios through the FastAPI `TestClient`:
```bash
.\.venv311\Scripts\python.exe -m pytest backend\tests\test_e2e_smoke.py -v
```

**Tested Scenarios:**
1. **Scenario 1:** Wi-Fi / Company Portal Connectivity (network incident, diagnostic tool, in-progress status)
2. **Scenario 2:** Corporate VPN Failure (VPN incident, diagnostic verification, resolution guidance)
3. **Scenario 3:** Software Installation Service Request (sensitive action, pending approval, approved checkpoint resume)
4. **Scenario 4:** Production Outage (critical priority, server health diagnostic)
5. **Database Integrity:** SQL verification of `agent_runs`, `agent_steps`, `agent_checkpoints`, `incidents`, `approvals`, `mcp_tool_calls`, and `/api/stats/dashboard`.

### Multi-Agent Pipeline Suite
Validates agent state graph transitions, SSE event streaming, and checkpoint resume:
```bash
.\.venv311\Scripts\python.exe -m pytest backend\tests\test_agents.py -v
```

### Authentication, Database, and Cross-Role Tests
Validates JWT login, configured expiration and expired-token rejection, logout revocation and audit logging, role-based endpoint access, shared session/database usage, SQLite foreign-key enforcement, employee data isolation, and cross-role incident/approval visibility:
```bash
.\.venv311\Scripts\python.exe -m pytest backend\tests\test_auth.py backend\tests\test_database.py backend\tests\test_employee_portal.py -v
```

### MCP Tool Protocol Suite
Validates MCP server tool registry (10 tools), RBAC permission gates, DB mutations, and simulated diagnostic flags:
```bash
.\.venv311\Scripts\python.exe -m pytest backend\tests\test_mcp.py -v
```

### Support Workspace Suite
Validates incident assignment, verified resolution, read-only investigation, SQL-backed dashboard and operational-insight metrics, date filtering, response/resolution SLA calculations and history, role authorization, approval-gated escalation, and incident audit context:
```bash
.\.venv311\Scripts\python.exe -m pytest backend\tests\test_support_workspace.py -v
```

The agent approval test also verifies that a pending approval cannot be bypassed through the workflow-resume endpoint.

### Frontend Tests (Vitest)
Validates employee dashboard rendering, administrator metrics/SLA integration and errors, role navigation, login UI, and app smoke behavior:
```bash
cd frontend
npm test
```

---

## 3. Phase Gate Test Results Summary

Validated with Python **3.11.9** in the project-local `.venv311` environment. `pip check` reported no broken requirements.

| Phase | Test Suite / Command | Total Tests | Result |
|---|---|---|---|
| **Backend** | `.\.venv311\Scripts\python.exe -m pytest backend\tests -q` | 79 tests | ✅ PASSED (10 ChromaDB legacy embedding configuration deprecation warnings) |
| **Auth / DB / cross-role** | `.\.venv311\Scripts\python.exe -m pytest backend\tests\test_auth.py backend\tests\test_database.py backend\tests\test_employee_portal.py -q` | 29 tests | ✅ PASSED |
| **Frontend** | `cd frontend; npm test` | 20 tests | ✅ PASSED |
| **Production build** | `cd frontend; npm run build` | TypeScript + Vite | ✅ PASSED (902.36 kB minified JS chunk advisory) |
| **Database migration** | `.\.venv311\Scripts\python.exe -m alembic upgrade head` / `current` | Revision `0004_auth_session_revocation` | ✅ APPLIED; verified at head |
| **Live PostgreSQL RBAC** | Python 3.11 `TestClient` login and role checks | 3 roles | ✅ PASSED; employee/support denied admin knowledge access, admin allowed; support/admin incident counts matched |
| **Phase 2 live metrics/SLA** | Local PostgreSQL-backed API, administrator login | 5 endpoints | ✅ PASSED; dashboard, insights, policies, trends, and SLA risks returned 200; P1–P4 and 30 UTC trend days verified |
| **Phase 2 API authorization** | `test_support_workspace.py` metrics/SLA role checks | Employee / Support / Administrator | ✅ PASSED; employee denied protected metrics/SLA endpoints; permitted support and administrator access retained |

### Phase 2 UI Evidence

- [Administrator dashboard](./screenshots/phase2-administrator-dashboard.png)
- [Administrator dashboard analytics](./screenshots/phase2-administrator-dashboard-analytics.png)
- [SLA compliance page](./screenshots/phase2-sla-compliance.png)

---

## 4. Test Environment Troubleshooting

- **Database configuration:** Set `DATABASE_URL` to a reachable PostgreSQL database for local runs. SQLite is used only when `DATABASE_URL` explicitly names a SQLite URL (as the test configuration does); database connection failures are reported at startup.
- **Async Socket Sandbox Execution:** Any test executing an asyncio event loop with socket transport requires execution with network bypass privileges.
- **ChromaDB File Lock on Windows:** `test_rag.py` uses a temporary persistent directory and runs ingestion/query in separate processes so it does not delete or lock the application's `./chroma_data`. For local indexing, keep only one process writing to the same Chroma directory at a time.

