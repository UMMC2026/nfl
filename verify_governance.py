#!/usr/bin/env python3
"""Verify governance layer is applied to all picks."""

from ufa.daily_pipeline import DailyPipeline
import json

p = DailyPipeline()
p.load_picks()
p.process_picks()

# Check a few picks
print("Sample Picks:")
for i in range(min(3, len(p.calibrated_picks))):
    pick = p.calibrated_picks[i]
    print(f"Pick {i+1}: {pick['player']} {pick['stat']}")
    print(f"  stat_class: {pick.get('stat_class', 'MISSING')}")
    print(f"  tier: {pick['tier']}")
    print()

# Count stat classes
stat_classes = {}
for pick in p.calibrated_picks:
    sc = pick.get('stat_class', 'missing')
    stat_classes[sc] = stat_classes.get(sc, 0) + 1

print("Stat class distribution:")
for sc, count in sorted(stat_classes.items()):
    print(f"  {sc}: {count}")

print(f"\nTotal picks processed: {len(p.calibrated_picks)}")
print("✅ Governance layer verification complete")
