from flask import Blueprint, jsonify, current_app
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

bp_dashboard = Blueprint("dashboard", __name__)


@bp_dashboard.get("/api/students/list")
def list_students():
    """Return all students (for student selector in frontend)."""
    container = current_app.container
    db = container.student_repo()
    students = db.get_all_active()
    return jsonify([
        {
            "id": s.id,
            "name": s.name,
            "phone": s.phone,
            "channel": s.channel,
        }
        for s in students
    ])


@bp_dashboard.get("/api/dashboard/<student_id>")
def get_dashboard(student_id: str):
    container = current_app.container
    db = container.student_repo()
    student = db.find_by_id(student_id)

    if not student:
        return jsonify({"error": "Student not found"}), 404

    supabase = db._db
    today = date.today().isoformat()

    # All tasks for this student
    tasks_res = (
        supabase.table("tasks")
        .select("*")
        .eq("student_id", student_id)
        .order("due_date")
        .execute()
    )
    all_tasks = tasks_res.data or []

    # Latest schedule
    schedule_res = (
        supabase.table("schedules")
        .select("*")
        .eq("student_id", student_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    latest_schedule = schedule_res.data[0] if schedule_res.data else None

    # Resources: get distinct subjects from tasks, then find matching resources
    subjects = list({t.get("subject", "") for t in all_tasks if t.get("subject")})
    resources = []
    if subjects:
        try:
            res = (
                supabase.table("resources")
                .select("id, title, subject, resource_type, url")
                .in_("subject", subjects)
                .limit(50)
                .execute()
            )
            resources = res.data or []
        except Exception as e:
            logger.error("Failed to fetch resources: %s", e)

    # Also fetch video resources broadly (they're useful for recommendations)
    try:
        video_res = (
            supabase.table("resources")
            .select("id, title, subject, resource_type, url")
            .eq("resource_type", "video")
            .limit(50)
            .execute()
        )
        # Merge without duplicates
        existing_ids = {r["id"] for r in resources}
        for v in (video_res.data or []):
            if v["id"] not in existing_ids:
                resources.append(v)
    except Exception as e:
        logger.error("Failed to fetch video resources: %s", e)

    # Calendar status
    try:
        cal_res = (
            supabase.table("google_tokens")
            .select("student_id, updated_at")
            .eq("student_id", student_id)
            .execute()
        )
        calendar_connected = len(cal_res.data) > 0
        calendar_connected_at = cal_res.data[0].get("updated_at") if cal_res.data else None
    except Exception:
        calendar_connected = False
        calendar_connected_at = None

    # Recent messages (last 20)
    try:
        msg_res = (
            supabase.table("messages")
            .select("role, content, created_at")
            .eq("student_id", student_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        recent_messages = list(reversed(msg_res.data or []))
    except Exception:
        recent_messages = []

    # Compute summary stats
    pending = [t for t in all_tasks if not t.get("completed")]
    completed = [t for t in all_tasks if t.get("completed")]
    overdue = [t for t in pending if t.get("due_date") and t["due_date"] < today]
    upcoming_7d = [
        t for t in pending
        if t.get("due_date")
        and today <= t["due_date"] <= (date.today() + timedelta(days=7)).isoformat()
    ]

    # Hours summary
    total_estimated = sum(t.get("estimated_hours", 0) or 0 for t in pending)
    total_predicted = sum(t.get("predicted_hours", 0) or 0 for t in pending)

    # Priority breakdown
    priority_counts = {}
    for t in pending:
        p = t.get("priority", "Sin prioridad") or "Sin prioridad"
        priority_counts[p] = priority_counts.get(p, 0) + 1

    # Subject breakdown (pending tasks)
    subject_counts = {}
    for t in pending:
        s = t.get("subject", "Otro") or "Otro"
        subject_counts[s] = subject_counts.get(s, 0) + 1

    # Profile info
    profile = student.profile or {}

    return jsonify({
        "student": {
            "id": student.id,
            "name": student.name,
            "phone": student.phone,
            "personal_factor": student.personal_factor,
            "profile": profile,
        },
        "summary": {
            "total_tasks": len(all_tasks),
            "pending": len(pending),
            "completed": len(completed),
            "overdue": len(overdue),
            "upcoming_7d": len(upcoming_7d),
            "total_estimated_hours": round(total_estimated, 1),
            "total_predicted_hours": round(total_predicted, 1),
        },
        "priority_breakdown": priority_counts,
        "subject_breakdown": subject_counts,
        "overdue_tasks": overdue,
        "upcoming_tasks": upcoming_7d,
        "pending_tasks": pending,
        "completed_tasks": completed,
        "latest_schedule": latest_schedule,
        "resources": resources,
        "calendar": {
            "connected": calendar_connected,
            "connected_at": calendar_connected_at,
        },
        "recent_messages": recent_messages,
    })
