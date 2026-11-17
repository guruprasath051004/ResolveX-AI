# ResolveX AI: Contracts

## 1. Shared workflow state
{
  incident_id, employee_id, user_message,
  intent: "incident" | "service_request",
  category, priority,
  retrieved_chunks: [{doc, chunk, score}],
  diagnostics: [{tool, result, simulated}],
  proposed_resolution,
  requires_approval, approval_id,
  ticket_status,
  agent_trace: [{agent, summary, started_at, duration_ms, status}],
  errors: []
}

## 2. Agents (distinct functions, not personas)
- Triage: structured-output classification of category, priority, intent (validated JSON)
- Knowledge: RAG query with metadata filter; returns cited chunks
- Diagnostic: selects and calls MCP diagnostic tools based on category and retrieved docs
- Resolution: builds resolution from evidence; creates approval requests for sensitive actions; executes only approved actions
- Ticket: create/update/assign/status/SLA via MCP ticket tools only
- Supervisor: routes between agents, validates each output, retries or fails gracefully, owns human-approval pause and resume

## 3. MCP tools (JSON-schema validated, real DB operations, permission checked)
create_ticket, get_ticket, update_ticket, check_network_status, check_server_health, search_employee_assets, search_knowledge_base, assign_support_team, escalate_incident, update_incident_status, assign_incident_engineer, check_engineer_availability, reassign_incident
Each tool needs: description, input schema, role check, error handling, execution log row.

## 4. Tables
users, roles, incidents, service_requests, sla_policies, assets, asset_assignments, approvals, agent_runs, agent_steps, mcp_tool_calls, knowledge_documents, audit_logs, engineer_availability, assignment_exceptions, assignment_policies
Use proper foreign keys and Alembic migrations.

## 4.1 Intelligent Exception Handling & Incident Continuity Engine
- Operational Cycle: Detect → Understand → Decide → Act → Verify → Communicate → Audit
- Primary Scenario: Assigned Engineer on Leave → detects leave window/status → identifies skill-matched replacement (e.g. Sarah Chen) → reassigns atomically preserving created_at and SLA deadlines → communicates privacy-safe operational reality to employee → audits full trail.
- Concurrency Protection: `with_for_update` row locks and optimistic `lock_version` preventing race conditions on simultaneous claims.
- Feedback & Reopen: Employee "Not Resolved" verification reopens incident, adjusts priority, logs exception, and alerts engineer without creating duplicate tickets.

## 5. RAG
- Formats: PDF, DOCX, TXT, MD
- Chunk metadata: doc_id, title, category, page, chunk_idx
- Documents to create (10-12, mixed formats): network connectivity, VPN troubleshooting, password management, software installation, hardware failures, server monitoring and production-outage runbook, IT security policy, employee support procedures
- Every knowledge-based answer shows its source document and retrieved text
- Admin page: upload, list, delete, reindex

## 6. USM modules
- Incidents: unique IDs, category, priority, assignment, status, resolution history
- Service requests: software, hardware, account access, password reset
- SLA: response and resolution deadlines, breach detection, escalation
- Assets: employee assets, device info, assignments, simulated diagnostics
- Approvals: pending, history, approve/reject, execution only after approval

## 7. UI pages
Login; Employee (AI chat, my tickets, new request); Dashboard; Incidents; Service Requests; Approvals; SLA; Assets; Agent Command Center (agent status, current task, history, durations, React Flow handoff graph, activity log showing which agent called which tool and why); MCP Monitor (server status, registered tools, call history, input/output summaries, duration, success/failure, approval status); Knowledge Base admin.

Dashboard shows: total, open, resolved, critical incidents; average resolution time; SLA compliance %; AI automation rate; active agents; trend chart; priority distribution; category breakdown; activity timeline; pending approvals; SLA breach notifications. All computed from DB.

Employee chat shows live: active agent, decision summaries, retrieved sources, MCP calls and results (Simulated badge), resolution, ticket ID and status, plus a Resolved / Not resolved confirmation.

## 8. Acceptance scenarios (automated e2e tests)
1. "My laptop is connected to Wi-Fi, but the company portal is not opening."
   Incident created, priority set, network doc retrieved, check_network_status called, root cause investigated, resolution recommended, ticket updated.
2. "I cannot connect to the corporate VPN."
   VPN classification, VPN doc retrieved, diagnostic tool called, troubleshooting recommended, incident tracked.
3. "I need Python installed on my company laptop."
   Service request created, employee asset retrieved, approval requirement checked, routed to the right team, status updated after approval.
4. "The production application is unavailable."
   Critical classification, check_server_health called, runbook retrieved, team assigned, escalation started, admin notified.

## 9. Final acceptance
An interviewer can log in, submit an IT issue, watch six agents work live, see real MCP calls and RAG sources, approve the resolution, and see the ticket and dashboard update.

## 10. Phase gates
1 Foundation: compose up postgres, migrations apply, seed runs, pytest passes, login per role works, RBAC blocks Employee from admin endpoints.
2 RAG: all docs indexed; query "company portal not opening on Wi-Fi" returns the network doc first with chunk text and source; upload and delete via API work.
3 MCP: tools listed over the MCP protocol; create_ticket, check_network_status, check_server_health called via client; DB rows shown; permission-denied and invalid-input calls fail cleanly.
4 Agents: all 4 scenarios run through the API in demo mode (and live mode if a key is set); report incident, priority, sources, tools, approval behaviour, final status per scenario.
5 Frontend: build and Vitest pass; every page and button verified against the running stack; broken items fixed.
6 Integration: `docker compose up --build` starts everything; e2e smoke passes for all four scenarios; README, ARCHITECTURE (Mermaid diagrams), API, TESTING, and INTERVIEW_DEMO written; final table of requirement, implemented, verified how, known gaps.

## 11. Interview demo doc must cover
Business problem; USM architecture; multi-agent design; MCP implementation; RAG pipeline; end-to-end incident walkthrough; security and human approval; technical challenges and solutions; likely interviewer questions with short answers.