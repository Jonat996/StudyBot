from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class IncomingMessage:
    sender_id: str
    text: str
    channel: str
    raw: dict


class MessagingProvider(ABC):
    @abstractmethod
    def parse_incoming(self, request_data: dict) -> IncomingMessage:
        """Parses a raw webhook payload into a normalized IncomingMessage."""

    @abstractmethod
    def send_message(self, recipient_id: str, text: str) -> bool:
        """Sends a text message to the given recipient."""

    @abstractmethod
    def build_response(self, text: str) -> tuple[str, int]:
        """Builds the HTTP response expected by the messaging platform."""
