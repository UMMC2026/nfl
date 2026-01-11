#!/usr/bin/env python3
"""
Send Full Report Summary to Telegram
"""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

TELEGRAM_TOKEN = os.getenv("SPORTS_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_IDS"))

async def send_report():
    """Send comprehensive report to Telegram"""
    
    message = """<b>JAN 4, 2026 - COMPLETE DAILY ANALYSIS</b>

<b>NFL (8 Games) + NBA (8 Games) Summary:</b>
Total Props: 88
Expected Hits: 43-44 (49% confidence)

<b>TOP RECOMMENDATION (69.5%):</b>
NBA - Anthony Edwards OVER 28.5 pts
MIN @ WAS | LEG 1 for 3-leg core parlay

<b>LEAN PLAYS (60%+ confidence):</b>
1. Lamar Jackson OVER 275.5 pass yds (PIT @ CLE) - 60.7%
2. Josh Allen OVER 305.5 pass yds (KC @ BUF) - 55.7%
3. Daniel Jones OVER 255.5 pass yds (LAR @ NYG) - 55.6%

<b>RECOMMENDED 3-LEG PARLAY:</b>
+ Anthony Edwards OVER 28.5 (NBA) - 69.5%
+ Lamar Jackson OVER 275.5 (NFL) - 60.7%
+ Josh Allen OVER 305.5 (NFL) - 55.7%

Expected Hits: 2.0/3 | Odds: +160 to +200

<b>FULL REPORT SAVED:</b>
- FULL_REPORT_JAN4_ALL_GAMES_*.txt
- CHEAT_SHEET_JAN4_NFL_NBA_*.txt
- FULL_SLATE_JAN4_NFL8_NBA8_*.txt

Pipeline Complete: INGEST > HYDRATE > MC > OLLAMA > SEND"""
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url,
                json={
                    "chat_id": ADMIN_ID,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    msg_id = data.get("result", {}).get("message_id")
                    print(f"OK Sent to Telegram (Message ID: {msg_id})")
                else:
                    print(f"Error: {resp.status}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(send_report())
