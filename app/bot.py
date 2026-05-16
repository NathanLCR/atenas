"""Telegram bot integration for Atenas."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.config import Settings, get_settings
from core.academic.models import Assignment, TimeBlock
from core.academic.service import AcademicService
from skills.status import handler as status_handler

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import Application, ContextTypes

    from core.academic.models import Assignment, TimeBlock

logger = logging.getLogger(__name__)


class AllowlistFilter:
    """Allow only configured Telegram user IDs through to handlers."""

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


def build_application(settings: Settings | None = None) -> Application:
    """Build a configured python-telegram-bot application."""

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
    application.add_handler(MessageHandler(filters.COMMAND & allowlist_filter, unknown_command))
    return application


async def start_bot(app: Application) -> None:
    """Initialize and start the Telegram application under FastAPI control."""

    await app.initialize()
    await app.start()


async def stop_bot(app: Application) -> None:
    """Stop and shut down the Telegram application."""

    if app.running:
        await app.stop()
    await app.shutdown()


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
