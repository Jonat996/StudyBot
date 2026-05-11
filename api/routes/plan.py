from datetime import date
from flask import Blueprint, jsonify, request, current_app
from core.entities.task import Task
from infrastructure.ml.sklearn_predictor import MODEL_METRICS
from infrastructure.database.supabase_client import get_supabase_client
import logging

logger = logging.getLogger(__name__)

plan_bp = Blueprint("plan", __name__)


@plan_bp.post("/api/plan")
def generate_plan():
    body = request.get_json(silent=True)
    if not body or "tasks" not in body:
        return jsonify({"error": "Field 'tasks' is required"}), 400

    raw_tasks = body["tasks"]
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        return jsonify({"error": "tasks must be a non-empty list"}), 400

    try:
        tasks = [_parse_task(t, body.get("student_id")) for t in raw_tasks]
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"Invalid task data: {exc}"}), 400

    use_case = current_app.container.generate_plan_use_case()
    enriched, schedule = use_case.execute(
        tasks=tasks,
        student_id=body.get("student_id"),
        week=body.get("week", 1),
    )

    # Persist tasks and schedule to Supabase
    _persist_plan(body.get("student_id"), body.get("week", 1), enriched, schedule)

    return jsonify({
        "tasks": [_task_to_dict(t) for t in enriched],
        "schedule": schedule.slots_by_day,
        "max_day_load_pct": schedule.max_day_load_pct,
        "model_metrics": MODEL_METRICS,
    })


def _parse_task(raw: dict, student_id: str) -> Task:
    due_date_str = raw.get("due_date")
    due_date = date.fromisoformat(due_date_str) if due_date_str else date.today()
    return Task(
        subject=raw["subject"],
        difficulty=int(raw["difficulty"]),
        estimated_hours=float(raw["estimated_hours"]),
        due_date=due_date,
        student_id=student_id,
        days_available=raw.get("days_available"),
        origin=raw.get("origin", "api"),
    )


def _task_to_dict(task: Task) -> dict:
    return {
        "subject": task.subject,
        "difficulty": task.difficulty,
        "estimated_hours": task.estimated_hours,
        "predicted_hours": task.predicted_hours,
        "priority": task.priority,
        "compliance_probability": task.compliance_probability,
        "due_date": task.due_date.isoformat(),
        "days_available": task.days_available,
    }


def _persist_plan(student_id: str, week: int, tasks: list[Task], schedule):
    """Save enriched tasks and schedule to Supabase."""
    if not student_id:
        return
    try:
        settings = current_app.container._settings
        db = get_supabase_client(settings.supabase_url, settings.supabase_key)

        for t in tasks:
            db.table("tasks").insert({
                "student_id": student_id,
                "week": week,
                "subject": t.subject,
                "due_date": t.due_date.isoformat(),
                "difficulty": t.difficulty,
                "estimated_hours": t.estimated_hours,
                "days_available": t.days_available,
                "predicted_hours": t.predicted_hours,
                "priority": t.priority,
                "origin": t.origin or "chat",
            }).execute()

        db.table("schedules").insert({
            "student_id": student_id,
            "week": week,
            "slots_by_day": schedule.slots_by_day,
            "max_day_load_pct": schedule.max_day_load_pct,
        }).execute()
    except Exception as e:
        logger.error("Failed to persist plan: %s", e)
