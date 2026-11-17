# ResolveX AI – Interview Kit

> Talking points, demo script, and prepared Q&A for the HCLTech USM & Generative AI interview.

---

## 1. Business Problem Statement

**Problem:** Enterprise IT support teams are overwhelmed by repetitive, high-volume incidents. Manual triage, knowledge lookup, and diagnostics slow resolution, breach SLAs, and frustrate employees.

**Solution:** ResolveX AI is an autonomous Unified Service Management (USM) platform where employees report IT issues in natural language. Six specialized AI agents autonomously triage, research, diagnose, resolve, and manage tickets — with human-in-the-loop approval for sensitive actions.

**Value proposition:**
- **80%+ automation rate** for routine incidents (password resets, connectivity, software requests)
- **Sub-second triage** with LLM-powered classification
- **Evidence-based resolution** using RAG over internal runbooks
- **Full auditability** — every agent decision, MCP tool call, and approval is logged
- **Human safety net** — sensitive actions (software install, server restart, account access) require explicit approval

---

## 2. Architecture Highlights

### Multi-Agent Design (LangGraph)
- **6 agents** with typed shared state: Triage → Knowledge → Diagnostic → Resolution → Ticket, orchestrated by a Supervisor
- Each agent has a single responsibility, producing short decision summaries (never raw chain-of-thought)
- State is checkpointed to Postgres for crash recovery

### MCP Server (Model Context Protocol)
- **10 tools** with JSON-schema validated inputs, RBAC permission checks, and execution logging
- Current agent/API calls use the registered server **in-process**; the standalone Streamable HTTP endpoint is not used by this client
- Every tool call is logged to `mcp_tool_calls` with timing, input/output summaries, and permission status

### RAG Pipeline
- **ChromaDB** vector store; existing vectors are 384-dimensional zero-vector compatibility embeddings, so Chroma distances are not meaningful relevance scores
- Ingests PDF, DOCX, TXT, MD runbooks with metadata (doc_id, title, category, chunk_idx)
- Retrieval evaluation shows actual chunks, citations, measured latency, and score availability

### Security & RBAC
- Password-verified login with a selected role and 3 demo roles: Employee, Support Engineer, Administrator
- API-level JWT/RBAC dependencies protect role-specific routes
- MCP tool permission checks and searchable, redacted call audit records are available
- Sensitive actions create PENDING approvals — execution only after human approval
- Audit log on every mutating action

---

## 3. Live Demo Script (5 minutes)

### Setup
1. Open browser to `http://localhost:3000`
2. Show the Login page — click **Employee** role

### Scenario 1: Network Issue (2 min)
1. In AI Chat, type: _"My laptop is connected to Wi-Fi, but the company portal is not opening."_
2. **Point out as it runs:**
   - Triage agent classifies → network, P2
   - Knowledge agent retrieves network connectivity runbook (show source citation)
   - Diagnostic agent calls `check_network_status` via MCP (show **Simulated** badge)
   - Resolution agent proposes fix based on evidence
   - Ticket agent creates incident with ID
3. Navigate to **Incidents Queue** → show the new incident
4. Navigate to **MCP Monitor** → show the logged tool call with timing
5. Navigate to **Agent Command Center** → show the React Flow graph and agent trace

### Scenario 2: Software Install with Approval (2 min)
1. New chat: _"I need Python installed on my company laptop."_
2. **Point out:**
   - Classified as service request
   - `search_employee_assets` called — shows the employee's laptop
   - Resolution detects sensitive action → creates PENDING approval
   - Chat shows "Awaiting approval" notice
3. Switch to **Support Engineer** role (logout → login)
4. Go to **Approvals** → Approve the request
5. Show the ticket status update

### Scenario 3: Critical Outage (1 min)
1. Login as Employee → _"The production application is unavailable."_
2. **Point out:**
   - P1 critical priority assigned
   - `check_server_health` called
   - Team assigned, escalation triggered
   - Dashboard updates in real-time

### Wrap-up
1. Show **Dashboard** — all metrics are SQL aggregates, not static
2. Show **Knowledge Base** admin — upload/delete/reindex
3. Show **SLA Compliance** page

---

## 4. Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| LangGraph over CrewAI/AutoGen | Typed state graph with checkpointing; deterministic routing; no agent "chatting" overhead |
| MCP over direct function calls | MCP schemas and permission checks are retained; current transport is in-process, so process isolation is not claimed |
| ChromaDB over Pinecone/Weaviate | Local, zero-config, sufficient for portfolio scale; swappable via interface |
| Current MCP transport | In-process wrapper; the standalone Streamable HTTP client integration remains a known gap |
| Demo mode with `simulated: true` | Interviewer can run the full pipeline without API keys; clearly labeled |
| RBAC at MCP tool level | Defense-in-depth; even if API is bypassed, tools enforce permissions |

---

## 5. Likely Interviewer Questions & Answers

### Architecture & Design

**Q: Why six agents instead of one?**
> Single-responsibility principle applied to AI. Each agent has a focused task with a clear input/output contract. This makes the system testable, debuggable, and extensible. Adding a new capability (e.g., change management) means adding one agent, not rewriting the whole pipeline.

**Q: How do you handle agent failures?**
> The Supervisor validates triage fields. Node starts, completions, and failures are persisted with measured durations and short summaries; handled diagnostic errors are marked as failed steps. Checkpointing supports approval resume.

**Q: Why MCP instead of direct function calls?**
> MCP is an open standard for tool use. This project uses its registered tool definitions and permission checks, and persists call records with timing and outcomes. The current agent/API client invokes the server in-process; process isolation and a live remote Streamable HTTP connection are not currently present.

### RAG & Knowledge

**Q: How do you ensure RAG quality?**
> Documents are chunked with metadata and retrieved through Chroma plus a labeled lexical fallback. The existing Chroma vectors are all-zero, so they cannot provide meaningful semantic ranking; the admin evaluation view reports scores unavailable for those results and shows citations and chunks for verification. The page supports upload, duplicate detection, preview, versions, chunk inspection, and reindex.

**Q: What if the knowledge base doesn't have the answer?**
> The existing zero-vector Chroma collection does not provide meaningful similarity scores. The admin evaluation view reports that limitation explicitly; retrieval can fall back to lexical overlap with its method labeled. Semantic relevance evaluation remains a known gap.

### Security & Compliance

**Q: How do you handle sensitive actions?**
> Rule 8 of our design: any sensitive action (software install, account access, password reset, server restart, escalation) creates a PENDING approval record. The Resolution agent does NOT execute it. A Support Engineer or Admin must explicitly approve it through the Approvals page. Only then does the action execute. Every approval/rejection is logged.

**Q: How is data secured?**
> Secrets are configured through environment variables, passwords are bcrypt-hashed, and the API enforces JWT/RBAC. Agent, MCP, approval, and knowledge operations are audited in their respective persisted records; a tamper-evident audit chain is not currently implemented.

### Production Readiness

**Q: What would you change for production?**
> 1. Replace demo LLM with a real provider (Anthropic/OpenAI/Gemini — the wrapper is ready)
> 2. Add real infrastructure diagnostics (replace simulated tools with actual monitoring APIs)
> 3. Add SSE/WebSocket for true live streaming of agent progress
> 4. Add rate limiting, request tracing (OpenTelemetry), and proper logging (structured JSON)
> 5. Horizontal scaling: stateless backend behind a load balancer, Postgres read replicas
> 6. CI/CD pipeline with automated testing gates

**Q: How would you scale the agent pipeline?**
> LangGraph supports async execution. For high throughput: (1) run each agent invocation as a Celery/Temporal task, (2) use Postgres-backed checkpointing for crash recovery, (3) add a queue (Redis/RabbitMQ) between the API and the Supervisor, (4) scale agent workers horizontally.

### HCLTech USM Specific

**Q: How does this align with HCLTech's USM vision?**
> ResolveX demonstrates the core USM pillars: unified incident and service request management, SLA-driven resolution, knowledge-centered support, and asset-aware diagnostics — all automated by Generative AI. The multi-agent architecture mirrors how a real L1→L2→L3 support organization works, but with AI doing the heavy lifting and humans approving critical decisions.

**Q: What ITIL processes does this cover?**
> Incident Management (full lifecycle), Service Request Fulfillment (with approval workflows), Knowledge Management (RAG-powered), Asset & Configuration Management (CMDB), and SLA Management. The architecture is extensible to Change Management and Problem Management.

---

## 6. Technical Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| MCP SDK v2.x breaking changes | Migrated from `FastMCP` to `MCPServer`, `httpx` to `httpx2` |
| Sandbox restrictions on sockets | Separated tests into sandboxed (unit) and bypass (integration) |
| PostgreSQL ↔ SQLite compatibility | Explicit URL-selected dialects; Alembic migrations manage the schema in all environments |
| Agent state consistency | TypedDict with strict schema validation at each agent boundary |
| Demo mode without API keys | Deterministic demo LLM with `[DEMO MODE: simulated]` labels |
| All diagnostics simulated | Every tool result carries `simulated: true`; UI shows Simulated badge |

---

## 7. Metrics to Quote

- **10 MCP tools** with RBAC, logging, and schema validation
- **6 LangGraph agents** with typed state and checkpointing
- **9+ knowledge documents** indexed in ChromaDB
- **4 acceptance scenarios** passing end-to-end
- **10 UI pages** — zero dead buttons or placeholder content
- **3 RBAC roles** with seeded demo users
- **Full audit trail** — every agent step, MCP call, and approval decision logged

