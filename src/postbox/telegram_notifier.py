"""Telegram notifications for owner."""

from __future__ import annotations

import httpx


async def send_telegram_message(bot_token: str, chat_id: int, message: str) -> bool:
    """Send message via Telegram bot.

    Args:
        bot_token: Bot API token
        chat_id: Telegram chat/user ID
        message: Message text (supports Markdown)

    Returns:
        True if message was sent, False otherwise
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            return response.status_code == 200
    except Exception:
        return False
