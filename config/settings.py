from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    supabase_url: str
    supabase_key: str

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    messaging_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""
    telegram_bot_token: str = ""

    hf_repo_id: str = "studybot/models"
    regression_model_file: str = "modelo_studybot.pkl"
    classifier_model_file: str = "modelo_clasificacion.pkl"

    daily_study_hours: int = 8
    max_day_load_pct: float = 0.40
    history_window: int = 10
    compression_threshold: int = 20
