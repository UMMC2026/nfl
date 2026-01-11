"""Quick test of parlay builder."""
import json
from itertools import combinations
from ufa.daily_pipeline import DailyPipeline

pipeline = DailyPipeline()
with open('picks_hydrated.json', 'r') as f:
    pipeline.picks = json.load(f)

calibrated = pipeline.process_picks()

# Filter to SLAM/STRONG
good_picks = [p for p in calibrated if p.get('tier') in ['SLAM', 'STRONG']]
print(f'Found {len(good_picks)} SLAM/STRONG picks')

# Build 5-leg parlays
legs = 5
parlays = []
for combo in combinations(good_picks, legs):
    teams = set(p.get('team') for p in combo)
    if len(teams) < 2:
        continue
    players = [p.get('player') for p in combo]
    if len(players) != len(set(players)):
        continue
    
    combined_prob = 1.0
    for p in combo:
        combined_prob *= p.get('display_prob', 0.5)
    
    edge = (combined_prob - 0.167) / 0.167 * 100
    parlays.append({'picks': combo, 'prob': combined_prob, 'edge': edge, 'teams': len(teams)})

parlays.sort(key=lambda x: x['edge'], reverse=True)

print(f'\nTop 5 {legs}-Leg Parlays:\n')
for i, p in enumerate(parlays[:5], 1):
    print(f'=== Parlay #{i} ===')
    print(f"Combined: {p['prob']*100:.1f}% | Edge: {p['edge']:+.1f}% | Teams: {p['teams']}")
    for pick in p['picks']:
        dir_sym = 'O' if pick['direction'] == 'higher' else 'U'
        print(f"  {pick['player']} ({pick['team']}) {dir_sym} {pick['line']} {pick['stat']} [{pick['display_prob']*100:.0f}%]")
    print()
