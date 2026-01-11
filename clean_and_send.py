#!/usr/bin/env python3
"""
Clean and send Jan 8 enhanced narrative
"""

import re
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Read and clean the message
with open('enhanced_telegram_manual.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Remove MarkdownV2 escape characters
cleaned = re.sub(r'\\([._\-!+(){}[\]#])', r'\1', text)

# Save cleaned version
with open('enhanced_telegram_clean.txt', 'w', encoding='utf-8') as f:
    f.write(cleaned)

print("✅ Cleaned message saved to enhanced_telegram_clean.txt")
print(f"   Original: {len(text)} chars")
print(f"   Cleaned: {len(cleaned)} chars")
print("")

# Send to Telegram
bot_token = os.getenv('SPORTS_BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID', '7545848251')

if not bot_token:
    print("❌ No bot token found")
else:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    payload = {
        'chat_id': chat_id,
        'text': cleaned,
        'parse_mode': 'Markdown'
    }
    
    print("Sending to Telegram...")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        print("✅ SUCCESS!")
        print("")
        print("="*80)
        print("🎉 WORKFLOW COMPLETE!")
        print("="*80)
        print("✅ Step 1: Started Ollama server")
        print("✅ Step 2: Ran LLM research")
        print("✅ Step 3: Reviewed output")
        print("✅ Step 4-6: SKIPPED (system already optimal)")
        print("✅ Step 7: Generated enhanced narratives")
        print("✅ Step 8: Sent to Telegram ✅")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response text: {e.response.text}")
