"""SLA policy, historical-compliance, and active-risk views."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from backend.api.auth import require_roles
from backend.database import get_db
from backend.models import Incident, RoleEnum, SLAPolicy
from backend.services.sla import (
    PRIORITY_VALUES,
    date_filters,
    iso_utc,
    percent,
    policy_priority_code,
    priority_code_expression,
    remaining_minutes,
    resolve_date_range,
    sla_risk,
    utc_now_naive,
)

router = APIRouter(
    prefix="/sla",
    tags=["sla"],
    dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))],
)

RESOLVED_STATUSES = ("resolved", "closed", "completed")
INACTIVE_STATUSES = (*RESOLVED_STATUSES, "cancelled", "canceled")


@router.get("/")
def list_sla_policies(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    start_date, end_date = resolve_date_range(start_date, end_date, today=utc_now_naive().date())
    history_filters = date_filters(Incident.resolved_at, start_date, end_date)
    policies = db.query(SLAPolicy).order_by(SLAPolicy.response_minutes).all()
    priority_expression = priority_code_expression(Incident.priority)
    resolved = and_(
        func.lower(func.trim(Incident.status)).in_(RESOLVED_STATUSES),
        Incident.resolved_at.is_not(None),
    )
    response_sample = and_(resolved, Incident.response_due_at.is_not(None))
    response_met = and_(
        response_sample,
        Incident.first_response_at.is_not(None),
        Incident.first_response_at <= Incident.response_due_at,
    )
    resolution_sample = and_(resolved, Incident.resolution_due_at.is_not(None))
    resolution_met = and_(
        resolution_sample,
        Incident.resolved_at <= Incident.resolution_due_at,
    )
    rows = (
        db.query(
            priority_expression,
            func.sum(case((response_sample, 1), else_=0)),
            func.sum(case((response_met, 1), else_=0)),
            func.sum(case((resolution_sample, 1), else_=0)),
            func.sum(case((resolution_met, 1), else_=0)),
        )
        .filter(resolved, *history_filters)
        .group_by(priority_expression)
        .all()
    )
    compliance_by_priority = {
        str(code): {
            "response_sample_count": int(response_sample_count or 0),
            "response_met_count": int(response_met_count or 0),
            "resolution_sample_count": int(resolution_sample_count or 0),
            "resolution_met_count": int(resolution_met_count or 0),
        }
        for (
            code,
            response_sample_count,
            response_met_count,
            resolution_sample_count,
            resolution_met_count,
        ) in rows
    }
    result = []
    for policy in policies:
        priority_code = policy_priority_code(policy.name)
        counts = compliance_by_priority.get(
            priority_code or "",
            {
                "response_sample_count": 0,
                "response_met_count": 0,
                "resolution_sample_count": 0,
                "resolution_met_count": 0,
            },
        )
        response_sample = counts["response_sample_count"]
        response_met = counts["response_met_count"]
        resolution_sample = counts["resolution_sample_count"]
        resolution_met = counts["resolution_met_count"]
        sample_count = response_sample + resolution_sample
        met_count = response_met + resolution_met
        compliance = percent(met_count, sample_count)
        result.append(
            {
                "id": policy.id,
                "name": policy.name,
                "priority_code": priority_code,
                "response_minutes": policy.response_minutes,
                "resolution_minutes": policy.resolution_minutes,
                "response_compliance_pct": percent(response_met, response_sample),
                "response_sample_count": response_sample,
                "resolution_compliance_pct": percent(resolution_met, resolution_sample),
                "resolution_sample_count": resolution_sample,
                "compliance_rate_pct": compliance,
                "sample_count": resolution_sample,
                "status": (
                    "No data"
                    if compliance is None
                    else "Compliant"
                    if compliance == 100
                    else "At Risk"
                ),
            }
        )
    return result


@router.get("/breaches")
def list_sla_risks(
    window_minutes: int = Query(default=60, ge=0, le=1440),
    limit: int = Query(default=100, ge=1, le=500),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    now = utc_now_naive()
    start_date, end_date = resolve_date_range(start_date, end_date, today=now.date())
    created_filters = date_filters(Incident.created_at, start_date, end_date)
    cutoff = now + timedelta(minutes=window_minutes)
    active = func.lower(func.trim(Incident.status)).notin_(INACTIVE_STATUSES)
    response_candidate = and_(
        Incident.response_due_at.is_not(None),
        Incident.response_due_at <= cutoff,
        or_(
            Incident.first_response_at.is_(None),
            Incident.first_response_at > Incident.response_due_at,
        ),
    )
    resolution_candidate = and_(
        Incident.resolution_due_at.is_not(None),
        Incident.resolution_due_at <= cutoff,
    )
    risk_deadline = case(
        (
            and_(response_candidate, resolution_candidate),
            case(
                (Incident.response_due_at <= Incident.resolution_due_at, Incident.response_due_at),
                else_=Incident.resolution_due_at,
            ),
        ),
        (response_candidate, Incident.response_due_at),
        else_=Incident.resolution_due_at,
    )
    incidents = (
        db.query(Incident)
        .filter(active, *created_filters, or_(response_candidate, resolution_candidate))
        .order_by(risk_deadline.asc())
        .limit(limit)
        .all()
    )

    results = []
    for incident in incidents:
        response_state = sla_risk(
            incident.response_due_at,
            incident.first_response_at,
            now=now,
            at_risk_deadline=cutoff,
        )
        resolution_state = sla_risk(
            incident.resolution_due_at,
            None,
            now=now,
            at_risk_deadline=cutoff,
        )
        risks = [
            (due, state, deadline_type)
            for due, state, deadline_type in (
                (incident.response_due_at, response_state, "response"),
                (incident.resolution_due_at, resolution_state, "resolution"),
            )
            if due is not None and state is not None
        ]
        if not risks:
            continue
        primary_due, _, primary_type = min(risks, key=lambda item: item[0])
        is_breached = any(state == "breached" for _, state, _ in risks)
        results.append(
            {
                "incident_id": incident.id,
                "ticket_id": f"INC-{incident.id:06d}",
                "priority": incident.priority,
                "priority_code": next(
                    (code for code, values in PRIORITY_VALUES.items()
                     if incident.priority.strip().lower() in values),
                    None,
                ),
                "status": incident.status,
                "response_due_at": iso_utc(incident.response_due_at),
                "resolution_due_at": iso_utc(incident.resolution_due_at),
                "response_minutes_remaining": (
                    remaining_minutes(incident.response_due_at, now)
                    if incident.response_due_at is not None
                    else None
                ),
                "resolution_minutes_remaining": (
                    remaining_minutes(incident.resolution_due_at, now)
                    if incident.resolution_due_at is not None
                    else None
                ),
                "response_risk": response_state,
                "resolution_risk": resolution_state,
                "risk": "breached" if is_breached else "at_risk",
                "deadline_type": primary_type,
                "minutes_remaining": remaining_minutes(primary_due, now),
                "escalation_eligible": is_breached,
                "escalation_reason": (
                    "At least one response or resolution deadline has been missed."
                    if is_breached
                    else None
                ),
            }
        )
    return results


@router.get("/trends")
def get_sla_compliance_trends(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    start_date, end_date = resolve_date_range(
        start_date,
        end_date,
        today=utc_now_naive().date(),
        default_days=30,
    )
    if start_date is None or end_date is None:
        raise RuntimeError("SLA trend date range was not resolved.")

    day_expression = func.date(Incident.resolved_at)
    priority_expression = priority_code_expression(Incident.priority)
    eligible = and_(
        func.lower(func.trim(Incident.status)).in_(RESOLVED_STATUSES),
        Incident.resolved_at.is_not(None),
    )
    response_sample = and_(eligible, Incident.response_due_at.is_not(None))
    response_met = and_(
        response_sample,
        Incident.first_response_at.is_not(None),
        Incident.first_response_at <= Incident.response_due_at,
    )
    resolution_sample = and_(eligible, Incident.resolution_due_at.is_not(None))
    resolution_met = and_(
        resolution_sample,
        Incident.resolved_at <= Incident.resolution_due_at,
    )
    rows = (
        db.query(
            day_expression,
            priority_expression,
            func.sum(case((response_sample, 1), else_=0)),
            func.sum(case((response_met, 1), else_=0)),
            func.sum(case((resolution_sample, 1), else_=0)),
            func.sum(case((resolution_met, 1), else_=0)),
        )
        .filter(
            eligible,
            *date_filters(Incident.resolved_at, start_date, end_date),
        )
        .group_by(day_expression, priority_expression)
        .all()
    )
    daily: dict[str, dict[str, int]] = {}
    by_day_priority: dict[str, dict[str, dict[str, int]]] = {}
    for day_value, priority_code, resp_total, resp_met, res_total, res_met in rows:
        day = day_value.isoformat() if hasattr(day_value, "isoformat") else str(day_value)
        totals = daily.setdefault(
            day,
            {
                "response_sample_count": 0,
                "response_met_count": 0,
                "resolution_sample_count": 0,
                "resolution_met_count": 0,
            },
        )
        counts = {
            "response_sample_count": int(resp_total or 0),
            "response_met_count": int(resp_met or 0),
            "resolution_sample_count": int(res_total or 0),
            "resolution_met_count": int(res_met or 0),
        }
        for key, value in counts.items():
            totals[key] += value
        by_day_priority.setdefault(day, {})[str(priority_code)] = counts

    trend = []
    for offset in range((end_date - start_date).days + 1):
        day = (start_date + timedelta(days=offset)).isoformat()
        totals = daily.get(
            day,
            {
                "response_sample_count": 0,
                "response_met_count": 0,
                "resolution_sample_count": 0,
                "resolution_met_count": 0,
            },
        )
        severity = {}
        for code in ("P1", "P2", "P3", "P4"):
            counts = by_day_priority.get(day, {}).get(
                code,
                {
                    "response_sample_count": 0,
                    "response_met_count": 0,
                    "resolution_sample_count": 0,
                    "resolution_met_count": 0,
                },
            )
            severity[code] = {
                "response_compliance_pct": percent(
                    counts["response_met_count"], counts["response_sample_count"]
                ),
                "resolution_compliance_pct": percent(
                    counts["resolution_met_count"], counts["resolution_sample_count"]
                ),
                "response_sample_count": counts["response_sample_count"],
                "resolution_sample_count": counts["resolution_sample_count"],
            }
        trend.append(
            {
                "date": day,
                "response_compliance_pct": percent(
                    totals["response_met_count"], totals["response_sample_count"]
                ),
                "resolution_compliance_pct": percent(
                    totals["resolution_met_count"], totals["resolution_sample_count"]
                ),
                "response_sample_count": totals["response_sample_count"],
                "resolution_sample_count": totals["resolution_sample_count"],
                "by_priority": severity,
            }
        )
    return {
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "trend": trend,
    }
