"""Telegram notifications for subscription events."""

import aiohttp
from stripe_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


async def notify_subscription(email: str, tier: str, event: str):
    """Send Telegram notification for subscription event."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"⚠️  Telegram not configured, skipping notification for {email}")
        return
    
    messages = {
        "created": f"✅ New subscription: {email} ({tier})",
        "updated": f"🔄 Subscription updated: {email} ({tier})",
        "canceled": f"❌ Subscription canceled: {email}",
    }
    
    message = messages.get(event, f"Subscription event: {email}")
    
    await send_telegram_message(message)


async def send_telegram_message(text: str):
    """Send message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"⚠️  Telegram error: {resp.status}")
    except Exception as e:
        print(f"⚠️  Failed to send Telegram: {e}")


async def notify_daily_analysis(tier: str, stats: dict):
    """Notify about daily analysis availability."""
    message = f"""
📊 Daily Analysis Ready!
Tier: {tier.upper()}
Date: {stats.get('date', 'N/A')}
Games: {stats.get('game_count', 0)}
Confidence: {stats.get('avg_confidence', 0):.1%}
    """
    
    await send_telegram_message(message)
