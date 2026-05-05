from abc import ABC, abstractmethod
from typing import Optional
from core.entities.student import Student


class StudentRepository(ABC):
    @abstractmethod
    def find_by_phone(self, phone: str) -> Optional[Student]:
        """Returns a student by phone number, or None if not found."""

    @abstractmethod
    def find_by_id(self, student_id: str) -> Optional[Student]:
        """Returns a student by UUID, or None if not found."""

    @abstractmethod
    def create(self, name: str, phone: str, channel: str) -> Student:
        """Creates and persists a new student record."""

    @abstractmethod
    def update_profile(self, student_id: str, updates: dict) -> bool:
        """Merges updates into the student's profile JSONB field."""
