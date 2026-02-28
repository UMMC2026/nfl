"""Test telegram_send_to_channel function from nfl_top10_telegram.py"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

# Import function
from nfl_top10_telegram import telegram_send_to_channel

print("🧪 Testing telegram_send_to_channel()...")
print(f"✓ Token loaded: {bool(os.getenv('TELEGRAM_BOT_TOKEN'))}")
print(f"✓ Channel ID: {os.getenv('TELEGRAM_CHANNEL_ID', '-1003743893834')}")
print()

result = telegram_send_to_channel("🏈 *TEST MESSAGE*\n\nTesting channel send function")

if result:
    print("✅ Message sent successfully!")
else:
    print("❌ Send failed")
