#!/usr/bin/env python3
"""Test Telegram bot connection and chat ID."""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def test_telegram():
    token = os.getenv("SPORTS_BOT_TOKEN")
    chat_id = os.getenv("ADMIN_TELEGRAM_IDS")
    
    if not token or not chat_id:
        print("❌ Missing credentials in .env")
        return
    
    print(f"🔍 Testing Telegram connection...")
    print(f"   Token: {token[:20]}...")
    print(f"   Chat ID: {chat_id}")
    
    # Test 1: Get bot info
    url = f"https://api.telegram.org/bot{token}/getMe"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            result = await resp.json()
            if result.get("ok"):
                bot_info = result['result']
                print(f"\n✅ Bot found: @{bot_info['username']} (ID: {bot_info['id']})")
                print(f"   Name: {bot_info['first_name']}")
            else:
                print(f"❌ Invalid token: {result}")
                return
    
    # Test 2: Send test message
    print(f"\n📤 Sending test message to chat {chat_id}...")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    message = "🧪 **TEST MESSAGE** - If you see this, the bot is working! ✅"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        ) as resp:
            result = await resp.json()
            if result.get("ok"):
                msg_id = result['result']['message_id']
                print(f"✅ Message sent! ID: {msg_id}")
                print(f"\n📝 **Action Required:**")
                print(f"   1. Check your Telegram for the test message")
                print(f"   2. If you don't see it, make sure you've started the bot (@{bot_info['username']})")
                print(f"   3. Check your chat settings (muted notifications?)")
            else:
                error = result.get("description", "Unknown error")
                print(f"❌ Failed to send: {error}")
                if "forbidden" in error.lower() or "chat not found" in error.lower():
                    print(f"\n⚠️  The bot can't message this chat ID. Possible causes:")
                    print(f"   - You haven't started the bot yet (message @{bot_info['username']} first)")
                    print(f"   - Wrong chat ID in .env")
                    print(f"   - Bot was blocked")

if __name__ == "__main__":
    asyncio.run(test_telegram())
