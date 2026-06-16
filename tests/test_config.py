"""Tests for Atenas settings loading."""

from pathlib import Path

import pytest

from app.config import Settings


def test_default_settings_load_without_env() -> None:
    """Default settings should be usable with no `.env` file."""

    settings = Settings(_env_file=None)

    assert settings.app_name == "Atenas"
    assert settings.min_confidence_threshold == 0.65
    assert settings.max_cloud_cost_per_day_usd == 1.00
    assert settings.max_cloud_calls_per_day == 50
    assert settings.telegram_allowed_user_ids == []
    assert settings.timezone == "Europe/Dublin"


def test_db_path_property_resolves_correctly(tmp_path: Path) -> None:
    """The db_path property should resolve inside data_dir."""

    settings = Settings(_env_file=None, data_dir=tmp_path / "data")

    assert settings.db_path == tmp_path / "data" / "atenas.sqlite"


def test_runtime_directories_cover_roots_without_duplicates(tmp_path: Path) -> None:
    """runtime_directories must include all roots and dedupe overlaps."""

    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        logs_dir=tmp_path / "logs",
        memory_dir=tmp_path / "memory",
        inbox_dir=tmp_path / "inbox",
        output_dir=tmp_path / "output",
        knowledge_file_roots=[tmp_path / "inbox", tmp_path / "memory"],
    )

    dirs = settings.runtime_directories

    assert tmp_path / "data" in dirs
    assert tmp_path / "logs" in dirs
    assert tmp_path / "inbox" in dirs
    assert tmp_path / "memory" in dirs
    assert tmp_path / "output" in dirs
    # inbox/memory appear in both the dir fields and knowledge_file_roots.
    assert len(dirs) == len(set(str(path) for path in dirs))


def test_single_numeric_telegram_user_id_is_accepted() -> None:
    """A single numeric Telegram ID should be normalized to a list."""

    settings = Settings(_env_file=None, telegram_allowed_user_ids=8552559127)

    assert settings.telegram_allowed_user_ids == [8552559127]


def test_valid_timezone_is_accepted() -> None:
    """A real IANA timezone should pass validation."""

    settings = Settings(_env_file=None, timezone="America/Sao_Paulo")

    assert settings.timezone == "America/Sao_Paulo"


def test_invalid_timezone_fails_fast() -> None:
    """A typo'd timezone should fail at settings construction (NFR-07)."""

    with pytest.raises(ValueError, match="Invalid IANA timezone"):
        Settings(_env_file=None, timezone="Europe/Lndon")


def test_timezone_is_declared_exactly_once() -> None:
    """Guard against the duplicate-field regression (second def silently wins)."""

    assert list(Settings.model_fields).count("timezone") == 1


def test_placeholder_telegram_bot_token_is_treated_as_unset() -> None:
    """Scaffolded Telegram token placeholders should not start the bot."""

    settings = Settings(_env_file=None, telegram_bot_token="YOUR_TELEGRAM_BOT_TOKEN_HERE")

    assert settings.telegram_bot_token is None


def test_ollama_small_model_falls_back_when_generation_model_is_unset() -> None:
    """Legacy OLLAMA_SMALL_MODEL env files should drive the active local model."""

    settings = Settings(_env_file=None, ollama_small_model="batiai/gemma4-e4b:q4")

    assert settings.ollama_model == "batiai/gemma4-e4b:q4"


def test_explicit_ollama_model_wins_over_small_model() -> None:
    """OLLAMA_MODEL remains the preferred explicit generation-model setting."""

    settings = Settings(
        _env_file=None,
        ollama_small_model="batiai/gemma4-e4b:q4",
        ollama_model="llama3.1:8b",
    )

    assert settings.ollama_model == "llama3.1:8b"
