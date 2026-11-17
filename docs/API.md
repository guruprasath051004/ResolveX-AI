# ResolveX AI – API Reference Specification

Base URL: `http://localhost:8000`

---

## 1. Authentication & RBAC (`/api/auth`)

### `POST /api/auth/login`
Authenticates an account and verifies that the requested role matches the account. The returned access token is required for protected endpoints.

- **Request Body:**
  ```json
  {
    "email": "employee@resolvex.ai",
    "password": "<employee password configured in .env>",
    "role": "employee"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "id": 1,
    "email": "employee@resolvex.ai",
    "role": "employee",
    "access_token": "<JWT access token>"
  }
  ```
- Invalid credentials or a role mismatch return `401`; missing or invalid fields return `422`.
- In demo mode, the three documented demo users are seeded at backend startup.
- Access tokens expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60; maximum 1440 minutes). No refresh token is issued; users reauthenticate after expiration.
- Send the token on protected routes as `Authorization: Bearer <access_token>`. `/api/auth/me` derives the account from this token; a client-supplied user ID is not used.
- `POST /api/auth/logout` revokes all access tokens for the authenticated account, writes an audit record, and requires reauthentication.

## 2. Employee Portal (`/api/employee`)

All employee endpoints require an employee access token and scope records to the authenticated account.

| Method and path | Purpose |
|---|---|
| `GET /api/employee/dashboard` | Profile, SQL-backed ticket counts, recent activity, announcements, assigned assets, service usage, recommendations, and approvals |
| `GET /api/employee/tickets?status=&search=` | Search/filter the employee's incidents and service requests |
| `GET /api/employee/tickets/{ticket_id}` | Owned ticket details, SLA fields, resolution notes, and conversation history |
| `POST /api/employee/tickets/{ticket_id}/comments` | Add an employee comment to an owned ticket |
| `POST /api/employee/tickets/{ticket_id}/reopen` | Reopen an owned resolved ticket |
| `POST /api/employee/tickets/{ticket_id}/feedback` | Record whether an owned issue is resolved |
| `GET /api/employee/service-requests` | List the employee's service requests |
| `POST /api/employee/service-requests` | Submit a validated catalog request; sensitive categories create a linked pending approval |
| `GET /api/employee/approvals` | View approval decisions and their requested action |
| `GET /api/employee/profile` / `PATCH /api/employee/profile` | Read profile or update permitted name and phone fields |
| `GET /api/employee/assets` | List assets assigned to the employee |
| `GET /api/employee/notifications` | List notifications for the employee |
| `POST /api/employee/notifications/{notification_id}/read` | Mark an owned notification as read |
| `GET /api/employee/announcements` | List active announcements |

`POST /api/admin/announcements/` and `/admin/knowledge/*` are administrator-only. Support engineers and administrators can update service-request status/team/notes and add support comments through `/api/service_requests/{id}`; those changes notify the requester and are audited. The support-side `POST /api/service_requests/` derives the requester from the access token, rejects client-supplied ownership fields, and links sensitive request types to a pending record in the shared approvals table. Approval decisions are support/admin-only under `/api/approvals/{id}/approve` and `/reject`.

---

## 3. Multi-Agent System (`/api/agent`)

### `POST /api/agent/run`
Executes the full 6-agent LangGraph workflow (`Triage → Knowledge → Diagnostic → Resolution → Ticket`).

- **Request Body:**
  ```json
  {
    "message": "My laptop is connected to Wi-Fi, but the company portal is not opening.",
    "thread_id": "optional_thread_identifier"
  }
  ```
- The backend derives the employee ID and demo/live provider mode from the authenticated user and server configuration. Unknown request fields are rejected.
- **Response (`200 OK`):**
  ```json
  {
    "incident_id": 40,
    "employee_id": 1,
    "user_message": "My laptop is connected to Wi-Fi, but the company portal is not opening.",
    "intent": "incident",
    "category": "network",
    "priority": "high",
    "retrieved_chunks": [
      {
        "doc": "Network Connectivity",
        "chunk": "Runbook excerpt...",
        "score": 0.88,
        "category": "network"
      }
    ],
    "diagnostics": [
      {
        "tool": "check_network_status",
        "result": { "status": "online", "latency_ms": 14 },
        "simulated": true
      }
    ],
    "proposed_resolution": "[DEMO MODE: simulated] Diagnostics confirm...",
    "requires_approval": false,
    "approval_id": null,
    "ticket_status": "in_progress",
    "agent_trace": [
      {
        "agent": "Triage Agent",
        "summary": "Classified intent as 'incident'...",
        "started_at": "2026-11-13T12:00:00Z",
        "duration_ms": 1,
        "status": "completed"
      }
    ],
    "errors": [],
    "is_demo": true,
    "thread_id": "thread_1794573339277"
  }
  ```

### `GET /api/agent/stream` / `POST /api/agent/stream`
Streams workflow execution events in real-time using Server-Sent Events (`text/event-stream`).

- **Query Parameters (GET):**
  - `message`: IT request text
- **Event Lifecycle Stream:**
  ```http
  HTTP/1.1 200 OK
  Content-Type: text/event-stream

  event: workflow_start
  data: {"thread_id": "thread_sse_123", "message": "Portal issue"}

  event: step_completed
  data: {"node": "triage", "output": {"intent": "incident", "category": "network"}}

  event: workflow_complete
  data: {"incident_id": 40, "ticket_status": "in_progress", ...}
  ```

### `POST /api/agent/resume/{thread_id}`
Resumes an approval-linked workflow using its stored thread.

- **Request Body:**
  ```json
  {
    "approved": true
  }
  ```
- The reviewer identity is derived from the support/admin access token.
- **Response (`200 OK`):**
  ```json
  {
    "status": "resumed",
    "thread_id": "thread_1794573340200",
    "approved": true,
    "ticket_status": "in_progress",
    "agent_trace": [...]
  }
  ```

### `GET /api/agent/runs`
Support Engineer/Admin only. Lists persisted execution runs with status, sanitized summaries, real step start/duration/status, retry count, and pagination (`limit` 1–200, `offset`). Optional `status` and `incident_id` filters are supported. Node records are written as each node starts and finishes; approval pauses are represented as `waiting`. The graph does not currently retry nodes, so recorded retry counts remain zero.

- **Response (`200 OK`):**
  ```json
  [
    {
      "run_id": 1,
      "agent_name": "ResolveX USM Multi-Agent System",
      "incident_id": 40,
      "thread_id": "thread_1794573339277",
      "status": "completed",
      "started_at": "2026-11-13T12:00:00Z",
      "finished_at": "2026-11-13T12:00:01Z",
      "steps": [
        { "step_id": 1, "step_name": "Triage Agent", "status": "completed", "summary": "Classified the report.", "duration_ms": 1 }
      ]
    }
  ]
  ```

### `GET /api/agent/runs/metrics`
Support Engineer/Admin only. Returns SQL aggregates for run status and per-agent execution, failure, and average duration counts.

### `GET /api/agent/runs/{run_id}`
Support Engineer/Admin only. Returns sanitized input/output summaries, decision summaries, retrieved-document citation references, actual MCP call records, status/error details, and execution outcome. The current pipeline does not record token usage or model identity; those values are not inferred.

### `GET /api/agent/runs/timeline/{incident_id}`
Support Engineer/Admin only. Joins persisted incident history, agent runs/steps, MCP calls, and linked approval/decision events. Each event carries its source row identifier and run/incident identifiers where available.

### `POST /api/agent/investigate/{incident_id}`
Support Engineer/Admin only. Runs the existing agent workflow against an existing incident in read-only ticket mode; it does not create a duplicate incident or change incident status. An optional `message` adds engineer context. The response includes retrieved chunks, diagnostic results, proposed resolution, trace, errors, and demo-mode flag. Diagnostic tool calls are correlated to the incident and agent run.

---

## 3. USM Dashboard (`/api/stats`)

### `GET /api/stats/dashboard`
Returns SQL aggregates from incident, approval, agent-run, MCP-call, and recorded SLA rows. Optional `start_date` and `end_date` are inclusive UTC dates, limited to a maximum 366-day range. Incident counts and distributions use `created_at`; average resolution, automation, and SLA-compliance samples use `resolved_at`. Current assignment/workload and active SLA-risk values are point-in-time values and are not hidden by the historical date filter. Trend rows are zero-filled by UTC day (last 7 days by default). Empty-rate denominators return `null`, not a fabricated percentage.

`sla_response_compliance_pct` and `sla_resolution_compliance_pct` report milestone rates separately; `sla_compliance_pct` is the weighted rate over recorded response and resolution deadline milestones. A due milestone without a recorded on-time completion is counted as missed. `ai_automation_rate_pct` counts resolved incidents with a completed linked agent run divided by resolved incidents with a recorded resolution timestamp; this is agent-linked, not proof of fully autonomous resolution.

- **Response (`200 OK`):**
  ```json
  {
    "total_incidents": 0,
    "assigned_incidents": 0,
    "unassigned_incidents": 0,
    "open_incidents": 0,
    "in_progress_incidents": 0,
    "resolved_incidents": 0,
    "critical_incidents": 0,
    "approaching_sla_count": 0,
    "pending_approvals_count": 0,
    "average_resolution_time_min": null,
    "sla_compliance_pct": null,
    "sla_response_compliance_pct": null,
    "sla_resolution_compliance_pct": null,
    "ai_automation_rate_pct": null,
    "priority_distribution": [],
    "category_breakdown": [],
    "status_distribution": [],
    "team_workload": [],
    "trend_chart": [],
    "activity_timeline": [],
    "recent_agent_runs": [],
    "sla_breaches": []
  }
  ```

### `GET /api/stats/insights`
Returns explainable rule-based signals derived from actual incident/SLA/asset rows: period-over-period incident and category increases, recurring categories, high unresolved team workloads, repeated asset incidents, and active deadline risks. Optional `start_date` and `end_date` use inclusive UTC dates; the default is the last 30 days. Each item includes its observed evidence and a suggested review action. It does not generate predictions or execute escalations.

---

## 4. Incidents Management (`/api/incidents`)

### `GET /api/incidents/`
Support Engineer/Admin only. Returns a filtered, sorted, paginated incident queue. Query parameters: `priority`, `category`, `status`, `team`, `assignment=all|mine|unassigned`, `sla_risk=all|on_track|at_risk|breached|unknown`, `search`, `sort_by=created_at|priority|resolution_due_at`, `sort_order=asc|desc`, `limit` (1–100), and `offset`.

- **Response (`200 OK`):**
  ```json
  { "items": [], "total": 0, "limit": 25, "offset": 0 }
  ```

`GET /api/incidents/{id}` returns employee/asset context, SLA countdown, incident history, comments, related incidents, agent runs/steps, and MCP call audit rows. `GET /api/incidents/support-users` returns assignable Support Engineer identities.

`PATCH /api/incidents/{id}` supports status, priority, team/user assignment, reporter asset link, and resolution notes. Setting status to `resolved` or `closed` requires both a non-empty `resolution_summary` and `resolution_verified: true`. Updates create incident-history, audit, and applicable requester-notification rows. `POST /api/incidents/{id}/comments` adds a support comment and audit event.

---

## 5. Human Approvals (`/api/approvals`)

Support Engineer/Admin only. `GET /api/approvals/?status=pending` returns requester identity, linked incident/service-request details, requested action, decision identity/time/comments, and execution result.

### `POST /api/approvals/{approval_id}/approve`
Records approval, writes an audit row, and executes a linked approved MCP action or resumes its workflow. A requester cannot approve their own request. If execution fails after the decision is saved, the endpoint returns `502` and persists the failure in `execution_result`.

### `POST /api/approvals/{approval_id}/reject`
Records rejection, writes an audit row, notifies the requester, and cancels an approval-linked workflow when present.

---

## 6. MCP Server Monitoring (`/api/mcp`)

### `GET /api/mcp/status`
Lists tools from the in-process MCP server wrapper. It reports `transport: in_process`, whether a remote endpoint is configured, and that this client does not use a remote endpoint. Diagnostic network/server tools are labeled simulated; local database and RAG tools are not represented as production infrastructure checks.

- **Response (`200 OK`):**
  ```json
  {
    "status": "available",
    "transport": "in_process",
    "remote_server_configured": false,
    "remote_server_used": false,
    "total_tools": 10,
    "tools": [
      { "name": "create_ticket", "description": "Create new incident or service request" },
      { "name": "check_network_status", "description": "Diagnose network connectivity" }
    ]
  }
  ```

  ### `GET /api/mcp/metrics`
  Support Engineer/Admin only. Returns SQL aggregates for invocation success/failure, authorization failures, timeout text matches, average latency, and usage grouped by tool and calling agent. MCP authentication failures are not recorded in `mcp_tool_calls` and are explicitly marked as unavailable.

### `GET /api/mcp/calls`
  Returns sanitized logged rows from `mcp_tool_calls`; filters include `incident_id`, `tool_name`, `calling_agent`, `status`, searchable text, and bounded `limit`.

- **Response (`200 OK`):**
  ```json
  [
    {
      "id": 1,
      "tool_name": "check_network_status",
      "input_summary": "target_host=portal.internal.corp",
      "output_summary": "status=online, latency=14ms",
      "duration_ms": 6,
      "status": "success",
      "permission_status": "granted"
    }
  ]
  ```

### `POST /api/mcp/tools/{tool_name}/execute`
Executes a registered tool using the caller role from the access token. Client-provided `user_role` is rejected. Include `incident_id` and an `arguments` object. Escalation requests create a pending approval and do not execute immediately; only an Administrator can approve and execute escalation. Direct MCP status updates cannot resolve/close tickets; use the verified incident resolution route.

---

## 7. SLA Management (`/api/sla`)

### `GET /api/sla/`
Lists the configured P1–P4 targets without changing or seeding policy data. Optional inclusive UTC `start_date` / `end_date` filters historical outcomes by `resolved_at`. Each policy reports response compliance (`first_response_at` versus `response_due_at`), resolution compliance (`resolved_at` versus `resolution_due_at`), sample counts, and the weighted milestone rate. Missing deadline samples return `null` compliance.

### `GET /api/sla/breaches`
Returns active incidents with a response or resolution deadline already breached or due within `window_minutes` (default 60, bounded to 0–1440). It includes UTC deadlines, remaining minutes for both milestones, per-milestone risk, priority tier, and `escalation_eligible`. Eligibility is informational only; this read endpoint does not execute an escalation.

### `GET /api/sla/trends`
Returns zero-filled daily historical response and resolution compliance for resolved incidents, with sample counts and P1–P4 breakdowns. Optional inclusive UTC date filters are supported; the default is the last 30 days. The maximum range is 366 days.

---

## 8. Asset CMDB (`/api/assets`)

### `GET /api/assets/`
Returns CMDB asset inventory and hardware assignments.

---

## 9. Knowledge Base Admin (`/admin/knowledge`)

Administrator only.

- `GET /admin/knowledge/` – List document metadata, duplicate source rows, version, indexing state/errors, chunk count, and model metadata.
- `POST /admin/knowledge/upload` – Multipart upload (`file`, optional `category`) of PDF/DOCX/TXT/Markdown up to 10 MB. Detects exact-content duplicates, versions changed same-path documents, indexes into the existing Chroma collection, and reports indexing failure explicitly.
- `GET /admin/knowledge/{doc_id}` – Document preview and version history.
- `GET /admin/knowledge/{doc_id}/chunks` – Inspect indexed chunk IDs, content, and metadata.
- `GET /admin/knowledge/stats` – SQL document/index aggregates plus Chroma collection and embedding metadata.
- `POST /admin/knowledge/evaluate` – Evaluate retrieval (`query`, optional `category`, `top_k` 1–10); returns actual chunks, citations, measured latency, and score availability.
- `DELETE /admin/knowledge/{doc_id}` – Removes the document record and, when no duplicate source record remains, its vectors and in-directory file.
- `POST /admin/knowledge/reindex` – Reindexes existing documents in-process, preserving the current Chroma collection and recording per-document failures.

**Embedding limitation:** the existing vector collection uses 384-dimensional zero vectors. Chroma distances are not meaningful relevance scores, so evaluation reports them as unavailable. The implementation uses explicit query embeddings to avoid Chroma's legacy `query_texts` embedding-function warning; it does not claim semantic-quality retrieval.

---

## 10. Health Check (`/health`)

- `GET /health` – Returns `{"status": "ok", "service": "resolvex-backend"}`.

