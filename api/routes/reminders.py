from flask import Blueprint, jsonify, current_app
from datetime import date

bp_reminders = Blueprint("reminders", __name__)


@bp_reminders.get("/api/reminders/today")
def reminders_today():
    """
    Called by n8n every day at 7am (Mon-Sat).
    Returns today's study tasks for all active students.
    n8n iterates the list and sends each student a Telegram message.
    """
    try:
        container = current_app.container
        student_repo = container.student_repo()
        schedule_repo = container.schedule_repository()

        today = date.today()
        day_name = today.strftime("%A").lower()

        students = student_repo.get_all_active()
        reminders = []

        for student in students:
            schedule = schedule_repo.get_current_week(student.id)
            if not schedule:
                continue

            todays_slots = schedule.slots_by_day.get(day_name, [])
            if not todays_slots:
                continue

            reminders.append({
                "student_id": student.id,
                "student_name": student.name,
                "tasks": [
                    {
                        "subject": slot.get("subject", slot.get("materia", "")),
                        "hours": slot.get("hours", 1),
                        "priority": slot.get("priority", slot.get("nivel_riesgo", "Media")),
                        "tip": _get_tip(slot.get("priority", "Media")),
                    }
                    for slot in todays_slots
                ],
            })

        return jsonify({"reminders": reminders, "date": str(today), "day": day_name})

    except Exception as e:
        return jsonify({"error": str(e), "reminders": []}), 500


def _get_tip(priority: str) -> str:
    tips = {
        "Maxima": "¡Prioridad máxima! Empieza con esto hoy sin falta.",
        "Alta": "Tarea importante, no la dejes para el final del día.",
        "Media": "Recuerda tomar descansos de 10 min cada hora.",
        "Baja": "Buen momento para repasar con calma.",
    }
    return tips.get(priority, "¡Tú puedes! 💪")
