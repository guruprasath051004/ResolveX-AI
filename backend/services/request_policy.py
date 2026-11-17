"""Shared service-request approval policy."""

SENSITIVE_SERVICE_REQUEST_TYPES = frozenset(
    {"software_installation", "account_access", "password_reset"}
)
