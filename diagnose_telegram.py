#!/usr/bin/env python3
"""Diagnostic script to verify Telegram bot and chat configuration."""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def diagnose_telegram():
    token = os.getenv("SPORTS_BOT_TOKEN")
    admin_ids = os.getenv("ADMIN_TELEGRAM_IDS")
    channel = os.getenv("TELEGRAM_CHAT_ID")
    
    print("=" * 60)
    print("TELEGRAM BOT DIAGNOSTICS")
    print("=" * 60)
    
    print("\n📋 CONFIGURATION:")
    print(f"   Token: {token[:20]}..." if token else "   ❌ No token found")
    print(f"   Admin IDs: {admin_ids}" if admin_ids else "   ❌ No admin IDs")
    print(f"   Channel: {channel}" if channel else "   ❌ No channel ID")
    
    if not token:
        print("\n❌ Missing SPORTS_BOT_TOKEN in .env")
        return
    
    # Get bot info
    print("\n🤖 BOT STATUS:")
    url = f"https://api.telegram.org/bot{token}/getMe"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            result = await resp.json()
            if result.get("ok"):
                bot = result['result']
                print(f"   ✅ Bot: @{bot['username']}")
                print(f"   ID: {bot['id']}")
                print(f"   Name: {bot['first_name']}")
            else:
                print(f"   ❌ Bot check failed: {result.get('description')}")
                return
    
    # Try sending to admin IDs
    if admin_ids:
        print(f"\n📤 TESTING MESSAGE TO ADMIN IDS ({admin_ids}):")
        test_msg = f"🧪 Diagnostic test at {datetime.now().strftime('%H:%M:%S')}"
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"chat_id": admin_ids, "text": test_msg}
            ) as resp:
                result = await resp.json()
                if result.get("ok"):
                    print(f"   ✅ Message sent! ID: {result['result']['message_id']}")
                    print(f"\n   ⚠️ IF YOU DON'T SEE THIS MESSAGE:")
                    print(f"      1. Search for @{bot['username']} in Telegram")
                    print(f"      2. Click 'Start' to initiate the bot")
                    print(f"      3. Then you'll receive future messages")
                else:
                    error = result.get("description", "Unknown error")
                    print(f"   ❌ Send failed: {error}")
                    
                    if "forbidden" in error.lower():
                        print(f"\n   💡 The bot cannot message this chat because:")
                        print(f"      • You haven't started the bot yet")
                        print(f"      • Search @{bot['username']} in Telegram")
                        print(f"      • Click 'Start' to activate it")
                    elif "chat not found" in error.lower():
                        print(f"\n   💡 Chat ID {admin_ids} not found")
                        print(f"      • Verify the ADMIN_TELEGRAM_IDS in .env")
    
    # Check updates (recent messages TO the bot)
    print(f"\n📥 CHECKING FOR MESSAGES TO BOT:")
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            result = await resp.json()
            if result.get("ok"):
                updates = result.get("result", [])
                if updates:
                    print(f"   Found {len(updates)} recent updates from users")
                    for update in updates[-3:]:  # Show last 3
                        if "message" in update:
                            msg = update["message"]
                            sender = msg.get("from", {}).get("username", "unknown")
                            text = msg.get("text", "[no text]")[:50]
                            print(f"   - @{sender}: {text}")
                else:
                    print(f"   ℹ️ No recent updates. Users haven't messaged the bot yet.")
                    print(f"      Users MUST start the bot with /start before it can send them messages")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
1. Open Telegram and search for @UMMC_Sportsbot
2. Click the chat
3. Click 'Start' or type /start
4. The bot will confirm activation
5. Future analysis will appear in your chat

Without starting the bot, it cannot send you messages.
""")

if __name__ == "__main__":
    asyncio.run(diagnose_telegram())
