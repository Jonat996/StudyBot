from abc import ABC, abstractmethod


class ScheduleRepository(ABC):
    @abstractmethod
    def get_current_week(self, student_id: str):
        """Returns the most recent schedule for the student."""

    @abstractmethod
    def save(self, student_id: str, week: int, slots_by_day: dict, max_load_pct: float):
        """Persists a generated schedule."""
