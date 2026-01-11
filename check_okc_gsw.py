import json

# Load hydrated picks
with open('picks_hydrated.json') as f:
    hydrated = json.load(f)

# Filter OKC/GSW with stats
okc_gsw = [p for p in hydrated if p.get('team') in ['OKC', 'GSW'] and 'mu' in p and p.get('mu') is not None]

print(f"OKC/GSW picks with stats: {len(okc_gsw)}")
print("\nTop picks:")
for p in okc_gsw[:15]:
    player = p['player']
    stat = p['stat']
    line = p['line']
    mu = p.get('mu', 0)
    sigma = p.get('sigma', 0)
    direction = p['direction']
    
    # Calculate rough probability
    if sigma > 0:
        z = (line - mu) / sigma
        if direction == 'higher':
            prob = 100 - (50 + 50 * (z / (1 + abs(z)**0.5)))
        else:
            prob = 50 + 50 * (z / (1 + abs(z)**0.5))
    else:
        prob = 0
    
    print(f"{player:25} {direction:8} {line:5} {stat:15} mu:{mu:5.1f} prob:{prob:3.0f}%")
