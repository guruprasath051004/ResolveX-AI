"""Database-backed dashboard metrics and explainable operational signals."""

from datetime import date, datetime, timedelta
from math import ceil
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, distinct, extract, func, or_
from sqlalchemy.orm import Session

from backend.api.auth import require_roles
from backend.database import get_db
from backend.models import (
    AgentRun,
    Approval,
    Asset,
    Incident,
    MCPToolCall,
    RoleEnum,
    User,
)
from backend.services.sla import (
    date_filters,
    iso_utc,
    percent,
    resolve_date_range,
    remaining_minutes,
    sla_risk,
    utc_now_naive,
)

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator))],
)

OPEN_STATUSES = ("open", "new", "assigned", "pending", "pending_approval", "awaiting_approval")
IN_PROGRESS_STATUSES = ("investigating", "in_progress", "in progress")
RESOLVED_STATUSES = ("resolved", "closed", "completed")
INACTIVE_STATUSES = ("resolved", "closed", "completed", "cancelled", "canceled")


def _day_text(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _date_series(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def _status_label(value: str | None) -> str:
    labels = {
        "in_progress": "In Progress",
        "in progress": "In Progress",
        "pending_approval": "Pending Approval",
        "awaiting_approval": "Awaiting Approval",
    }
    normalized = (value or "unknown").strip().lower()
    return labels.get(normalized, normalized.replace("_", " ").title())


def _trend_rows(
    db: Session,
    *,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, int], dict[str, int]]:
    start_at = datetime.combine(start_date, datetime.min.time())
    end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    incident_rows = (
        db.query(func.date(Incident.created_at), func.count(Incident.id))
        .filter(Incident.created_at >= start_at, Incident.created_at < end_at)
        .group_by(func.date(Incident.created_at))
        .all()
    )
    resolved_rows = (
        db.query(func.date(Incident.resolved_at), func.count(Incident.id))
        .filter(
            Incident.resolved_at >= start_at,
            Incident.resolved_at < end_at,
            Incident.resolved_at.is_not(None),
            func.lower(Incident.status).in_(RESOLVED_STATUSES),
        )
        .group_by(func.date(Incident.resolved_at))
        .all()
    )
    return (
        {_day_text(day): int(count) for day, count in incident_rows},
        {_day_text(day): int(count) for day, count in resolved_rows},
    )


@router.get("/dashboard")
def get_dashboard_metrics(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.support_engineer, RoleEnum.administrator)),
) -> dict[str, Any]:
    now = utc_now_naive()
    start_date, end_date = resolve_date_range(start_date, end_date, today=now.date())
    incident_filters = date_filters(Incident.created_at, start_date, end_date)
    normalized_status = func.lower(func.trim(Incident.status))
    normalized_priority = func.lower(func.trim(Incident.priority))
    resolved_condition = and_(
        normalized_status.in_(RESOLVED_STATUSES),
        Incident.resolved_at.is_not(None),
    )
    active_condition = normalized_status.notin_(INACTIVE_STATUSES)

    counts = (
        db.query(
            func.count(Incident.id),
            func.sum(case((normalized_status.in_(OPEN_STATUSES), 1), else_=0)),
            func.sum(case((normalized_status.in_(IN_PROGRESS_STATUSES), 1), else_=0)),
            func.sum(case((normalized_status.in_(RESOLVED_STATUSES), 1), else_=0)),
            func.sum(case((normalized_priority.in_(("critical", "p1")), 1), else_=0)),
        )
        .filter(*incident_filters)
        .one()
    )
    (
        total_incidents,
        open_incidents,
        in_progress_incidents,
        resolved_count,
        critical_count,
    ) = (int(value or 0) for value in counts)

    pending_approvals = db.query(Approval).filter(Approval.status == "pending").count()
    assigned_to_user = (
        db.query(Incident)
        .filter(Incident.assigned_to_user_id == current_user.id, active_condition)
        .count()
    )
    unassigned = (
        db.query(Incident)
        .filter(
            Incident.assigned_to_user_id.is_(None),
            Incident.assigned_team.is_(None),
            active_condition,
        )
        .count()
    )
    approaching_cutoff = now + timedelta(hours=1)
    approaching_sla = (
        db.query(Incident)
        .filter(
            active_condition,
            or_(
                and_(
                    Incident.response_due_at.is_not(None),
                    Incident.first_response_at.is_(None),
                    Incident.response_due_at >= now,
                    Incident.response_due_at <= approaching_cutoff,
                ),
                and_(
                    Incident.resolution_due_at.is_not(None),
                    Incident.resolution_due_at >= now,
                    Incident.resolution_due_at <= approaching_cutoff,
                ),
            ),
        )
        .count()
    )

    priority_label = case(
        (normalized_priority.in_(("critical", "p1")), "P1 Critical"),
        (normalized_priority.in_(("high", "p2")), "P2 High"),
        (normalized_priority.in_(("medium", "p3")), "P3 Medium"),
        (normalized_priority.in_(("low", "p4")), "P4 Low"),
        else_=func.coalesce(Incident.priority, "Unknown"),
    )
    priority_rows = (
        db.query(priority_label, func.count(Incident.id))
        .filter(*incident_filters)
        .group_by(priority_label)
        .all()
    )
    category_label = func.lower(func.trim(func.coalesce(Incident.category, "unknown")))
    category_rows = (
        db.query(category_label, func.count(Incident.id))
        .filter(*incident_filters)
        .group_by(category_label)
        .all()
    )
    status_group = case(
        (normalized_status.in_(IN_PROGRESS_STATUSES), "in_progress"),
        else_=normalized_status,
    )
    status_rows = (
        db.query(status_group, func.count(Incident.id))
        .filter(*incident_filters)
        .group_by(status_group)
        .all()
    )
    team_rows = (
        db.query(Incident.assigned_team, func.count(Incident.id))
        .filter(active_condition)
        .group_by(Incident.assigned_team)
        .all()
    )

    if db.bind.dialect.name == "sqlite":
        resolution_minutes = func.avg(
            (func.julianday(Incident.resolved_at) - func.julianday(Incident.created_at))
            * 24
            * 60
        )
    else:
        resolution_minutes = func.avg(
            extract("epoch", Incident.resolved_at - Incident.created_at) / 60.0
        )
    average_resolution = (
        db.query(resolution_minutes)
        .filter(
            resolved_condition,
            *date_filters(Incident.resolved_at, start_date, end_date),
        )
        .scalar()
    )

    sla_counts = (
        db.query(
            func.count(Incident.id),
            func.sum(case((Incident.response_due_at.is_not(None), 1), else_=0)),
            func.sum(
                case(
                    (
                        and_(
                            Incident.response_due_at.is_not(None),
                            Incident.first_response_at.is_not(None),
                            Incident.first_response_at <= Incident.response_due_at,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            func.sum(case((Incident.resolution_due_at.is_not(None), 1), else_=0)),
            func.sum(
                case(
                    (
                        and_(
                            Incident.resolution_due_at.is_not(None),
                            Incident.resolved_at <= Incident.resolution_due_at,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
        )
        .filter(
            resolved_condition,
            *date_filters(Incident.resolved_at, start_date, end_date),
        )
        .one()
    )
    (
        resolved_sample_count,
        response_sample_count,
        response_met_count,
        resolution_sample_count,
        resolution_met_count,
    ) = (int(value or 0) for value in sla_counts)

    response_compliance = percent(response_met_count, response_sample_count)
    resolution_compliance = percent(resolution_met_count, resolution_sample_count)
    sla_compliance = percent(
        response_met_count + resolution_met_count,
        response_sample_count + resolution_sample_count,
    )
    linked_resolutions = (
        db.query(func.count(distinct(Incident.id)))
        .join(AgentRun, AgentRun.incident_id == Incident.id)
        .filter(
            resolved_condition,
            func.lower(AgentRun.status) == "completed",
            *date_filters(Incident.resolved_at, start_date, end_date),
        )
        .scalar()
        or 0
    )
    automation_rate = percent(int(linked_resolutions), resolved_sample_count)
    active_agent_count = (
        db.query(func.count(distinct(AgentRun.agent_name)))
        .filter(AgentRun.status == "running")
        .scalar()
        or 0
    )

    trend_start = start_date or (now.date() - timedelta(days=6))
    trend_end = end_date or now.date()
    created_by_day, resolved_by_day = _trend_rows(
        db,
        start_date=trend_start,
        end_date=trend_end,
    )
    trend = [
        {
            "date": day,
            "incidents": created_by_day.get(day, 0),
            "resolved": resolved_by_day.get(day, 0),
        }
        for day in _date_series(trend_start, trend_end)
    ]

    response_candidate = and_(
        Incident.response_due_at.is_not(None),
        Incident.response_due_at <= approaching_cutoff,
        or_(
            Incident.first_response_at.is_(None),
            Incident.first_response_at > Incident.response_due_at,
        ),
    )
    resolution_candidate = and_(
        Incident.resolution_due_at.is_not(None),
        Incident.resolution_due_at <= approaching_cutoff,
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
    breach_candidates = (
        db.query(Incident)
        .filter(
            active_condition,
            or_(response_candidate, resolution_candidate),
        )
        .order_by(risk_deadline.asc())
        .limit(10)
        .all()
    )
    breaches = []
    for incident in breach_candidates:
        response_risk = sla_risk(
            incident.response_due_at,
            incident.first_response_at,
            now=now,
            at_risk_deadline=approaching_cutoff,
        )
        resolution_risk = sla_risk(
            incident.resolution_due_at,
            None,
            now=now,
            at_risk_deadline=approaching_cutoff,
        )
        risks = [risk for risk in (response_risk, resolution_risk) if risk]
        if not risks:
            continue
        breached = "breached" in risks
        relevant_deadlines = [
            due
            for due, risk in (
                (incident.response_due_at, response_risk),
                (incident.resolution_due_at, resolution_risk),
            )
            if due is not None and risk
        ]
        next_deadline = min(relevant_deadlines)
        breaches.append(
            {
                "id": incident.id,
                "title": f"INC-{incident.id:06d}: {incident.description.splitlines()[0][:100]}",
                "severity": incident.priority.upper(),
                "time_remaining_min": remaining_minutes(next_deadline, now),
                "status": incident.status,
                "response_risk": response_risk,
                "resolution_risk": resolution_risk,
            }
        )

    run_query = db.query(AgentRun)
    call_query = db.query(MCPToolCall)
    if start_date is not None:
        run_query = run_query.filter(AgentRun.started_at >= datetime.combine(start_date, datetime.min.time()))
        call_query = call_query.filter(MCPToolCall.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        exclusive_end = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        run_query = run_query.filter(AgentRun.started_at < exclusive_end)
        call_query = call_query.filter(MCPToolCall.created_at < exclusive_end)
    recent_runs = run_query.order_by(AgentRun.started_at.desc()).limit(8).all()
    activity_calls = call_query.order_by(MCPToolCall.created_at.desc()).limit(8).all()
    activity = [
        {
            "id": f"mcp-{call.id}",
            "action": f"{call.calling_agent or 'Agent'}: {call.tool_name}",
            "status": call.status,
            "duration_ms": call.duration_ms,
            "time": iso_utc(call.created_at),
            "summary": call.output_summary[:180] if call.output_summary else None,
        }
        for call in activity_calls
    ]

    return {
        "total_incidents": total_incidents,
        "assigned_incidents": assigned_to_user,
        "unassigned_incidents": unassigned,
        "open_incidents": open_incidents,
        "in_progress_incidents": in_progress_incidents,
        "resolved_incidents": resolved_count,
        "critical_incidents": critical_count,
        "approaching_sla_count": approaching_sla,
        "pending_approvals_count": pending_approvals,
        "average_resolution_time_min": (
            round(float(average_resolution), 1) if average_resolution is not None else None
        ),
        "sla_compliance_pct": sla_compliance,
        "sla_response_compliance_pct": response_compliance,
        "sla_resolution_compliance_pct": resolution_compliance,
        "sla_response_sample_count": response_sample_count,
        "sla_resolution_sample_count": resolution_sample_count,
        "sla_compliance_sample_count": response_sample_count + resolution_sample_count,
        "ai_automation_rate_pct": automation_rate,
        "ai_automation_sample_count": resolved_sample_count,
        "ai_automation_definition": (
            "Resolved incidents with a completed linked agent run divided by resolved incidents "
            "with recorded resolution timestamps; this is agent-linked, not proof of autonomous resolution."
        ),
        "active_agents_count": int(active_agent_count),
        "priority_distribution": [
            {"name": str(priority).title(), "value": int(count)}
            for priority, count in priority_rows
        ],
        "category_breakdown": [
            {"name": str(category).replace("_", " ").title(), "value": int(count)}
            for category, count in category_rows
        ],
        "status_distribution": [
            {"name": _status_label(status), "value": int(count)}
            for status, count in status_rows
        ],
        "team_workload": [
            {"team": team or "Unassigned", "active_incidents": int(count)}
            for team, count in team_rows
        ],
        "trend_chart": trend,
        "trend_date_range": {
            "start_date": trend_start.isoformat(),
            "end_date": trend_end.isoformat(),
        },
        "applied_date_range": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "activity_timeline": activity,
        "recent_agent_runs": [
            {
                "id": run.id,
                "agent_name": run.agent_name,
                "incident_id": run.incident_id,
                "status": run.status,
                "started_at": iso_utc(run.started_at),
                "finished_at": iso_utc(run.finished_at),
            }
            for run in recent_runs
        ],
        "sla_breaches": breaches,
    }


@router.get("/insights")
def get_operational_insights(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    now = utc_now_naive()
    start_date, end_date = resolve_date_range(
        start_date,
        end_date,
        today=now.date(),
        default_days=30,
    )
    if start_date is None or end_date is None:
        raise RuntimeError("Operational insight date range was not resolved.")
    current_filters = date_filters(Incident.created_at, start_date, end_date)
    period_days = (end_date - start_date).days + 1
    previous_start = start_date - timedelta(days=period_days)
    previous_end = start_date - timedelta(days=1)
    previous_filters = date_filters(Incident.created_at, previous_start, previous_end)
    insights: list[dict[str, Any]] = []

    current_volume = (
        db.query(func.count(Incident.id)).filter(*current_filters).scalar() or 0
    )
    previous_volume = (
        db.query(func.count(Incident.id)).filter(*previous_filters).scalar() or 0
    )
    if current_volume >= 2 and current_volume > previous_volume:
        insights.append(
            {
                "key": "incident-volume-increase",
                "kind": "volume",
                "severity": "warning",
                "title": "Incident volume increased",
                "explanation": (
                    f"{current_volume} incidents were created from {start_date.isoformat()} through "
                    f"{end_date.isoformat()}, compared with {previous_volume} in the preceding "
                    f"{period_days}-day period."
                ),
                "recommendation": "Review the affected categories and team capacity for this period.",
                "evidence": {
                    "current_count": int(current_volume),
                    "previous_count": int(previous_volume),
                    "period_days": period_days,
                },
            }
        )

    normalized_category = func.lower(func.trim(func.coalesce(Incident.category, "unknown")))

    def category_counts(filters: list[Any]) -> dict[str, int]:
        rows = (
            db.query(normalized_category, func.count(Incident.id))
            .filter(*filters)
            .group_by(normalized_category)
            .all()
        )
        return {str(category): int(count) for category, count in rows}

    current_categories = category_counts(current_filters)
    previous_categories = category_counts(previous_filters)
    for category, count in sorted(current_categories.items(), key=lambda item: (-item[1], item[0])):
        if count >= 2:
            insights.append(
                {
                    "key": f"recurring-category-{category}",
                    "kind": "recurrence",
                    "severity": "warning",
                    "title": f"Recurring category: {category.replace('_', ' ').title()}",
                    "explanation": f"{count} incidents in this date range share this category.",
                    "recommendation": "Review the common causes and whether an existing runbook addresses them.",
                    "evidence": {"category": category, "incident_count": count},
                }
            )
        prior_count = previous_categories.get(category, 0)
        if count >= 2 and count > prior_count:
            insights.append(
                {
                    "key": f"increasing-category-{category}",
                    "kind": "category-trend",
                    "severity": "warning",
                    "title": f"Category volume increased: {category.replace('_', ' ').title()}",
                    "explanation": (
                        f"{count} incidents were recorded in this period, compared with "
                        f"{prior_count} in the preceding {period_days}-day period."
                    ),
                    "recommendation": "Check for a shared service or asset issue before closing related incidents.",
                    "evidence": {
                        "category": category,
                        "current_count": count,
                        "previous_count": prior_count,
                        "period_days": period_days,
                    },
                }
            )

    active_status = func.lower(func.trim(Incident.status)).notin_(INACTIVE_STATUSES)
    team_rows = (
        db.query(Incident.assigned_team, func.count(Incident.id))
        .filter(active_status)
        .group_by(Incident.assigned_team)
        .all()
    )
    nonzero_team_counts = [int(count) for _, count in team_rows if count]
    average_team_workload = (
        sum(nonzero_team_counts) / len(nonzero_team_counts) if nonzero_team_counts else 0
    )
    team_threshold = (
        5
        if len(nonzero_team_counts) <= 1
        else max(5, ceil(average_team_workload * 1.5))
    )
    for team, count in team_rows:
        count = int(count)
        if count >= team_threshold:
            insights.append(
                {
                    "key": f"team-workload-{team or 'unassigned'}",
                    "kind": "team-workload",
                    "severity": "warning",
                    "title": f"High unresolved workload: {team or 'Unassigned'}",
                    "explanation": (
                        f"{count} active incidents are in this team's queue, above the "
                        f"data-based threshold of {team_threshold}."
                    ),
                    "recommendation": "Review assignment capacity and redistribute work if appropriate.",
                    "evidence": {
                        "team": team or "Unassigned",
                        "active_incidents": count,
                        "threshold": team_threshold,
                    },
                }
            )

    repeated_asset_rows = (
        db.query(Asset.id, Asset.serial_number, func.count(Incident.id))
        .join(Incident, Incident.asset_id == Asset.id)
        .filter(*current_filters)
        .group_by(Asset.id, Asset.serial_number)
        .having(func.count(Incident.id) >= 2)
        .order_by(func.count(Incident.id).desc(), Asset.serial_number.asc())
        .limit(5)
        .all()
    )
    for asset_id, serial_number, count in repeated_asset_rows:
        insights.append(
            {
                "key": f"repeated-asset-{asset_id}",
                "kind": "asset-pattern",
                "severity": "warning",
                "title": f"Repeated incidents on asset {serial_number}",
                "explanation": f"{int(count)} incidents in this period are linked to this asset.",
                "recommendation": "Inspect the asset's incident history for a recurring hardware or configuration issue.",
                "evidence": {
                    "asset_id": asset_id,
                    "serial_number": serial_number,
                    "incident_count": int(count),
                },
            }
        )

    cutoff = now + timedelta(minutes=60)
    response_risk = and_(
        Incident.response_due_at.is_not(None),
        Incident.response_due_at <= cutoff,
        or_(
            Incident.first_response_at.is_(None),
            Incident.first_response_at > Incident.response_due_at,
        ),
    )
    resolution_risk = and_(
        Incident.resolution_due_at.is_not(None),
        Incident.resolution_due_at <= cutoff,
    )
    due_filter = or_(response_risk, resolution_risk)
    due_count = (
        db.query(func.count(Incident.id))
        .filter(active_status, due_filter)
        .scalar()
        or 0
    )
    response_breached = and_(
        Incident.response_due_at.is_not(None),
        Incident.response_due_at < now,
        or_(
            Incident.first_response_at.is_(None),
            Incident.first_response_at > Incident.response_due_at,
        ),
    )
    resolution_breached = and_(
        Incident.resolution_due_at.is_not(None),
        Incident.resolution_due_at < now,
    )
    breached_count = (
        db.query(func.count(Incident.id))
        .filter(active_status, or_(response_breached, resolution_breached))
        .scalar()
        or 0
    )
    due_incidents = (
        db.query(Incident.id, Incident.response_due_at, Incident.resolution_due_at)
        .filter(active_status, due_filter)
        .order_by(
            func.coalesce(Incident.response_due_at, Incident.resolution_due_at).asc()
        )
        .limit(5)
        .all()
    )
    if due_count:
        insights.append(
            {
                "key": "sla-deadline-risk",
                "kind": "sla-risk",
                "severity": "critical" if breached_count else "warning",
                "title": f"{int(due_count)} active incidents have an SLA risk",
                "explanation": (
                    "These incidents have an unresolved or late response deadline, or a resolution "
                    "deadline that has passed or is within the next hour."
                ),
                "recommendation": "Review the SLA queue and escalate eligible breached incidents under existing policy.",
                "evidence": {
                    "incident_ids": [row.id for row in due_incidents],
                    "incident_count": int(due_count),
                    "shown_count": len(due_incidents),
                    "breached_count": int(breached_count),
                    "window_minutes": 60,
                },
            }
        )

    return {
        "source": "database-rules",
        "generated_at": iso_utc(now),
        "date_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "previous_start_date": previous_start.isoformat(),
            "previous_end_date": previous_end.isoformat(),
        },
        "insights": insights,
    }
