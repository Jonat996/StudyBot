from core.interfaces.messaging_provider import MessagingProvider, IncomingMessage

_NOT_IMPLEMENTED_MSG = "Switch MESSAGING_PROVIDER env var to 'telegram' and install python-telegram-bot to use this provider"


class TelegramProvider(MessagingProvider):
    def __init__(self, bot_token: str):
        self._bot_token = bot_token

    def parse_incoming(self, request_data: dict) -> IncomingMessage:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def send_message(self, recipient_id: str, text: str) -> bool:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def build_response(self, text: str) -> tuple[str, int]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
