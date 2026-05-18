"""Application configuration loading for Atenas Core."""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_UNSET_OPTIONAL_SECRET_VALUES = {
    "YOUR_TELEGRAM_BOT_TOKEN_HERE",
    "YOUR_OPENAI_API_KEY_HERE",
    "YOUR_OPENROUTER_API_KEY_HERE",
    "YOUR_OPENROUTER_MODEL_HERE",
}


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "Atenas"
    app_version: str = "0.1.0"

    # IANA timezone for all wall-clock scheduling (shifts, classes, plans,
    # "today"/"this week" windows). Stored timestamps stay UTC ISO 8601;
    # only user-facing scheduling math is interpreted in this zone.
    timezone: str = "Europe/Dublin"

    telegram_bot_token: str | None = None
    telegram_allowed_user_ids: list[int] = Field(default_factory=list)

    data_dir: Path = Path("data")
    memory_dir: Path = Path("memory")
    output_dir: Path = Path("output")
    inbox_dir: Path = Path("inbox")
    logs_dir: Path = Path("logs")

    local_llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_small_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: int = 60

    cloud_llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None

    enable_cloud_fallback: bool = False
    max_cloud_cost_per_day_usd: float = 1.00
    max_cloud_calls_per_day: int = 50
    min_confidence_threshold: float = 0.65
    max_llm_retries: int = 2

    log_level: str = "INFO"

    @field_validator(
        "telegram_bot_token",
        "openai_api_key",
        "openrouter_api_key",
        "openrouter_model",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        """Treat empty or scaffolded env placeholders as unset optional settings."""

        if isinstance(value, str):
            value = value.strip()
            if value == "" or value.upper() in _UNSET_OPTIONAL_SECRET_VALUES:
                return None
            return value
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Fail fast on an invalid IANA timezone instead of much later."""

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Invalid IANA timezone: {value!r}") from exc
        return value

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: object) -> object:
        """Parse comma-separated Telegram IDs from environment variables."""

        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @property
    def db_path(self) -> Path:
        """Path to the SQLite operational database."""

        return self.data_dir / "atenas.sqlite"

    @property
    def actions_log_path(self) -> Path:
        """Path to the structured action/event JSONL log."""

        return self.logs_dir / "events.jsonl"

    @property
    def llm_log_path(self) -> Path:
        """Path to the structured LLM call JSONL log."""

        return self.logs_dir / "llm_calls.jsonl"

    @property
    def errors_log_path(self) -> Path:
        """Path to the structured error JSONL log."""

        return self.logs_dir / "errors.jsonl"

    @property
    def APP_NAME(self) -> str:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.app_name

    @property
    def APP_VERSION(self) -> str:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.app_version

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str | None:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.telegram_bot_token

    @property
    def TELEGRAM_ALLOWED_USER_IDS(self) -> list[int]:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.telegram_allowed_user_ids


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""

    return Settings()


def clear_settings_cache() -> None:
    """Clear the cached settings singleton. Useful for testing."""

    get_settings.cache_clear()
