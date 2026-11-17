# ResolveX AI – Architecture

> Multi-agent autonomous USM platform architecture documentation.

## System Overview

```mermaid
flowchart TB
    subgraph FE["Frontend (React + Vite)"]
        LP["Login Page"]
        EC["Employee AI Chat"]
        DB["USM Dashboard"]
        IQ["Incidents Queue"]
        AP["Approvals"]
        CC["Agent Command Center"]
        MM["MCP Monitor"]
        SL["SLA Compliance"]
        AS["Asset CMDB"]
        KB["Knowledge Base Admin"]
    end

    subgraph BE["Backend (FastAPI)"]
        AUTH["Password Login API (bcrypt; role checked)"]
        AGENT_API["Agent API"]
        STATS["Stats API"]
        INC_API["Incidents API"]
        APP_API["Approvals API"]
        MCP_MON["MCP Monitor API"]
        SLA_API["SLA API"]
        ASSET_API["Assets API"]
        KB_API["Knowledge Admin API"]
    end

    subgraph AGENTS["LangGraph Agent Pipeline"]
        SUP["Supervisor"]
        TR["Triage Agent"]
        KN["Knowledge Agent"]
        DI["Diagnostic Agent"]
        RE["Resolution Agent"]
        TI["Ticket Agent"]
    end

    subgraph INFRA["Infrastructure"]
        PG["PostgreSQL 16"]
        CH["ChromaDB"]
        MCP["In-process MCP tool registry"]
        LLM["LLM Provider"]
    end

    FE -->|REST API| BE
    AGENT_API --> SUP
    SUP --> TR --> KN --> DI --> RE --> TI
    DI -->|MCPClient wrapper| MCP
    TI -->|MCPClient wrapper| MCP
    KN -->|Vector Search| CH
    MCP -->|SQL| PG
    BE -->|SQL| PG
    TR -->|Classify| LLM
    RE -->|Generate| LLM
```

## Agent Pipeline Flow

```mermaid
sequenceDiagram
    participant U as Employee
    participant API as FastAPI
    participant S as Supervisor
    participant T as Triage
    participant K as Knowledge
    participant D as Diagnostic
    participant R as Resolution
    participant TK as Ticket
    participant MCP as In-process MCP tools
    participant DB as PostgreSQL
    participant RAG as ChromaDB

    U->>API: POST /api/agent/run {message}
    API->>S: Start pipeline
    S->>T: Classify intent, category, priority
    T->>S: {intent, category, priority}
    S->>K: Retrieve relevant knowledge
    K->>RAG: Vector similarity search
    RAG-->>K: Top-k chunks with sources
    K->>S: {retrieved_chunks}
    S->>D: Run diagnostics
    D->>MCP: call_tool(check_network_status)
    MCP->>DB: Log MCP call
    MCP-->>D: {result, simulated: true}
    D->>S: {diagnostics}
    S->>R: Build resolution
    R->>S: {proposed_resolution, requires_approval}
    S->>TK: Create/update ticket
    TK->>MCP: call_tool(create_ticket)
    MCP->>DB: INSERT incident
    MCP-->>TK: {incident_id}
    TK->>S: {ticket_status}
    S-->>API: Complete AgentState
    API-->>U: AgentRunResponse
```

## RAG Pipeline Architecture

```mermaid
flowchart TD
    subgraph INGEST["Document Ingestion Pipeline"]
        DOCS["Runbook Files\n(.md, .pdf, .docx, .txt)"]
        LOAD["Format Loaders\n(pdfminer, docx2txt, text)"]
        CHUNK["Word chunks\n(200 words, 50-word overlap)"]
        META["Metadata Tagging\n(doc_id, title, category, chunk_idx)"]
        EMBED["Legacy zero-vector compatibility\n(384 dimensions; no semantic score)"]
        VECTOR_DB[("ChromaDB Vector Store\n(resolvex_docs collection)")]

        DOCS --> LOAD --> CHUNK --> META --> EMBED --> VECTOR_DB
    end

    subgraph QUERY["Online Retrieval Flow"]
        USER_MSG["User Issue Message"]
        CAT_FILTER["Category Metadata Filter\n(network, vpn, server, software)"]
        QUERY_EMBED["Explicit zero-vector query"]
        SIM_SEARCH["Chroma candidate retrieval\n(distance not meaningful)"]
        CITATIONS["Cited chunks\n(score unavailable for Chroma results)"]
        AGENT["Knowledge Agent Response"]

        USER_MSG --> QUERY_EMBED
        CAT_FILTER --> SIM_SEARCH
        QUERY_EMBED --> SIM_SEARCH
        VECTOR_DB -.-> SIM_SEARCH
        SIM_SEARCH --> CITATIONS --> AGENT
    end
```

When Chroma is unavailable or returns no candidates, retrieval falls back to local lexical overlap and labels that score method explicitly. RAG administration exposes actual chunks, citations, measured latency, and score availability. Moving to semantic embeddings requires a separate, validated re-embedding plan; existing vectors are not replaced here.

## Data Model (ER Diagram)

```mermaid
erDiagram
    users ||--o{ incidents : creates
    users ||--o{ service_requests : submits
    users ||--o{ approvals : reviews
    incidents ||--o{ agent_runs : triggers
    agent_runs ||--o{ agent_steps : contains
    agent_runs ||--o{ mcp_tool_calls : generates
    assets ||--o{ asset_assignments : has
    users ||--o{ asset_assignments : assigned
    incidents ||--o{ approvals : requires

    users {
        int id PK
        string email
        string role
        string hashed_password
        datetime created_at
    }
    incidents {
        int id PK
        int employee_id FK
        string category
        string priority
        string status
        text description
        text resolution
        datetime created_at
        datetime resolved_at
    }
    approvals {
        int id PK
        int incident_id FK
        string action_type
        string status
        int requested_by FK
        int reviewed_by FK
        datetime created_at
    }
    agent_runs {
        int id PK
        int incident_id FK
        string status
        text user_message
        datetime started_at
        datetime completed_at
    }
    agent_steps {
        int id PK
        int run_id FK
        string agent_name
        string status
        text summary
        int duration_ms
    }
    mcp_tool_calls {
        int id PK
        int run_id FK
        string tool_name
        string calling_agent
        text input_summary
        text output_summary
        int duration_ms
        string status
        string permission_status
    }
    assets {
        int id PK
        string asset_type
        string name
        string serial_number
        string status
    }
```

## MCP Tool Execution (Current Runtime)

```mermaid
flowchart LR
    subgraph BACKEND["FastAPI Backend Process"]
        CW["MCPClient wrapper"]
        REG["Tool Registry (10 tools)"]
        PERM["Permission Checker (RBAC)"]
        EXEC["Tool Executor"]
        LOG["Call Logger"]
        CW --> REG
        REG --> PERM --> EXEC --> LOG
    end

    subgraph TOOLS["Registered Tools"]
        T1["create_ticket"]
        T2["get_ticket"]
        T3["update_ticket"]
        T4["check_network_status"]
        T5["check_server_health"]
        T6["search_employee_assets"]
        T7["search_knowledge_base"]
        T8["assign_support_team"]
        T9["escalate_incident"]
        T10["update_incident_status"]
    end

    EXEC --> TOOLS
    LOG -->|SQL| DB["PostgreSQL"]
```

The application backend currently calls the registered tools in-process; `/api/mcp/status` reports `in_process`. The separate Streamable HTTP endpoint is not yet used by agent or API calls. MCP call rows persist tool, calling agent, incident/run/user correlation, duration, status, and permission result.

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TypeScript + Vite | SPA with modern tooling |
| Styling | Tailwind CSS | Utility-first responsive design |
| Charts | Recharts | Dashboard data visualization |
| Agent Graph | React Flow | Visual agent handoff diagram |
| State Mgmt | TanStack React Query | Server state + caching |
| Backend | FastAPI + Python 3.11 | REST API with auto-docs |
| ORM | SQLAlchemy 2.x + Alembic | Type-safe DB access + migrations |
| Auth | JWT bearer tokens + bcrypt | Protected API routes enforce role permissions; employees are scoped to their own records |
| Agents | LangGraph | Typed state graph with checkpointing |
| MCP | Official `mcp` Python SDK | In-process tool registry and execution wrapper; standalone HTTP client integration remains a known gap |
| RAG | ChromaDB + legacy zero-vector compatibility | Candidate retrieval plus labeled lexical fallback; meaningful Chroma similarity scores are unavailable |
| Database | PostgreSQL 16 | Relational data store |
| Infra | Docker Compose | Multi-container orchestration |
| Testing | pytest + Vitest | Backend + frontend test suites |

