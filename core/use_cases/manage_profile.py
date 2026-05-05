from core.entities.student import Student
from core.interfaces.student_repository import StudentRepository

PROFILE_TEMPLATE = """
Nombre: {name}
Canal: {channel}
Factor personal: {personal_factor}
Horas disponibles: {available_hours}
Materias difíciles: {difficult_subjects}
Tasa de cumplimiento: {compliance_rate}
""".strip()


class ManageProfile:
    def __init__(self, repository: StudentRepository):
        self._repo = repository

    def get_or_create_student(self, phone: str, channel: str, name: str = "Estudiante") -> Student:
        student = self._repo.find_by_phone(phone)
        if student:
            return student
        return self._repo.create(name=name, phone=phone, channel=channel)

    def update_profile(self, student_id: str, updates: dict) -> bool:
        return self._repo.update_profile(student_id, updates)

    def get_context_for_llm(self, student_id: str) -> str:
        student = self._repo.find_by_id(student_id)
        if not student:
            return "Sin perfil previo."

        profile = student.profile
        return PROFILE_TEMPLATE.format(
            name=student.name,
            channel=student.channel,
            personal_factor=student.personal_factor,
            available_hours=profile.get("available_hours", "No definido"),
            difficult_subjects=", ".join(profile.get("difficult_subjects", [])) or "Ninguna",
            compliance_rate=profile.get("compliance_rate", "Sin datos"),
        )
