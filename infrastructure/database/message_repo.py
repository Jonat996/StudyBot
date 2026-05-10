from core.entities.message import Message
from core.interfaces.message_repository import MessageRepository
from infrastructure.database.supabase_client import get_supabase_client


class SupabaseMessageRepository(MessageRepository):
    TABLE = "messages"

    def __init__(self, settings):
        self._db = get_supabase_client(settings.supabase_url, settings.supabase_key)

    def save(self, message: Message) -> bool:
        payload = {
            "student_id": message.student_id,
            "role": message.role,
            "content": message.content,
        }
        self._db.table(self.TABLE).insert(payload).execute()
        return True

    def get_recent(self, student_id: str, limit: int = 10) -> list[Message]:
        result = (
            self._db.table(self.TABLE)
            .select("*")
            .eq("student_id", student_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(reversed(result.data))
        return [self._to_entity(r) for r in rows]

    def count(self, student_id: str) -> int:
        result = (
            self._db.table(self.TABLE)
            .select("id", count="exact")
            .eq("student_id", student_id)
            .execute()
        )
        return result.count or 0

    def delete_oldest(self, student_id: str, count: int) -> bool:
        result = (
            self._db.table(self.TABLE)
            .select("id")
            .eq("student_id", student_id)
            .order("created_at", desc=False)
            .limit(count)
            .execute()
        )
        ids = [r["id"] for r in result.data]
        if ids:
            self._db.table(self.TABLE).delete().in_("id", ids).execute()
        return True

    def delete_old_messages(self, student_id: str, messages: list) -> None:
        ids = [m.id for m in messages if m.id]
        if ids:
            self._db.table(self.TABLE).delete().in_("id", ids).execute()

    def _to_entity(self, row: dict) -> Message:
        return Message(
            id=row["id"],
            student_id=row["student_id"],
            role=row["role"],
            content=row["content"],
        )
