"""
Check for missing player/stat combos between slate and stat cache.
"""
import json
from pathlib import Path

# CONFIG
slate_file = 'phi_ind_slate_20260119.json'  # Update if needed
cache_file = 'outputs/stats_cache/nba_mu_sigma_L10_L5_blend0.65_auto_2026-01-19.json'

# Load slate
with open(slate_file, 'r') as f:
    slate = json.load(f)

# Load cache
with open(cache_file, 'r') as f:
    cache = json.load(f)

# Build player/stat set from cache
cache_players = set()
cache_stats = set()
for player, stats in cache.items():
    cache_players.add(player.strip().lower())
    for stat in stats:
        cache_stats.add(stat.strip().lower())

missing = []
for pick in slate:
    player = pick['player'].strip().lower()
    stat = pick['stat'].strip().lower()
    if player not in cache_players:
        missing.append((pick['player'], pick['stat'], 'PLAYER NOT IN CACHE'))
    elif stat not in cache_stats:
        missing.append((pick['player'], pick['stat'], 'STAT NOT IN CACHE'))

if missing:
    print("=== MISSING PLAYER/STAT COMBOS ===")
    for p, s, reason in missing:
        print(f"{p:20} {s:15}  -->  {reason}")
else:
    print("All player/stat combos in slate are present in the stat cache!")
