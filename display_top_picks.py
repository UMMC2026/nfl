#!/usr/bin/env python3
"""Display top 10 over and top 5 under picks from real game slate."""

import json
from scipy.stats import norm

# Load slate
with open('realistic_game_slate.json') as f:
    slate = json.load(f)

# Calculate probabilities for each prop
results = []
for prop in slate['props']:
    player = prop['player']
    stat = prop['stat']
    line = prop['line']
    direction = prop['direction']
    
    # Known hydrated stats
    stats_data = {
        ('Patrick Mahomes', 'pass_yds'): {'mu': 264.80, 'sigma': 34.49},
        ('Travis Kelce', 'rec_yds'): {'mu': 47.60, 'sigma': 20.28},
        ('Mike Evans', 'rec_yds'): {'mu': 30.90, 'sigma': 24.29},
        ('Leonard Fournette', 'rush_yds'): {'mu': 52.0, 'sigma': 18.0},
        ('Chris Jones', 'pass_yds'): {'mu': None, 'sigma': None},  # Defense stat
    }
    
    key = (player, stat)
    data = stats_data.get(key)
    
    if data and data['mu']:
        if direction.lower() == 'higher':
            prob_over = 1 - norm.cdf(line, loc=data['mu'], scale=data['sigma'])
        else:
            prob_over = norm.cdf(line, loc=data['mu'], scale=data['sigma'])
    else:
        prob_over = 0.25
    
    results.append({
        'player': player,
        'stat': stat,
        'line': line,
        'prob_over': prob_over,
        'mu': data['mu'] if data else None
    })

# Separate overs and unders
overs = sorted(results, key=lambda x: x['prob_over'], reverse=True)
unders = sorted(results, key=lambda x: x['prob_over'])

print('\n' + '='*90)
print(' 🔥 TOP 10 OVER PICKS (By Probability)')
print('='*90)
print()

for i, pick in enumerate(overs[:10], 1):
    prob_pct = pick['prob_over'] * 100
    status = '✅ QUALIFIED' if prob_pct >= 65 else '⚠️  MARGINAL'
    mu = pick['mu'] if pick['mu'] else 'N/A'
    print(f'{i:2d}. {pick["player"]:20s} | {pick["stat"]:10s} > {pick["line"]:7.1f}')
    print(f'    P(Over): {prob_pct:5.1f}% | Mean: {str(mu):8s} | {status}')
    print()

print('\n' + '='*90)
print(' ❄️  TOP 5 UNDER PICKS (By Probability)')
print('='*90)
print()

for i, pick in enumerate(unders[:5], 1):
    prob_under = (1 - pick['prob_over']) * 100
    prob_over = pick['prob_over'] * 100
    status = '✅ QUALIFIED' if prob_under >= 65 else '⚠️  MARGINAL'
    mu = pick['mu'] if pick['mu'] else 'N/A'
    print(f'{i}. {pick["player"]:20s} | {pick["stat"]:10s} < {pick["line"]:7.1f}')
    print(f'   P(Under): {prob_under:5.1f}% (Over: {prob_over:5.1f}%) | Mean: {str(mu):8s} | {status}')
    print()

print('='*90)
print(f'Summary: {len(overs)} Over picks | {len(unders)} Under picks')
print('='*90 + '\n')
