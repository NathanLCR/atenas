"""Tests for the Atenas Click CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from app.cli import main
from core.db import init_db


def test_cli_help_renders() -> None:
    """CLI help should render without error."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Atenas" in result.output


def test_tui_command_launches_tui_entrypoint(monkeypatch) -> None:
    """tui should call the same entrypoint as `python -m app.tui`."""
    import app.tui.__main__ as tui_entrypoint

    calls: list[str] = []
    monkeypatch.setattr(tui_entrypoint, "run", lambda: calls.append("run"))

    runner = CliRunner()
    result = runner.invoke(main, ["tui"])

    assert result.exit_code == 0
    assert calls == ["run"]


def test_backup_command_creates_archive(settings) -> None:
    """backup should create an archive with temp settings."""
    init_db(settings.db_path)

    runner = CliRunner()
    with patch("app.cli.get_settings", return_value=settings):
        result = runner.invoke(main, ["backup"])

    assert result.exit_code == 0
    assert "Backup created:" in result.output
    assert list((settings.output_dir / "backups").glob("atenas-backup-*.zip"))


def test_restore_command_refuses_overwrite_without_force(settings) -> None:
    """restore should surface overwrite refusal as a command error."""
    init_db(settings.db_path)
    runner = CliRunner()
    with patch("app.cli.get_settings", return_value=settings):
        backup_result = runner.invoke(main, ["backup"])
    archive_path = backup_result.output.split("Backup created:", 1)[1].strip()

    with patch("app.cli.get_settings", return_value=settings):
        restore_result = runner.invoke(main, ["restore", archive_path])

    assert restore_result.exit_code != 0
    assert "already exists" in restore_result.output


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
