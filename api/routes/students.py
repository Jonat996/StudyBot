from flask import Blueprint, jsonify, request, current_app

students_bp = Blueprint("students", __name__)


@students_bp.post("/api/students")
def create_or_get_student():
    body = request.get_json(silent=True)
    if not body or "phone" not in body:
        return jsonify({"error": "Field 'phone' is required"}), 400

    phone = body["phone"].strip()
    channel = body.get("channel", "whatsapp")
    name = body.get("name", "Estudiante")

    manage_profile = current_app.container.manage_profile_use_case()
    student = manage_profile.get_or_create_student(phone=phone, channel=channel, name=name)

    return jsonify({
        "id": student.id,
        "name": student.name,
        "phone": student.phone,
        "channel": student.channel,
        "personal_factor": student.personal_factor,
    })


@students_bp.get("/api/students/<student_id>/history")
def get_student_history(student_id: str):
    container = current_app.container
    db = container.student_repo()
    student = db.find_by_id(student_id)

    if not student:
        return jsonify({"error": "Student not found"}), 404

    supabase = container.student_repo()._db
    tasks = supabase.table("tasks").select("*").eq("student_id", student_id).order("created_at", desc=True).execute()
    schedules = supabase.table("schedules").select("*").eq("student_id", student_id).order("generated_at", desc=True).execute()

    return jsonify({
        "student_id": student_id,
        "tasks": tasks.data,
        "schedules": schedules.data,
    })
