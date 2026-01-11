"""
Governed Telegram Transport — Fail Loud on Missing Config

Rule: Missing env vars = immediate RuntimeError (no silent failures)
"""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()  # Load .env first


async def _send_async(text: str) -> dict:
    """
    Send async message to Telegram API.

    Args:
        text: Message text

    Returns:
        Response dict from Telegram API

    Raises:
        RuntimeError: If config missing or API fails
    """
    token = os.getenv("SPORTS_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # FAIL CLOSED: No silent failures
    if not token:
        raise RuntimeError(
            "❌ SPORTS_BOT_TOKEN not set in .env"
        )
    if not chat_id:
        raise RuntimeError(
            "❌ TELEGRAM_CHAT_ID not set in .env"
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            body = await resp.text()
            if resp.status != 200:
                raise RuntimeError(
                    f"❌ Telegram API error {resp.status}: {body}"
                )
            return {"status": "ok", "response": body}


def send_message(text: str) -> dict:
    """
    Synchronous wrapper for async send.

    Args:
        text: Message text

    Returns:
        Response dict

    Raises:
        RuntimeError: On any error
    """
    return asyncio.run(_send_async(text))
