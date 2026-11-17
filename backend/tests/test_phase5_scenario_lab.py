"""Test suite for Phase 5: Scenario Testing Lab & Admin Verification.
Validates all 20 predefined scenarios, batch execution, export capabilities,
strict test isolation, and RBAC protection.
"""
from datetime import datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database as database
from backend.api import auth, workforce as workforce_api
from backend.database.migrations import upgrade_database
from backend.models import (
    EngineerAvailability,
    Incident,
    RoleEnum,
    User,
)
from backend.services.workforce import seed_workforce


@pytest.fixture
def lab_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    upgrade_database(engine)
    session_factory = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)

    monkeypatch.setattr(auth, "SessionLocal", session_factory)
    monkeypatch.setattr(database, "SessionLocal", session_factory)

    def _override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(database, "get_db", _override_get_db)
    monkeypatch.setattr(workforce_api, "get_db", _override_get_db)

    db = session_factory()
    admin = User(
        email="admin@resolvex.ai",
        hashed_password=auth._hash_password("Demo123"),
        role=RoleEnum.administrator,
        full_name="Admin User",
    )
    support = User(
        email="support2@resolvex.ai",
        hashed_password=auth._hash_password("Demo123"),
        role=RoleEnum.support_engineer,
        full_name="Sarah Chen",
        department="Network Operations",
    )
    support_mgr = User(
        email="support_mgr@resolvex.ai",
        hashed_password=auth._hash_password("Demo123"),
        role=RoleEnum.support_engineer,
        full_name="David Kim",
        department="Support Management",
    )
    emp = User(
        email="employee@resolvex.ai",
        hashed_password=auth._hash_password("Demo123"),
        role=RoleEnum.employee,
        full_name="Employee User",
    )
    db.add_all([admin, support, support_mgr, emp])
    db.commit()
    seed_workforce(db)
    db.close()

    app = FastAPI()
    app.dependency_overrides[workforce_api.get_db] = _override_get_db
    app.include_router(workforce_api.router, prefix="/api")

    with TestClient(app) as client:
        yield client, db, admin, support, emp

    db.close()
    engine.dispose()


def test_scenario_library_contains_20_scenarios(lab_client):
    client, _, admin, _, _ = lab_client
    token = auth.create_access_token(admin)
    res = client.get("/api/workforce/scenario-lab/scenarios", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    scenarios = res.json()
    assert len(scenarios) == 20
    ids = [s["id"] for s in scenarios]
    assert "scenario_1" in ids
    assert "scenario_20" in ids


def test_scenario_execution_rbac_enforcement(lab_client):
    client, _, _, support, emp = lab_client
    emp_token = auth.create_access_token(emp)
    supp_token = auth.create_access_token(support)

    # Employee cannot access scenario lab
    res_emp = client.get("/api/workforce/scenario-lab/scenarios", headers={"Authorization": f"Bearer {emp_token}"})
    assert res_emp.status_code == 403

    # Support Engineer cannot run scenarios (Admin only)
    res_supp = client.post(
        "/api/workforce/scenario-lab/run",
        json={"scenario_id": "scenario_1"},
        headers={"Authorization": f"Bearer {supp_token}"},
    )
    assert res_supp.status_code == 403


def test_batch_run_all_20_scenarios(lab_client):
    client, _, admin, _, _ = lab_client
    token = auth.create_access_token(admin)
    res = client.post("/api/workforce/scenario-lab/run-all", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_scenarios"] == 20
    assert data["passed_count"] == 20
    assert data["failed_count"] == 0
    assert data["pass_rate_pct"] == 100.0
    assert data["simulated"] is True
    assert len(data["results"]) == 20


def test_scenario_lab_export_json_and_csv(lab_client):
    client, _, admin, _, _ = lab_client
    token = auth.create_access_token(admin)

    # JSON export
    res_json = client.get("/api/workforce/scenario-lab/export?format=json", headers={"Authorization": f"Bearer {token}"})
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["total_scenarios"] == 20
    assert data["passed_count"] == 20

    # CSV export
    res_csv = client.get("/api/workforce/scenario-lab/export?format=csv", headers={"Authorization": f"Bearer {token}"})
    assert res_csv.status_code == 200
    assert res_csv.headers["content-type"] == "text/csv; charset=utf-8"
    assert "Scenario ID,Name,Category,Verdict" in res_csv.text


def test_strict_test_isolation_guarantee(lab_client):
    client, db, admin, _, _ = lab_client
    token = auth.create_access_token(admin)

    initial_incident_count = db.query(Incident).count()

    # Run scenario that simulates engineer on leave and reassigns
    res = client.post(
        "/api/workforce/scenario-lab/run",
        json={"scenario_id": "scenario_4"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    # Verify zero simulated incidents leaked into production incidents table
    final_incident_count = db.query(Incident).count()
    assert final_incident_count == initial_incident_count
