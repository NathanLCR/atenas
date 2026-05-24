"""Click-based CLI for Atenas operational tasks."""

from __future__ import annotations

import logging
import sys
import zipfile
from pathlib import Path

import click

from app.config import Settings, get_settings
from core.backup import BackupService
from core.db import get_connection, init_db
from core.llm.client import OllamaClient
from core.llm.engine import EngineHealth, OllamaEngine


logger = logging.getLogger(__name__)


@click.group()
def main() -> None:
    """Atenas — Telegram-first study assistant."""


@main.command()
def doctor() -> None:
    """Check system health: DB, config, Ollama, logs."""
    _run_doctor()


@main.command()
@click.option("--limit", default=20, type=int, help="Number of recent traces")
def traces(limit: int) -> None:
    """Show recent agent trace records."""
    _run_traces(limit)


@main.command()
def tui() -> None:
    """Launch the terminal TUI dashboard."""
    from app.tui.__main__ import main as tui_main
    tui_main()


@main.command()
@click.option("--include-logs", is_flag=True)
def backup(include_logs: bool) -> None:
    """Create a local backup archive."""
    settings = get_settings()
    archive_path = BackupService(settings).create_backup(include_logs=include_logs)
    click.echo(f"Backup created: {archive_path}")


@main.command()
@click.argument("archive_path")
@click.option("--force", is_flag=True)
def restore(archive_path: str, force: bool) -> None:
    """Restore a local backup archive."""
    settings = get_settings()
    try:
        BackupService(settings).restore_backup(Path(archive_path), force=force)
    except (FileExistsError, ValueError, zipfile.BadZipFile) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Backup restored.")


def _run_doctor() -> None:
    settings = get_settings()
    ok = True

    click.echo("Atenas Doctor")
    click.echo("=" * 40)

    # DB
    db_path = settings.db_path
    if db_path.exists():
        click.echo(f"  DB: {db_path} — OK")
    else:
        try:
            init_db(db_path)
            click.echo(f"  DB: {db_path} — initialized")
        except Exception as exc:
            click.echo(f"  DB: {db_path} — ERROR: {exc}")
            ok = False

    # Logs
    for name, log_path in [
        ("Events log", settings.actions_log_path),
        ("LLM log", settings.llm_log_path),
        ("Errors log", settings.errors_log_path),
    ]:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists():
            click.echo(f"  {name}: {log_path} — OK ({log_path.stat().st_size} bytes)")
        else:
            click.echo(f"  {name}: {log_path.parent}/ — dir OK, no file yet")

    # Local-only config
    if settings.allow_non_loopback_clients:
        click.echo("  WARNING: allow_non_loopback_clients is enabled — not local-only")
    else:
        click.echo("  Local-only guard: enabled — OK")

    # Telegram allowlist
    token = settings.telegram_bot_token
    allowed = settings.telegram_allowed_user_ids
    if token:
        if allowed:
            click.echo(f"  Telegram allowlist: {len(allowed)} user(s) — OK")
        else:
            click.echo("  WARNING: Telegram token present but allowlist is empty")
    else:
        click.echo("  Telegram: disabled (no token)")

    # Ollama
    engine = OllamaEngine(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout=settings.ollama_timeout_seconds,
    )
    health = engine.health()
    if health.available:
        click.echo(f"  Ollama: {settings.ollama_base_url} — OK")
        model_status = "available" if settings.ollama_model in health.models else "MISSING"
        click.echo(f"  Model {settings.ollama_model}: {model_status}")
        if health.models:
            click.echo(f"  Available models ({len(health.models)}): {', '.join(sorted(health.models))}")
    else:
        click.echo(f"  Ollama: {settings.ollama_base_url} — {health.error or 'unreachable'}")
        ok = False

    # Web tools
    web_enabled = getattr(settings, "enable_web_tools", False)
    click.echo(f"  Web tools: {'enabled' if web_enabled else 'disabled'}")

    click.echo()
    if ok:
        click.echo("All checks passed.")
    else:
        click.echo("Some checks failed — see above.")
        sys.exit(1)


def _run_traces(limit: int) -> None:
    settings = get_settings()
    db_path = settings.db_path

    if not db_path.exists():
        click.echo("No database found. Run `atenas doctor` first.")
        return

    try:
        from core.nl.traces import AgentTraceStore
        store = AgentTraceStore(db_path)
        rows = store.list_recent(limit=limit)
    except Exception as exc:
        click.echo(f"Error loading traces: {exc}")
        return

    if not rows:
        click.echo("No agent traces found.")
        return

    for row in rows:
        status_color = "OK" if row["status"] == "success" else row["status"].upper()
        tools = row.get("tool_call_count", "?")
        pending = row.get("pending_action_type") or ""
        click.echo(
            f"[{row['started_at'][:19]}] {status_color} "
            f"user={row['actor_user_id'] or '?'} "
            f"model={row['model'] or '?'} "
            f"tools={tools} "
            f"{pending}"
        )
        click.echo(f"  User: {row['user_message_summary'][:80]}")
        final = row.get("final_message_summary")
        if final:
            click.echo(f"  Reply: {final[:80]}")
        click.echo()
