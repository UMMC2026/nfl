import json

with open('picks.json', 'r') as f:
    picks = json.load(f)

# Find all players with Lillard
lillard_picks = [p for p in picks if 'Lillard' in p.get('player', '')]
print(f'Lillard picks found: {len(lillard_picks)}')
for p in lillard_picks:
    print(f"{p['player']} ({p['team']}) - {p['stat']}: {p['line']} {p['direction']}")

# Also check for Damian
damian_picks = [p for p in picks if 'Damian' in p.get('player', '')]
print(f'\nDamian picks found: {len(damian_picks)}')
for p in damian_picks:
    print(f"{p['player']} ({p['team']}) - {p['stat']}: {p['line']} {p['direction']}")
