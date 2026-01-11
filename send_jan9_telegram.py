#!/usr/bin/env python3
"""
Send January 9 enhanced analysis to Telegram
Handles 4096 char limit with smart splitting
"""

import re
import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def split_message(text, max_length=4000):
    """Split message at natural boundaries (section breaks)"""
    parts = []
    current = ""
    
    # Split by sections (= separators)
    sections = text.split("=" * 50)
    
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # If adding this section would exceed limit, save current and start new
        if len(current) + len(section) + 55 > max_length:
            if current:
                parts.append(current)
            current = section
        else:
            if current:
                current += "\n\n" + "=" * 50 + "\n\n" + section
            else:
                current = section
    
    if current:
        parts.append(current)
    
    return parts

def send_to_telegram(bot_token, chat_id, message):
    """Send message via Telegram Bot API"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Send failed: {e}")
        return False

def main():
    """Main execution"""
    print("📱 TELEGRAM BROADCAST - JANUARY 9 ANALYSIS")
    print("=" * 70)
    
    # Load credentials
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("❌ ERROR: Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env")
        return
    
    print(f"🔑 Bot Token: {bot_token[:10]}...")
    print(f"💬 Chat ID: {chat_id}")
    print()
    
    # Read enhanced message
    message_file = Path('outputs/enhanced_telegram_jan9.txt')
    if not message_file.exists():
        print(f"❌ ERROR: {message_file} not found")
        return
    
    with open(message_file, 'r', encoding='utf-8') as f:
        text = f.read()
    
    print(f"📄 Message loaded: {len(text)} characters")
    
    # Clean Markdown escaping
    cleaned = re.sub(r'\\([._\-!+(){}[\]#])', r'\1', text)
    
    # Split into parts
    parts = split_message(cleaned, max_length=4000)
    
    print(f"📦 Split into {len(parts)} parts")
    print()
    
    # Send each part
    for i, part in enumerate(parts, 1):
        print(f"📤 Sending part {i}/{len(parts)} ({len(part)} chars)...")
        
        success = send_to_telegram(bot_token, chat_id, part)
        
        if success:
            print(f"   ✅ Part {i} sent successfully")
        else:
            print(f"   ❌ Part {i} failed")
            break
        
        # Rate limit (1 message per second)
        if i < len(parts):
            time.sleep(1.5)
    
    print()
    print("=" * 70)
    print("✅ BROADCAST COMPLETE")

if __name__ == '__main__':
    main()
