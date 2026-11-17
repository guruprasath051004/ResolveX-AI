import asyncio
import json
from datetime import datetime

import chromadb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database as database
from backend.agents import supervisor
from backend.api import agent as agent_api
from backend.api import auth, knowledge, mcp_monitor
from backend.database.migrations import upgrade_database
from backend.models import (
    AgentRun,
    AgentStep,
    Approval,
    Incident,
    IncidentHistory,
    MCPToolCall,
    RoleEnum,
    User,
)
from backend.rag import indexing, retriever
from backend.rag.embeddings import embed_texts


def _delete_test_collection(client):
    collection_names = {
        getattr(collection, "name", collection)
        for collection in client.list_collections()
    }
    if "resolvex_docs" in collection_names:
        client.delete_collection("resolvex_docs")


@pytest.fixture
def phase3_client(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "phase3-observability-test-secret")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    upgrade_database(engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(database, "SessionLocal", test_session)
    monkeypatch.setattr(auth, "SessionLocal", test_session)
    monkeypatch.setattr(agent_api, "SessionLocal", test_session)
    monkeypatch.setattr(supervisor, "SessionLocal", test_session)

    db = test_session()
    db.add_all(
        [
            User(
                email="support@phase3.test",
                hashed_password=auth._hash_password("support-password"),
                role=RoleEnum.support_engineer,
                full_name="Support Reviewer",
            ),
            User(
                email="employee@phase3.test",
                hashed_password=auth._hash_password("employee-password"),
                role=RoleEnum.employee,
            ),
            User(
                email="admin@phase3.test",
                hashed_password=auth._hash_password("admin-password"),
                role=RoleEnum.administrator,
                full_name="Platform Admin",
            ),
        ]
    )
    db.commit()
    incident = Incident(
        category="network",
        priority="high",
        description="Company portal unavailable",
        status="in_progress",
        owner_id=2,
    )
    db.add(incident)
    db.commit()
    incident_id = incident.id
    run = AgentRun(
        agent_name="ResolveX USM Multi-Agent System",
        incident_id=incident.id,
        thread_id="phase3-thread",
        status="completed",
        input_summary="Portal failure reported by [REDACTED_EMAIL]",
        output_summary="Knowledge lookup completed.",
        execution_data=json.dumps(
            {
                "retrieved_knowledge": [
                    {
                        "document": "Network Runbook",
                        "citation": "Network Runbook#chunk-0",
                        "source_path": "private/source/path",
                    }
                ],
                "tool_invocations": [],
            }
        ),
    )
    db.add(run)
    db.commit()
    run_id = run.id
    db.add_all(
        [
            AgentStep(
                run_id=run.id,
                step_name="Knowledge Agent",
                status="completed",
                summary="Retrieved indexed knowledge.",
                duration_ms=17,
            ),
            MCPToolCall(
                tool_name="check_network_status",
                input_summary=json.dumps({"password": "do-not-show", "target_host": "gateway"}),
                output_summary=json.dumps({"access_token": "do-not-show", "simulated": True}),
                duration_ms=4,
                status="error",
                permission_status="denied",
                calling_agent="diagnostic_agent",
                incident_id=incident.id,
                run_id=run.id,
                user_id=1,
            ),
            Approval(
                request_type="service_request:software",
                status="rejected",
                requester_id=2,
                incident_id=incident.id,
                thread_id=run.thread_id,
                decided_at=datetime.utcnow(),
                decision_reason="Risk review",
            ),
            IncidentHistory(
                incident_id=incident.id,
                event_type="status_changed",
                details="Incident moved to in progress.",
            ),
        ]
    )
    db.commit()
    db.close()

    app = FastAPI()
    for router in (auth.router, agent_api.router, mcp_monitor.router):
        app.include_router(router, prefix="/api")
    app.include_router(knowledge.router)

    with TestClient(app) as client:
        support_login = client.post(
            "/api/auth/login",
            json={
                "email": "support@phase3.test",
                "password": "support-password",
                "role": "support_engineer",
            },
        )
        employee_login = client.post(
            "/api/auth/login",
            json={
                "email": "employee@phase3.test",
                "password": "employee-password",
                "role": "employee",
            },
        )
        admin_login = client.post(
            "/api/auth/login",
            json={
                "email": "admin@phase3.test",
                "password": "admin-password",
                "role": "administrator",
            },
        )
        assert support_login.status_code == employee_login.status_code == admin_login.status_code == 200
        yield (
            client,
            test_session,
            {
                "support": {"Authorization": f"Bearer {support_login.json()['access_token']}"},
                "employee": {"Authorization": f"Bearer {employee_login.json()['access_token']}"},
                "admin": {"Authorization": f"Bearer {admin_login.json()['access_token']}"},
            },
            incident_id,
            run_id,
            engine,
            tmp_path,
            monkeypatch,
        )
    engine.dispose()


def test_execution_detail_metrics_timeline_and_rbac(phase3_client):
    client, _, headers, incident_id, run_id, *_ = phase3_client
    metrics = client.get("/api/agent/runs/metrics", headers=headers["support"])
    assert metrics.status_code == 200
    assert metrics.json()["runs"]["total"] == 1
    assert metrics.json()["agents"][0]["average_duration_ms"] == 17

    detail = client.get(f"/api/agent/runs/{run_id}", headers=headers["support"])
    assert detail.status_code == 200
    assert detail.json()["execution"]["retrieved_knowledge"][0]["citation"] == "Network Runbook#chunk-0"
    assert "private/source/path" not in detail.text
    assert "do-not-show" not in detail.text
    assert detail.json()["tool_invocations"][0]["permission_status"] == "denied"

    timeline = client.get(
        f"/api/agent/runs/timeline/{incident_id}",
        headers=headers["support"],
    )
    assert timeline.status_code == 200
    assert {event["event_type"] for event in timeline.json()} >= {
        "agent_run",
        "agent_step",
        "mcp_call",
        "approval",
        "approval_decision",
        "status_changed",
    }

    for path in ("/api/agent/runs", "/api/agent/runs/metrics", "/api/mcp/metrics"):
        assert client.get(path, headers=headers["employee"]).status_code == 403


def test_mcp_aggregates_and_search_redact_persisted_secrets(phase3_client):
    client, _, headers, *_ = phase3_client
    metrics = client.get("/api/mcp/metrics", headers=headers["support"])
    assert metrics.status_code == 200
    assert metrics.json()["calls"]["total"] == 1
    assert metrics.json()["calls"]["failed"] == 1
    assert metrics.json()["calls"]["authorization_failures"] == 1
    assert metrics.json()["calls"]["authentication_failures"] is None
    assert metrics.json()["calls"]["average_latency_ms"] == 4.0

    calls = client.get("/api/mcp/calls?search=network", headers=headers["support"])
    assert calls.status_code == 200
    assert len(calls.json()) == 1
    assert "do-not-show" not in calls.text
    status = client.get("/api/mcp/status", headers=headers["support"])
    assert status.json()["transport"] == "in_process"
    assert status.json()["remote_server_used"] is False
    assert next(
        tool for tool in status.json()["tools"] if tool["name"] == "check_network_status"
    )["integration_mode"] == "simulated"


def test_observed_agent_steps_and_duplicate_active_thread_guard(phase3_client):
    _, test_session, _, _, _, _, _, _ = phase3_client
    run = supervisor._create_run(
        thread_id="active-thread",
        incident_id=None,
        user_message="A safe summary",
    )
    with pytest.raises(supervisor.ActiveAgentRunError):
        supervisor._create_run(
            thread_id="active-thread",
            incident_id=None,
            user_message="A duplicate request",
        )

    async def successful_node(state):
        return {
            "agent_trace": state.get("agent_trace", [])
            + [
                {
                    "agent": "Triage Agent",
                    "summary": "Classified request.",
                    "status": "completed",
                }
            ]
        }

    observed = supervisor._observed_node("Triage Agent", successful_node)
    asyncio.run(observed({"run_id": run.id, "agent_trace": []}))
    supervisor._finalize_run(
        run.id,
        {
            "thread_id": "active-thread",
            "approval_id": 11,
            "ticket_status": "pending_approval",
            "agent_trace": [],
        },
        "waiting",
    )
    db = test_session()
    steps = db.query(AgentStep).filter(AgentStep.run_id == run.id).all()
    step = next(item for item in steps if item.step_name == "Triage Agent")
    assert step.status == "completed"
    assert step.duration_ms is not None
    assert step.started_at is not None
    assert db.query(AgentRun).filter(AgentRun.id == run.id).one().status == "waiting"
    assert any(item.step_name == "Supervisor Agent" and item.status == "waiting" for item in steps)
    db.close()

    failed_run = supervisor._create_run(
        thread_id="failing-thread",
        incident_id=None,
        user_message="A safe summary",
    )

    async def failing_node(_state):
        raise ValueError("diagnostic failed")

    with pytest.raises(ValueError, match="diagnostic failed"):
        asyncio.run(supervisor._observed_node("Diagnostic Agent", failing_node)({"run_id": failed_run.id}))
    supervisor._finalize_run(failed_run.id, {}, "failed", "ValueError: diagnostic failed")
    db = test_session()
    failed_step = (
        db.query(AgentStep)
        .filter(
            AgentStep.run_id == failed_run.id,
            AgentStep.step_name == "Diagnostic Agent",
        )
        .one()
    )
    assert failed_step.status == "failed"
    assert db.query(AgentRun).filter(AgentRun.id == failed_run.id).one().status == "failed"
    db.close()


def test_knowledge_upload_versioning_chunks_and_retrieval(phase3_client):
    client, test_session, headers, _, _, _, tmp_path, monkeypatch = phase3_client
    monkeypatch.setattr(knowledge, "DOC_ROOT", tmp_path / "documents")
    knowledge.DOC_ROOT.mkdir()
    vector_client = chromadb.EphemeralClient()
    _delete_test_collection(vector_client)
    monkeypatch.setattr(indexing, "_client", lambda: vector_client)
    monkeypatch.setattr(retriever.chromadb, "PersistentClient", lambda **_kwargs: vector_client)

    first = client.post(
        "/admin/knowledge/upload",
        files={"file": ("network_runbook.md", b"Company portal network recovery steps.", "text/markdown")},
        data={"category": "network"},
        headers=headers["admin"],
    )
    assert first.status_code == 200, first.text
    assert first.json()["index_status"] == "indexed"
    document_id = first.json()["id"]

    duplicate = client.post(
        "/admin/knowledge/upload",
        files={"file": ("duplicate.md", b"Company portal network recovery steps.", "text/markdown")},
        data={"category": "network"},
        headers=headers["admin"],
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["duplicate_of"] == document_id

    second_version = client.post(
        "/admin/knowledge/upload",
        files={"file": ("network_runbook.md", b"Updated network recovery and DNS steps.", "text/markdown")},
        data={"category": "network"},
        headers=headers["admin"],
    )
    assert second_version.status_code == 200, second_version.text
    assert second_version.json()["version_number"] == 2

    preview = client.get(f"/admin/knowledge/{document_id}", headers=headers["admin"])
    assert preview.status_code == 200
    assert preview.json()["versions"][0]["version_number"] == 1
    assert "Updated network recovery" in preview.json()["preview"]
    chunks = client.get(f"/admin/knowledge/{document_id}/chunks", headers=headers["admin"])
    assert chunks.status_code == 200
    assert chunks.json()["chunk_count"] > 0

    evaluation = client.post(
        "/admin/knowledge/evaluate",
        json={"query": "network recovery", "category": "network", "top_k": 3},
        headers=headers["admin"],
    )
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()["result_count"] > 0
    assert evaluation.json()["relevance_scores_available"] is False
    assert evaluation.json()["results"][0]["relevance_score"] is None
    assert evaluation.json()["results"][0]["citation_verified"] is True

    stats = client.get("/admin/knowledge/stats", headers=headers["admin"])
    assert stats.status_code == 200
    assert stats.json()["vector_database"]["chunk_count"] > 0
    assert stats.json()["vector_database"]["document_count"] == 1
    reindexed = client.post("/admin/knowledge/reindex", headers=headers["admin"])
    assert reindexed.status_code == 200
    assert reindexed.json()["files_indexed"] == 1
    assert reindexed.json()["files_failed"] == 0
    assert client.get("/admin/knowledge/", headers=headers["support"]).status_code == 403
    db = test_session()
    assert db.query(knowledge.knowledge_model.KnowledgeDocumentVersion).count() == 1
    assert db.query(knowledge.knowledge_model.KnowledgeDocument).count() == 1
    assert db.query(knowledge.knowledge_model.KnowledgeDocument).one().content_hash
    db.close()


def test_knowledge_inventory_flags_cross_path_duplicate_hashes(phase3_client, tmp_path):
    client, test_session, headers, *_ = phase3_client
    db = test_session()
    first = knowledge.knowledge_model.KnowledgeDocument(
        title="First copy",
        category="general",
        source_path=str(tmp_path / "first.md"),
        file_path=str(tmp_path / "first.md"),
        doc_type="md",
        content_hash="shared-content-hash",
        index_status="legacy_unverified",
    )
    second = knowledge.knowledge_model.KnowledgeDocument(
        title="Second copy",
        category="general",
        source_path=str(tmp_path / "second.md"),
        file_path=str(tmp_path / "second.md"),
        doc_type="md",
        content_hash="shared-content-hash",
        index_status="legacy_unverified",
    )
    db.add_all([first, second])
    db.commit()
    first_id = str(first.id)
    second_id = str(second.id)
    db.close()

    documents = client.get("/admin/knowledge/", headers=headers["admin"])
    assert documents.status_code == 200
    duplicates = [item for item in documents.json() if item["duplicate"]]
    assert len(duplicates) == 1
    assert duplicates[0]["id"] in {first_id, second_id}
    assert duplicates[0]["duplicate_of"] in {first_id, second_id}
    assert duplicates[0]["id"] != duplicates[0]["duplicate_of"]


def test_zero_vector_chroma_retrieval_does_not_publish_fake_scores(monkeypatch):
    client = chromadb.EphemeralClient()
    _delete_test_collection(client)
    collection = client.get_or_create_collection("resolvex_docs")
    collection.add(
        ids=["network-0"],
        documents=["Network connectivity troubleshooting instructions."],
        metadatas=[{"doc_id": "network-doc", "title": "Network Guide", "category": "network", "chunk_idx": 0}],
        embeddings=embed_texts(["Network connectivity troubleshooting instructions."]),
    )
    monkeypatch.setattr(retriever.chromadb, "PersistentClient", lambda **_kwargs: client)
    diagnostics = {}
    results = retriever.retrieve_knowledge(
        "network troubleshooting",
        category="network",
        top_k=1,
        diagnostics=diagnostics,
    )
    assert results[0]["score"] is None
    assert results[0]["citation"] == "Network Guide#chunk-0"
    assert diagnostics["relevance_scores_available"] is False
    assert diagnostics["method"] == "chroma"
