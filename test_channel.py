"""Test sending to UMMCSPORTS Telegram channel."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
channel_id = "-1003743893834"  # TELEGRAM_CHANNEL_ID from .env

print(f"🔑 Token: {token[:20]}...")
print(f"📢 Channel ID: {channel_id}")
print()

url = f"https://api.telegram.org/bot{token}/sendMessage"

payload = {
    "chat_id": channel_id,
    "text": "🏈 *NFL TOP 10 TEST*\n\nThis is a test message to verify channel delivery.\n\n✅ If you see this, the channel is working!",
    "parse_mode": "Markdown"
}

print(f"📤 Sending to channel...")

try:
    response = requests.post(url, json=payload, timeout=10)
    data = response.json()
    
    print(f"📊 Status: {response.status_code}")
    
    if data.get("ok"):
        print("✅ Message sent to UMMCSPORTS channel successfully!")
        print(f"📄 Message ID: {data['result']['message_id']}")
    else:
        print(f"❌ Error: {data.get('description', 'Unknown error')}")
        print(f"📄 Full response: {data}")
        
except Exception as e:
    print(f"❌ Exception: {e}")
