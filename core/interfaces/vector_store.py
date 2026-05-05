from abc import ABC, abstractmethod
from typing import Optional


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, id: str, text: str, metadata: dict) -> bool:
        """Generates embedding and stores it with metadata."""

    @abstractmethod
    def search(
        self, query: str, top_k: int = 3, filters: Optional[dict] = None
    ) -> list[dict]:
        """Finds the top_k most semantically similar documents."""
