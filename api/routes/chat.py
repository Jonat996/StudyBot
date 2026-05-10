from flask import Blueprint, jsonify, request, current_app

chat_bp = Blueprint("chat", __name__)


@chat_bp.post("/api/chat")
def chat():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body is required"}), 400

    student_id = body.get("student_id")
    message = body.get("message", "").strip()

    if not student_id:
        return jsonify({"error": "Field 'student_id' is required"}), 400
    if not message:
        return jsonify({"error": "Field 'message' is required"}), 400

    use_case = current_app.container.process_message_use_case()
    result = use_case.execute(student_id=student_id, user_text=message)

    return jsonify(result)
