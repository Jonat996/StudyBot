from core.interfaces.llm_provider import LLMProvider

_NOT_IMPLEMENTED_MSG = "Switch LLM_PROVIDER env var to 'groq' and install groq package to use this provider"


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    def chat(self, messages: list[dict], system_prompt: str, temperature: float = 0.3) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def extract_entities(self, text: str, schema: dict) -> dict:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def compress_history(self, messages: list[dict]) -> str:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)

    def generate_embedding(self, text: str) -> list[float]:
        raise NotImplementedError(_NOT_IMPLEMENTED_MSG)
