"""Shared UTC and policy helpers for SLA reporting."""

import math
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func

PRIORITY_VALUES = {
    "P1": ("critical", "p1"),
    "P2": ("high", "p2"),
    "P3": ("medium", "p3"),
    "P4": ("low", "p4"),
}


def utc_now_naive() -> datetime:
    """Return UTC in the naive form used by the existing database columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.isoformat().replace("+00:00", "Z")


def resolve_date_range(
    start_date: date | None,
    end_date: date | None,
    *,
    today: date | None = None,
    default_days: int | None = None,
) -> tuple[date | None, date | None]:
    today = today or utc_now_naive().date()
    if start_date is None and end_date is None:
        if default_days is None:
            return None, None
        start_date = today - timedelta(days=default_days - 1)
        end_date = today
    elif start_date is None:
        start_date = end_date - timedelta(days=29)
    elif end_date is None:
        end_date = today

    if start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    if end_date > today:
        raise HTTPException(status_code=422, detail="SLA reporting dates cannot be in the future")
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days")
    return start_date, end_date


def date_filters(column: Any, start_date: date | None, end_date: date | None) -> list[Any]:
    filters = []
    if start_date is not None:
        filters.append(column >= datetime.combine(start_date, time.min))
    if end_date is not None:
        filters.append(column < datetime.combine(end_date + timedelta(days=1), time.min))
    return filters


def priority_code_expression(column: Any) -> Any:
    normalized = func.lower(func.trim(column))
    return case(
        (normalized.in_(PRIORITY_VALUES["P1"]), "P1"),
        (normalized.in_(PRIORITY_VALUES["P2"]), "P2"),
        (normalized.in_(PRIORITY_VALUES["P3"]), "P3"),
        (normalized.in_(PRIORITY_VALUES["P4"]), "P4"),
        else_="Unknown",
    )


def policy_priority_code(name: str) -> str | None:
    match = re.search(r"\bP[1-4]\b", name.upper())
    return match.group(0) if match else None


def sla_risk(
    due_at: datetime | None,
    completed_at: datetime | None,
    *,
    now: datetime,
    at_risk_deadline: datetime,
) -> str | None:
    if due_at is None:
        return None
    if completed_at is not None:
        return "breached" if completed_at > due_at else None
    if due_at < now:
        return "breached"
    if due_at <= at_risk_deadline:
        return "at_risk"
    return None


def remaining_minutes(due_at: datetime, now: datetime) -> int:
    seconds = (due_at - now).total_seconds()
    return math.ceil(seconds / 60) if seconds >= 0 else math.floor(seconds / 60)


def percent(met: int, sample: int) -> float | None:
    return round(met * 100 / sample, 1) if sample else None
