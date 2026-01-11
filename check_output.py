import json
with open('outputs/validated_primary_edges.json') as f:
    edges = json.load(f)

# Check unique game_ids
game_ids = set()
for e in edges:
    game_ids.add(e.get('game_id', 'UNKNOWN'))

print(f"Unique game_ids in output: {len(game_ids)}")
for gid in sorted(game_ids)[:10]:
    print(f"  {gid}")

# Check no Kevin Durant in BKN
print("\nKevin Durant team assignments:")
for e in edges:
    if 'Kevin' in e.get('player', '') and 'Durant' in e.get('player', ''):
        print(f"  {e['player']}: {e['team']}")
