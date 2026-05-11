from datetime import date
from core.entities.task import Task
from core.entities.schedule import Schedule
from core.interfaces.ml_predictor import MLPredictor

PRIORITY_ORDER = {"Maxima": 4, "Alta": 3, "Media": 2, "Baja": 1}
WEEK_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

# Translate Spanish day names to English
_ES_TO_EN = {
    "lunes": "monday", "martes": "tuesday", "miércoles": "wednesday",
    "miercoles": "wednesday", "jueves": "thursday", "viernes": "friday",
    "sábado": "saturday", "sabado": "saturday", "domingo": "sunday",
}


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


def _parse_hours(time_str: str) -> float:
    """Convert 'HH:MM' to decimal hours."""
    parts = time_str.split(":")
    return int(parts[0]) + int(parts[1]) / 60.0


class GeneratePlan:
    def __init__(self, predictor: MLPredictor, daily_study_hours: int = 8, max_day_load_pct: float = 0.40):
        self._predictor = predictor
        self._daily_hours = daily_study_hours
        self._max_load = max_day_load_pct

    def execute(self, tasks: list[Task], student_id: str = None, week: int = 1,
                available_schedule: dict = None) -> tuple[list[Task], Schedule]:
        enriched = self._enrich_tasks(tasks)
        schedule = self._build_schedule(enriched, student_id, week, available_schedule)
        return enriched, schedule

    def _enrich_tasks(self, tasks: list[Task]) -> list[Task]:
        for task in tasks:
            task.predicted_hours = self._predictor.predict_time(task)
            compliance = self._predictor.predict_compliance(task)
            task.compliance_probability = compliance["probability"]
            task.priority = _apply_priority_rules(task)
        return tasks

    def _build_schedule(self, tasks: list[Task], student_id: str, week: int,
                        available_schedule: dict = None) -> Schedule:
        # Normalize available_schedule keys to English
        if available_schedule:
            available_schedule = {
                _ES_TO_EN.get(k.lower(), k.lower()): v
                for k, v in available_schedule.items()
            }
            active_days = [d for d in WEEK_DAYS if d in available_schedule]
            if not active_days:
                active_days = list(available_schedule.keys())
        else:
            active_days = WEEK_DAYS

        # Calculate daily limits from available_schedule hours (or default)
        day_limits: dict[str, float] = {}
        for d in active_days:
            if available_schedule and d in available_schedule:
                sched = available_schedule[d]
                start_h = _parse_hours(sched["start"])
                end_h = _parse_hours(sched["end"])
                day_limits[d] = max(end_h - start_h, 0.5)  # actual available hours
            else:
                day_limits[d] = self._daily_hours * self._max_load

        day_load: dict[str, float] = {d: 0.0 for d in active_days}
        slots_by_day: dict[str, list] = {d: [] for d in active_days}

        sorted_tasks = sorted(tasks, key=_sort_key)

        for task in sorted_tasks:
            hours = task.predicted_hours or task.estimated_hours
            assigned = self._assign_to_day(task, hours, day_load, day_limits, slots_by_day, active_days)
            if not assigned:
                # Spread across days if task doesn't fit in one
                remaining = hours
                for d in active_days:
                    space = day_limits[d] - day_load[d]
                    if space > 0 and remaining > 0:
                        chunk = min(space, remaining)
                        slots_by_day[d].append(self._slot(task, chunk))
                        day_load[d] += chunk
                        remaining -= chunk
                if remaining > 0:
                    # Still leftover — put in least loaded day
                    least_loaded = min(active_days, key=lambda d: day_load[d])
                    slots_by_day[least_loaded].append(self._slot(task, remaining))
                    day_load[least_loaded] += remaining

        max_day_hours = max(day_limits.values()) if day_limits else self._daily_hours
        max_load_pct = (max(day_load.values()) / max_day_hours) * 100 if max_day_hours else 0

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
        day_limits: dict,
        slots_by_day: dict,
        active_days: list,
    ) -> bool:
        for day in active_days:
            if day_load[day] + hours <= day_limits[day]:
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
