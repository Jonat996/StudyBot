from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.3,
    ) -> str:
        """Sends a conversation and returns the model's text response."""

    @abstractmethod
    def extract_entities(self, text: str, schema: dict) -> dict:
        """Extracts structured entities from free text using the given schema."""

    @abstractmethod
    def compress_history(self, messages: list[dict]) -> str:
        """Summarizes a list of messages into a compact memory string."""

    @abstractmethod
    def generate_embedding(self, text: str) -> list[float]:
        """Generates a vector embedding for semantic search."""
