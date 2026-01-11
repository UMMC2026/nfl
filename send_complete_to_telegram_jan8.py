# -*- coding: utf-8 -*-
"""Send January 8 Complete Portfolio to Telegram with Analytical Insights."""
import os
import requests
from dotenv import load_dotenv
from pathlib import Path
import json

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram_message(text: str):
    """Send message via Telegram API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        result = resp.json()
        if result.get("ok"):
            print("✅ Message sent successfully!")
            return True
        else:
            print(f"❌ Failed: {result.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def format_pick(pick):
    """Format pick with emoji and analytical edge"""
    player = pick['player']
    stat = pick['stat'].upper()
    line = pick['line']
    prob = int(pick['final_prob'] * 100)
    
    # Get edge if available
    edge = ""
    if pick.get('matchup_reason'):
        edge = f"\n   💡 {pick['matchup_reason']}"
    
    return f"• {player} ({pick['team']}) {stat} {line}+ [{prob}%]{edge}"

# Load portfolio
portfolio_file = Path("outputs/jan8_complete_portfolio.json")
with open(portfolio_file) as f:
    data = json.load(f)

top_entry = data['entries'][0]

# Build message
message = f"""🎯 *NBA PICKS - JANUARY 8, 2026*
📊 Complete 89-Prop Analytical Breakdown
🔬 4-Layer Enhancement Pipeline

━━━━━━━━━━━━━━━━━━━━

🔥 *\\#1 SLAM COMBO (3-PICK POWER)*

{format_pick(top_entry['picks'][0])}

{format_pick(top_entry['picks'][1])}

{format_pick(top_entry['picks'][2])}

━━━━━━━━━━━━━━━━━━━━

📈 *PORTFOLIO METRICS:*
✅ P(All Hit): {int(top_entry['stats']['p_win'] * 100)}%
💰 E\\[ROI\\]: \\+{int(top_entry['stats']['ev_roi'] * 100)}% ({top_entry['stats']['ev_units']:+.2f} units)
🎰 Payout: 6x
🏀 Teams: {', '.join(top_entry['constraints']['teams'])} ({top_entry['constraints']['unique_teams']} different)

━━━━━━━━━━━━━━━━━━━━

🎓 *KEY COACHING INSIGHTS:*

🏀 *IND@CHA (6:00PM CST):*
• Carlisle vs rookie Lee \\- experience edge
• Fastest pace (102\\.0) \\- volume boost
• LaMelo AST spike: Carlisle allows 7\\.8 to PGs

🏀 *CLE@MIN (7:00PM CST):*
• CLE ON B2B: 106 OFF\\_RTG vs 118\\.9 normal (\\-12\\.9 drop)
• Randle REB feast: CLE frontcourt fatigued
• Gobert rested = rim protection elite

🏀 *MIA@CHI (7:00PM CST):*
• Spoelstra vs Donovan \\- coaching mismatch
• Bam dominates: CHI allows 58\\.2% at rim
• Slow grind (98\\.5 pace) \\- MIA controls tempo

🏀 *DAL@UTA (8:00PM CST):*
• BLOWOUT ALERT (22% probability) \\- AVOIDED
• DAL B2B hurts AD (drops 3\\.8 ppg typically)
• UTA 29th DEF\\_RTG but game script risk

━━━━━━━━━━━━━━━━━━━━

🧠 *ANALYTICAL EDGE SUMMARY:*
✅ 89 props analyzed across 20 players
✅ 35 qualified picks (\\>=65% final probability)
✅ 15 primary edges (ONE per player, strict isolation)
✅ Defensive/offensive ratings factored (30 teams)
✅ B2B fatigue quantified (CLE \\-12\\.9 OFF\\_RTG drop)
✅ Blowout modeling (DAL@UTA avoided in top entries)

━━━━━━━━━━━━━━━━━━━━

⏰ *GAME TIMES (CST):*
🕔 6:00PM \\- IND@CHA
🕖 7:00PM \\- CLE@MIN
🕖 7:00PM \\- MIA@CHI
🕗 8:00PM \\- DAL@UTA

✨ *Analysis: Bayesian Beta\\-Binomial \\+ Matchup\\-Specific Adjustments \\+ Coaching Intelligence*
🔬 *Full analytical report: JAN8\\_COMPLETE\\_FINAL\\_PICKS\\.txt*
"""

print("\n" + "="*80)
print("SENDING TO TELEGRAM")
print("="*80 + "\n")
print(f"Bot Token: {BOT_TOKEN[:20]}...")
print(f"Chat ID: {CHAT_ID}")
print(f"\nMessage Preview (first 500 chars):\n{message[:500]}...\n")
print("="*80)

confirm = input("\nSend to Telegram? (yes/no): ").strip().lower()

if confirm == "yes":
    print("\nSending...")
    success = send_telegram_message(message)
    if success:
        print("\n✅ TELEGRAM BROADCAST COMPLETE!")
        print("Top 3-pick entry sent with full analytical insights")
    else:
        print("\n❌ Failed to send. Check credentials and chat ID.")
else:
    print("\n❌ Cancelled by user")
    print(f"\nFull message text:\n{message}")
