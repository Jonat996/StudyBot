from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Student:
    id: str
    name: str
    phone: str
    channel: str = "whatsapp"
    personal_factor: float = 1.0
    profile: dict = field(default_factory=dict)
