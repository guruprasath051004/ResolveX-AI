"""Authentication and User session router."""
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.database import SessionLocal
from backend.models import AuditLog, RoleEnum, User

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_MINUTES = 60
MAX_ACCESS_TOKEN_MINUTES = 1440

DEMO_ACCOUNTS = (
    (
        "employee@resolvex.ai",
        RoleEnum.employee,
        os.getenv("DEMO_EMPLOYEE_PASSWORD"),
    ),
    (
        "support@resolvex.ai",
        RoleEnum.support_engineer,
        os.getenv("DEMO_SUPPORT_PASSWORD"),
    ),
    (
        "admin@resolvex.ai",
        RoleEnum.administrator,
        os.getenv("DEMO_ADMIN_PASSWORD"),
    ),
)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def seed_demo_users() -> None:
    """Create or repair the documented demo accounts when running in demo mode."""
    if os.getenv("LLM_PROVIDER", "demo").lower() != "demo":
        return

    db = SessionLocal()
    try:
        for email, role, password in DEMO_ACCOUNTS:
            if not password:
                raise RuntimeError(
                    f"Set the demo password environment variable for the {role.value} account."
                )
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                db.add(User(email=email, hashed_password=_hash_password(password), role=role))
                continue

            if user.role != role:
                user.role = role
            if not _verify_password(password, user.hashed_password):
                user.hashed_password = _hash_password(password)

        db.commit()
    finally:
        db.close()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: RoleEnum
    email: str = Field(
        min_length=3,
        max_length=320,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    password: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserResponse(BaseModel):
    id: int
    email: str
    role: str


class LoginResponse(UserResponse):
    access_token: str
    token_type: str = "bearer"


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY is not configured")
    return secret


def _access_token_minutes() -> int:
    configured = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(DEFAULT_ACCESS_TOKEN_MINUTES))
    try:
        minutes = int(configured)
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer.") from exc
    if not 1 <= minutes <= MAX_ACCESS_TOKEN_MINUTES:
        raise RuntimeError(
            f"ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and {MAX_ACCESS_TOKEN_MINUTES}."
        )
    return minutes


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "ver": user.token_version,
            "iat": now,
            "exp": now + timedelta(minutes=_access_token_minutes()),
        },
        _jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = jwt.decode(
            credentials.credentials,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(claims["sub"])
        token_version = int(claims["ver"])
    except (JWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or user.token_version != token_version:
            raise HTTPException(
                status_code=401,
                detail="Session has been revoked or the user no longer exists",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    finally:
        db.close()


def require_roles(*roles: RoleEnum):
    allowed_roles = {role.value for role in roles}

    def check_role(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient role permissions")
        return user

    return check_role


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """Authenticate an account and verify that its stored role matches the selection."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload.email).first()
        if (
            user is None
            or user.role != payload.role
            or not _verify_password(payload.password, user.hashed_password)
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid email, password, or role",
            )

        return LoginResponse(
            id=user.id,
            email=user.email,
            role=user.role.value,
            access_token=create_access_token(user),
        )
    finally:
        db.close()


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse(id=user.id, email=user.email, role=user.role.value)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user)):
    """Revoke all active access tokens for the authenticated account."""
    db = SessionLocal()
    try:
        current_user = (
            db.query(User)
            .filter(User.id == user.id)
            .with_for_update()
            .first()
        )
        if current_user is None:
            raise HTTPException(status_code=401, detail="User no longer exists")
        current_user.token_version += 1
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="auth.logout",
                table_name="users",
                record_id=current_user.id,
                details="Revoked active access tokens for this account",
            )
        )
        db.commit()
        return Response(status_code=204)
    finally:
        db.close()
