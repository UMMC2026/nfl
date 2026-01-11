#!/usr/bin/env python3
"""Debug why Telegram bot returns no signals."""
import json
from pathlib import Path
from ufa.models.user import PlanTier
from ufa.services.telegram_shaper import filter_and_shape_signals_for_telegram

# Load signals
signals_file = Path("output/signals_latest.json")
print(f"[1] Checking signals file: {signals_file.absolute()}")
print(f"    Exists: {signals_file.exists()}")

if not signals_file.exists():
    print("    ERROR: signals_latest.json not found!")
    exit(1)

with open(signals_file) as f:
    signals = json.load(f)

print(f"\n[2] Loaded {len(signals)} signals")
print(f"    First signal tier: {signals[0].get('tier')}")
print(f"    All tiers present: {set(s.get('tier') for s in signals)}")

# Test filtering
for tier in [PlanTier.FREE, PlanTier.STARTER, PlanTier.PRO]:
    shaped, total = filter_and_shape_signals_for_telegram(signals, tier, limit=-1)
    print(f"\n[3] {tier.value} tier:")
    print(f"    Shaped signals: {len(shaped)}")
    print(f"    Total available: {total}")
    
    if shaped:
        print(f"    Sample (first): {shaped[0].get('player')} {shaped[0].get('stat')}")
    else:
        print(f"    ⚠️  NO SIGNALS RETURNED FOR {tier.value} TIER!")

# Check what filter is looking for
print(f"\n[4] Filter criteria check:")
print(f"    FREE expects: tier == 'SLAM'")
slam_count = len([s for s in signals if s.get('tier') == 'SLAM'])
print(f"    Signals with tier='SLAM': {slam_count}")

strong_slam = len([s for s in signals if s.get('tier') in ['SLAM', 'STRONG']])
print(f"    Signals with tier in ['SLAM', 'STRONG']: {strong_slam}")
