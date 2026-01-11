import json
from datetime import datetime

with open('outputs/validated_primary_edges.json') as f:
    edges = json.load(f)

print('Sample edges (first 5):')
for e in edges[:5]:
    print(f"  {e['player']} | team={e['team']} | stat={e['stat']} | game_id={e['game_id']}")

print(f"\nTotal edges: {len(edges)}")
print(f"Unique teams: {len(set(e['team'] for e in edges))}")
print(f"Teams: {sorted(set(e['team'] for e in edges))}")
