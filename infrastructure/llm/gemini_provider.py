import json
from google import genai
from google.genai import types
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
{long_term_memory}

FORMATO DE RESPUESTA INTERNO (solo para el sistema, no lo muestres al usuario):

Cuando te falte información, responde EXACTAMENTE así:
{{"action": "collecting", "reply": "<tu mensaje conversacional aquí>"}}

Cuando tengas materia + dificultad + horas_estimadas + días_disponibles, responde EXACTAMENTE así:
{{"action": "generate_plan", "tasks": [{{"subject": "...", "difficulty": N, "estimated_hours": N.N, "days_available": N}}]}}

IMPORTANTE:
- Responde SIEMPRE con JSON válido, sin texto adicional, sin markdown, sin backticks.
- "reply" debe estar en español, ser empático y natural.
- Si el estudiante menciona una fecha (ej: "el viernes"), calcula days_available desde hoy.
- Si no menciona dificultad, pregunta UNA sola cosa a la vez.
- Nunca asumas dificultad sin preguntar."""

MODEL = "gemini-2.5-flash"


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def chat(self, messages: list[dict], system_prompt: str, temperature: float = 0.3) -> str:
        history = [
            types.Content(
                role=m["role"] if m["role"] in ("user", "model") else "user",
                parts=[types.Part(text=m["content"])]
            )
            for m in messages[:-1]
        ]
        last_message = messages[-1]["content"]

        response = self._client.models.generate_content(
            model=MODEL,
            contents=history + [types.Content(role="user", parts=[types.Part(text=last_message)])],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            ),
        )
        return response.text

    def extract_entities(self, text: str, schema: dict) -> dict:
        schema_str = json.dumps(schema, ensure_ascii=False)
        prompt = (
            f"Extrae las siguientes entidades del texto. "
            f"Responde SOLO con un JSON valido con estas claves: {schema_str}\n"
            f"Si una entidad no esta presente, usa null.\n\nTexto: {text}"
        )
        response = self._client.models.generate_content(model=MODEL, contents=prompt)
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
        response = self._client.models.generate_content(model=MODEL, contents=prompt)
        return response.text

    def generate_embedding(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return response.embeddings[0].values
