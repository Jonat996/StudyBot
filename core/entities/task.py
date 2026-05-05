from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Task:
    subject: str
    difficulty: int
    estimated_hours: float
    due_date: date
    student_id: Optional[str] = None
    days_available: Optional[int] = None
    predicted_hours: Optional[float] = None
    priority: Optional[str] = None
    compliance_probability: Optional[float] = None
    origin: str = "chat"
