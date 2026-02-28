"""
Verify ESPNCBBFetcher.get_player_stats() now returns current-season data.

Solomon Washington (Maryland) career: ~5.8 PTS, 113 GP
Current season 2025-26:         ~10.1 PTS, ~16 GP
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sports.cbb.ingest.cbb_data_provider import ESPNCBBFetcher

fetcher = ESPNCBBFetcher()
SOLOMON_ID = "5105562"

print("=== get_player_stats() after fix ===")
player = fetcher.get_player_stats(SOLOMON_ID)
if player is None:
    print("FAIL: player is None")
    sys.exit(1)

print(f"  Name:  {player.name}")
print(f"  GP:    {player.games_played}")
print(f"  PTS:   {player.points_per_game:.2f}")
print(f"  REB:   {player.rebounds_per_game:.2f}")
print(f"  AST:   {player.assists_per_game:.2f}")
print(f"  MIN:   {player.minutes_per_game:.2f}")

# Assertions — current-season data, NOT career
passed = 0
total = 3

# GP should be < 40 (current season), NOT 113 (career)
if player.games_played < 40:
    print(f"  [PASS] GP={player.games_played} < 40 (current season, not career)")
    passed += 1
else:
    print(f"  [FAIL] GP={player.games_played} — looks like career data!")

# PTS should be > 8 (current season ~10.1), NOT ~5.8 (career)
if player.points_per_game > 8.0:
    print(f"  [PASS] PTS={player.points_per_game:.2f} > 8.0 (current season)")
    passed += 1
else:
    print(f"  [FAIL] PTS={player.points_per_game:.2f} — still looks like career avg!")

# REB should be > 7 (current season ~8.75), NOT ~5.2 (career)
if player.rebounds_per_game > 7.0:
    print(f"  [PASS] REB={player.rebounds_per_game:.2f} > 7.0 (current season)")
    passed += 1
else:
    print(f"  [FAIL] REB={player.rebounds_per_game:.2f} — still looks like career avg!")

print(f"\n{'='*40}")
print(f"  RESULT: {passed}/{total} assertions passed")
if passed == total:
    print("  ✓ ESPN data provider now returns CURRENT SEASON stats")
else:
    print("  ✗ Fix incomplete — still getting career data")
