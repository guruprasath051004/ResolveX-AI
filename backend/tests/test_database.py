import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

import backend.database as database
from backend.api import approvals, auth, employee, incidents, service_requests
from backend.database import create_database_engine
from backend.database.migrations import upgrade_database


def test_api_modules_share_one_database_session_factory():
    assert auth.SessionLocal is database.SessionLocal
    assert incidents.SessionLocal is database.SessionLocal
    assert approvals.SessionLocal is database.SessionLocal
    assert service_requests.SessionLocal is database.SessionLocal
    assert employee.get_db.__globals__["SessionLocal"] is database.SessionLocal


def test_database_url_is_required():
    with pytest.raises(RuntimeError, match="DATABASE_URL must be set"):
        create_database_engine(None)


def test_sqlite_is_available_when_explicitly_configured():
    engine = create_database_engine("sqlite://")
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("select 1")) == 1
    finally:
        engine.dispose()


def test_explicit_sqlite_engine_enforces_foreign_keys():
    engine = create_database_engine("sqlite://")
    try:
        upgrade_database(engine)
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO incidents (category, priority, description, owner_id) "
                        "VALUES ('network', 'high', 'Missing reporter', 9999)"
                    )
                )
    finally:
        engine.dispose()


def test_configured_database_connection_failure_is_visible():
    with pytest.raises(RuntimeError, match="Could not connect to the configured DATABASE_URL"):
        create_database_engine(
            "postgresql+psycopg2://test:test@127.0.0.1:1/test?connect_timeout=1"
        )


def test_fresh_database_is_created_by_linear_alembic_history():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        upgrade_database(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "agent_checkpoints" in tables
        assert "knowledge_documents" in tables
        assert not any(table.startswith("knowledge_documents_") for table in tables)
        category = next(
            column
            for column in inspector.get_columns("knowledge_documents")
            if column["name"] == "category"
        )
        assert category["nullable"] is False

        config = Config("alembic.ini")
        config.attributes["connection"] = engine.connect()
        try:
            command.downgrade(config, "base")
        finally:
            config.attributes["connection"].close()

        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    finally:
        engine.dispose()
