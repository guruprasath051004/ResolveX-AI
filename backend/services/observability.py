"""Safe summaries for persisted execution telemetry."""

import json
import re
from typing import Any


_SENSITIVE_KEYS = {
    "api_key",
    "api_token",
    "access_token",
    "authorization",
    "client_secret",
    "content",
    "description",
    "email",
    "employee_id",
    "file_path",
    "owner_id",
    "password",
    "phone",
    "query",
    "refresh_token",
    "raw",
    "secret",
    "serial_number",
    "source_path",
    "token",
}
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_CREDENTIAL = re.compile(
    r"(?i)\b(password|passcode|access[_-]?token|refresh[_-]?token|token|secret|client[_-]?secret|api[_-]?(?:key|token))\b\s*[:=]\s*\S+"
)
_BEARER = re.compile(r"(?i)\bBearer\s+\S+")


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in _SENSITIVE_KEYS else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        redacted = _BEARER.sub("Bearer [REDACTED]", value)
        redacted = _CREDENTIAL.sub(r"\1=[REDACTED]", redacted)
        return _EMAIL.sub("[REDACTED_EMAIL]", redacted)
    return value


def safe_text_summary(value: str | None, limit: int = 500) -> str | None:
    if value is None:
        return None
    summary = redact_sensitive(value)
    return " ".join(summary.split())[:limit]


def safe_json_summary(value: str | None, limit: int = 800) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return safe_text_summary(value, limit)
    summary = json.dumps(redact_sensitive(parsed), ensure_ascii=True, default=str)
    return summary[:limit] + ("..." if len(summary) > limit else "")
