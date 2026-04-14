"""
Configuration management using pydantic-settings.
Loads environment variables from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    The app is intentionally tolerant of missing provider credentials so that
    individual channels can be enabled incrementally.
    """

    # OpenAI Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_HTTP_REFERER: str = ""
    OPENAI_APP_NAME: str = "Sabeel Homeo Clinic"

    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""
    TWILIO_VERIFY_SIGNATURE: bool = True

    # ElevenLabs Configuration (Text-to-Speech)
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    ELEVENLABS_MODEL_ID: str = "eleven_multilingual_v2"

    # Deepgram Configuration (Speech-to-Text)
    DEEPGRAM_API_KEY: str = ""

    # Meta/Facebook Configuration (WhatsApp/Messenger)
    META_PAGE_ACCESS_TOKEN: str = ""
    META_VERIFY_TOKEN: str = ""

    # Public base URL (used for webhook validation and static URLs)
    PUBLIC_BASE_URL: str = ""

    # CORS
    CORS_ALLOW_ORIGINS: str = "*"

    # Supabase Configuration
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Evolution API Configuration (WhatsApp Alternative - Baileys)
    WHATSAPP_API_URL: str = ""
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_INSTANCE_NAME: str = "sabeel_homeo"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def public_base_url(self) -> str:
        return self.PUBLIC_BASE_URL.rstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        raw = self.CORS_ALLOW_ORIGINS.strip()
        if not raw or raw == "*":
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def openai_enabled(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def openai_base_url(self) -> str:
        return self.OPENAI_BASE_URL.rstrip("/")

    @property
    def openai_default_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if "openrouter.ai" in self.openai_base_url:
            if self.OPENAI_HTTP_REFERER.strip():
                headers["HTTP-Referer"] = self.OPENAI_HTTP_REFERER.strip()
            if self.OPENAI_APP_NAME.strip():
                headers["X-Title"] = self.OPENAI_APP_NAME.strip()
        return headers

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN)

    @property
    def elevenlabs_enabled(self) -> bool:
        return bool(self.ELEVENLABS_API_KEY)

    @property
    def deepgram_enabled(self) -> bool:
        return bool(self.DEEPGRAM_API_KEY)

    @property
    def meta_enabled(self) -> bool:
        return bool(self.META_PAGE_ACCESS_TOKEN)

    @property
    def evolution_enabled(self) -> bool:
        return bool(self.WHATSAPP_API_URL and self.WHATSAPP_API_KEY)


settings = Settings()
