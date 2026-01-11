#!/usr/bin/env python3
"""
Send enhanced analysis notification to Telegram FIRST
"""

import aiohttp
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("SPORTS_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_TELEGRAM_IDS")

async def send_telegram_message(text):
    """Send message to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": int(ADMIN_ID),
        "text": text,
        "parse_mode": "HTML"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("result", {}).get("message_id")
            else:
                print(f"Error: {response.status}")
                return None

async def main():
    # Build notification message
    message = """<b>🚀 ENHANCED ANALYSIS INITIATED</b>
<b>Both Sides of the Ball | NFL + NBA</b>

<b>📊 Slate Overview:</b>
• 16 Games Total (8 NFL + 8 NBA)
• 156 Props Total (increased from 88)
• <b>NEW: Defensive Stats Included!</b>

<b>🛡️ What's New:</b>
✅ Offensive Stats: Pass Yards, Rush Yards, Rec Yards, Points, Rebounds, Assists
✅ Defensive Stats: Sacks, Tackles, Steals, Blocks, Pass Deflections

<b>NFL Defensive Coverage:</b>
• Pass Rushers: T.J. Watt, Nick Bosa, Aaron Donald, Von Miller
• Linebackers: Jeremiah Owusu-Koramoah, De'Vondre Campbell, Patrick Queen
• Defensive Backs: Denzel Ward, Derek Stingley Jr., Micah Hyde

<b>NBA Defensive Coverage:</b>
• Elite Defenders: Giannis, Evan Mobley, Rudy Gobert
• Perimeter: Shai G-A, Donovan Mitchell, Mikal Bridges
• Versatile: Bam Adebayo, Brook Lopez, Anthony Davis

<b>🔄 Pipeline Status:</b>
INGEST → HYDRATE (Both Sides) → MONTE CARLO → OLLAMA → ANALYSIS COMPLETE

<i>Full enhanced analysis with both-sides-of-ball coverage incoming...</i>

⏳ Running Monte Carlo simulation now (10,000 trials per game)"""
    
    msg_id = await send_telegram_message(message)
    if msg_id:
        print(f"✅ Telegram notification sent! Message ID: {msg_id}")
    else:
        print("❌ Failed to send Telegram notification")

if __name__ == "__main__":
    asyncio.run(main())
