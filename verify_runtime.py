#!/usr/bin/env python3
"""Verify runtime is locked (SOP verification)."""
import sys
import os
from pathlib import Path

print("\n" + "="*60)
print("RUNTIME VERIFICATION (SOP)")
print("="*60 + "\n")

# 1. Python interpreter
expected_path = r"C:\Users\hiday\UNDERDOG ANANLYSIS\.venv\Scripts\python.exe"
current_path = sys.executable

print(f"Expected: {expected_path}")
print(f"Current:  {current_path}")

if current_path.lower() == expected_path.lower():
    print("✅ PYTHON LOCKED")
else:
    print("❌ WRONG PYTHON")
    sys.exit(1)

print()

# 2. Telegram version
try:
    import telegram
    print(f"Telegram version: {telegram.__version__}")
    if telegram.__version__ == "13.15":
        print("✅ TELEGRAM LOCKED (v13.15)")
    else:
        print(f"❌ WRONG TELEGRAM VERSION (need 13.15, have {telegram.__version__})")
        sys.exit(1)
except Exception as e:
    print(f"❌ TELEGRAM NOT INSTALLED: {e}")
    sys.exit(1)

print()

# 3. Requirements file
if Path("requirements.txt").exists():
    print(f"✅ requirements.txt found")
else:
    print(f"❌ requirements.txt missing")
    sys.exit(1)

print()

# 4. .env file
if Path(".env").exists():
    print(f"✅ .env configured")
else:
    print(f"❌ .env missing")
    sys.exit(1)

print()
print("="*60)
print("✅ RUNTIME LOCKED - ALL SYSTEMS GO")
print("="*60)
print("\nCommand to start bot:")
print("  python start_bot.py")
print()
