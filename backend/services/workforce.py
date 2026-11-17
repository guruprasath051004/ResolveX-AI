"""Workforce and Engineer Availability management for ResolveX USM."""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    AssignmentPolicy,
    EngineerAvailability,
    Incident,
    RoleEnum,
    User,
)

# Demo support engineers with diverse skillsets, availability, and teams
DEMO_ENGINEERS = [
    {
        "email": "support@resolvex.ai",
        "full_name": "Alex Rivera",
        "department": "Network Operations",
        "role": RoleEnum.support_engineer,
        "team": "Network Operations",
        "status": "on_leave",
        "working_schedule": "09:00 - 17:00 UTC",
        "leave_offset_days": (-1, 4),  # on leave starting yesterday for 5 days
        "skills": ["network", "vpn"],
        "max_active_tickets": 5,
        "notes": "Approved annual leave [Simulated]",
    },
    {
        "email": "support2@resolvex.ai",
        "full_name": "Sarah Chen",
        "department": "Network Operations",
        "role": RoleEnum.support_engineer,
        "team": "Network Operations",
        "status": "available",
        "working_schedule": "09:00 - 17:00 UTC",
        "leave_offset_days": None,
        "skills": ["network", "vpn", "server"],
        "max_active_tickets": 5,
        "notes": "Primary network operations on-shift engineer [Simulated]",
    },
    {
        "email": "support3@resolvex.ai",
        "full_name": "Marcus Vance",
        "department": "Platform Infrastructure",
        "role": RoleEnum.support_engineer,
        "team": "Platform Infrastructure",
        "status": "available",
        "working_schedule": "08:00 - 16:00 UTC",
        "leave_offset_days": None,
        "skills": ["server", "database", "network"],
        "max_active_tickets": 5,
        "notes": "Platform & systems infrastructure lead [Simulated]",
    },
    {
        "email": "support4@resolvex.ai",
        "full_name": "Elena Rostova",
        "department": "IT Desktop Support",
        "role": RoleEnum.support_engineer,
        "team": "IT Desktop Support",
        "status": "busy",
        "working_schedule": "09:00 - 17:00 UTC",
        "leave_offset_days": None,
        "skills": ["software", "hardware"],
        "max_active_tickets": 3,
        "notes": "Desktop support specialist, currently at capacity [Simulated]",
    },
    {
        "email": "support_mgr@resolvex.ai",
        "full_name": "David Kim",
        "department": "Support Management",
        "role": RoleEnum.support_engineer,
        "team": "Support Management",
        "status": "available",
        "working_schedule": "08:00 - 18:00 UTC",
        "leave_offset_days": None,
        "skills": ["escalation", "management", "network", "server", "software", "hardware", "vpn"],
        "max_active_tickets": 15,
        "notes": "Support Operations Manager & Escalation Authority [Simulated]",
    },
]


def get_or_create_default_policy(db: Session) -> AssignmentPolicy:
    """Ensure default assignment policy exists."""
    policy = db.query(AssignmentPolicy).filter(AssignmentPolicy.name == "default").first()
    if policy is None:
        policy = AssignmentPolicy(
            name="default",
            max_workload_per_engineer=5,
            max_reassignment_attempts=3,
            sla_at_risk_threshold_minutes=30,
            auto_escalate_on_no_engineer=True,
            require_skill_match=True,
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
    return policy


def seed_workforce(db: Session, force: bool = False) -> None:
    """Seed or update workforce records, schedules, skills, and availability."""
    now = datetime.utcnow()
    get_or_create_default_policy(db)

    # Password for demo accounts
    import os
    import bcrypt
    password = os.getenv("DEMO_SUPPORT_PASSWORD", "Demo123")
    hashed_pwd = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    for eng in DEMO_ENGINEERS:
        user = db.query(User).filter(User.email == eng["email"]).first()
        if user is None:
            user = User(
                email=eng["email"],
                hashed_password=hashed_pwd,
                role=eng["role"],
                full_name=eng["full_name"],
                department=eng["department"],
            )
            db.add(user)
            db.flush()
        else:
            if not user.full_name:
                user.full_name = eng["full_name"]
            if not user.department:
                user.department = eng["department"]

        # Availability record
        avail = db.query(EngineerAvailability).filter(EngineerAvailability.user_id == user.id).first()
        leave_start = None
        leave_end = None
        if eng["leave_offset_days"]:
            start_off, end_off = eng["leave_offset_days"]
            leave_start = now + timedelta(days=start_off)
            leave_end = now + timedelta(days=end_off)

        if avail is None:
            avail = EngineerAvailability(
                user_id=user.id,
                status=eng["status"],
                working_schedule=eng["working_schedule"],
                leave_start=leave_start,
                leave_end=leave_end,
                max_active_tickets=eng["max_active_tickets"],
                skills=json.dumps(eng["skills"]),
                team=eng["team"],
                is_simulated=True,
                notes=eng["notes"],
                updated_at=now,
            )
            db.add(avail)
        elif force:
            avail.status = eng["status"]
            avail.working_schedule = eng["working_schedule"]
            avail.leave_start = leave_start
            avail.leave_end = leave_end
            avail.max_active_tickets = eng["max_active_tickets"]
            avail.skills = json.dumps(eng["skills"])
            avail.team = eng["team"]
            avail.notes = eng["notes"]
            avail.is_simulated = True
            avail.updated_at = now

    db.commit()


def get_engineer_workload(db: Session, user_id: int) -> int:
    """Count active unresolved incidents assigned to this engineer."""
    active_statuses = {"open", "assigned", "investigating", "in_progress", "pending_approval"}
    count = (
        db.query(func.count(Incident.id))
        .filter(
            Incident.assigned_to_user_id == user_id,
            Incident.status.in_(active_statuses),
        )
        .scalar()
    )
    return int(count or 0)


def parse_working_hours(schedule_str: Optional[str]) -> Optional[Tuple[int, int, int, int]]:
    """Parse 'HH:MM - HH:MM UTC' into (start_h, start_m, end_h, end_m).
    Returns None if schedule cannot be parsed or is invalid.
    """
    if not schedule_str or not isinstance(schedule_str, str):
        return None
    try:
        parts = schedule_str.split("-")
        if len(parts) != 2:
            return None
        start_raw = parts[0].strip().split()[0]
        end_raw = parts[1].strip().split()[0]
        sh, sm = [int(v) for v in start_raw.split(":")]
        eh, em = [int(v) for v in end_raw.split(":")]
        if 0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59:
            return sh, sm, eh, em
    except Exception:
        return None
    return None


def is_within_working_hours(schedule_str: Optional[str], now: datetime) -> Tuple[bool, str]:
    """Check whether a given UTC datetime falls within the engineer's working hours."""
    hours = parse_working_hours(schedule_str)
    if not hours:
        # Invalid or unparseable schedule defaults safely to within hours with a note
        return True, "Schedule open or unspecified"
    sh, sm, eh, em = hours
    start_minutes = sh * 60 + sm
    end_minutes = eh * 60 + em
    current_minutes = now.hour * 60 + now.minute

    if start_minutes <= end_minutes:
        in_hours = start_minutes <= current_minutes <= end_minutes
    else:
        # Overnight shift spanning midnight
        in_hours = current_minutes >= start_minutes or current_minutes <= end_minutes

    if not in_hours:
        return False, f"Current time ({now.strftime('%H:%M')} UTC) is outside working hours ({schedule_str})"
    return True, "Within working hours"


def is_engineer_available(
    db: Session,
    user_id: int,
    now: Optional[datetime] = None,
    enforce_schedule: bool = False,
) -> Tuple[bool, str, Optional[EngineerAvailability]]:
    """Check whether a support engineer is currently eligible and available for incident assignment.
    
    Considers:
    - User account status and support_engineer role
    - Explicit availability status (available, on_leave, temporarily_unavailable, busy, shift_ended, outside_working_hours, inactive)
    - Approved leave periods
    - Configured workload thresholds
    - Working schedule when enforce_schedule=True
    """
    now = now or datetime.utcnow()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False, "User account not found", None
    if user.role != RoleEnum.support_engineer:
        return False, f"User has role '{user.role.value}', not support_engineer", None

    avail = db.query(EngineerAvailability).filter(EngineerAvailability.user_id == user_id).first()
    if not avail:
        workload = get_engineer_workload(db, user_id)
        if workload >= 5:
            return False, f"Engineer is at maximum workload capacity ({workload}/5)", None
        return True, "Available (default)", None

    # Check status enum
    status = (avail.status or "").lower()
    if status == "on_leave":
        return False, "Engineer is currently on approved leave", avail
    if status == "temporarily_unavailable":
        return False, "Engineer is temporarily unavailable", avail
    if status in ("shift_ended", "outside_working_hours"):
        return False, "Engineer is outside active working hours", avail
    if status == "busy":
        return False, "Engineer is currently busy with high-priority tasks", avail
    if status in ("inactive", "disabled"):
        return False, "Engineer account is inactive", avail

    # Check leave date range
    if avail.leave_start and avail.leave_end:
        if avail.leave_start <= now <= avail.leave_end:
            return False, "Engineer is within an approved leave schedule window", avail
    elif avail.leave_start and not avail.leave_end:
        if now >= avail.leave_start:
            return False, "Engineer is on leave starting from " + avail.leave_start.isoformat(), avail

    # Check schedule if explicitly requested
    if enforce_schedule and avail.working_schedule:
        in_schedule, sched_reason = is_within_working_hours(avail.working_schedule, now)
        if not in_schedule:
            return False, sched_reason, avail

    # Check workload limit
    current_workload = get_engineer_workload(db, user_id)
    if current_workload >= avail.max_active_tickets:
        return False, f"Engineer workload limit reached ({current_workload}/{avail.max_active_tickets})", avail

    return True, "Available", avail


def find_eligible_engineers(
    db: Session,
    category: str,
    priority: str = "medium",
    exclude_user_ids: Optional[List[int]] = None,
    preferred_team: Optional[str] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Find and rank all eligible support engineers based on skills, availability, and workload.
    
    Ranking factors:
    1. Direct technical skill match (e.g., 'vpn', 'network')
    2. Availability status
    3. Team membership match
    4. Workload balance (least loaded first)
    """
    now = now or datetime.utcnow()
    exclude_ids = set(exclude_user_ids or [])

    engineers = (
        db.query(User)
        .filter(User.role == RoleEnum.support_engineer)
        .all()
    )

    eligible = []
    category_lower = (category or "general").lower()

    for eng in engineers:
        if eng.id in exclude_ids:
            continue

        is_avail, reason, avail = is_engineer_available(db, eng.id, now=now)
        if not is_avail:
            continue

        if avail and avail.team == "Support Management" and preferred_team != "Support Management":
            continue

        skills_list = []
        team_name = "IT Service Desk"
        max_tickets = 5
        if avail:
            team_name = avail.team
            max_tickets = avail.max_active_tickets
            try:
                skills_list = json.loads(avail.skills) if avail.skills else []
            except Exception:
                skills_list = [avail.skills] if avail.skills else []

        workload = get_engineer_workload(db, eng.id)

        # Calculate matching score
        has_exact_skill = any(s.lower() == category_lower for s in skills_list)
        has_partial_skill = any(
            category_lower in s.lower() or s.lower() in category_lower
            for s in skills_list
        )
        is_same_team = (preferred_team is not None and team_name.lower() == preferred_team.lower())

        score = 0
        if has_exact_skill:
            score += 100
        elif has_partial_skill:
            score += 50
        else:
            score += 10  # general IT support eligibility

        if is_same_team:
            score += 30

        # Prioritize lower workload
        workload_penalty = workload * 5
        score -= workload_penalty

        eligible.append({
            "user_id": eng.id,
            "full_name": eng.full_name or eng.email,
            "email": eng.email,
            "team": team_name,
            "skills": skills_list,
            "current_workload": workload,
            "max_workload": max_tickets,
            "has_skill_match": has_exact_skill or has_partial_skill,
            "score": score,
        })

    # Sort descending by score
    eligible.sort(key=lambda x: x["score"], reverse=True)
    return eligible


def evaluate_assignment_decision(
    db: Session,
    category: str,
    priority: str = "medium",
    exclude_user_ids: Optional[List[int]] = None,
    preferred_team: Optional[str] = None,
    now: Optional[datetime] = None,
    policy_name: str = "default",
) -> Dict[str, Any]:
    """Produce a deterministic, structured assignment decision evaluation.
    
    Returns:
    - selected_engineer: Top-ranked candidate or None
    - eligible_candidates: Ranked list of all eligible engineers
    - matching_criteria: Configured weights and criteria
    - workload_evaluation: Map of engineer IDs to workload metrics
    - selection_reason: Explanation of selection or escalation need
    - rejected_candidates: List of evaluated engineers disqualified with reasons
    - applied_policy: Name and parameters of applied assignment policy
    """
    now = now or datetime.utcnow()
    policy = get_or_create_default_policy(db)
    exclude_ids = set(exclude_user_ids or [])

    engineers = (
        db.query(User)
        .filter(User.role == RoleEnum.support_engineer)
        .all()
    )

    eligible = []
    rejected = []
    workload_eval: Dict[str, Any] = {}
    category_lower = (category or "general").lower()

    for eng in engineers:
        workload = get_engineer_workload(db, eng.id)
        workload_eval[str(eng.id)] = {
            "name": eng.full_name or eng.email,
            "active_tickets": workload,
        }

        if eng.id in exclude_ids:
            rejected.append({
                "user_id": eng.id,
                "name": eng.full_name or eng.email,
                "reason": "Excluded from candidates (previously attempted or requested)",
            })
            continue

        is_avail, reason, avail = is_engineer_available(db, eng.id, now=now)
        if not is_avail:
            rejected.append({
                "user_id": eng.id,
                "name": eng.full_name or eng.email,
                "reason": reason,
            })
            continue

        skills_list = []
        team_name = "IT Service Desk"
        max_tickets = policy.max_workload_per_engineer
        if avail:
            team_name = avail.team
            max_tickets = avail.max_active_tickets
            try:
                skills_list = json.loads(avail.skills) if avail.skills else []
            except Exception:
                skills_list = [avail.skills] if avail.skills else []

        has_exact_skill = any(s.lower() == category_lower for s in skills_list)
        has_partial_skill = any(
            category_lower in s.lower() or s.lower() in category_lower
            for s in skills_list
        )

        if policy.require_skill_match and not (has_exact_skill or has_partial_skill):
            rejected.append({
                "user_id": eng.id,
                "name": eng.full_name or eng.email,
                "reason": f"Missing required skill for category '{category}'",
            })
            continue

        is_same_team = (preferred_team is not None and team_name.lower() == preferred_team.lower())

        score = 0
        if has_exact_skill:
            score += 100
        elif has_partial_skill:
            score += 50
        else:
            score += 10

        if is_same_team:
            score += 30

        score -= (workload * 10)

        candidate = {
            "user_id": eng.id,
            "full_name": eng.full_name or eng.email,
            "email": eng.email,
            "team": team_name,
            "skills": skills_list,
            "current_workload": workload,
            "max_workload": max_tickets,
            "has_skill_match": has_exact_skill or has_partial_skill,
            "score": score,
        }
        eligible.append(candidate)

    eligible.sort(key=lambda x: x["score"], reverse=True)
    selected = eligible[0] if eligible else None

    if selected:
        reason = (
            f"Selected {selected['full_name']} ({selected['team']}) with score {selected['score']} "
            f"based on skill match ({', '.join(selected['skills'])}) and workload capacity ({selected['current_workload']}/{selected['max_workload']})."
        )
    else:
        reason = f"No eligible engineer available matching category '{category}' within workload limits."

    return {
        "selected_engineer": selected,
        "eligible_candidates": eligible,
        "matching_criteria": {
            "exact_skill_weight": 100,
            "partial_skill_weight": 50,
            "team_match_weight": 30,
            "workload_penalty_per_ticket": 10,
            "require_skill_match": policy.require_skill_match,
        },
        "workload_evaluation": workload_eval,
        "selection_reason": reason,
        "rejected_candidates": rejected,
        "applied_policy": {
            "name": policy.name,
            "max_workload": policy.max_workload_per_engineer,
            "max_reassignments": policy.max_reassignment_attempts,
            "auto_escalate": policy.auto_escalate_on_no_engineer,
        },
    }

