"""Tests for the Atenas Click CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from app.cli import main


def test_cli_help_renders() -> None:
    """CLI help should render without error."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Atenas" in result.output


def test_doctor_succeeds_with_mocked_ollama(settings) -> None:
    """doctor should pass when all services are healthy."""
    from app.cli import main

    runner = CliRunner()
    with patch("app.cli.get_settings", return_value=settings):
        with patch("app.cli.OllamaEngine") as mock_engine:
            mock_instance = mock_engine.return_value
            mock_instance.health.return_value = type(
                "EngineHealth",
                (),
                {"available": True, "models": ["llama3.1:8b"], "error": None},
            )()
            result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0


def test_doctor_warns_empty_allowlist(tmp_path, monkeypatch) -> None:
    """doctor should warn when Telegram token present but allowlist empty."""
    from app.config import Settings
    from app.cli import main

    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        output_dir=tmp_path / "output",
        inbox_dir=tmp_path / "inbox",
        logs_dir=tmp_path / "logs",
        telegram_bot_token="fake:token",
        telegram_allowed_user_ids=[],
    )

    runner = CliRunner()
    with patch("app.cli.get_settings", return_value=settings):
        with patch("app.cli.OllamaEngine") as mock_engine:
            mock_instance = mock_engine.return_value
            mock_instance.health.return_value = type(
                "EngineHealth",
                (),
                {"available": True, "models": ["llama3.1:8b"], "error": None},
            )()
            result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "allowlist is empty" in result.output


def test_traces_handles_empty_db(tmp_path) -> None:
    """traces should handle empty database gracefully."""
    from app.config import Settings
    from app.cli import main
    from core.db import init_db

    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        output_dir=tmp_path / "output",
        inbox_dir=tmp_path / "inbox",
        logs_dir=tmp_path / "logs",
    )
    init_db(settings.db_path)

    runner = CliRunner()
    with patch("app.cli.get_settings", return_value=settings):
        result = runner.invoke(main, ["traces"])
    assert result.exit_code == 0
    assert "No agent traces found" in result.output
