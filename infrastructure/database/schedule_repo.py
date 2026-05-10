from core.interfaces.schedule_repository import ScheduleRepository
from infrastructure.database.supabase_client import get_supabase_client


class _Schedule:
    def __init__(self, slots_by_day: dict):
        self.slots_by_day = slots_by_day


class SupabaseScheduleRepository(ScheduleRepository):
    TABLE = "schedules"

    def __init__(self, settings):
        self._db = get_supabase_client(settings.supabase_url, settings.supabase_key)

    def get_current_week(self, student_id: str):
        result = self._db.table(self.TABLE)\
            .select("*")\
            .eq("student_id", student_id)\
            .order("generated_at", desc=True)\
            .limit(1)\
            .execute()
        if not result.data:
            return None
        return _Schedule(slots_by_day=result.data[0]["slots_by_day"])

    def save(self, student_id: str, week: int, slots_by_day: dict, max_load_pct: float):
        self._db.table(self.TABLE).insert({
            "student_id": student_id,
            "week": week,
            "slots_by_day": slots_by_day,
            "max_day_load_pct": max_load_pct,
        }).execute()
