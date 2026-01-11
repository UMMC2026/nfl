import json
from collections import Counter

with open('output/signals_latest.json') as f:
    signals = json.load(f)

print(f"\n{'='*70}")
print(f"TONIGHT'S SIGNALS SUMMARY - {len(signals)} Total")
print(f"{'='*70}\n")

# Player counts
player_counts = Counter(x['player'] for x in signals)
print("PLAYERS:")
for player, count in player_counts.most_common():
    print(f"  {player}: {count} props")

# Teams
team_counts = Counter(x['team'] for x in signals)
print(f"\nTEAMS ({len(team_counts)} teams):")
for team, count in sorted(team_counts.items()):
    print(f"  {team}: {count} props")

# Games
games = set(x.get('game_id', 'N/A') for x in signals)
print(f"\nGAMES: {len(games)} games tonight")

# Garland breakdown
garland = [x for x in signals if 'Garland' in x['player']]
print(f"\n{'='*70}")
print(f"DARIUS GARLAND PROPS ({len(garland)} total):")
print(f"{'='*70}")
for g in garland:
    play = "OVER" if g['direction'] == 'higher' else 'UNDER'
    print(f"\n{g['stat']} {play} {g['line']}")
    print(f"  Probability: {g.get('probability', 0)*100:.1f}%")
    print(f"  Tier: {g.get('confidence_tier', 'N/A')}")
    print(f"  Analysis: {g.get('ollama_notes', 'N/A')[:100]}...")
