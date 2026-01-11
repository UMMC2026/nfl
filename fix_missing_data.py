import json

with open('picks_hydrated.json', 'r') as f:
    picks = json.load(f)

# Fix picks without data - set default mu/sigma based on line
fixed = 0
for p in picks:
    if p.get('recent_values') is None and p.get('mu') is None:
        # Use line as mu with 20% std (coin flip probability)
        p['mu'] = p['line']
        p['sigma'] = p['line'] * 0.2
        print(f"Fixed: {p['player']} - {p['stat']} (no data, defaulting to 50%)")
        fixed += 1

with open('picks_hydrated.json', 'w') as f:
    json.dump(picks, f, indent=2)

print(f"\nDone - fixed {fixed} picks")
