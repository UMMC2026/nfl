"""Send Monte Carlo combo recommendations to Telegram."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


import argparse
BOT_TOKEN = os.getenv("SPORTS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram_message(text: str):
    """Send message via Telegram API."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": send_telegram_message.chat_id,
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

send_telegram_message(message)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat_id", type=str, default=DEFAULT_CHAT_ID, help="Override Telegram chat ID")
    parser.add_argument("--message_file", type=str, default=None, help="File containing message to send")
    args = parser.parse_args()

    # Allow dynamic chat switching
    send_telegram_message.chat_id = args.chat_id

    # Craft the message (or load from file)
    if args.message_file:
        with open(args.message_file, "r", encoding="utf-8") as f:
            message = f.read()
    else:
        message = """🚀 *MONTE CARLO ANALYSIS - LATE GAMES*
📅 Wednesday 9:10pm PST
⚡️ 11 Qualified Picks (65%+ Bayesian)

━━━━━━━━━━━━━━━━━━━━

🔥 *TOP SLAM PICKS (74.9%):*
✅ AJ Green 1.5+ REB
✅ Deni Avdija 1.5+ 3PM 🧙 GOBLIN
✅ Al Horford 0.5+ 3PM 🧙 GOBLIN
✅ Myles Turner 0.5+ AST 🧙 GOBLIN

━━━━━━━━━━━━━━━━━━━━

💪 *STRONG PICKS (69.9%):*
• Shaedon Sharpe 2.5+ REB
• Gary Harris 2.5- REB
• Dorian Finney-Smith 0.5+ 3PM 🧙
• Brandin Podziemski 0.5+ 3PM 🧙
• DFS 0.5+ AST 🧙
• Bobby Portis 0.5+ AST 🧙
• Al Horford 0.5+ AST 🧙

━━━━━━━━━━━━━━━━━━━━

🏆 *#1 BEST COMBO (6x Power):*
1⃣ AJ Green 1.5+ REB (74.9%)
2⃣ Deni Avdija 1.5+ 3PM (74.9%)
3⃣ Al Horford 0.5+ 3PM (74.9%)

📊 *42.0% hit rate*
💰 *+155.7% E[ROI]*
🎯 10,000 Monte Carlo simulations

━━━━━━━━━━━━━━━━━━━━

🎯 *BEST DIVERSIFIED (3 stats):*
1⃣ AJ Green 1.5+ REB
2⃣ Al Horford 0.5+ 3PM
3⃣ Myles Turner 0.5+ AST

📊 *42.0% hit rate*
💰 *+154.1% E[ROI]*
🔀 Maximum stat diversity

━━━━━━━━━━━━━━━━━━━━

⏰ *Games: POR vs HOU, GSW vs MIL*
🕘 *Tip-off: 9:10pm PST*
🧙 = Goblin (non-standard payout line)

⚠️ *System Note: MODERATE OVERS bias detected in market (76.9% 3PM, 83.3% REB). Bayesian adjustment applied.*

✨ *Analysis: Bayesian Beta + 10K Monte Carlo*"""

    print("Sending to Telegram...")
    print(f"Bot Token: {BOT_TOKEN[:20]}...")
    print(f"Chat ID: {send_telegram_message.chat_id}")
    print()
    send_telegram_message(message)
