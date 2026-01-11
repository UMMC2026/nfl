import json

with open('picks.json', 'r') as f:
    picks = json.load(f)

# Find MIL picks  
mil_picks = [p for p in picks if p.get('team') == 'MIL']
print(f'Total MIL picks: {len(mil_picks)}')
print()
for p in mil_picks[:15]:
    print(f"{p.get('player')} - {p.get('stat')}: {p.get('line')} {p.get('direction')}")
