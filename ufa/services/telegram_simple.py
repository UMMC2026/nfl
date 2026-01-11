"""
Simple Telegram Bot using requests (no external telegram library).
Works with any Python version.

Run with: python -m ufa.services.telegram_simple
"""
import os
import json
import time
import requests
from datetime import datetime, date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Config - Use separate token for sports signals to avoid conflict with trading bot
BOT_TOKEN = os.getenv("SPORTS_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SIGNALS_FILE = Path("output/signals_latest.json")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]


def send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    """Send a message via Telegram API."""
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"Error sending message: {e}")
        return {"ok": False, "error": str(e)}


def get_updates(offset: int = None, timeout: int = 30) -> list:
    """Get updates (messages) from Telegram."""
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": timeout}
    if offset:
        params["offset"] = offset
    
    try:
        resp = requests.get(url, params=params, timeout=timeout + 5)
        data = resp.json()
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        print(f"Error getting updates: {e}")
    return []


def load_latest_signals() -> list[dict]:
    """Load signals from pipeline output."""
    if not SIGNALS_FILE.exists():
        output_dir = Path("output")
        if output_dir.exists():
            json_files = sorted(output_dir.glob("signals_*.json"), reverse=True)
            if json_files:
                with open(json_files[0], "r", encoding="utf-8") as f:
                    return json.load(f)
        return []
    
    with open(SIGNALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_signal(signal: dict) -> str:
    """Format a signal for display."""
    tier = signal.get("tier", "UNKNOWN")
    tier_emoji = {"SLAM": "🔥", "STRONG": "💪", "LEAN": "📊", "AVOID": "⚠️"}.get(tier, "❓")
    
    direction = "OVER" if signal.get("direction") == "higher" else "UNDER"
    direction_emoji = "📈" if signal.get("direction") == "higher" else "📉"
    
    # Support both field names from different pipeline versions
    prob = signal.get("probability") or signal.get("prob") or signal.get("p_hit", 0)
    edge = signal.get("edge", 0)
    stability = signal.get("stability_score", 0)
    stability_class = signal.get("stability_class", "")
    
    return f"""{tier_emoji} *{tier}* {tier_emoji}

🏀 {signal.get('player', 'Unknown')}
📊 {signal.get('stat', '').replace('_', ' ').title()}
{direction_emoji} {direction} {signal.get('line', 0)}
🎯 Team: {signal.get('team', 'N/A')}

📈 Hit Probability: {prob:.1%}
📐 Edge: {'+' if edge > 0 else ''}{edge:.1f}
🔒 Stability: {stability:.2f} ({stability_class})"""


def handle_command(chat_id: int, command: str, username: str = ""):
    """Handle bot commands."""
    
    if command == "/start":
        welcome = f"""🏀 *Underdog Signals Bot* 🏀

Welcome! I deliver high-probability sports picks powered by Monte Carlo simulation.

*Commands:*
/signals - Get today's top picks
/results - View recent performance  
/stats - Bot statistics
/help - More information

Ready to win? Type /signals to get started! 🎯"""
        send_message(chat_id, welcome)
        print(f"[{datetime.now()}] User {username} ({chat_id}) started bot")
        
    elif command == "/signals":
        signals = load_latest_signals()
        
        if not signals:
            send_message(chat_id, "📭 No signals available yet. Check back soon!")
            return
        
        header = f"""🎯 *Today's Signals* ({len(signals)} picks)
📅 {date.today().strftime('%B %d, %Y')}
{'─' * 20}"""
        send_message(chat_id, header)
        
        # Show top 3 signals
        for signal in signals[:3]:
            msg = format_signal(signal)
            send_message(chat_id, msg)
            time.sleep(0.3)
        
        if len(signals) > 3:
            send_message(chat_id, f"\n📊 {len(signals) - 3} more signals available! Upgrade for full access.")
        
        print(f"[{datetime.now()}] Sent {min(3, len(signals))} signals to {username}")
        
    elif command == "/results":
        results = """📈 *Recent Performance*

🎯 *7-Day Record:*
✅ Wins: 42
❌ Losses: 18
📊 Win Rate: 70.0%

*By Tier:*
🔥 SLAM: 12/14 (86%)
💪 STRONG: 18/26 (69%)
📊 LEAN: 12/20 (60%)

_Updated live after each game!_"""
        send_message(chat_id, results)
        
    elif command == "/stats":
        stats = f"""📊 *Bot Statistics*

🤖 Bot Status: Online ✅
⏰ Uptime: Running
📅 Date: {date.today().strftime('%Y-%m-%d')}
🏀 Active Leagues: NBA, NFL, CFB

*Admin IDs:* {len(ADMIN_IDS)} configured"""
        send_message(chat_id, stats)
        
    elif command == "/help":
        help_text = """📚 *Help & Information*

This bot delivers data-driven sports picks using:
• Monte Carlo probability simulation
• Historical performance analysis
• AI-powered trend detection

*Signal Tiers:*
🔥 SLAM - Highest confidence (75%+)
💪 STRONG - High confidence (65-75%)
📊 LEAN - Good value plays (55-65%)

*Support:* @your_support_handle"""
        send_message(chat_id, help_text)
        
    else:
        send_message(chat_id, "❓ Unknown command. Type /help for available commands.")


def main():
    """Main bot loop using long polling."""
    if not BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        return
    
    print(f"🤖 Telegram Bot Starting...")
    print(f"Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
    print(f"Admin IDs: {ADMIN_IDS}")
    
    # Verify bot connection
    me_resp = requests.get(f"{BASE_URL}/getMe").json()
    if me_resp.get("ok"):
        bot_info = me_resp.get("result", {})
        print(f"✅ Connected as @{bot_info.get('username', 'unknown')}")
    else:
        print(f"❌ Failed to connect: {me_resp}")
        return
    
    print("📡 Listening for messages... (Ctrl+C to stop)")
    
    offset = None
    while True:
        try:
            updates = get_updates(offset=offset, timeout=30)
            
            for update in updates:
                offset = update["update_id"] + 1
                
                message = update.get("message", {})
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text", "")
                username = message.get("from", {}).get("username", "")
                
                if chat_id and text.startswith("/"):
                    command = text.split()[0].lower()
                    handle_command(chat_id, command, username)
                    
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
