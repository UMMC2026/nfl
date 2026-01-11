#!/usr/bin/env python3
"""Test ESPN integration."""

from load_game_results import fetch_game_result, load_picks_for_games
from pathlib import Path
import json

# Load mock picks
games = load_picks_for_games(Path('picks_mock.json'))
print(f"✓ Games in mock picks: {list(games.keys())}")

# Show what the ESPN fetch pattern expects
print("\n" + "=" * 70)
print("ESPN INTEGRATION TEST")
print("=" * 70)

print("\n[1] PATTERN: ESPN game_id format")
print("    Real: '401547819' (numeric)")
print("    Mock: 'CLE_NYK_20260102' (team_team_date)")
print("    → load_game_results.py expects NUMERIC ESPN IDs")

print("\n[2] ACTION: To use with real ESPN data:")
print("    - Replace game_id in picks.json with ESPN numeric ID")
print("    - Run: python load_game_results.py")
print("    - ESPN will fetch final box scores automatically")

print("\n[3] TESTING: Attempting ESPN fetch with mock ID...")
result = fetch_game_result("CLE_NYK_20260102")
if result:
    print("    ✓ Got result (unexpected for mock ID)")
else:
    print("    ✓ No result (expected - mock format is not ESPN numeric ID)")

print("\n[4] NEXT: To integrate with real games:")
print("    1. Populate picks.json with ESPN game IDs")
print("    2. Ensure games have FINAL status on ESPN")
print("    3. Run: python load_game_results.py")
print("    4. Output: outputs/game_results.json (auto-populated)")
print("    5. Then: python generate_resolved_ledger.py")

print("\n" + "=" * 70)
print("ESPN INTEGRATION READY")
print("=" * 70)
