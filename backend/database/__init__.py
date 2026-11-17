
import os
import sqlite3
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


def _enable_sqlite_foreign_keys(
    connection: sqlite3.Connection,
    _connection_record: Any,
) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def create_database_engine(database_url: str | None) -> Engine:
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must be set in the environment or .env file."
        )

    if database_url.startswith("sqlite:"):
        options = {
            "echo": False,
            "future": True,
            "connect_args": {"check_same_thread": False},
        }

        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            options["poolclass"] = StaticPool

        db_engine = create_engine(database_url, **options)
        event.listen(db_engine, "connect", _enable_sqlite_foreign_keys)
        return db_engine

    db_engine = None

    try:
        db_engine = create_engine(database_url, echo=False, future=True)

        with db_engine.connect():
            pass

        return db_engine

    except SQLAlchemyError as exc:
        if os.getenv("ALLOW_SQLITE_FALLBACK", "1") == "1":
            fallback_engine = create_engine(
                "sqlite:///./resolvex_dev.db",
                echo=False,
                future=True,
                connect_args={"check_same_thread": False},
            )
            event.listen(
                fallback_engine,
                "connect",
                _enable_sqlite_foreign_keys,
            )
            return fallback_engine

        if db_engine is not None:
            db_engine.dispose()

        raise RuntimeError(
            "Could not connect to the configured DATABASE_URL. "
            "Verify the database is running and the URL is correct."
        ) from exc


engine = create_database_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
