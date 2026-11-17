from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database.migrations import upgrade_database

from backend.api import auth
from backend.models import AuditLog, RoleEnum, User


@pytest.fixture
def api_client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("JWT_SECRET_KEY", "auth-test-signing-key")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    upgrade_database(engine)
    test_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(auth, "SessionLocal", test_session)
    auth.seed_demo_users()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api")
    with TestClient(app) as client:
        yield client
    engine.dispose()


@pytest.mark.parametrize(
    ("email", "role", "password"),
    [(email, role.value, password) for email, role, password in auth.DEMO_ACCOUNTS],
)
def test_login_accepts_credentials_for_each_role(api_client, email, role, password):
    response = api_client.post(
        "/api/auth/login",
        json={"email": email, "password": password, "role": role},
    )

    assert response.status_code == 200
    assert response.json()["email"] == email
    assert response.json()["role"] == role


@pytest.mark.parametrize(
    ("email", "role", "password"),
    [(email, role.value, password) for email, role, password in auth.DEMO_ACCOUNTS],
)
def test_login_rejects_wrong_password(api_client, email, role, password):
    response = api_client.post(
        "/api/auth/login",
        json={"email": email, "password": f"{password}-wrong", "role": role},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email, password, or role"


def test_login_rejects_credentials_for_a_different_role(api_client):
    response = api_client.post(
        "/api/auth/login",
        json={
            "email": "admin@resolvex.ai",
            "password": auth.DEMO_ACCOUNTS[2][2],
            "role": RoleEnum.employee.value,
        },
    )

    assert response.status_code == 401


def test_login_does_not_create_unknown_users(api_client):
    response = api_client.post(
        "/api/auth/login",
        json={
            "email": "unknown@resolvex.ai",
            "password": "not-a-demo-password",
            "role": RoleEnum.employee.value,
        },
    )

    assert response.status_code == 401
    db = auth.SessionLocal()
    try:
        assert db.query(User).count() == len(auth.DEMO_ACCOUNTS)
    finally:
        db.close()


def test_login_requires_password_and_valid_role(api_client):
    missing_password = api_client.post(
        "/api/auth/login",
        json={"email": "employee@resolvex.ai", "role": "employee"},
    )
    invalid_role = api_client.post(
        "/api/auth/login",
        json={
            "email": "employee@resolvex.ai",
            "password": auth.DEMO_ACCOUNTS[0][2],
            "role": "admin",
        },
    )

    assert missing_password.status_code == 422
    assert invalid_role.status_code == 422


def test_demo_seed_repairs_legacy_placeholder_credentials(api_client):
    db = auth.SessionLocal()
    try:
        user = db.query(User).filter(User.email == "employee@resolvex.ai").one()
        user.hashed_password = "demo_hashed_password"
        user.role = RoleEnum.administrator
        db.commit()
    finally:
        db.close()

    auth.seed_demo_users()
    response = api_client.post(
        "/api/auth/login",
        json={
            "email": "employee@resolvex.ai",
            "password": auth.DEMO_ACCOUNTS[0][2],
            "role": RoleEnum.employee.value,
        },
    )

    assert response.status_code == 200


def test_current_user_identity_comes_from_validated_token(api_client):
    login = api_client.post(
        "/api/auth/login",
        json={
            "email": "employee@resolvex.ai",
            "password": auth.DEMO_ACCOUNTS[0][2],
            "role": RoleEnum.employee.value,
        },
    )
    token = login.json()["access_token"]
    response = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == login.json()["id"]


def test_access_token_uses_configured_expiration(api_client, monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "7")
    response = api_client.post(
        "/api/auth/login",
        json={
            "email": "admin@resolvex.ai",
            "password": auth.DEMO_ACCOUNTS[2][2],
            "role": RoleEnum.administrator.value,
        },
    )
    assert response.status_code == 200
    claims = jwt.decode(
        response.json()["access_token"],
        auth._jwt_secret(),
        algorithms=[auth.JWT_ALGORITHM],
    )

    assert claims["exp"] - claims["iat"] == 7 * 60


def test_invalid_access_token_expiration_configuration_fails_explicitly(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "0")

    with pytest.raises(RuntimeError, match="between 1 and 1440"):
        auth._access_token_minutes()


def test_logout_requires_authentication(api_client):
    response = api_client.post("/api/auth/logout")

    assert response.status_code == 401


def test_logout_revokes_all_access_tokens_and_audits_the_action(api_client):
    login_payload = {
        "email": "admin@resolvex.ai",
        "password": auth.DEMO_ACCOUNTS[2][2],
        "role": RoleEnum.administrator.value,
    }
    first_login = api_client.post("/api/auth/login", json=login_payload)
    second_login = api_client.post("/api/auth/login", json=login_payload)
    first_token = first_login.json()["access_token"]
    second_token = second_login.json()["access_token"]

    logout_response = api_client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert logout_response.status_code == 204
    assert api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {first_token}"},
    ).status_code == 401
    assert api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {second_token}"},
    ).status_code == 401

    relogin = api_client.post("/api/auth/login", json=login_payload)
    assert api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {relogin.json()['access_token']}"},
    ).status_code == 200

    db = auth.SessionLocal()
    try:
        user = db.query(User).filter(User.email == login_payload["email"]).one()
        assert user.token_version == 1
        assert (
            db.query(AuditLog)
            .filter(AuditLog.user_id == user.id, AuditLog.action == "auth.logout")
            .count()
            == 1
        )
    finally:
        db.close()


def test_expired_access_token_is_rejected(api_client):
    login = api_client.post(
        "/api/auth/login",
        json={
            "email": "employee@resolvex.ai",
            "password": auth.DEMO_ACCOUNTS[0][2],
            "role": RoleEnum.employee.value,
        },
    )
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": str(login.json()["id"]),
            "role": RoleEnum.employee.value,
            "ver": 0,
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        },
        auth._jwt_secret(),
        algorithm=auth.JWT_ALGORITHM,
    )

    response = api_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
