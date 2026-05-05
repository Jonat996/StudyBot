from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Schedule:
    student_id: Optional[str]
    week: int
    slots_by_day: dict
    max_day_load_pct: float = 0.0
