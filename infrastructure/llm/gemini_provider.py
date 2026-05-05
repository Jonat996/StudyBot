import json
import google.generativeai as genai
from core.interfaces.llm_provider import LLMProvider

STUDYBOT_SYSTEM_PROMPT = """Eres StudyBot, un asistente academico inteligente. Tu trabajo es ayudar a estudiantes universitarios a organizar su semana de estudio de forma optima.

COMPORTAMIENTO:
- Conversa en espanol de forma natural y empatica
- Extrae informacion de los mensajes del estudiante sin hacer preguntas redundantes
- Cuando tengas materia, dificultad, horas estimadas y fecha de entrega, genera el plan
- Si falta informacion, pregunta UNA sola cosa a la vez
- Nunca inventes predicciones — siempre usa los datos del modelo ML
- Recuerda todo lo que el estudiante te ha dicho en conversaciones anteriores

PARA GENERAR UN PLAN necesitas:
1. Materia o tema a estudiar
2. Dificultad percibida (1=muy facil, 5=muy dificil)
3. Horas que cree que necesita
4. Fecha de entrega o dias disponibles

CUANDO TENGAS TODO: responde con el JSON exacto:
{{"action": "generate_plan", "tasks": [...]}}

CUANDO FALTA INFO: responde conversacionalmente y pregunta lo que falta.

PERFIL DEL ESTUDIANTE:
{profile}

MEMORIA DE CONVERSACIONES ANTERIORES:
{long_term_memory}"""

ROLE_MAP = {"user": "user", "model": "model"}


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel("gemini-1.5-flash")
        self._embedding_model = "models/embedding-001"

    def chat(self, messages: list[dict], system_prompt: str, temperature: float = 0.3) -> str:
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=system_prompt,
        )
        history = [
            {"role": ROLE_MAP.get(m["role"], "user"), "parts": [m["content"]]}
            for m in messages[:-1]
        ]
        last_message = messages[-1]["content"]
        chat = model.start_chat(history=history)
        response = chat.send_message(
            last_message,
            generation_config=genai.GenerationConfig(temperature=temperature),
        )
        return response.text

    def extract_entities(self, text: str, schema: dict) -> dict:
        schema_str = json.dumps(schema, ensure_ascii=False)
        prompt = (
            f"Extrae las siguientes entidades del texto. "
            f"Responde SOLO con un JSON valido con estas claves: {schema_str}\n"
            f"Si una entidad no esta presente, usa null.\n\nTexto: {text}"
        )
        response = self._model.generate_content(prompt)
        try:
            raw = response.text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            return json.loads(raw[start:end]) if start != -1 else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def compress_history(self, messages: list[dict]) -> str:
        conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
        prompt = (
            "Resume la siguiente conversacion en un parrafo conciso que capture "
            "los datos importantes del estudiante: materias, fechas, disponibilidad, "
            "dificultades y compromisos mencionados.\n\n" + conversation
        )
        response = self._model.generate_content(prompt)
        return response.text

    def generate_embedding(self, text: str) -> list[float]:
        result = genai.embed_content(
            model=self._embedding_model,
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]
