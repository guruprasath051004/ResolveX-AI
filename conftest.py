"""Pytest defaults that keep tests isolated from a developer's database."""

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEMO_EMPLOYEE_PASSWORD"] = "employee-test-password"
os.environ["DEMO_SUPPORT_PASSWORD"] = "support-test-password"
os.environ["DEMO_ADMIN_PASSWORD"] = "admin-test-password"


def pytest_sessionstart(session):
    from backend.database.migrations import upgrade_database

    upgrade_database()
