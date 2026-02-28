#!/usr/bin/env python3
"""Quick test for CBB opponent field fix."""

import sys
import json
from pathlib import Path

print("=" * 60)
print("CBB OPPONENT FIX TEST")
print("=" * 60)
print()

# Import CBB ingestion function
sys.path.insert(0, str(Path(__file__).parent))
from sports.cbb.cbb_main import run_cbb_odds_api_ingest

print("[1/3] Running OddsAPI ingestion...")
print("-" * 60)
try:
    run_cbb_odds_api_ingest()
    print("\n✅ Ingestion completed")
except Exception as e:
    print(f"\n❌ Ingestion failed: {e}")
    sys.exit(1)

print("\n[2/3] Checking saved slate file...")
print("-" * 60)
slate_path = Path("sports/cbb/inputs/cbb_slate_latest.json")
if not slate_path.exists():
    print(f"❌ Slate file not found: {slate_path}")
    sys.exit(1)

with open(slate_path) as f:
    data = json.load(f)

props = data.get("props", [])
print(f"   Total props: {len(props)}")

# Check for opponent field
props_with_opponent = [p for p in props if "opponent" in p]
props_with_real_opponent = [p for p in props if p.get("opponent") and p.get("opponent") != "UNK"]

print(f"   Props with 'opponent' field: {len(props_with_opponent)}")
print(f"   Props with real opponent (not UNK): {len(props_with_real_opponent)}")

print("\n[3/3] Sample props:")
print("-" * 60)
for i, prop in enumerate(props[:5]):
    player = prop.get("player", "?")
    team = prop.get("team", "?")
    opponent = prop.get("opponent", "MISSING")
    stat = prop.get("stat", "?")
    line = prop.get("line", "?")
    print(f"   {i+1}. {player} ({team} vs {opponent}) — {stat} {line}")

print()
print("=" * 60)
if len(props_with_opponent) == len(props):
    print("✅ SUCCESS: All props have opponent field")
    if len(props_with_real_opponent) > 0:
        print(f"✅ SUCCESS: {len(props_with_real_opponent)} props have real opponents")
    else:
        print("⚠️  WARNING: All opponents are 'UNK' (roster resolution may have failed)")
else:
    print(f"❌ FAILURE: {len(props) - len(props_with_opponent)} props missing opponent field")
print("=" * 60)
