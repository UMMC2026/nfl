#!/usr/bin/env python3
"""
Send Friday Slate Top 10 Picks to Telegram
Generated: 2026-01-31
"""
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('SPORTS_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

print(f"Bot token exists: {bool(BOT_TOKEN)}")
print(f"Chat ID: {CHAT_ID}")

# Best 10 picks from MC optimization + Optimal Picks analysis
picks = [
    {'rank': 1, 'player': 'Bam Adebayo', 'stat': 'PTS', 'line': 22.5, 'dir': 'UNDER', 'conf': 82.3, 'team': 'MIA vs CHI', 'note': 'MC TOP PICK - Anchor for all optimal entries'},
    {'rank': 2, 'player': 'Collin Sexton', 'stat': 'PTS', 'line': 10.5, 'dir': 'OVER', 'conf': 76.9, 'team': 'CHA vs SAS', 'note': 'MC CORE LEG - High-floor scorer'},
    {'rank': 3, 'player': 'Jalen Smith', 'stat': 'PTS', 'line': 13.5, 'dir': 'UNDER', 'conf': 76.1, 'team': 'CHI', 'note': 'MC CORE LEG - Low-usage role'},
    {'rank': 4, 'player': 'Clint Capela', 'stat': 'PTS', 'line': 5.5, 'dir': 'UNDER', 'conf': 73.7, 'team': 'HOU vs DAL', 'note': 'MC POWER LEG - Rim-runner, no shot creation'},
    {'rank': 5, 'player': 'Pelle Larsson', 'stat': 'PTS', 'line': 12.5, 'dir': 'UNDER', 'conf': 72.7, 'team': 'SAC', 'note': 'Bench depth piece, limited touches'},
    {'rank': 6, 'player': 'Dru Smith', 'stat': 'PTS', 'line': 8.5, 'dir': 'UNDER', 'conf': 71.5, 'team': 'MIA', 'note': 'Deep rotation guard'},
    {'rank': 7, 'player': 'Kasparas Jakucionis', 'stat': 'PTS', 'line': 6.5, 'dir': 'UNDER', 'conf': 71.5, 'team': 'SAC', 'note': 'Rookie minutes uncertain'},
    {'rank': 8, 'player': 'Miles Bridges', 'stat': 'PTS', 'line': 15.5, 'dir': 'OVER', 'conf': 69.7, 'team': 'CHA vs SAS', 'note': 'Primary option with Sexton'},
    {'rank': 9, 'player': 'Jeremiah Fears', 'stat': 'PTS', 'line': 8.5, 'dir': 'OVER', 'conf': 68.8, 'team': 'OKC', 'note': 'Appears in MC #2 entry'},
    {'rank': 10, 'player': 'Matas Buzelis', 'stat': 'PTS', 'line': 17.5, 'dir': 'UNDER', 'conf': 68.7, 'team': 'CHI', 'note': 'Appears in MC #6 entry'},
]

# Build message (plain text to avoid Markdown parsing issues)
now = datetime.now().strftime('%B %d, %Y')
msg = f"""🎯 FRIDAY SLATE - TOP 10 PICKS
📅 {now}
━━━━━━━━━━━━━━━━━━━━

🔥 MONTE CARLO OPTIMIZED
EV: +2.55 | Sharpe: 0.53 | P(profit): 35.5%

"""

for p in picks:
    emoji = '📉' if p['dir'] == 'UNDER' else '📈'
    tier = '🔥' if p['conf'] >= 75 else '💪' if p['conf'] >= 65 else '📊'
    msg += f"""{tier} #{p['rank']} {p['player']}
{emoji} {p['stat']} {p['dir']} {p['line']} | {p['conf']}%
🏀 {p['team']}
💡 {p['note']}

"""

# Best entry recommendation
msg += """━━━━━━━━━━━━━━━━━━━━
💎 BEST 4-LEG POWER ENTRY:
1️⃣ Bam Adebayo PTS U22.5 (82.3%)
2️⃣ Collin Sexton PTS O10.5 (76.9%)  
3️⃣ Jalen Smith PTS U13.5 (76.1%)
4️⃣ Clint Capela PTS U5.5 (73.7%)

📊 Kelly Stake: 2.8% bankroll
🎯 Avg Hit Rate: 77.3%
━━━━━━━━━━━━━━━━━━━━

💎 BEST 3-LEG FLEX (SAFEST):
1️⃣ Bam Adebayo PTS U22.5
2️⃣ Collin Sexton PTS O10.5
3️⃣ Jalen Smith PTS U13.5

📊 P(profit): 88.1% | Sharpe: 0.78
━━━━━━━━━━━━━━━━━━━━

⚠️ Data suggests. Not financial advice.
🤖 UNDERDOG ANALYSIS | Risk-First Engine
"""

# Send
url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
payload = {'chat_id': CHAT_ID, 'text': msg}
print(f"\nSending to chat_id: {CHAT_ID}")
print(f"Message length: {len(msg)} chars")

try:
    resp = requests.post(url, json=payload, timeout=15)
    data = resp.json()
    print(f"\nResponse: {data}")
    if data.get('ok'):
        print('\n✅ MESSAGE SENT SUCCESSFULLY!')
    else:
        print(f'\n❌ FAILED: {data.get("description")}')
except Exception as e:
    print(f'\n❌ ERROR: {e}')
