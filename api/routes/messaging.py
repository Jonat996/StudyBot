# ─────────────────────────────────────────────────────────────
# DEPRECATED: Este endpoint era el webhook directo de Twilio.
# Con la integración de n8n, el canal de mensajería es manejado
# por n8n (Telegram / WhatsApp). Flask ahora solo expone JSON puro
# via /api/chat. Este código se conserva como referencia y fallback.
# Estado: DESHABILITADO — no conectar en producción por ahora.
# ─────────────────────────────────────────────────────────────
from flask import Blueprint, request, current_app, jsonify

messaging_bp = Blueprint("messaging", __name__)


@messaging_bp.post("/api/webhook/whatsapp")
def whatsapp_webhook():
    # DEPRECATED: ver comentario de módulo
    return jsonify({"status": "deprecated", "message": "Use /api/chat with n8n integration"}), 410

    container = current_app.container  # noqa: F401 — referencia, no se ejecuta
    provider = container.messaging()
    incoming = provider.parse_incoming(request.form.to_dict())

    manage_profile = container.manage_profile_use_case()
    student = manage_profile.get_or_create_student(
        phone=incoming.sender_id,
        channel=incoming.channel,
    )

    process_message = container.process_message_use_case()
    reply = process_message.execute(student_id=student.id, user_text=incoming.text)

    response_body, status_code = provider.build_response(reply)
    return response_body, status_code, {"Content-Type": "application/xml"}


@messaging_bp.post("/api/webhook/telegram")
def telegram_webhook():
    container = current_app.container
    provider = container.messaging()
    data = request.get_json(silent=True) or {}
    incoming = provider.parse_incoming(data)

    manage_profile = container.manage_profile_use_case()
    student = manage_profile.get_or_create_student(
        phone=incoming.sender_id,
        channel=incoming.channel,
    )

    process_message = container.process_message_use_case()
    result = process_message.execute(student_id=student.id, user_text=incoming.text)
    reply = result.get("reply", "") if isinstance(result, dict) else result

    provider.send_message(incoming.sender_id, reply)
    response_body, status_code = provider.build_response(reply)
    return response_body, status_code
