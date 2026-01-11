import json
from engine.normalize_picks import normalize_picks

with open('picks_hydrated.json') as f:
    picks = json.load(f)

normalized = normalize_picks(picks[:10])
for p in normalized:
    team = p.get('team', 'X')
    opponent = p.get('opponent', 'NONE')
    player = p.get('player', 'X')
    print(f"{team} vs {opponent} | {player}")
