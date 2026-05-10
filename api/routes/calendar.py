from flask import Blueprint, request, jsonify, current_app
from infrastructure.calendar.google_calendar import get_auth_url, exchange_code, create_events
from infrastructure.database.supabase_client import get_supabase_client
from datetime import datetime, timezone

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
        return f"<h2>❌ Error: {str(e)}</h2>", 500


@bp_calendar.post("/api/calendar/events")
def create_calendar_events():
    data = request.json or {}
    student_id = data.get("student_id")
    slots = data.get("schedule", {})

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
        count = create_events(tokens, slots, settings)
        return jsonify({"events_created": count, "student_id": student_id})

    except Exception as e:
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
