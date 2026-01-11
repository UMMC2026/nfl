#!/usr/bin/env python3
"""Send top 10 picks to Telegram subscribers"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import time

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def get_subscribers():
    """Get all subscriber chat IDs from database"""
    import sqlite3
    try:
        conn = sqlite3.connect('ufa.db')
        cursor = conn.cursor()
        cursor.execute("SELECT telegram_id FROM users WHERE telegram_id IS NOT NULL")
        subscribers = [str(row[0]) for row in cursor.fetchall()]
        conn.close()
        return subscribers
    except Exception as e:
        print(f"❌ Database error: {e}")
        return []

def send_message(chat_id, text):
    """Send message to Telegram chat"""
    url = f"{TELEGRAM_API}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        if response.status_code != 200:
            print(f"    Error response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"    Exception: {e}")
        return False

def main():
    # Load signals
    signals_file = Path("output/signals_latest.json")
    with open(signals_file, 'r') as f:
        signals = json.load(f)
    
    # Sort by probability and get top 10
    top10 = sorted(signals, key=lambda x: x['probability'], reverse=True)[:10]
    
    # Format message
    message = "🏆 *TOP 10 PREMIUM PICKS - TONIGHT* 🏆\n\n"
    
    for i, pick in enumerate(top10, 1):
        player = pick['player']
        stat = pick['stat']
        direction = pick['direction'].upper()
        line = pick['line']
        prob = round(pick['probability'] * 100, 1)
        team = pick['team']
        opp = pick['opponent']
        # Truncate analysis to first 100 chars
        analysis = pick.get('ollama_notes', 'No analysis')[:100] + "..."
        
        message += f"*{i}. {player}* - {stat} {direction} {line}\n"
        message += f"📊 {team} vs {opp} | 🎯 {prob}%\n"
        message += f"💡 {analysis}\n\n"
    
    message += "🚀 *Built with UFA Analytics*"
    
    # Get subscribers
    subscribers = get_subscribers()
    if not subscribers:
        print("⚠️  No subscribers found. Sending to test mode...")
        print("\n" + "="*70)
        print(message)
        print("="*70)
        return
    
    # Send to all subscribers
    print(f"\n📤 Sending to {len(subscribers)} subscribers...")
    success_count = 0
    
    for chat_id in subscribers:
        if send_message(chat_id, message):
            success_count += 1
            print(f"  ✅ Sent to {chat_id}")
        else:
            print(f"  ❌ Failed to send to {chat_id}")
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n✨ Complete! Sent to {success_count}/{len(subscribers)} subscribers")

if __name__ == "__main__":
    main()
