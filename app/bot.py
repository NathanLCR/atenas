"""Telegram bot integration for Atenas."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from core.academic.models import Assignment, TimeBlock
from core.academic.service import AcademicService
from core.academic.validators import parse_kv_args, parse_weekday, validate_hours, validate_priority, validate_status
from core.knowledge.service import KnowledgeService
from core.llm.service import LLMService
from core.notifications.service import NotificationService, seconds_until, seconds_until_weekday
from core.retrieval.models import NO_SOURCE_FALLBACK
from core.retrieval.service import RetrievalService
from skills.status import handler as status_handler

if TYPE_CHECKING:
    from telegram import Bot
    from telegram import Update
    from telegram.ext import Application, ContextTypes

    from core.academic.models import Assignment, TimeBlock

logger = logging.getLogger(__name__)

ASK_NOTES_USAGE = (
    'Usage: /ask_notes q="transformers attention" '
    "[module=module_id] [assignment=assignment_id] [limit=5]"
)
ASK_NOTE_USAGE = 'Usage: /ask_note note=12 q="what is the main idea?" [limit=5]'
SOURCES_USAGE = (
    'Usage: /sources q="citation grounding" '
    "[module=module_id] [assignment=assignment_id] [limit=8]"
)


class AllowlistFilter:
    """Allow only configured Telegram user IDs through to handlers.

    This is the primary security boundary for the bot. All commands are
    registered with this filter. Updates from non-allowed users are
    silently dropped with a warning log.
    """

    def __init__(self, allowed_user_ids: Sequence[int] | None = None) -> None:
        self._allowed_user_ids = set(allowed_user_ids) if allowed_user_ids is not None else None

    def check_update(self, update: Update) -> bool:
        """Return whether the update should be handled."""

        return self.filter(update)

    def filter(self, update: Update) -> bool:
        """Return whether the update's effective user is allowed."""

        user = update.effective_user
        user_id = user.id if user is not None else None
        allowed_user_ids = self._allowed_user_ids
        if allowed_user_ids is None:
            allowed_user_ids = set(get_settings().TELEGRAM_ALLOWED_USER_IDS)
        if user_id is not None and user_id in allowed_user_ids:
            return True
        logger.warning(
            "blocked_telegram_update",
            extra={"event_type": "blocked_telegram_update", "user_id": user_id},
        )
        return False


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /ping."""

    await _reply(update, "pong")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /status with the formatted status skill output."""

    await _reply(update, _get_status_text())


async def skills_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /skills with the formatted skill listing."""

    await _reply(update, _get_skills_text())


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /today with today's deterministic schedule overview."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    await _reply(update, _format_today(service.get_today_overview()))


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /week with a deterministic weekly schedule summary."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    await _reply(update, _format_week(service.get_week_overview()))


async def deadlines_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /deadlines with upcoming open academic deadlines."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    await _reply(update, _format_deadlines(service.list_upcoming_assignments(limit=10)))


async def availability_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /availability with today's available study windows."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    await _reply(update, _format_availability(service.get_today_overview().availability))


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /plan with the deterministic weekly study plan."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    await _reply(update, _format_plan(service.get_study_plan()))


async def study_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /study with the next deterministic study recommendation."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    plan = service.get_study_plan()
    await _reply(
        update,
        _format_study_recommendation(
            today_block=service.get_today_study_recommendation(),
            next_block=service.get_next_study_recommendation(),
            plan=plan,
        ),
    )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to an allowlisted but unknown Telegram command."""

    logger.debug("unknown_telegram_command")
    await _reply(update, "Unknown command. Try /ping, /status, or /skills.")


async def add_module_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a study module via key-value arguments."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)

    name = args.get("name") or _extract_first_arg(text)
    if not name:
        await _reply(update, 'Usage: /add_module name="Deep Learning" code="DL"')
        return

    result = service.add_module(
        name=name,
        code=args.get("code"),
        lecturer=args.get("lecturer"),
        notes=args.get("notes"),
    )
    await _reply(update, result.message)


async def add_class_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a weekly class session via key-value arguments."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)

    title = args.get("title")
    day = args.get("day")
    start = args.get("start")
    end = args.get("end")

    if not all([title, day, start, end]):
        await _reply(update, 'Usage: /add_class title="DL" day=mon start=10:00 end=12:00 module=1')
        return

    weekday = parse_weekday(day)
    if weekday is None:
        await _reply(update, "Invalid weekday. Use 0-6 or mon/tue/wed/thu/fri/sat/sun.")
        return

    module_id = args.get("module")
    result = service.add_class_session(
        title=title,
        weekday=weekday,
        start_time=start,
        end_time=end,
        module_id=module_id or None,
        location=args.get("location"),
        notes=args.get("notes"),
    )
    await _reply(update, result.message)


async def add_shift_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a work shift via key-value arguments."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)

    start = args.get("start")
    end = args.get("end")

    if not all([start, end]):
        await _reply(update, 'Usage: /add_shift title="Work" start="2026-05-18 16:00" end="2026-05-18 23:00"')
        return

    energy = args.get("energy")
    result = service.add_work_shift(
        title=args.get("title", "Work"),
        start_at=start,
        end_at=end,
        location=args.get("location"),
        role=args.get("role"),
        energy_cost=int(energy) if energy else None,
        notes=args.get("notes"),
    )
    await _reply(update, result.message)


async def add_assignment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add an assignment via key-value arguments."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)

    title = args.get("title")
    due = args.get("due")

    if not all([title, due]):
        await _reply(update, 'Usage: /add_assignment title="NLP CA1" due="2026-05-21 23:59" module=2 priority=2 estimate=6')
        return

    module_id = args.get("module")
    priority_str = args.get("priority", "3")
    priority = int(priority_str) if priority_str.isdigit() else 3
    estimate_str = args.get("estimate")
    estimated = float(estimate_str) if estimate_str else None

    result = service.add_assignment(
        title=title,
        due_at=due,
        module_id=module_id or None,
        priority=priority,
        estimated_hours=estimated,
        notes=args.get("notes"),
    )
    await _reply(update, result.message)


async def set_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update assignment status."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)

    assignment_id = args.get("assignment")
    status = args.get("status")

    if not all([assignment_id, status]):
        await _reply(update, "Usage: /set_status assignment=8 status=in_progress")
        return

    result = service.update_assignment_status(assignment_id, status)
    await _reply(update, result.message)


async def set_hours_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Update assignment completed hours."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)

    assignment_id = args.get("assignment")
    completed = args.get("completed")

    if not all([assignment_id, completed]):
        await _reply(update, "Usage: /set_hours assignment=8 completed=2.5")
        return

    try:
        hours = float(completed)
    except ValueError:
        await _reply(update, "completed must be a number.")
        return

    result = service.update_completed_hours(assignment_id, hours)
    await _reply(update, result.message)


async def modules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all study modules."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    modules = service.list_modules()

    if not modules:
        await _reply(update, "No modules found.")
        return

    lines = ["Modules", ""]
    for m in modules:
        code = f" ({m.code})" if m.code else ""
        lines.append(f"#{m.id[:8]} {m.name}{code}")
    await _reply(update, "\n".join(lines))


async def classes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active class sessions grouped by weekday."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    sessions = service.list_class_sessions()

    if not sessions:
        await _reply(update, "No class sessions found.")
        return

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    by_day: dict[int, list] = {}
    for s in sessions:
        by_day.setdefault(s.weekday, []).append(s)

    lines = ["Classes", ""]
    for day in sorted(by_day):
        lines.append(day_names[day])
        for s in by_day[day]:
            lines.append(f"  {s.start_time}\u2013{s.end_time} {s.title}")
        lines.append("")
    await _reply(update, "\n".join(lines).rstrip())


async def shifts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List upcoming work shifts."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    shifts = service.list_all_work_shifts(limit=30)

    if not shifts:
        await _reply(update, "No work shifts found.")
        return

    lines = ["Work shifts", ""]
    current_date = None
    for s in shifts:
        date_label = s.start_at.strftime("%a %d %b")
        if date_label != current_date:
            current_date = date_label
            lines.append(date_label)
        lines.append(f"  {s.start_at.strftime('%H:%M')}\u2013{s.end_at.strftime('%H:%M')} {s.title}")
        lines.append("")
    await _reply(update, "\n".join(lines).rstrip())


async def assignments_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List open assignments."""

    settings = _get_bot_settings(context)
    service = AcademicService(settings.db_path, timezone=settings.timezone)
    assignments = service.list_all_assignments(include_completed=False)

    if not assignments:
        await _reply(update, "No open assignments found.")
        return

    lines = ["Assignments", ""]
    for a in assignments:
        lines.append(f"#{a.id[:8]} {a.title}")
        lines.append(f"  Due: {a.due_at.strftime('%a %d %b %H:%M')}")
        lines.append(f"  Status: {a.status.value}")
        if a.estimated_hours is not None:
            lines.append(f"  Estimate: {_format_hours(a.estimated_hours)}")
        if a.completed_hours > 0:
            lines.append(f"  Completed: {_format_hours(a.completed_hours)}")
        lines.append("")
    await _reply(update, "\n".join(lines).rstrip())


async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to /reminders with notification status and upcoming alerts."""

    settings = _get_bot_settings(context)
    if not settings.NOTIFICATIONS_ENABLED:
        await _reply(update, "Notifications are disabled. Set NOTIFICATIONS_ENABLED=true to enable.")
        return

    chat_id = settings.NOTIFICATIONS_CHAT_ID
    alert_hours = settings.DEADLINE_ALERT_HOURS
    service = _build_notification_service(context)

    lines: list[str] = [
        f"Notifications: enabled",
        f"Alert window: {alert_hours}h",
        f"Push chat ID: {chat_id or 'not configured (set NOTIFICATIONS_CHAT_ID)'}",
        "",
    ]

    deadline_msg = service.format_deadline_alerts_message(alert_hours=alert_hours)
    if deadline_msg:
        lines.append(deadline_msg)
    else:
        lines.append(f"No deadlines within the next {alert_hours}h.")

    overdue_msg = service.format_overdue_message()
    if overdue_msg:
        lines.extend(["", overdue_msg])

    await _reply(update, "\n".join(lines))


async def _notify_deadline_alerts(bot: Bot, settings: Settings) -> None:
    """Send deadline alerts to the configured notifications chat."""

    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = NotificationService(db_path=settings.db_path, timezone=settings.timezone)
    msg = service.format_deadline_alerts_message(alert_hours=settings.DEADLINE_ALERT_HOURS)
    if msg:
        await bot.send_message(chat_id=chat_id, text=msg)
        logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "deadline_alert"})


async def _notify_overdue(bot: Bot, settings: Settings) -> None:
    """Send overdue assignment alerts to the configured notifications chat."""

    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = NotificationService(db_path=settings.db_path, timezone=settings.timezone)
    msg = service.format_overdue_message()
    if msg:
        await bot.send_message(chat_id=chat_id, text=msg)
        logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "overdue_alert"})


async def _notify_study_block(bot: Bot, settings: Settings) -> None:
    """Send a study block reminder if one is starting soon."""

    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = NotificationService(db_path=settings.db_path, timezone=settings.timezone)
    reminder = service.study_block_reminder()
    if reminder:
        await bot.send_message(chat_id=chat_id, text=reminder.format_message())
        logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "study_block"})


async def _notify_weekly_review(bot: Bot, settings: Settings) -> None:
    """Send a weekly review prompt."""

    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = NotificationService(db_path=settings.db_path, timezone=settings.timezone)
    msg = service.weekly_review_message()
    await bot.send_message(chat_id=chat_id, text=msg)
    logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "weekly_review"})


async def _run_deadline_alert_loop(app: Application) -> None:
    """Daily job: send deadline alerts each morning at 08:00 local time."""

    from datetime import datetime
    from zoneinfo import ZoneInfo

    settings: Settings = app.bot_data["settings"]
    tz = ZoneInfo(settings.timezone)
    while True:
        now = datetime.now(tz)
        delay = seconds_until(8, 0, now)
        await asyncio.sleep(delay)
        try:
            await _notify_deadline_alerts(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "deadline_alerts"})


async def _run_overdue_check_loop(app: Application) -> None:
    """Daily job: warn about overdue assignments each evening at 22:00 local time."""

    from datetime import datetime
    from zoneinfo import ZoneInfo

    settings: Settings = app.bot_data["settings"]
    tz = ZoneInfo(settings.timezone)
    while True:
        now = datetime.now(tz)
        delay = seconds_until(22, 0, now)
        await asyncio.sleep(delay)
        try:
            await _notify_overdue(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "overdue_check"})


async def _run_study_reminder_loop(app: Application) -> None:
    """Periodic job: check every 15 minutes for an upcoming study block."""

    settings: Settings = app.bot_data["settings"]
    while True:
        await asyncio.sleep(15 * 60)
        try:
            await _notify_study_block(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "study_reminder"})


async def _run_weekly_review_loop(app: Application) -> None:
    """Weekly job: send a review prompt each Sunday at 18:00 local time."""

    from datetime import datetime
    from zoneinfo import ZoneInfo

    settings: Settings = app.bot_data["settings"]
    tz = ZoneInfo(settings.timezone)
    while True:
        now = datetime.now(tz)
        delay = seconds_until_weekday(6, 18, 0, now)  # 6=Sunday
        await asyncio.sleep(delay)
        try:
            await _notify_weekly_review(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "weekly_review"})


def _build_notification_service(context: ContextTypes.DEFAULT_TYPE) -> NotificationService:
    settings = _get_bot_settings(context)
    return NotificationService(db_path=settings.db_path, timezone=settings.timezone)


def build_application(settings: Settings | None = None) -> Application:
    """Build a configured python-telegram-bot application.

    Registers all command handlers with the allowlist filter.
    Settings are stored in bot_data for handler access.
    """

    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    runtime_settings = settings or get_settings()
    token = runtime_settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set; Telegram bot startup is disabled.")

    allowlist_filter = _build_allowlist_filter()
    application = Application.builder().token(token).build()
    application.bot_data["settings"] = runtime_settings
    application.add_handler(CommandHandler("ping", ping_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("status", status_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("skills", skills_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("today", today_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("week", week_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("deadlines", deadlines_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("availability", availability_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("plan", plan_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("study", study_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("add_module", add_module_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("add_class", add_class_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("add_shift", add_shift_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("add_assignment", add_assignment_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("set_status", set_status_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("set_hours", set_hours_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("modules", modules_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("classes", classes_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("shifts", shifts_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("assignments", assignments_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("add_note", add_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("notes", notes_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("note", note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("archive_note", archive_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("add_file", add_file_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("files", files_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("search", search_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("link_note_file", link_note_file_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("ask_notes", ask_notes_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("ask_note", ask_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("sources", sources_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("summarize_note", summarize_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("explain_note", explain_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("questions_note", questions_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("flashcards_note", flashcards_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("rewrite_note", rewrite_note_command, filters=allowlist_filter))
    application.add_handler(CommandHandler("reminders", reminders_command, filters=allowlist_filter))
    application.add_handler(MessageHandler(filters.COMMAND & allowlist_filter, unknown_command))
    return application


async def start_bot(app: Application) -> None:
    """Initialize and start the Telegram application under FastAPI control."""

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    _start_notification_tasks(app)


async def stop_bot(app: Application) -> None:
    """Stop and shut down the Telegram application."""

    _cancel_notification_tasks(app)
    if app.updater and app.updater.running:
        await app.updater.stop()
    if app.running:
        await app.stop()
    await app.shutdown()


def _start_notification_tasks(app: Application) -> None:
    """Start asyncio background tasks for proactive notifications."""

    settings: Settings = app.bot_data.get("settings") or get_settings()
    if not settings.NOTIFICATIONS_ENABLED:
        return
    tasks = [
        asyncio.create_task(_run_deadline_alert_loop(app), name="deadline_alerts"),
        asyncio.create_task(_run_overdue_check_loop(app), name="overdue_check"),
        asyncio.create_task(_run_study_reminder_loop(app), name="study_reminder"),
        asyncio.create_task(_run_weekly_review_loop(app), name="weekly_review"),
    ]
    app.bot_data["_notification_tasks"] = tasks
    logger.info(
        "notification_tasks_started",
        extra={"event_type": "notification_tasks_started", "count": len(tasks)},
    )


def _cancel_notification_tasks(app: Application) -> None:
    """Cancel all background notification tasks."""

    tasks: list[asyncio.Task] = app.bot_data.pop("_notification_tasks", [])
    for task in tasks:
        task.cancel()


def _build_allowlist_filter() -> AllowlistFilter:
    """Build the runtime PTB UpdateFilter subclass for handler registration."""

    from telegram.ext import filters

    class TelegramAllowlistFilter(filters.UpdateFilter, AllowlistFilter):
        def __init__(self) -> None:
            filters.UpdateFilter.__init__(self, name="AllowlistFilter")
            AllowlistFilter.__init__(self)

        def filter(self, update: Update) -> bool:
            return AllowlistFilter.filter(self, update)

    return TelegramAllowlistFilter()


def _get_bot_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    """Return settings from bot_data, falling back to the global cache."""

    stored = context.bot_data.get("settings")
    if isinstance(stored, Settings):
        return stored
    return get_settings()


async def _reply(update: Update, text: str) -> None:
    """Reply on the effective message when one exists."""

    message = update.effective_message
    if message is None:
        logger.debug("telegram_update_without_message")
        return
    await message.reply_text(text)


def _get_status_text() -> str:
    """Return formatted status text from the status skill."""

    return status_handler.get_status()


def _get_skills_text() -> str:
    """Return formatted skill text from the status skill."""

    return status_handler.get_skills()


def _format_today(overview: object) -> str:
    """Format a compact /today response."""

    classes = overview.classes
    work_shifts = overview.work_shifts
    deadlines = overview.deadlines
    availability = overview.availability
    if not classes and not work_shifts and not deadlines:
        return "\n".join(
            [
                "Today",
                "",
                "No classes, work shifts, or deadlines found.",
                f"Available study time: {_format_duration(availability.total_study_minutes)}",
            ]
        )

    lines = [f"Today - {_format_date(overview.date)}", ""]
    lines.extend(_format_block_section("Classes", classes, "No classes today"))
    lines.append("")
    lines.extend(_format_block_section("Work", work_shifts, "No work shifts today"))
    lines.append("")
    lines.extend(_format_window_section("Study windows", availability.study_windows))
    lines.append("")
    lines.extend(_format_deadline_section(deadlines))
    lines.append("")
    lines.append(f"Total study time: {_format_duration(availability.total_study_minutes)}")
    return "\n".join(lines)


def _format_week(overview: object) -> str:
    """Format a compact /week response."""

    lines = [
        f"Week - {_format_short_date(overview.start_date)} to {_format_short_date(overview.end_date)}",
        "",
        "Summary",
        f"- Classes: {overview.class_count}",
        f"- Work shifts: {overview.work_shift_count}",
        f"- Open deadlines: {overview.open_deadline_count}",
        f"- Study time: {_format_duration(overview.availability.total_study_minutes)}",
        "",
    ]
    for summary in overview.day_summaries:
        lines.append(
            "{day}: classes {classes}, work {work}, study {study}".format(
                day=summary.date.strftime("%a"),
                classes=_format_duration(summary.class_minutes),
                work=_format_duration(summary.work_minutes),
                study=_format_duration(summary.study_minutes),
            )
        )
    return "\n".join(lines)


def _format_deadlines(assignments: list[Assignment]) -> str:
    """Format a compact /deadlines response."""

    if not assignments:
        return "No open deadlines found."
    lines = ["Upcoming deadlines"]
    for assignment in assignments:
        lines.append("")
        lines.append(f"- {_format_date(assignment.due_at.date())} - {assignment.title}")
        detail = f"  Priority: {assignment.priority} | Status: {assignment.status.value}"
        if assignment.estimated_hours is not None:
            detail += f" | Estimate: {_format_hours(assignment.estimated_hours)}"
        lines.append(detail)
    return "\n".join(lines)


def _format_availability(day: object) -> str:
    """Format a compact /availability response."""

    lines = ["Availability today", ""]
    if day.study_windows:
        for window in day.study_windows:
            lines.append(
                f"- {_format_time(window.start_at)}-{_format_time(window.end_at)} - {_format_duration(window.minutes)}"
            )
    else:
        lines.append("No study windows available today.")
    lines.append("")
    lines.append(f"Total: {_format_duration(day.total_study_minutes)}")
    return "\n".join(lines)


def _format_plan(plan: object) -> str:
    """Format a compact /plan response."""

    summary = plan.summary
    if (
        not plan.blocks
        and summary.total_required_minutes == 0
        and not summary.unestimated_assignments
        and not summary.overdue_assignments
    ):
        return "No open assignments to plan."

    if not plan.blocks and summary.total_required_minutes > 0 and summary.total_available_minutes == 0:
        lines = [
            "No study windows available this week.",
            "",
            f"Required workload: {_format_duration(summary.total_required_minutes)}",
            f"Unscheduled: {_format_duration(summary.total_unscheduled_minutes)}",
        ]
        lines.extend(_format_plan_warnings(plan))
        return "\n".join(lines)

    lines = [
        f"Study plan - {_format_short_date(plan.start_date)} to {_format_short_date(plan.end_date)}",
        "",
        "Summary",
        f"- Available: {_format_duration(summary.total_available_minutes)}",
        f"- Required: {_format_duration(summary.total_required_minutes)}",
        f"- Planned: {_format_duration(summary.total_planned_minutes)}",
        f"- Unscheduled: {_format_duration(summary.total_unscheduled_minutes)}",
    ]
    if plan.blocks:
        current_day = None
        for block in sorted(plan.blocks, key=lambda item: (item.start_at, item.assignment_id)):
            day_label = block.start_at.strftime("%a")
            if day_label != current_day:
                current_day = day_label
                lines.extend(["", day_label])
            lines.append(
                f"- {_format_time(block.start_at)}-{_format_time(block.end_at)} {_study_block_title(block)}"
            )
    else:
        lines.extend(["", "No planned study blocks."])
    lines.extend(_format_plan_warnings(plan))
    return "\n".join(lines)


def _format_study_recommendation(
    *,
    today_block: object | None,
    next_block: object | None,
    plan: object,
) -> str:
    """Format a compact /study response."""

    if today_block is not None:
        return "\n".join(
            [
                "Study next",
                "",
                f"Today {_format_time(today_block.start_at)}-{_format_time(today_block.end_at)} - {_study_block_title(today_block)}",
                f"Reason: {today_block.reason}",
                f"Due: {_format_date(today_block.due_at.date())}",
                f"Priority: {today_block.priority}",
            ]
        )

    if next_block is not None:
        return "\n".join(
            [
                "No more study blocks today.",
                "",
                "Next:",
                f"{_format_date(next_block.start_at.date())} {_format_time(next_block.start_at)}-{_format_time(next_block.end_at)} - {_study_block_title(next_block)}",
                f"Reason: {next_block.reason}",
            ]
        )

    lines = [
        "No study recommendation available.",
        "",
        "Possible reasons:",
        "- no open assignments",
        "- assignments have no estimated hours",
        "- no available study windows",
    ]
    if plan.summary.unestimated_assignments:
        lines.append(
            f"- {len(plan.summary.unestimated_assignments)} assignments need estimated hours"
        )
    return "\n".join(lines)


def _format_plan_warnings(plan: object) -> list[str]:
    """Return warning lines for a study plan."""

    summary = plan.summary
    warnings: list[str] = []
    if summary.total_required_minutes > summary.total_available_minutes:
        warnings.append("- Required workload exceeds available study time")
    for item in plan.unscheduled:
        warnings.append(
            "- {title}: {minutes} unscheduled before deadline".format(
                title=item.assignment_title,
                minutes=_format_duration(item.unscheduled_minutes),
            )
        )
    if summary.unestimated_assignments:
        warnings.append(
            f"- {len(summary.unestimated_assignments)} assignments need estimated hours"
        )
    if summary.overdue_assignments:
        warnings.append(f"- {len(summary.overdue_assignments)} overdue assignments")
    if not warnings:
        return []
    return ["", "Warnings", *warnings]


def _format_block_section(title: str, blocks: list[TimeBlock], empty: str) -> list[str]:
    lines = [title]
    if not blocks:
        lines.append(f"- {empty}")
        return lines
    for block in blocks:
        lines.append(f"- {_format_time(block.start_at)}-{_format_time(block.end_at)} {block.title}")
    return lines


def _format_window_section(title: str, windows: list[object]) -> list[str]:
    lines = [title]
    if not windows:
        lines.append("- No study windows available today")
        return lines
    for window in windows:
        lines.append(
            f"- {_format_time(window.start_at)}-{_format_time(window.end_at)} - {_format_duration(window.minutes)}"
        )
    return lines


def _format_deadline_section(assignments: list[Assignment]) -> list[str]:
    lines = ["Deadlines"]
    if not assignments:
        lines.append("- No open deadlines due soon")
        return lines
    for assignment in assignments:
        lines.append(f"- {assignment.title} - due {_format_date(assignment.due_at.date())}")
    return lines


def _format_time(value: object) -> str:
    return value.strftime("%H:%M")


def _format_date(value: object) -> str:
    return f"{value.strftime('%a')} {value.day} {value.strftime('%b')}"


def _format_short_date(value: object) -> str:
    return f"{value.day} {value.strftime('%b')}"


def _study_block_title(block: object) -> str:
    if block.module_name:
        return f"{block.assignment_title} ({block.module_name})"
    return block.assignment_title


def _format_duration(minutes: int) -> str:
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h{remainder:02d}"


def _format_hours(hours: float) -> str:
    if hours.is_integer():
        return f"{int(hours)}h"
    return f"{hours:g}h"


def _extract_first_arg(text: str) -> str | None:
    """Extract the first positional argument after the command name."""

    parts = text.split(None, 1)
    if len(parts) < 2:
        return None
    return parts[1].strip()


def _format_note_date(iso_str: str) -> str:
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(iso_str)
        return f"{dt.day} {dt.strftime('%b')}"
    except (ValueError, TypeError):
        return iso_str[:10]


async def add_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    title = args.get("title")
    body = args.get("body")
    if not all([title, body]):
        await _reply(update, 'Usage: /add_note title="My note" body="Note content..." module=abc123 tags="tag1,tag2"')
        return
    module_id = args.get("module")
    assignment_id = args.get("assignment")
    source_type = args.get("source", "manual")
    tags_str = args.get("tags")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    result = service.create_note(title=title, body=body, module_id=module_id,
                                  assignment_id=assignment_id, source_type=source_type, tags=tags)
    await _reply(update, result.message)


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    module_id = args.get("module")
    assignment_id = args.get("assignment")
    tag = args.get("tag")
    notes = service.list_notes(module_id=module_id, assignment_id=assignment_id, tag=tag, limit=20)
    if not notes:
        await _reply(update, "No notes found.")
        return
    lines = ["Notes", ""]
    for n in notes:
        updated = _format_note_date(n.updated_at)
        tags_label = f"\nTags: {', '.join(n.tags)}" if n.tags else ""
        lines.append(f"#{n.id} {n.title}")
        lines.append(f"Updated: {updated}{tags_label}")
        lines.append("")
    await _reply(update, "\n".join(lines).rstrip())


async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        await _reply(update, "Usage: /note <id>")
        return
    try:
        note_id = int(parts[1].strip())
    except ValueError:
        await _reply(update, "Invalid note ID. Use: /note <id>")
        return
    note = service.get_note(note_id)
    if note is None:
        await _reply(update, f"Note #{note_id} not found.")
        return
    body_preview = note.body[:1500]
    if len(note.body) > 1500:
        body_preview += "..."
    tags_label = f"\nTags: {', '.join(note.tags)}" if note.tags else ""
    await _reply(update, f"#{note.id} \u2014 {note.title}\n\n{body_preview}{tags_label}")


async def archive_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    parts = text.split(None, 1)
    if len(parts) < 2:
        await _reply(update, "Usage: /archive_note <id>")
        return
    try:
        note_id = int(parts[1].strip())
    except ValueError:
        await _reply(update, "Invalid note ID. Use: /archive_note <id>")
        return
    result = service.archive_note(note_id)
    await _reply(update, result.message)


async def add_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    path = args.get("path")
    if not path:
        await _reply(update, 'Usage: /add_file path="/path/to/file.pdf" title="My file" module=abc123 tags="tag1,tag2"')
        return
    title = args.get("title")
    module_id = args.get("module")
    assignment_id = args.get("assignment")
    tags_str = args.get("tags")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    result = service.register_file(path=path, title=title, module_id=module_id,
                                    assignment_id=assignment_id, tags=tags)
    await _reply(update, result.message)


async def files_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    module_id = args.get("module")
    assignment_id = args.get("assignment")
    tag = args.get("tag")
    files = service.list_files(module_id=module_id, assignment_id=assignment_id, tag=tag, limit=20)
    if not files:
        await _reply(update, "No files found.")
        return
    lines = ["Files", ""]
    for f in files:
        type_label = f"\nType: {f.file_type}" if f.file_type else ""
        tags_label = f"\nTags: {', '.join(f.tags)}" if f.tags else ""
        lines.append(f"#{f.id} {f.title or f.filename}")
        lines.append(f"Path: {f.path}{type_label}{tags_label}")
        lines.append("")
    await _reply(update, "\n".join(lines).rstrip())


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    query = args.get("q")
    if not query:
        parts = text.split(None, 1)
        if len(parts) < 2:
            await _reply(update, 'Usage: /search <query> or /search q="my query"')
            return
        query = parts[1].strip()
    module_id = args.get("module")
    assignment_id = args.get("assignment")
    results, error = service.search(query=query, module_id=module_id, assignment_id=assignment_id, limit=20)
    if error:
        await _reply(update, error)
        return
    lines = [f'Search results for "{query}"', ""]
    note_results = [r for r in results if r.kind == "note"]
    file_results = [r for r in results if r.kind == "file"]
    if note_results:
        lines.append("Notes")
        for r in note_results:
            lines.append(f"#{r.id} {r.title}")
            lines.append(f"  {r.snippet}")
            lines.append("")
    if file_results:
        lines.append("Files")
        for r in file_results:
            lines.append(f"#{r.id} {r.title}")
            lines.append(f"  {r.snippet}")
            lines.append("")
    await _reply(update, "\n".join(lines).rstrip())


async def ask_notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    query = args.get("q") or _extract_first_arg(text)
    if not query:
        await _reply(update, ASK_NOTES_USAGE)
        return
    service = _build_retrieval_service(context)
    result = service.answer_question(
        query,
        module_id=args.get("module"),
        assignment_id=args.get("assignment"),
        max_sources=_parse_limit(args.get("limit"), default=5, maximum=8),
    )
    await _reply(update, _format_retrieval_answer(result))


async def ask_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    note_id, query, error = _parse_ask_note_args(text, args)
    if error:
        await _reply(update, error)
        return
    service = _build_retrieval_service(context)
    result = service.answer_question(
        query or "",
        note_id=note_id,
        max_sources=_parse_limit(args.get("limit"), default=5, maximum=8),
        include_files=False,
    )
    await _reply(update, _format_retrieval_answer(result))


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    query = args.get("q") or _extract_first_arg(text)
    if not query:
        await _reply(update, SOURCES_USAGE)
        return
    service = _build_retrieval_service(context)
    sources, error = service.retrieve_sources(
        query,
        module_id=args.get("module"),
        assignment_id=args.get("assignment"),
        limit=_parse_limit(args.get("limit"), default=8, maximum=12),
    )
    if error:
        await _reply(update, error)
        return
    if not sources:
        await _reply(update, NO_SOURCE_FALLBACK)
        return
    lines = [f'Sources for "{query}"', ""]
    lines.extend(_format_retrieval_source_lines(sources))
    await _reply(update, "\n".join(lines).rstrip())


async def link_note_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _get_bot_settings(context)
    service = KnowledgeService(settings.db_path, timezone=settings.timezone)
    text = update.effective_message.text or ""
    args = parse_kv_args(text)
    note_str = args.get("note")
    file_str = args.get("file")
    if not all([note_str, file_str]):
        await _reply(update, "Usage: /link_note_file note=12 file=4")
        return
    try:
        note_id = int(note_str)
        file_id = int(file_str)
    except ValueError:
        await _reply(update, "Invalid IDs. Use: /link_note_file note=12 file=4")
        return
    result = service.link_note_file(note_id, file_id)
    await _reply(update, result.message)


def _build_retrieval_service(context: ContextTypes.DEFAULT_TYPE) -> RetrievalService:
    settings = _get_bot_settings(context)
    return RetrievalService(
        db_path=settings.db_path,
        timezone=settings.timezone,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout=settings.ollama_timeout_seconds,
    )


def _parse_ask_note_args(text: str, args: dict[str, str]) -> tuple[int | None, str | None, str | None]:
    note_str = args.get("note")
    query = args.get("q")
    if note_str is None:
        parts = text.split(None, 2)
        if len(parts) < 2:
            return None, None, ASK_NOTE_USAGE
        note_str = parts[1]
        if query is None and len(parts) >= 3:
            query = parts[2].strip()
    try:
        note_id = int(note_str)
    except (TypeError, ValueError):
        return None, None, f"Invalid note ID: {note_str}"
    if not query:
        return None, None, ASK_NOTE_USAGE
    return note_id, query, None


def _parse_limit(value: str | None, *, default: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(1, min(parsed, maximum))


def _format_retrieval_answer(result: object) -> str:
    if not result.success:
        error = result.error or "Retrieval failed."
        if "unavailable" in error.lower() or "connection" in error.lower():
            lines = [
                "Local LLM unavailable.",
                "",
                "Check that Ollama is running:",
                "ollama serve",
            ]
            if result.sources:
                lines.extend(["", "Sources found"])
                lines.extend(_format_retrieval_source_lines(result.sources))
            return "\n".join(lines)
        return f"Error: {error}"

    if not result.sources:
        return result.answer

    lines = [f'Answer for "{result.question}"', ""]
    if result.model:
        lines.extend([f"Model: {result.model}", ""])
    lines.append(_truncate_text(result.answer, 1800))
    lines.extend(["", "Sources"])
    lines.extend(_format_retrieval_source_lines(result.sources))
    return "\n".join(lines).rstrip()


def _format_retrieval_source_lines(sources: Sequence[object]) -> list[str]:
    lines: list[str] = []
    for source in sources:
        lines.append(f"- [{source.chunk_label}] {source.title}")
        if source.snippet:
            lines.append(f"  {_truncate_text(source.snippet, 260)}")
    return lines


def _truncate_text(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _build_llm_service(context: ContextTypes.DEFAULT_TYPE) -> LLMService:
    settings = _get_bot_settings(context)
    return LLMService(
        db_path=settings.db_path,
        timezone=settings.timezone,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_timeout=settings.ollama_timeout_seconds,
    )


def _parse_note_id_from_command(text: str) -> tuple[int | None, str | None]:
    """Extract note ID from command text. Returns (note_id, error)."""

    parts = text.split(None, 1)
    if len(parts) < 2:
        return None, "Usage: /<command> <note_id> [key=value...]"
    first = parts[1].split()[0]
    try:
        return int(first), None
    except ValueError:
        return None, f"Invalid note ID: {first}"


def _format_llm_result(result: object, note_title: str) -> str:
    """Format LLM action result for Telegram."""

    if not result.success:
        if "unavailable" in (result.error or "").lower() or "connection" in (result.error or "").lower():
            return (
                f"Local LLM unavailable.\n\n"
                f"Check that Ollama is running:\n"
                f"ollama serve"
            )
        return f"Error: {result.error}"

    model_label = f"\nModel: {result.model}" if result.model else ""
    return f"{note_title}{model_label}\n\n{result.output[:2000]}"


async def summarize_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    note_id, error = _parse_note_id_from_command(text)
    if error:
        await _reply(update, error)
        return
    service = _build_llm_service(context)
    result = service.summarize_note(note_id)
    note = service.knowledge.get_note(note_id)
    title = f"#{note_id} \u2014 {note.title}" if note else f"Note #{note_id}"
    await _reply(update, _format_llm_result(result, title))


async def explain_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    note_id, error = _parse_note_id_from_command(text)
    if error:
        await _reply(update, error)
        return
    service = _build_llm_service(context)
    result = service.explain_note(note_id)
    note = service.knowledge.get_note(note_id)
    title = f"#{note_id} \u2014 {note.title}" if note else f"Note #{note_id}"
    await _reply(update, _format_llm_result(result, title))


async def questions_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    note_id, error = _parse_note_id_from_command(text)
    if error:
        await _reply(update, error)
        return
    service = _build_llm_service(context)
    result = service.generate_questions_from_note(note_id)
    note = service.knowledge.get_note(note_id)
    title = f"#{note_id} \u2014 {note.title}" if note else f"Note #{note_id}"
    await _reply(update, _format_llm_result(result, title))


async def flashcards_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    note_id, error = _parse_note_id_from_command(text)
    if error:
        await _reply(update, error)
        return
    service = _build_llm_service(context)
    result = service.generate_flashcards_from_note(note_id)
    note = service.knowledge.get_note(note_id)
    title = f"#{note_id} \u2014 {note.title}" if note else f"Note #{note_id}"
    await _reply(update, _format_llm_result(result, title))


async def rewrite_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.effective_message.text or ""
    note_id, error = _parse_note_id_from_command(text)
    if error:
        await _reply(update, error)
        return
    args = parse_kv_args(text)
    style = args.get("style", "concise")
    service = _build_llm_service(context)
    result = service.rewrite_note(note_id, style=style)
    note = service.knowledge.get_note(note_id)
    title = f"#{note_id} \u2014 {note.title}" if note else f"Note #{note_id}"
    await _reply(update, _format_llm_result(result, title))
