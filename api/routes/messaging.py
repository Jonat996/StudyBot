from flask import Blueprint, request, current_app

messaging_bp = Blueprint("messaging", __name__)


@messaging_bp.post("/api/webhook/whatsapp")
def whatsapp_webhook():
    container = current_app.container
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
    reply = process_message.execute(student_id=student.id, user_text=incoming.text)

    provider.send_message(incoming.sender_id, reply)
    response_body, status_code = provider.build_response(reply)
    return response_body, status_code
