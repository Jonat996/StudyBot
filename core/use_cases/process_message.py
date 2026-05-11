import json
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Optional
from core.entities.message import Message
from core.entities.task import Task
from core.interfaces.llm_provider import LLMProvider
from core.interfaces.student_repository import StudentRepository
from core.interfaces.message_repository import MessageRepository
from core.interfaces.vector_store import VectorStore
from core.use_cases.generate_plan import GeneratePlan
from core.use_cases.manage_profile import ManageProfile

PLAN_ACTION = "generate_plan"
ENTITY_SCHEMA = {
    "subject": "str",
    "difficulty": "int (1-5)",
    "estimated_hours": "float",
    "due_date": "YYYY-MM-DD or null",
    "days_available": "int or null",
}

logger = logging.getLogger(__name__)


class ProcessMessage:
    def __init__(
        self,
        llm: LLMProvider,
        student_repo: StudentRepository,
        message_repo: MessageRepository,
        generate_plan: GeneratePlan,
        manage_profile: ManageProfile,
        vector_store: Optional[VectorStore] = None,
        history_window: int = 10,
        compression_threshold: int = 20,
    ):
        self._llm = llm
        self._student_repo = student_repo
        self._message_repo = message_repo
        self._generate_plan = generate_plan
        self._manage_profile = manage_profile
        self._vector_store = vector_store
        self._history_window = history_window
        self._compression_threshold = compression_threshold

    def execute(self, student_id: str, user_text: str) -> dict:
        history = self._message_repo.get_recent(student_id, self._history_window)
        profile_context = self._manage_profile.get_context_for_llm(student_id)
        student = self._student_repo.find_by_id(student_id)
        long_term_memory = student.profile.get("long_term_memory", "") if student else ""

        # RAG: search for relevant resources
        resources_context = self._search_resources(user_text)

        messages = self._build_message_list(history, user_text)
        system_prompt = self._build_system_prompt(profile_context, long_term_memory, resources_context)

        raw_reply = self._llm.chat(messages, system_prompt)
        result = self._handle_llm_reply(raw_reply, student_id)

        self._message_repo.save(Message(student_id=student_id, role="user", content=user_text))
        self._message_repo.save(Message(student_id=student_id, role="model", content=result["reply"]))

        self._maybe_compress_history(student_id)
        self._maybe_update_profile(student_id, user_text)

        return result

    def _build_message_list(self, history: list[Message], user_text: str) -> list[dict]:
        messages = [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": user_text})
        return messages

    def _build_system_prompt(self, profile_context: str, long_term_memory: str, resources_context: str = "") -> str:
        from infrastructure.llm.gemini_provider import STUDYBOT_SYSTEM_PROMPT

        # Current datetime in Bogota timezone (UTC-5)
        bogota_tz = timezone(timedelta(hours=-5))
        now_bogota = datetime.now(bogota_tz)
        day_names_es = {
            0: "lunes", 1: "martes", 2: "miércoles",
            3: "jueves", 4: "viernes", 5: "sábado", 6: "domingo",
        }
        month_names_es = {
            1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
            5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
            9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
        }
        current_datetime = (
            f"{day_names_es[now_bogota.weekday()]} {now_bogota.day} de "
            f"{month_names_es[now_bogota.month]} de {now_bogota.year}, "
            f"{now_bogota.strftime('%I:%M %p')} (hora Colombia)"
        )

        return STUDYBOT_SYSTEM_PROMPT.format(
            current_datetime=current_datetime,
            profile=profile_context,
            long_term_memory=long_term_memory or "Sin conversaciones anteriores.",
            resources=resources_context or "No se encontraron recursos relevantes para este mensaje.",
        )

    def _search_resources(self, user_text: str) -> str:
        """Search for relevant study resources using vector similarity."""
        if not self._vector_store:
            return ""
        try:
            results = self._vector_store.search(user_text, top_k=3)
            if not results:
                return ""
            pieces = []
            for r in results:
                title = r.get("title", "Sin titulo")
                content = r.get("content", "")[:500]
                url = r.get("url", "")
                resource_type = r.get("resource_type", "")
                entry = f"- [{resource_type}] {title}"
                if url:
                    entry += f"\n  URL: {url}"
                entry += f"\n  Contenido: {content}"
                pieces.append(entry)
            return "\n\n".join(pieces)
        except Exception as e:
            logger.error("RAG search failed: %s", e)
            return ""

    def _handle_llm_reply(self, raw_reply: str, student_id: str) -> dict:
        logger.info("Raw LLM reply (first 500 chars): %s", raw_reply[:500])
        try:
            # Strip markdown code fences that LLMs sometimes wrap around JSON
            cleaned = raw_reply.strip()
            if cleaned.startswith("```"):
                # Remove opening fence (```json or ```)
                first_newline = cleaned.find("\n")
                if first_newline != -1:
                    cleaned = cleaned[first_newline + 1:]
                # Remove closing fence
                if cleaned.rstrip().endswith("```"):
                    cleaned = cleaned.rstrip()[:-3].rstrip()

            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start == -1:
                return {"action": "collecting", "reply": raw_reply}

            payload = json.loads(cleaned[start:end])
            action = payload.get("action", "collecting")
            reply_text = payload.get("reply", raw_reply)

            # Safety: if reply_text is still JSON, try to extract the inner reply
            reply_text = self._extract_reply_text(reply_text)

            if action != PLAN_ACTION:
                return {"action": "collecting", "reply": reply_text}

            tasks = self._parse_tasks(payload.get("tasks", []), student_id)
            if not tasks:
                return {"action": "collecting", "reply": payload.get("reply", raw_reply)}

            # Extract per-day schedule from LLM or fall back to stored profile
            available_schedule = payload.get("available_schedule", {})
            schedule_source = "llm"
            if not available_schedule:
                student = self._student_repo.find_by_id(student_id)
                if student and student.profile.get("available_hours"):
                    available_schedule = student.profile["available_hours"]
                    schedule_source = "profile_fallback"
            logger.info("available_schedule source=%s data=%s", schedule_source, available_schedule)
            if available_schedule:
                # Save/refresh schedule to student profile for future use
                self._student_repo.update_profile(student_id, {
                    "available_hours": available_schedule,
                })

            enriched, schedule = self._generate_plan.execute(
                tasks, student_id, available_schedule=available_schedule
            )

            return {
                "action": "generate_plan",
                "reply": self._format_plan_reply(enriched, schedule),
                "schedule": schedule.slots_by_day,
                "tasks": [self._task_to_dict(t) for t in enriched],
                "available_schedule": available_schedule,
                "max_day_load_pct": schedule.max_day_load_pct,
                "model_metrics": {
                    "MAE": 0.567, "RMSE": 0.807,
                    "R2": 0.852, "F1": 0.900, "Accuracy": 0.825,
                },
            }
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("JSON parse failed: %s — extracting reply from raw", e)
            # Try to extract reply text even if full JSON parse failed
            reply_text = self._extract_reply_text(raw_reply)
            return {"action": "collecting", "reply": reply_text}

    @staticmethod
    def _extract_reply_text(text: str) -> str:
        """Extract plain reply text, handling nested JSON or raw JSON strings."""
        if not isinstance(text, str):
            return str(text)
        stripped = text.strip()
        # If it looks like JSON, try to extract the reply field
        if stripped.startswith("{"):
            try:
                inner = json.loads(stripped)
                if isinstance(inner, dict) and "reply" in inner:
                    return inner["reply"]
            except (json.JSONDecodeError, ValueError):
                pass
        return text

    def _parse_tasks(self, raw_tasks: list[dict], student_id: str) -> list[Task]:
        tasks = []
        for t in raw_tasks:
            due_date_raw = t.get("due_date")
            due_date = date.fromisoformat(due_date_raw) if due_date_raw else date.today()
            task = Task(
                subject=t["subject"],
                difficulty=int(t.get("difficulty", 3)),
                estimated_hours=float(t.get("estimated_hours", 2.0)),
                due_date=due_date,
                student_id=student_id,
                days_available=t.get("days_available"),
                origin="chat",
            )
            tasks.append(task)
        return tasks

    def _format_plan_reply(self, tasks: list, schedule) -> str:
        day_names = {
            "monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles",
            "thursday": "Jueves", "friday": "Viernes", "saturday": "Sábado",
        }
        priority_emoji = {"Maxima": "🔴", "Alta": "🟠", "Media": "🟡", "Baja": "🟢"}
        lines = ["📚 *Tu plan semanal está listo:*\n"]
        for day, slots in schedule.slots_by_day.items():
            if not slots:
                continue
            lines.append(f"*{day_names.get(day, day)}:*")
            for slot in slots:
                emoji = priority_emoji.get(slot.get("priority", "Media"), "📚")
                lines.append(f"  {emoji} {slot['subject']} — {slot['hours']:.1f}h")
        lines.append(f"\n📊 _Carga máxima por día: {schedule.max_day_load_pct:.1f}%_")
        return "\n".join(lines)

    def _task_to_dict(self, task) -> dict:
        return {
            "subject": task.subject,
            "difficulty": task.difficulty,
            "estimated_hours": task.estimated_hours,
            "predicted_hours": task.predicted_hours,
            "priority": task.priority,
            "compliance_probability": task.compliance_probability,
        }

    def _maybe_compress_history(self, student_id: str) -> None:
        total = self._message_repo.count(student_id)
        if total <= self._compression_threshold:
            return

        oldest = self._message_repo.get_recent(student_id, self._history_window)
        oldest_messages = [{"role": m.role, "content": m.content} for m in oldest]
        compressed = self._llm.compress_history(oldest_messages)

        student = self._student_repo.find_by_id(student_id)
        if student:
            self._student_repo.update_profile(student_id, {"long_term_memory": compressed})

        self._message_repo.delete_oldest(student_id, self._history_window)

    def _maybe_update_profile(self, student_id: str, user_text: str) -> None:
        profile_schema = {
            "available_hours": "dict of day -> list of time ranges",
            "difficult_subjects": "list of subject names",
            "compliance_rate": "float 0-1",
        }
        extracted = self._llm.extract_entities(user_text, profile_schema)
        # Never overwrite structured available_hours from generate_plan
        relevant = {k: v for k, v in extracted.items() if v is not None and k != "available_hours"}
        if relevant:
            self._student_repo.update_profile(student_id, relevant)
