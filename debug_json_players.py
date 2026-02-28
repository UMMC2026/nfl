import json

with open('outputs/NOP_SAS1_RISK_FIRST_20260125_FROM_UD.json', 'r') as f:
    data = json.load(f)

props = data if isinstance(data, list) else data.get('props', [])

print(f"Total props: {len(props)}\n")
print("Sample players:")
for p in props[:10]:
    print(f"  {p['player']} ({p['team']}) - {p['market']}")
