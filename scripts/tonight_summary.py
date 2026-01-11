"""Quick view of tonight's games and best available picks."""
import json
from collections import defaultdict

# Load data
picks = json.load(open('picks.json', encoding='utf-8'))
try:
    hydrated = json.load(open('picks_hydrated.json', encoding='utf-8'))
    hydrated_keys = {(p['player'], p['stat'], p['line'], p['direction']) for p in hydrated}
except:
    hydrated_keys = set()

# Group by game
games = defaultdict(list)
for pick in picks:
    matchup = pick.get('matchup', 'Unknown')
    game_time = pick.get('game_time', 'TBD')
    key = (pick['player'], pick['stat'], pick['line'], pick['direction'])
    
    is_hydrated = key in hydrated_keys
    games[f"{matchup} - {game_time}"].append({
        'player': pick['player'],
        'stat': pick['stat'],
        'line': pick['line'],
        'direction': pick['direction'],
        'hydrated': is_hydrated
    })

# Print summary
print("="*80)
print(" TONIGHT'S SLATE SUMMARY")
print("="*80)
print(f"Total picks: {len(picks)}")
print(f"Hydrated picks: {len(hydrated_keys)}")
print(f"Games: {len(games)}")
print("\n" + "="*80)
print(" GAMES TONIGHT")
print("="*80)

for game, game_picks in sorted(games.items()):
    hydrated_count = sum(1 for p in game_picks if p['hydrated'])
    total = len(game_picks)
    
    print(f"\n{game}")
    print(f"  Props: {total} | Hydrated: {hydrated_count}/{total} ({100*hydrated_count//total if total else 0}%)")
    
    # Show sample hydrated props
    hydrated_props = [p for p in game_picks if p['hydrated']]
    if hydrated_props:
        print(f"  Ready to analyze: {', '.join([p['player'] for p in hydrated_props[:3]])}...")

print("\n" + "="*80)
print(f" 💡 Hydration progress: {len(hydrated_keys)}/{len(picks)} ({100*len(hydrated_keys)//len(picks) if len(picks) else 0}%)")
print("="*80)
