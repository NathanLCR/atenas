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
