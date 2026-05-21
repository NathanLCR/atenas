"""Telegram authorization helpers."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AllowlistFilter:
    """Allow only configured Telegram user IDs through to handlers."""

    def __init__(self, allowed_user_ids: Sequence[int] | None = None) -> None:
        self._allowed_user_ids = set(allowed_user_ids) if allowed_user_ids is not None else None

    def check_update(self, update) -> bool:
        return self.filter(update)

    def filter(self, update) -> bool:
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


def telegram_user_authorized(settings: Settings, user_id: int | None) -> bool:
    """Return whether a plain-message handler should process this user.

    Default-deny: returns False for empty, malformed, or missing allowlists.
    """
    allowed_user_ids = getattr(settings, "TELEGRAM_ALLOWED_USER_IDS", [])
    if not isinstance(allowed_user_ids, Sequence) or isinstance(allowed_user_ids, (str, bytes)):
        return False
    if not allowed_user_ids:
        return False
    return user_id is not None and user_id in set(allowed_user_ids)
