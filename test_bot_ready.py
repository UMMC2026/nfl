#!/usr/bin/env python3
"""Quick test to verify Telegram bot can load and handle signals."""
import json
from pathlib import Path
import logging

# Setup logging to see what's happening
logging.basicConfig(level=logging.DEBUG)

print("Testing Telegram bot components...\n")

# Test 1: Load signals
print("[1] Loading signals...")
signals_file = Path("output/signals_latest.json")
if signals_file.exists():
    with open(signals_file) as f:
        signals = json.load(f)
    print(f"    ✅ Loaded {len(signals)} signals")
else:
    print(f"    ❌ File not found: {signals_file}")
    exit(1)

# Test 2: Import bot components
print("\n[2] Importing bot modules...")
try:
    from ufa.services.telegram_bot import (
        load_latest_signals,
        filter_and_shape_signals_for_telegram,
        format_signal_for_telegram,
    )
    print("    ✅ Imports successful")
except Exception as e:
    print(f"    ❌ Import failed: {e}")
    exit(1)

# Test 3: Test load_latest_signals()
print("\n[3] Testing load_latest_signals()...")
try:
    sigs = load_latest_signals()
    print(f"    ✅ Loaded {len(sigs)} signals from function")
except Exception as e:
    print(f"    ❌ Error: {e}")
    exit(1)

# Test 4: Test filtering
print("\n[4] Testing filter_and_shape_signals_for_telegram()...")
try:
    from ufa.models.user import PlanTier
    shaped, total = filter_and_shape_signals_for_telegram(sigs, PlanTier.FREE)
    print(f"    ✅ FREE tier: {len(shaped)} signals (total: {total})")
    
    if shaped:
        print(f"       First signal keys: {list(shaped[0].keys())[:5]}...")
    else:
        print(f"    ❌ No signals returned!")
except Exception as e:
    print(f"    ❌ Error: {e}", exc_info=True)
    exit(1)

# Test 5: Test formatting
print("\n[5] Testing format_signal_for_telegram()...")
try:
    if shaped:
        msg = format_signal_for_telegram(shaped[0], PlanTier.FREE, show_probability=False)
        if msg:
            print(f"    ✅ Message generated ({len(msg)} chars)")
            print(f"       Preview: {msg[:100]}...")
        else:
            print(f"    ❌ Message is None/empty")
except Exception as e:
    print(f"    ❌ Error: {e}", exc_info=True)
    exit(1)

print("\n✅ ALL COMPONENT TESTS PASSED")
print("\nBot token status:")
import os
token = os.getenv("TELEGRAM_BOT_TOKEN")
if token:
    print(f"  ✅ TELEGRAM_BOT_TOKEN is set ({len(token)} chars)")
else:
    print(f"  ❌ TELEGRAM_BOT_TOKEN not found in environment")
    print("     Set it with: $env:TELEGRAM_BOT_TOKEN = 'your-token'")
