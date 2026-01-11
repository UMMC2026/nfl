import json

with open('picks_hydrated.json') as f:
    hydrated = json.load(f)

curry = [p for p in hydrated if 'Stephen Curry' in p.get('player', '') and 'mu' in p and p.get('mu')]

print(f"Stephen Curry picks hydrated: {len(curry)}")
print()

for p in curry:
    stat = p['stat']
    direction = p['direction']
    line = p['line']
    mu = p.get('mu', 0)
    sigma = p.get('sigma', 0)
    
    # Quick prob calc
    if sigma > 0:
        z = (line - mu) / sigma
        if direction == 'higher':
            prob = 100 - (50 + 50 * (z / (1 + abs(z)**0.5)))
        else:
            prob = 50 + 50 * (z / (1 + abs(z)**0.5))
    else:
        prob = 0
    
    print(f"{stat:15} {direction:8} {line:5.1f}  mu:{mu:5.1f}  prob:{prob:3.0f}%")
