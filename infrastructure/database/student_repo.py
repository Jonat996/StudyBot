from typing import Optional
from core.entities.student import Student
from core.interfaces.student_repository import StudentRepository
from infrastructure.database.supabase_client import get_supabase_client


class SupabaseStudentRepository(StudentRepository):
    TABLE = "students"

    def __init__(self, settings):
        self._db = get_supabase_client(settings.supabase_url, settings.supabase_key)

    def find_by_phone(self, phone: str) -> Optional[Student]:
        result = self._db.table(self.TABLE).select("*").eq("phone", phone).execute()
        if result.data:
            return self._to_entity(result.data[0])
        return None

    def find_by_id(self, student_id: str) -> Optional[Student]:
        result = self._db.table(self.TABLE).select("*").eq("id", student_id).execute()
        if result.data:
            return self._to_entity(result.data[0])
        return None

    def create(self, name: str, phone: str, channel: str) -> Student:
        payload = {"name": name, "phone": phone, "channel": channel}
        result = self._db.table(self.TABLE).insert(payload).execute()
        return self._to_entity(result.data[0])

    def update_profile(self, student_id: str, updates: dict) -> bool:
        existing = self.find_by_id(student_id)
        if not existing:
            return False
        merged_profile = {**existing.profile, **updates}
        self._db.table(self.TABLE).update({"profile": merged_profile}).eq("id", student_id).execute()
        return True

    def _to_entity(self, row: dict) -> Student:
        return Student(
            id=row["id"],
            name=row["name"],
            phone=row.get("phone", ""),
            channel=row.get("channel", "whatsapp"),
            personal_factor=float(row.get("personal_factor", 1.0)),
            profile=row.get("profile", {}),
        )
