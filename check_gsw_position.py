import json

with open('picks.json') as f:
    picks = json.load(f)

gsw_picks = [(i, p['player']) for i, p in enumerate(picks) if p['team'] == 'GSW']

print(f"Total GSW picks: {len(gsw_picks)}")
print(f"\nFirst 10 GSW picks:")
for idx, player in gsw_picks[:10]:
    print(f"  Position {idx}: {player}")

print(f"\nLast hydrated was pick ~757")
print(f"First GSW at position: {gsw_picks[0][0] if gsw_picks else 'None'}")
