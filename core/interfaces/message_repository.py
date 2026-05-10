from abc import ABC, abstractmethod
from core.entities.message import Message


class MessageRepository(ABC):
    @abstractmethod
    def save(self, message: Message) -> bool:
        """Persists a single message."""

    @abstractmethod
    def get_recent(self, student_id: str, limit: int = 10) -> list[Message]:
        """Returns the most recent messages for a student, oldest first."""

    @abstractmethod
    def count(self, student_id: str) -> int:
        """Returns total message count for a student."""

    @abstractmethod
    def delete_oldest(self, student_id: str, count: int) -> bool:
        """Deletes the oldest N messages for a student."""

    @abstractmethod
    def delete_old_messages(self, student_id: str, messages: list) -> None:
        """Deletes a specific set of messages (used during history compression)."""
