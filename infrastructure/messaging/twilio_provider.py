from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from core.interfaces.messaging_provider import MessagingProvider, IncomingMessage


class TwilioProvider(MessagingProvider):
    def __init__(self, settings):
        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._from_number = settings.twilio_whatsapp_number

    def parse_incoming(self, request_data: dict) -> IncomingMessage:
        sender = request_data.get("From", "")
        text = request_data.get("Body", "").strip()
        return IncomingMessage(
            sender_id=sender,
            text=text,
            channel="whatsapp",
            raw=request_data,
        )

    def send_message(self, recipient_id: str, text: str) -> bool:
        try:
            self._client.messages.create(
                body=text,
                from_=self._from_number,
                to=recipient_id,
            )
            return True
        except Exception:
            return False

    def build_response(self, text: str) -> tuple[str, int]:
        response = MessagingResponse()
        response.message(text)
        return str(response), 200
