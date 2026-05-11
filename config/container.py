from config.settings import Settings
from core.interfaces.llm_provider import LLMProvider
from core.interfaces.messaging_provider import MessagingProvider
from core.interfaces.ml_predictor import MLPredictor
from core.interfaces.vector_store import VectorStore
from core.interfaces.student_repository import StudentRepository
from core.interfaces.message_repository import MessageRepository
from core.interfaces.schedule_repository import ScheduleRepository
from core.use_cases.generate_plan import GeneratePlan
from core.use_cases.manage_profile import ManageProfile
from core.use_cases.process_message import ProcessMessage


class Container:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._llm: LLMProvider = None
        self._messaging: MessagingProvider = None
        self._predictor: MLPredictor = None
        self._vector_store: VectorStore = None
        self._student_repo: StudentRepository = None
        self._message_repo: MessageRepository = None
        self._schedule_repo: ScheduleRepository = None

    def llm(self) -> LLMProvider:
        if not self._llm:
            provider = self._settings.llm_provider
            if provider == "gemini":
                from infrastructure.llm.gemini_provider import GeminiProvider
                self._llm = GeminiProvider(self._settings.gemini_api_key)
            elif provider == "openai":
                from infrastructure.llm.openai_provider import OpenAIProvider
                self._llm = OpenAIProvider(self._settings.openai_api_key)
            elif provider == "groq":
                from infrastructure.llm.groq_provider import GroqProvider
                self._llm = GroqProvider(self._settings.groq_api_key)
            else:
                raise ValueError(f"Unknown LLM provider: {provider}")
        return self._llm

    def messaging(self) -> MessagingProvider:
        if not self._messaging:
            provider = self._settings.messaging_provider
            if provider == "twilio":
                from infrastructure.messaging.twilio_provider import TwilioProvider
                self._messaging = TwilioProvider(self._settings)
            elif provider == "telegram":
                from infrastructure.messaging.telegram_provider import TelegramProvider
                self._messaging = TelegramProvider(self._settings.telegram_bot_token)
            else:
                raise ValueError(f"Unknown messaging provider: {provider}")
        return self._messaging

    def predictor(self) -> MLPredictor:
        if not self._predictor:
            from infrastructure.ml.sklearn_predictor import SklearnPredictor
            self._predictor = SklearnPredictor(self._settings)
        return self._predictor

    def vector_store(self) -> VectorStore:
        if not self._vector_store:
            from infrastructure.vector.supabase_vector_store import SupabaseVectorStore
            self._vector_store = SupabaseVectorStore(self._settings, self.llm())
        return self._vector_store

    def student_repo(self) -> StudentRepository:
        if not self._student_repo:
            from infrastructure.database.student_repo import SupabaseStudentRepository
            self._student_repo = SupabaseStudentRepository(self._settings)
        return self._student_repo

    def message_repo(self) -> MessageRepository:
        if not self._message_repo:
            from infrastructure.database.message_repo import SupabaseMessageRepository
            self._message_repo = SupabaseMessageRepository(self._settings)
        return self._message_repo

    def schedule_repository(self) -> ScheduleRepository:
        if not self._schedule_repo:
            from infrastructure.database.schedule_repo import SupabaseScheduleRepository
            self._schedule_repo = SupabaseScheduleRepository(self._settings)
        return self._schedule_repo

    def generate_plan_use_case(self) -> GeneratePlan:
        return GeneratePlan(
            predictor=self.predictor(),
            daily_study_hours=self._settings.daily_study_hours,
            max_day_load_pct=self._settings.max_day_load_pct,
        )

    def manage_profile_use_case(self) -> ManageProfile:
        return ManageProfile(repository=self.student_repo())

    def process_message_use_case(self) -> ProcessMessage:
        return ProcessMessage(
            llm=self.llm(),
            student_repo=self.student_repo(),
            message_repo=self.message_repo(),
            generate_plan=self.generate_plan_use_case(),
            manage_profile=self.manage_profile_use_case(),
            vector_store=self.vector_store(),
            history_window=self._settings.history_window,
            compression_threshold=self._settings.compression_threshold,
        )
