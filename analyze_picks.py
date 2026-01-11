import json

def prob_under(line, mu, sigma):
    """Calculate P(X < line) using normal CDF approximation"""
    from math import erf, sqrt
    z = (line - mu) / sigma
    return 0.5 * (1 + erf(z / sqrt(2)))

picks = json.load(open('picks_hydrated.json'))

print("=" * 80)
print("TOP UNDER PLAYS (by probability)")
print("=" * 80)

unders = []
for p in picks:
    if p['direction'] == 'lower' and p.get('mu') is not None and p.get('sigma') is not None:
        prob = prob_under(p['line'], p['mu'], p['sigma'])
        unders.append({
            'player': p['player'],
            'team': p['team'],
            'stat': p['stat'],
            'line': p['line'],
            'mu': p['mu'],
            'sigma': p['sigma'],
            'prob': prob
        })

unders.sort(key=lambda x: x['prob'], reverse=True)

print(f"{'Player':25s} {'Team':5s} {'Stat':15s} {'Line':>6s} {'Avg':>6s} {'Prob':>6s}")
print("-" * 70)
for u in unders[:20]:
    print(f"{u['player']:25s} {u['team']:5s} {u['stat']:15s} {u['line']:6.1f} {u['mu']:6.1f} {u['prob']:6.1%}")

print("\n" + "=" * 80)
print("TOP OVER PLAYS (by probability)")
print("=" * 80)

overs = []
for p in picks:
    if p['direction'] == 'higher' and p.get('mu') is not None and p.get('sigma') is not None:
        prob = 1 - prob_under(p['line'], p['mu'], p['sigma'])
        overs.append({
            'player': p['player'],
            'team': p['team'], 
            'stat': p['stat'],
            'line': p['line'],
            'mu': p['mu'],
            'sigma': p['sigma'],
            'prob': prob
        })

overs.sort(key=lambda x: x['prob'], reverse=True)

print(f"{'Player':25s} {'Team':5s} {'Stat':15s} {'Line':>6s} {'Avg':>6s} {'Prob':>6s}")
print("-" * 70)
for o in overs[:20]:
    print(f"{o['player']:25s} {o['team']:5s} {o['stat']:15s} {o['line']:6.1f} {o['mu']:6.1f} {o['prob']:6.1%}")
