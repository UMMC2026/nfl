"""Monte Carlo optimizer for CLE @ PHI slate"""
import json
from pathlib import Path
from datetime import datetime
from itertools import combinations
import random

data = json.loads(Path('outputs/CLE_PHI_FULL_RISK_FIRST_20260116_FROM_UD.json').read_text(encoding='utf-8'))
results = data.get('results', [])

picks = []
for r in results:
    decision = r.get('decision', r.get('status', ''))
    if decision in ['PLAY', 'LEAN']:
        picks.append({
            'player': r['player'],
            'team': r['team'],
            'stat': r['stat'],
            'direction': r['direction'],
            'line': r['line'],
            'p_hit': r['effective_confidence'] / 100.0,
        })

print(f'Found {len(picks)} playable picks')
print()

POWER_PAYOUTS = {2: 3.0, 3: 6.0, 4: 10.0, 5: 20.0}
FLEX_PAYOUTS = {
    3: {3: 2.25, 2: 1.25},
    4: {4: 5.0, 3: 1.5},
    5: {5: 10.0, 4: 2.0, 3: 0.5}
}

def sim_power(probs, payout, n=10000):
    wins = sum(1 for _ in range(n) if all(random.random() < p for p in probs))
    return wins/n, (wins/n)*payout - 1

def sim_flex(probs, payouts, n=10000):
    total = 0
    wins = 0
    for _ in range(n):
        hits = sum(1 for p in probs if random.random() < p)
        pay = payouts.get(hits, 0)
        total += pay
        if pay > 0:
            wins += 1
    return wins/n, total/n - 1

print('='*60)
print('MONTE CARLO - CLE @ PHI')
print('='*60)
for p in picks:
    pname = p['player']
    stat = p['stat']
    dir_ = p['direction']
    line = p['line']
    prob = p['p_hit']*100
    print(f'  {pname} {stat} {dir_} {line} ({prob:.1f}%)')
print()

best_power = []
best_flex = []

for legs in range(2, min(6, len(picks)+1)):
    for combo in combinations(range(len(picks)), legs):
        cp = [picks[i] for i in combo]
        probs = [p['p_hit'] for p in cp]
        teams = set(p['team'] for p in cp)
        if len(teams) < 2:
            continue
        if legs in POWER_PAYOUTS:
            wr, ev = sim_power(probs, POWER_PAYOUTS[legs])
            best_power.append({'legs': legs, 'picks': cp, 'wr': wr, 'ev': ev})
        if legs in FLEX_PAYOUTS:
            wr, ev = sim_flex(probs, FLEX_PAYOUTS[legs])
            best_flex.append({'legs': legs, 'picks': cp, 'wr': wr, 'ev': ev})

best_power.sort(key=lambda x: x['ev'], reverse=True)
best_flex.sort(key=lambda x: x['ev'], reverse=True)

print('TOP POWER ENTRIES (Must hit all):')
print('-'*60)
for i, e in enumerate(best_power[:5], 1):
    legs = e['legs']
    wr = e['wr']
    ev = e['ev']
    print(f'{i}. {legs}L POWER | Win: {wr*100:.1f}% | EV: {ev:+.2f}')
    for p in e['picks']:
        print(f"    {p['player']} {p['stat']} {p['direction']} {p['line']}")
    print()

print()
print('TOP FLEX ENTRIES (Partial payouts):')
print('-'*60)
for i, e in enumerate(best_flex[:5], 1):
    legs = e['legs']
    wr = e['wr']
    ev = e['ev']
    print(f'{i}. {legs}L FLEX | Profit: {wr*100:.1f}% | EV: {ev:+.2f}')
    for p in e['picks']:
        print(f"    {p['player']} {p['stat']} {p['direction']} {p['line']}")
    print()

# Save
out_file = f"outputs/monte_carlo_CLE_PHI_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
with open(out_file, 'w') as f:
    f.write('='*60 + '\n')
    f.write('MONTE CARLO - CLE @ PHI\n')
    f.write('='*60 + '\n\n')
    f.write('PICKS:\n')
    for p in picks:
        f.write(f"  {p['player']} {p['stat']} {p['direction']} {p['line']} ({p['p_hit']*100:.1f}%)\n")
    f.write('\nTOP POWER:\n')
    for i, e in enumerate(best_power[:3], 1):
        f.write(f"{i}. {e['legs']}L | Win: {e['wr']*100:.1f}% | EV: {e['ev']:+.2f}\n")
        for p in e['picks']:
            f.write(f"    {p['player']} {p['stat']} {p['direction']} {p['line']}\n")
    f.write('\nTOP FLEX:\n')
    for i, e in enumerate(best_flex[:3], 1):
        f.write(f"{i}. {e['legs']}L | Profit: {e['wr']*100:.1f}% | EV: {e['ev']:+.2f}\n")
        for p in e['picks']:
            f.write(f"    {p['player']} {p['stat']} {p['direction']} {p['line']}\n")

print(f'Saved: {out_file}')
