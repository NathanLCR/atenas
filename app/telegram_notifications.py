"""Telegram notification functions."""

from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.telegram_services import build_notification_service
from core.notifications.service import seconds_until, seconds_until_weekday

logger = logging.getLogger(__name__)


async def notify_deadline_alerts(bot, settings: Settings) -> None:
    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = build_notification_service(settings)
    msg = service.format_deadline_alerts_message(alert_hours=settings.DEADLINE_ALERT_HOURS)
    if msg:
        await bot.send_message(chat_id=chat_id, text=msg)
        logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "deadline_alert"})


async def notify_overdue(bot, settings: Settings) -> None:
    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = build_notification_service(settings)
    msg = service.format_overdue_message()
    if msg:
        await bot.send_message(chat_id=chat_id, text=msg)
        logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "overdue_alert"})


async def notify_study_block(bot, settings: Settings) -> None:
    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = build_notification_service(settings)
    reminder = service.study_block_reminder()
    if reminder:
        await bot.send_message(chat_id=chat_id, text=reminder.format_message())
        logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "study_block"})


async def notify_weekly_review(bot, settings: Settings) -> None:
    chat_id = settings.NOTIFICATIONS_CHAT_ID
    if not chat_id or not settings.NOTIFICATIONS_ENABLED:
        return
    service = build_notification_service(settings)
    msg = service.weekly_review_message()
    await bot.send_message(chat_id=chat_id, text=msg)
    logger.info("notification_sent", extra={"event_type": "notification_sent", "kind": "weekly_review"})


async def run_deadline_alert_loop(app) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    settings: Settings = app.bot_data["settings"]
    tz = ZoneInfo(settings.timezone)
    while True:
        now = datetime.now(tz)
        delay = seconds_until(8, 0, now)
        await asyncio.sleep(delay)
        try:
            await notify_deadline_alerts(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "deadline_alerts"})


async def run_overdue_check_loop(app) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    settings: Settings = app.bot_data["settings"]
    tz = ZoneInfo(settings.timezone)
    while True:
        now = datetime.now(tz)
        delay = seconds_until(22, 0, now)
        await asyncio.sleep(delay)
        try:
            await notify_overdue(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "overdue_check"})


async def run_study_reminder_loop(app) -> None:
    settings: Settings = app.bot_data["settings"]
    while True:
        await asyncio.sleep(15 * 60)
        try:
            await notify_study_block(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "study_reminder"})


async def run_weekly_review_loop(app) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    settings: Settings = app.bot_data["settings"]
    tz = ZoneInfo(settings.timezone)
    while True:
        now = datetime.now(tz)
        delay = seconds_until_weekday(6, 18, 0, now)
        await asyncio.sleep(delay)
        try:
            await notify_weekly_review(app.bot, settings)
        except Exception:
            logger.exception("notification_job_error", extra={"event_type": "notification_job_error", "job": "weekly_review"})


def start_notification_tasks(app) -> None:
    settings: Settings = app.bot_data.get("settings")
    if not settings or not settings.NOTIFICATIONS_ENABLED:
        return
    tasks = [
        asyncio.create_task(run_deadline_alert_loop(app), name="deadline_alerts"),
        asyncio.create_task(run_overdue_check_loop(app), name="overdue_check"),
        asyncio.create_task(run_study_reminder_loop(app), name="study_reminder"),
        asyncio.create_task(run_weekly_review_loop(app), name="weekly_review"),
    ]
    app.bot_data["_notification_tasks"] = tasks
    logger.info(
        "notification_tasks_started",
        extra={"event_type": "notification_tasks_started", "count": len(tasks)},
    )


def cancel_notification_tasks(app) -> None:
    tasks: list[asyncio.Task] = app.bot_data.pop("_notification_tasks", [])
    for task in tasks:
        task.cancel()
