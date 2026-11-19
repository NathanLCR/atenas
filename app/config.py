"""Application configuration loading for Atenas Core."""

import ipaddress
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


DEFAULT_OLLAMA_SMALL_MODEL = "llama3.2"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b"

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
    timezone: str = "UTC"

    telegram_bot_token: str | None = None
    telegram_allowed_user_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    notifications_chat_id: int | None = None
    deadline_alert_hours: int = Field(default=72, ge=1, le=336)
    notifications_enabled: bool = True

    data_dir: Path = Path("data")
    memory_dir: Path = Path("memory")
    output_dir: Path = Path("output")
    inbox_dir: Path = Path("inbox")
    logs_dir: Path = Path("logs")
    knowledge_file_roots: Annotated[list[Path], NoDecode] = Field(
        default_factory=lambda: [Path("inbox"), Path("memory")]
    )

    local_llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_small_model: str = DEFAULT_OLLAMA_SMALL_MODEL
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_timeout_seconds: int = 60

    agent_model_profile: str = "conservative"
    agent_context_window_tokens: int | None = None
    agent_prompt_token_budget: int | None = None
    agent_timeout_seconds: int | None = None
    agent_max_history_items: int | None = None
    agent_max_tools_per_turn: int | None = None
    agent_max_turn_iterations: int | None = None
    agent_strict_json: bool | None = None
    agent_temperature: float | None = None

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
    enable_web_tools: bool = False
    allow_external_ollama: bool = False
    allow_non_loopback_clients: bool = False
    # Narrow allowlist of private/loopback CIDRs whose peers may reach the
    # local-only API/dashboard (e.g. the Docker bridge gateway). Empty = none.
    trusted_client_networks: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Two short lines shown in the dashboard header stamp.
    dashboard_stamp_line1: str = "LOCAL STUDY DESK"
    dashboard_stamp_line2: str | None = None

    log_level: str = "INFO"

    @model_validator(mode="before")
    @classmethod
    def apply_legacy_ollama_small_model_fallback(cls, data: object) -> object:
        """Use OLLAMA_SMALL_MODEL as the generation model when OLLAMA_MODEL is unset.

        Early Atenas config examples exposed only OLLAMA_SMALL_MODEL. Current
        LLM call sites use OLLAMA_MODEL, so this preserves existing local env
        files without preventing an explicit OLLAMA_MODEL override.
        """

        if not isinstance(data, dict):
            return data
        values = dict(data)
        keys = {str(key).lower() for key in values}
        if "ollama_model" in keys:
            return values
        small_model = values.get("ollama_small_model") or values.get("OLLAMA_SMALL_MODEL")
        if isinstance(small_model, str) and small_model != DEFAULT_OLLAMA_SMALL_MODEL:
            values["ollama_model"] = small_model
        return values

    @field_validator(
        "telegram_bot_token",
        "openai_api_key",
        "openrouter_api_key",
        "openrouter_model",
        "notifications_chat_id",
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

    @field_validator("trusted_client_networks", mode="before")
    @classmethod
    def parse_trusted_client_networks(cls, value: object) -> object:
        """Parse and validate trusted CIDRs: private/loopback only, never any-address."""

        if value is None or value == "":
            return []
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if not isinstance(value, (list, tuple)):
            raise ValueError("TRUSTED_CLIENT_NETWORKS must be a comma-separated list of CIDRs")
        normalized: list[str] = []
        for item in value:
            try:
                network = ipaddress.ip_network(str(item).strip(), strict=False)
            except ValueError as exc:
                raise ValueError(f"Invalid trusted client network: {item!r}") from exc
            if network.prefixlen == 0:
                raise ValueError(f"Trusted client network too broad: {item!r}")
            if not (network.is_private or network.is_loopback) or network.is_unspecified:
                raise ValueError(
                    f"Trusted client network must be private or loopback: {item!r}"
                )
            normalized.append(str(network))
        return normalized

    @field_validator("telegram_allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: object) -> object:
        """Parse comma-separated Telegram IDs from environment variables."""

        if value is None or value == "":
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @field_validator("knowledge_file_roots", mode="before")
    @classmethod
    def parse_knowledge_file_roots(cls, value: object) -> object:
        """Parse comma-separated allowed file roots from environment variables."""

        if value is None or value == "":
            return [Path("inbox"), Path("memory")]
        if isinstance(value, str):
            if value.strip().startswith("["):
                return [Path(item) for item in json.loads(value)]
            return [Path(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_local_egress_settings(self) -> "Settings":
        """Reject non-loopback Ollama URLs unless explicitly opted in."""
        parsed = urlparse(self.ollama_base_url)
        host = parsed.hostname
        if host and not self.allow_external_ollama and not _is_loopback_host(host):
            raise ValueError(
                "Refusing non-loopback Ollama URL without allow_external_ollama=true."
            )
        return self

    @property
    def runtime_directories(self) -> list[Path]:
        """Runtime directories that must exist before services start.

        Includes the configured data/logs/memory/inbox/output roots plus any
        knowledge file roots, deduplicated while preserving order. A fresh
        checkout omits these gitignored directories, so startup and `atenas
        doctor` create them before constructing services that require them.
        """

        candidates = [
            self.data_dir,
            self.logs_dir,
            self.memory_dir,
            self.inbox_dir,
            self.output_dir,
            *self.knowledge_file_roots,
        ]
        seen: set[str] = set()
        ordered: list[Path] = []
        for path in candidates:
            key = str(path)
            if key not in seen:
                seen.add(key)
                ordered.append(path)
        return ordered

    @property
    def trusted_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        """Parsed trusted client networks."""

        return [ipaddress.ip_network(item) for item in self.trusted_client_networks]

    @property
    def dashboard_stamp_lines(self) -> tuple[str, str]:
        """Header stamp lines: configured, else app name and timezone city."""

        line1 = self.dashboard_stamp_line1.strip() or self.app_name.upper()
        line2 = self.dashboard_stamp_line2
        if line2 is None:
            city = self.timezone.rsplit("/", 1)[-1].replace("_", " ")
            line2 = city
        return line1, line2.strip()

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

    @property
    def NOTIFICATIONS_CHAT_ID(self) -> int | None:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.notifications_chat_id

    @property
    def NOTIFICATIONS_ENABLED(self) -> bool:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.notifications_enabled

    @property
    def DEADLINE_ALERT_HOURS(self) -> int:
        """Compatibility alias for brief-style uppercase settings access."""

        return self.deadline_alert_hours

    def get_model_profile(self) -> "core.nl.model_profiles.ModelProfile":
        """Return the effective model profile, merged with overrides."""
        from core.nl.model_profiles import get_profile

        profile = get_profile(self.agent_model_profile)
        overrides = {}
        if self.agent_context_window_tokens is not None:
            overrides["context_window_tokens"] = self.agent_context_window_tokens
        if self.agent_prompt_token_budget is not None:
            overrides["prompt_token_budget"] = self.agent_prompt_token_budget
        if self.agent_timeout_seconds is not None:
            overrides["timeout_seconds"] = self.agent_timeout_seconds
        if self.agent_max_history_items is not None:
            overrides["max_history_items"] = self.agent_max_history_items
        if self.agent_max_tools_per_turn is not None:
            overrides["max_tools_per_turn"] = self.agent_max_tools_per_turn
        if self.agent_max_turn_iterations is not None:
            overrides["max_turn_iterations"] = self.agent_max_turn_iterations
        if self.agent_strict_json is not None:
            overrides["strict_json"] = self.agent_strict_json
        if self.agent_temperature is not None:
            overrides["temperature"] = self.agent_temperature

        if overrides:
            return profile.model_copy(update=overrides)
        return profile


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""

    return Settings()


def clear_settings_cache() -> None:
    """Clear the cached settings singleton. Useful for testing."""

    get_settings.cache_clear()


def _is_loopback_host(host: str) -> bool:
    """Return whether a hostname is a loopback address."""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        import ipaddress
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
