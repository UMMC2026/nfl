#!/usr/bin/env python3
"""
Send Jan 4 NBA Slate Analysis to Telegram
"""

import os
import asyncio
import aiohttp
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

async def send_telegram_message(message: str) -> bool:
    """Send message to Telegram"""
    token = os.getenv("SPORTS_BOT_TOKEN")
    chat_id = os.getenv("ADMIN_TELEGRAM_IDS")
    
    if not token or not chat_id:
        print("❌ Missing Telegram credentials")
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                result = await resp.json()
                if result.get("ok"):
                    print(f"OK Sent to Telegram (ID: {result['result']['message_id']})")
                    return True
                else:
                    print(f"FAILED: {result.get('description')}")
                    return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def format_message():
    """Format the MC analysis for Telegram"""
    
    message = """<b>JAN 4 NBA 8-GAME SLATE - MONTE CARLO ANALYSIS</b>
Generated: 2026-01-04 11:44
Pipeline: INGEST > HYDRATE > MC (10k trials)

<b>GAME RESULTS (Expected Hits):</b>

DET @ CLE (1:00 PM)
12 props | 5.4 avg hits | 45.0% hit rate

MIL @ SAC (8:00 PM) 
9 props | 5.6 avg hits | 62.2% hit rate ⭐

MEM @ LAL (8:30 PM)
10 props | 4.6 avg hits | 46.0% hit rate

IND @ ORL (2:00 PM)
10 props | 4.6 avg hits | 46.0% hit rate

DEN @ BKN (2:30 PM)
9 props | 4.1 avg hits | 45.6% hit rate

NOP @ MIA (5:00 PM)
9 props | 3.7 avg hits | 41.1% hit rate

MIN @ WAS (5:00 PM)
8 props | 3.7 avg hits | 46.3% hit rate

OKC @ PHX (7:00 PM)
9 props | 3.6 avg hits | 40.0% hit rate

<b>SLATE TOTALS:</b>
77 props | 35.3 expected hits | 45.8% avg confidence

<b>TOP INDIVIDUAL EDGES:</b>
- Shai Gilgeous-Alexander OVER 31.5 Pts (72%)
- Luka Doncic OVER 34.5 Pts (70%)
- Anthony Edwards OVER 30.5 Pts (68%)
- Giannis Antetokounmpo OVER 29.5 Pts (67%)

Report: /outputs/MC_JAN4_SLATE_8GAMES_20260104_114413.txt
"""
    return message

async def main():
    msg = format_message()
    success = await send_telegram_message(msg)
    if success:
        print("\nMessage delivered successfully")
    else:
        print("\nFailed to send message")

if __name__ == "__main__":
    asyncio.run(main())
