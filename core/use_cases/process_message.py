import json
from datetime import date
from core.entities.message import Message
from core.entities.task import Task
from core.interfaces.llm_provider import LLMProvider
from core.interfaces.student_repository import StudentRepository
from core.interfaces.message_repository import MessageRepository
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


class ProcessMessage:
    def __init__(
        self,
        llm: LLMProvider,
        student_repo: StudentRepository,
        message_repo: MessageRepository,
        generate_plan: GeneratePlan,
        manage_profile: ManageProfile,
        history_window: int = 10,
        compression_threshold: int = 20,
    ):
        self._llm = llm
        self._student_repo = student_repo
        self._message_repo = message_repo
        self._generate_plan = generate_plan
        self._manage_profile = manage_profile
        self._history_window = history_window
        self._compression_threshold = compression_threshold

    def execute(self, student_id: str, user_text: str) -> str:
        history = self._message_repo.get_recent(student_id, self._history_window)
        profile_context = self._manage_profile.get_context_for_llm(student_id)
        student = self._student_repo.find_by_id(student_id)
        long_term_memory = student.profile.get("long_term_memory", "") if student else ""

        messages = self._build_message_list(history, user_text)
        system_prompt = self._build_system_prompt(profile_context, long_term_memory)

        raw_reply = self._llm.chat(messages, system_prompt)
        reply = self._handle_llm_reply(raw_reply, student_id)

        self._message_repo.save(Message(student_id=student_id, role="user", content=user_text))
        self._message_repo.save(Message(student_id=student_id, role="model", content=reply))

        self._maybe_compress_history(student_id)
        self._maybe_update_profile(student_id, user_text)

        return reply

    def _build_message_list(self, history: list[Message], user_text: str) -> list[dict]:
        messages = [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": user_text})
        return messages

    def _build_system_prompt(self, profile_context: str, long_term_memory: str) -> str:
        from infrastructure.llm.gemini_provider import STUDYBOT_SYSTEM_PROMPT
        return STUDYBOT_SYSTEM_PROMPT.format(
            profile=profile_context,
            long_term_memory=long_term_memory or "Sin conversaciones anteriores.",
        )

    def _handle_llm_reply(self, raw_reply: str, student_id: str) -> str:
        try:
            start = raw_reply.find("{")
            end = raw_reply.rfind("}") + 1
            if start == -1:
                return raw_reply

            payload = json.loads(raw_reply[start:end])
            if payload.get("action") != PLAN_ACTION:
                return raw_reply

            tasks = self._parse_tasks(payload.get("tasks", []), student_id)
            if not tasks:
                return raw_reply

            enriched, schedule = self._generate_plan.execute(tasks, student_id)
            return self._format_plan_response(enriched, schedule)
        except (json.JSONDecodeError, KeyError, ValueError):
            return raw_reply

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

    def _format_plan_response(self, tasks: list[Task], schedule) -> str:
        lines = ["Aqui esta tu plan de estudio:\n"]
        for day, slots in schedule.slots_by_day.items():
            if not slots:
                continue
            lines.append(f"*{day.capitalize()}*:")
            for slot in slots:
                lines.append(f"  - {slot['subject']}: {slot['hours']:.1f}h (prioridad: {slot['priority']})")
        lines.append(f"\nCarga maxima diaria: {schedule.max_day_load_pct:.1f}%")
        return "\n".join(lines)

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
        relevant = {k: v for k, v in extracted.items() if v is not None}
        if relevant:
            self._student_repo.update_profile(student_id, relevant)
