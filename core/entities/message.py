from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    student_id: str
    role: str
    content: str
    created_at: Optional[datetime] = None
    id: Optional[str] = None
