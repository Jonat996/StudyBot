from datetime import date
from core.entities.task import Task
from core.entities.schedule import Schedule
from core.interfaces.ml_predictor import MLPredictor

PRIORITY_ORDER = {"Maxima": 4, "Alta": 3, "Media": 2, "Baja": 1}
WEEK_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def _apply_priority_rules(task: Task) -> str:
    days = task.days_available or 999
    diff = task.difficulty

    if days < 3 and diff >= 4:
        return "Maxima"
    if days < 3:
        return "Alta"
    if days <= 5 and diff >= 4:
        return "Alta"
    if days <= 5:
        return "Media"
    return "Baja"


def _sort_key(task: Task) -> tuple:
    priority_score = PRIORITY_ORDER.get(task.priority or "Baja", 1)
    days = task.days_available or 999
    return (-priority_score, days)


class GeneratePlan:
    def __init__(self, predictor: MLPredictor, daily_study_hours: int = 8, max_day_load_pct: float = 0.40):
        self._predictor = predictor
        self._daily_hours = daily_study_hours
        self._max_load = max_day_load_pct

    def execute(self, tasks: list[Task], student_id: str = None, week: int = 1) -> tuple[list[Task], Schedule]:
        enriched = self._enrich_tasks(tasks)
        schedule = self._build_schedule(enriched, student_id, week)
        return enriched, schedule

    def _enrich_tasks(self, tasks: list[Task]) -> list[Task]:
        for task in tasks:
            task.predicted_hours = self._predictor.predict_time(task)
            compliance = self._predictor.predict_compliance(task)
            task.compliance_probability = compliance["probability"]
            task.priority = _apply_priority_rules(task)
        return tasks

    def _build_schedule(self, tasks: list[Task], student_id: str, week: int) -> Schedule:
        day_load: dict[str, float] = {d: 0.0 for d in WEEK_DAYS}
        slots_by_day: dict[str, list] = {d: [] for d in WEEK_DAYS}
        daily_limit = self._daily_hours * self._max_load

        sorted_tasks = sorted(tasks, key=_sort_key)

        for task in sorted_tasks:
            hours = task.predicted_hours or task.estimated_hours
            assigned = self._assign_to_day(task, hours, day_load, daily_limit, slots_by_day)
            if not assigned:
                least_loaded = min(WEEK_DAYS, key=lambda d: day_load[d])
                slots_by_day[least_loaded].append(self._slot(task, hours))
                day_load[least_loaded] += hours

        total_capacity = self._daily_hours * len(WEEK_DAYS)
        max_load_pct = (max(day_load.values()) / self._daily_hours) * 100 if self._daily_hours else 0

        return Schedule(
            student_id=student_id,
            week=week,
            slots_by_day=slots_by_day,
            max_day_load_pct=round(max_load_pct, 2),
        )

    def _assign_to_day(
        self,
        task: Task,
        hours: float,
        day_load: dict,
        daily_limit: float,
        slots_by_day: dict,
    ) -> bool:
        for day in WEEK_DAYS:
            if day_load[day] + hours <= daily_limit:
                slots_by_day[day].append(self._slot(task, hours))
                day_load[day] += hours
                return True
        return False

    def _slot(self, task: Task, hours: float) -> dict:
        return {
            "subject": task.subject,
            "hours": hours,
            "priority": task.priority,
            "compliance_probability": task.compliance_probability,
        }
