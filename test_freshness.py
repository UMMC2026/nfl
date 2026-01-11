#!/usr/bin/env python3
"""Quick freshness test"""
from pathlib import Path
import time
from datetime import datetime

OUTPUT_FILE = Path("outputs/validated_primary_edges.json")
MAX_AGE_SECONDS = 120 * 60

if OUTPUT_FILE.exists():
    age = time.time() - OUTPUT_FILE.stat().st_mtime
    ts = datetime.fromtimestamp(OUTPUT_FILE.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    print(f"✅ File timestamp: {ts} (age: {int(age/60)} min)")
    print(f"   Max allowed: {int(MAX_AGE_SECONDS/60)} min")
    if age > MAX_AGE_SECONDS:
        print(f"❌ STALE: Would be rejected")
    else:
        print(f"✅ FRESH: Would be accepted for Telegram")
else:
    print("❌ File not found")
