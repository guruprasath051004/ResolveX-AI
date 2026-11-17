# ResolveX AI – HCLTech Interview Demo Guide

> Comprehensive presentation, architecture breakdown, live demo walkthrough, and Q&A playbook for HCLTech USM & Generative AI interviews.

---

## 1. Business Problem Statement

Enterprise IT support organizations face critical operational bottlenecks:
- **High-volume repetitive tickets:** Routine incidents (Wi-Fi dropouts, VPN certificates, software requests) consume 60-70% of Service Desk capacity.
- **SLA breaches & slow triage:** Manual categorization, tier-1 routing, and runbook searches delay mean time to respond (MTTR).
- **Knowledge fragmentation:** Runbooks and standard operating procedures (SOPs) are scattered across PDFs, Word documents, and wikis.
- **Security risks with unmonitored automation:** Unchecked autonomous tools risk executing unauthorized actions (installing unlicensed software, rebooting production hosts).

**ResolveX AI Solution:**
An autonomous Unified Service Management (USM) platform where employees report issues in natural language. Six coordinated LangGraph agents handle triage, knowledge retrieval (RAG), simulated diagnostics via a dedicated Model Context Protocol (MCP) server, resolution synthesis, and ticket management — backed by human-in-the-loop approval gates for sensitive actions.

---

## 2. USM Architecture

```
┌────────────────────────────────────────────────────────┐
│  Presentation Layer (React 18 + Vite + Tailwind CSS)   │
│  Login │ AI Chat │ Dashboard │ Incidents │ Approvals   │
└───────────────────────────┬────────────────────────────┘
                            │ REST & SSE Streams
┌───────────────────────────▼────────────────────────────┐
│  API & Application Layer (FastAPI + SQLAlchemy 2.x)    │
│  ┌──────────────────────────────────────────────────┐  │
│  │ LangGraph Multi-Agent Swarm (StateGraph)         │  │
│  │ Supervisor Agent (Checkpointed to PostgreSQL)    │  │
│  │ ├─ Triage Agent (Structured JSON Output)         │  │
│  │ ├─ Knowledge Agent (RAG Vector Search)           │  │
│  │ ├─ Diagnostic Agent (registered MCP tools)       │  │
│  │ ├─ Resolution Agent (Evidence-Based Synthesis)   │  │
│  │ └─ Ticket Agent (MCP Tool Lifecycle Management)  │  │
│  └──────────────────┬───────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────┘
                      │ Current client calls: in-process
┌─────────────────────▼──────────────────────────────────┐
│  MCP Server Registry (Official mcp Python SDK)         │
│  10 Tools │ RBAC Evaluation │ Execution Audit Logger   │
└─────────────────────┬──────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────┐
│  Data & Persistence Tier                               │
│  PostgreSQL 16 (Relational) │ ChromaDB (Vector Store)  │
└────────────────────────────────────────────────────────┘
```

---

## 3. Multi-Agent Design

### The 6 LangGraph Agents:
1. **Supervisor Agent:** Coordinates graph transitions, validates triage fields, persists execution summaries, pauses on approval gates, and checkpoints state to PostgreSQL via `PostgresSaver`. Automatic node retries are not implemented.
2. **Triage Agent:** Classifies user intent (`incident` vs. `service_request`), category (`network`, `vpn`, `software`, `server`), and priority (`low`, `medium`, `high`, `critical`) with Pydantic structured output.
3. **Knowledge Agent:** Queries ChromaDB embeddings for runbook excerpts with category filtering and source metadata.
4. **Diagnostic Agent:** Invokes registered MCP tools (`check_network_status`, `check_server_health`, `search_employee_assets`) through the current in-process wrapper.
5. **Resolution Agent:** Builds actionable resolution steps; enforces human approval requirements for sensitive operations.
6. **Ticket Agent:** Manages incident creation, team assignment, and lifecycle status transitions strictly through MCP ticket tools.

---

## 4. MCP Implementation (Model Context Protocol)

- **Official SDK:** Built using the official MCP Python SDK (`MCPServer`). Agent/API calls currently use the in-process server wrapper; the standalone Streamable HTTP app is not used by the current client.
- **10 Registered Tools:**
  1. `create_ticket`
  2. `get_ticket`
  3. `update_ticket`
  4. `check_network_status`
  5. `check_server_health`
  6. `search_employee_assets`
  7. `search_knowledge_base`
  8. `assign_support_team`
  9. `escalate_incident`
  10. `update_incident_status`
- **RBAC & Protocol Audit:** Every tool call evaluates caller role against required privileges and persists an audit row to `mcp_tool_calls` recording input/output summaries, execution duration, and status.
- **Rule 4 Compliance:** All simulated diagnostics carry `"simulated": true` and display a `Simulated` badge in the UI.

---

## 5. RAG Pipeline

- **Vector Store:** ChromaDB persistent client managing collection `resolvex_docs`.
- **Embeddings:** The existing collection uses 384-dimensional zero-vector compatibility embeddings. Chroma distances are not meaningful and the UI reports scores as unavailable; semantic re-embedding remains a separate known gap.
- **Multi-Format Ingestion:** Parsers for `.pdf` (`pdfminer`), `.docx` (`docx2txt`), `.md`, and `.txt`.
- **Chunking Strategy:** 200-word chunks with 50-word overlap tagged with `doc_id`, `title`, `category`, and `chunk_idx`.
- **Admin Management:** Dedicated UI and API endpoints for document upload, category search, deletion, and background re-indexing.

---

## 6. End-to-End Walkthrough (5-Minute Demo Script)

### Step 1: Login & Role Selection (30 seconds)
- Open `http://localhost:3000`.
- Point out the dark navy sidebar and clean modern styling.
- Select **Employee** role (`employee@resolvex.ai`).

### Step 2: Scenario 1 – Network / Portal Issue (1.5 minutes)
- In the Employee AI Chat, click the quick prompt: *"My laptop is connected to Wi-Fi, but the company portal is not opening."*
- **Explain live agent telemetry:**
  - `Triage Agent`: Classified as `incident:network`, priority `high`.
  - `Knowledge Agent`: Retrieved indexed runbook citations. Chroma similarity scores are unavailable for the current zero-vector embedding collection.
  - `Diagnostic Agent`: Called `check_network_status` via MCP (point out **`Simulated`** badge).
  - `Resolution Agent`: Isolated DNS cache issue after Wi-Fi handover; recommended `ipconfig /flushdns`.
  - `Ticket Agent`: Created Ticket `#40`, assigned to `Network Operations`, status `in_progress`.
- Demonstrate the **"Resolved / Not resolved"** confirmation buttons.

### Step 3: Scenario 3 – Software Request & Human Approval (1.5 minutes)
- Send prompt: *"I need Python installed on my company laptop."*
- **Explain sensitive action safety net:**
  - Triage classifies as `service_request:software`.
  - Diagnostic calls `search_employee_assets` to identify user hardware.
  - Resolution Agent flags sensitive software provisioning $\rightarrow$ generates **PENDING Approval Workflow**.
  - Supervisor pauses the LangGraph workflow and saves state checkpoint to PostgreSQL.
- **Switch to Support Engineer:**
  - Log out $\rightarrow$ Log in as **Support Engineer** (`support@resolvex.ai`).
  - Navigate to **Pending Approvals** page.
  - Click **Approve**. Show the status change and audit log entry.
  - Show how the workflow resumes and updates the ticket.

### Step 4: Scenario 4 – Production Outage & Escalation (1 minute)
- Send prompt: *"The production application is unavailable."*
- Show critical priority (`P1`), `check_server_health` tool execution, automated escalation to `Platform Infrastructure`, and instant reflection in the **USM Dashboard**.

### Step 5: Dashboard & MCP Monitor (30 seconds)
- Navigate to **USM Dashboard**: show that all 8 KPIs, priority distribution, and trends are real-time SQL aggregates over database rows.
- Navigate to **MCP Server Monitor**: show the live execution audit log from `mcp_tool_calls` with latencies and permission checks.

---

## 7. Security and Human Approval (Rule 8)

1. **Principle of Least Privilege:** RBAC enforced at API endpoint level and inside every MCP tool executor.
2. **Deterministic Approval Barrier:** Sensitive operations (software installation, account access, password resets, server restarts, team escalations) cannot be auto-executed by agents.
3. **Audit Trail:** Every approval decision records reviewer ID, timestamp, and action description in `audit_logs`.
4. **Resumable Checkpoints:** LangGraph state machine pauses cleanly at the approval boundary and resumes execution using thread checkpoints persisted to PostgreSQL.

---

## 8. Technical Challenges & Solutions

| Technical Challenge | Root Cause | Engineering Solution |
|---------------------|------------|----------------------|
| **MCP transport boundary** | The current agent/API client invokes the registered server in-process. | The monitor labels the transport `in_process`; the standalone Streamable HTTP endpoint is not presented as a live connection. |
| **Windows Sandbox Socket Restrictions** | Windows sandbox environment restricts socket pair IPC and asyncio TCP binding. | Separated test execution: standard unit tests run sandboxed, while socket-bound integration runs with network permissions. |
| **Database Portability** | Support PostgreSQL 16 for production containerization while enabling zero-config local development. | Dual-engine database abstraction in `backend/database/__init__.py` connecting to PostgreSQL with fallback to SQLite. |
| **Agent State Pause & Resume** | Standard memory checkpointer loses thread state if the server process restarts during pending approval. | Implemented `PostgresSaver` subclassing `MemorySaver` that serializes and commits thread checkpoints to PostgreSQL table `agent_checkpoints`. |
| **Deterministic Demo Mode Without Keys** | Interview demonstrations need to run offline without external API keys or rate-limit concerns. | Implemented rule-based demo mode in `backend/agents/llm.py` labeled explicitly with `[DEMO MODE: simulated]`. |

---

## 9. Likely Interviewer Questions & High-Impact Answers

### Architecture & Design
**Q: Why LangGraph over AutoGen or CrewAI?**
> *Answer:* LangGraph provides deterministic, cyclic state graph orchestration with strictly typed shared state (`AgentState`), built-in checkpointing for pause-and-resume workflows, and fine-grained supervisor routing. Unlike free-form multi-agent frameworks, LangGraph prevents uncontrolled conversational loops and produces auditable, reproducible workflows.

**Q: What is the benefit of Model Context Protocol (MCP) in USM?**
> *Answer:* MCP standardizes tool discovery and schema validation. In this implementation, agent/API calls use an in-process server wrapper and persist tool-call audit rows; the standalone Streamable HTTP endpoint is not currently used, so I would not claim process isolation or a live remote connection.

### RAG & Retrieval
**Q: How do you prevent hallucinations in resolution proposals?**
> *Answer:* The Knowledge Agent applies category filtering and returns source citations. The existing vectors are zero vectors, so Chroma distances are not meaningful; retrieval scores are reported unavailable for those results. The admin evaluation view exposes actual returned chunks and measured latency. Semantic embedding quality is a known gap.

### Production Readiness
**Q: How would you scale this architecture to enterprise volume?**
> *Answer:*
> 1. Switch LLM provider wrapper to Claude 3.5 Sonnet or Gemini 1.5 Pro with fallback routing.
> 2. Decouple agent graph execution using Celery or Temporal message queues for horizontal worker scaling.
> 3. Use PostgreSQL read replicas and connection pooling (PgBouncer).
> 4. Stream real-time agent updates to frontend clients via Server-Sent Events (SSE).

