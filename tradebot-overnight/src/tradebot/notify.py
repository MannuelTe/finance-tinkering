from __future__ import annotations

import logging

import httpx

from tradebot.config import settings

logger = logging.getLogger(__name__)


def notify(message: str) -> None:
    """Best-effort Telegram push. Never raises — a notification failure must not take down
    the trading loop. Falls back to a log line when Telegram isn't configured."""
    if not settings.telegram_token or not settings.telegram_chat_id:
        logger.info("notify (telegram not configured): %s", message)
        return

    url = f"https://api.telegram.org/bot{settings.telegram_token}/sendMessage"
    try:
        httpx.post(url, json={"chat_id": settings.telegram_chat_id, "text": message}, timeout=10.0)
    except httpx.HTTPError:
        logger.exception("failed to send telegram notification")
