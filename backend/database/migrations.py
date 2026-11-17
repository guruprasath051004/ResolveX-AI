"""Helpers for applying the Alembic-managed schema."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

from . import engine as default_engine


def upgrade_database(target_engine: Engine = default_engine) -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))

    with target_engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
