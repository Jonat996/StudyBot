from flask import Blueprint, request, jsonify, current_app
from infrastructure.calendar.google_calendar import get_auth_url, exchange_code, create_events
from infrastructure.database.supabase_client import get_supabase_client
from datetime import datetime, timezone
import requests as http_requests
import logging

logger = logging.getLogger(__name__)

bp_calendar = Blueprint("calendar", __name__)


@bp_calendar.post("/api/auth/calendar/start")
def calendar_start():
    data = request.json or {}
    student_id = data.get("student_id")
    if not student_id:
        return jsonify({"error": "student_id required"}), 400

    settings = current_app.container._settings
    auth_url = get_auth_url(settings, student_id)
    return jsonify({"auth_url": auth_url, "student_id": student_id})


@bp_calendar.get("/auth/google/callback")
def calendar_callback():
    code = request.args.get("code")
    student_id = request.args.get("state")

    if not code or not student_id:
        return "<h2>❌ Error: faltan parámetros</h2>", 400

    try:
        settings = current_app.container._settings
        tokens = exchange_code(settings, code)

        db = get_supabase_client(settings.supabase_url, settings.supabase_key)
        db.table("google_tokens").upsert({
            "student_id": student_id,
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_at": tokens.get("expires_at"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        # Send Telegram confirmation to the student
        _notify_telegram_connected(settings, db, student_id)
        logger.info("OAuth callback successful for student %s", student_id)

        return """
        <html>
        <head><meta charset='utf-8'></head>
        <body style='font-family:sans-serif;text-align:center;padding:60px;background:#0D1117;color:white'>
          <h1>✅ Google Calendar conectado</h1>
          <p style='color:#1D9E75;font-size:20px'>¡Todo listo! Vuelve a Telegram.</p>
          <p style='color:#6B7280'>StudyBot ya puede crear eventos en tu calendario automáticamente.</p>
        </body>
        </html>
        """, 200

    except Exception as e:
        logger.error("OAuth callback failed: %s", e, exc_info=True)
        return f"<h2>❌ Error: {str(e)}</h2>", 500


@bp_calendar.post("/api/calendar/events")
def create_calendar_events():
    data = request.json or {}
    student_id = data.get("student_id")
    slots = data.get("schedule", {})
    available_schedule = data.get("available_schedule", {})

    if not student_id or not slots:
        return jsonify({"error": "student_id and schedule required"}), 400

    try:
        settings = current_app.container._settings
        db = get_supabase_client(settings.supabase_url, settings.supabase_key)

        result = db.table("google_tokens")\
            .select("*")\
            .eq("student_id", student_id)\
            .execute()

        if not result.data:
            return jsonify({
                "error": "calendar_not_connected",
                "message": "El estudiante no ha conectado su Google Calendar",
            }), 404

        tokens = result.data[0]
        count = create_events(tokens, slots, settings, available_schedule)
        logger.info("Created %d calendar events for student %s", count, student_id)
        return jsonify({"events_created": count, "student_id": student_id})

    except Exception as e:
        logger.error("Calendar events failed for student %s: %s", student_id, e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp_calendar.get("/api/calendar/status/<student_id>")
def calendar_status(student_id):
    try:
        settings = current_app.container._settings
        db = get_supabase_client(settings.supabase_url, settings.supabase_key)
        result = db.table("google_tokens")\
            .select("student_id, updated_at")\
            .eq("student_id", student_id)\
            .execute()
        return jsonify({
            "student_id": student_id,
            "calendar_connected": len(result.data) > 0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _notify_telegram_connected(settings, db, student_id: str):
    """Send a Telegram message confirming Calendar connection."""
    try:
        bot_token = settings.telegram_bot_token
        if not bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, skipping notification")
            return

        student = db.table("students").select("phone").eq("id", student_id).execute()
        if not student.data:
            logger.warning("Student %s not found for Telegram notification", student_id)
            return

        phone = student.data[0].get("phone", "")
        telegram_id = phone.replace("+57", "") if phone.startswith("+57") else phone
        logger.info("Sending Telegram notification to chat_id=%s", telegram_id)

        text = (
            "✅ *¡Google Calendar conectado exitosamente!*\n\n"
            "A partir de ahora, cada vez que genere un plan de estudio, "
            "las sesiones se agregarán automáticamente a tu calendario.\n\n"
            "_Cuéntame qué tienes que estudiar esta semana._"
        )
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = http_requests.post(url, json={
            "chat_id": telegram_id,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        logger.info("Telegram API response: %s %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("Failed to send Telegram calendar confirmation: %s", e)
