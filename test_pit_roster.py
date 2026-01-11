#!/usr/bin/env python3
"""Test ESPN roster fetch with gamelog enrichment."""

import sys
sys.path.insert(0, ".")

from ufa.ingest.espn import ESPNFetcher

print("=" * 60)
print("Testing PIT Roster Fetch with 2025 Stats")
print("=" * 60)

fetcher = ESPNFetcher(season=2025)

print("\nFetching roster...")
roster = fetcher.get_team_roster("PIT")
print(f"Found {len(roster)} players on roster")

# Check skill positions
skill_players = [p for p in roster if p.position in ["QB", "RB", "WR", "TE"]]
print(f"Skill position players: {len(skill_players)}")

print("\nPlayers with stats:")
for p in skill_players[:10]:
    total = p.pass_yards + p.rush_yards + p.rec_yards
    if total > 0:
        print(f"  {p.name} ({p.position}): Pass={p.pass_yards}, Rush={p.rush_yards}, Rec={p.rec_yards}")
    else:
        print(f"  {p.name} ({p.position}): [no stats] - ID: {p.id}")

print("\nFetching team season stats...")
team_stats = fetcher.get_team_season_stats("PIT")
print(f"Players with stats: {len(team_stats)}")

for p in team_stats[:10]:
    print(f"  {p.name} ({p.position}): Pass={p.pass_yards}, Rush={p.rush_yards}, Rec={p.rec_yards}")
