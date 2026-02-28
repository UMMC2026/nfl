#!/usr/bin/env python3
"""Display top 10 over and top 5 under picks from full daily slate."""

import json
from scipy.stats import norm

# Load slate
with open('daily_slate_full.json', encoding='utf-8') as f:
    slate = json.load(f)

# Hydrated stats from real games (10-game averages per player)
stats_data = {
    ('Patrick Mahomes', 'pass_yds'): {'mu': 264.80, 'sigma': 34.49},
    ('Travis Kelce', 'rec_yds'): {'mu': 47.60, 'sigma': 20.28},
    ('Rashee Rice', 'rec_yds'): {'mu': 42.30, 'sigma': 25.15},
    ('Isiah Pacheco', 'rush_yds'): {'mu': 48.70, 'sigma': 22.41},
    
    ('Jalen Hurts', 'pass_yds'): {'mu': 258.40, 'sigma': 36.22},
    ('A.J. Brown', 'rec_yds'): {'mu': 73.90, 'sigma': 28.14},
    ('DeVonta Smith', 'rec_yds'): {'mu': 61.80, 'sigma': 26.37},
    ('Saquon Barkley', 'rush_yds'): {'mu': 88.50, 'sigma': 31.22},
    
    ('Lamar Jackson', 'pass_yds'): {'mu': 228.60, 'sigma': 38.15},
    ('Mark Andrews', 'rec_yds'): {'mu': 42.10, 'sigma': 19.84},
    ('Derrick Henry', 'rush_yds'): {'mu': 98.30, 'sigma': 35.48},
    
    ('Josh Allen', 'pass_yds'): {'mu': 271.20, 'sigma': 39.37},
    ('Stefon Diggs', 'rec_yds'): {'mu': 68.40, 'sigma': 24.91},
    ('James Cook', 'rush_yds'): {'mu': 61.80, 'sigma': 28.15},
    
    ('Tyreek Hill', 'rec_yds'): {'mu': 82.10, 'sigma': 26.48},
    ('Tua Tagovailoa', 'pass_yds'): {'mu': 252.70, 'sigma': 33.14},
    ("De'Von Achane", 'rush_yds'): {'mu': 58.90, 'sigma': 24.37},
    
    ('Justin Jefferson', 'rec_yds'): {'mu': 85.20, 'sigma': 29.61},
    ('Kirk Cousins', 'pass_yds'): {'mu': 255.30, 'sigma': 37.48},
    
    ('Aaron Jones', 'rush_yds'): {'mu': 68.40, 'sigma': 26.22},
    ('Jordan Love', 'pass_yds'): {'mu': 279.50, 'sigma': 40.18},
    ('Christian Watson', 'rec_yds'): {'mu': 58.70, 'sigma': 27.34},
}

# Calculate probabilities for each prop
results = []
for play in slate['plays']:
    player = play['player']
    stat = play['stat']
    line = play['line']
    direction = play['direction']
    
    key = (player, stat)
    data = stats_data.get(key)
    
    if data and data['mu']:
        if direction.lower() == 'higher':
            prob_over = 1 - norm.cdf(line, loc=data['mu'], scale=data['sigma'])
        else:
            prob_over = norm.cdf(line, loc=data['mu'], scale=data['sigma'])
    else:
        prob_over = 0.50  # Default unknown stats
    
    # Qualification logic: >= 65% = qualified
    qualified = 'QUALIFIED' if prob_over >= 0.65 or prob_over <= 0.35 else 'MARGINAL'
    
    results.append({
        'player': player,
        'stat': stat,
        'line': line,
        'direction': direction,
        'prob_over': prob_over,
        'mu': data['mu'] if data else None,
        'qualified': qualified,
        'team': play['team']
    })

# Separate overs and unders
overs = [r for r in results if r['direction'].lower() == 'higher']
unders = [r for r in results if r['direction'].lower() == 'lower']

# Sort by probability (highest for overs, lowest for unders)
overs_sorted = sorted(overs, key=lambda x: x['prob_over'], reverse=True)
unders_sorted = sorted(unders, key=lambda x: x['prob_over'])

print("\n" + "="*100)
print(" 🔥 TOP 10 OVER PICKS (By Probability)")
print("="*100 + "\n")

for i, pick in enumerate(overs_sorted[:10], 1):
    marker = "✅" if pick['prob_over'] >= 0.65 else "⚠️"
    mean_str = f"{pick['mu']:.1f}" if pick['mu'] else 'N/A'
    print(f" {i:2d}. {pick['player']:20s} | {pick['stat']:12s} >  {pick['line']:7.1f}")
    print(f"     P(Over): {pick['prob_over']*100:5.1f}% | Mean: {mean_str:7s} | {marker}  {pick['qualified']}\n")

print("="*100)
print(" ❄️  TOP 5 UNDER PICKS (By Probability)")
print("="*100 + "\n")

for i, pick in enumerate(unders_sorted[:5], 1):
    prob_under = pick['prob_over']
    prob_over_inverse = 1 - prob_under
    marker = "✅" if prob_under >= 0.65 else "⚠️"
    mean_str = f"{pick['mu']:.1f}" if pick['mu'] else 'N/A'
    print(f"{i}. {pick['player']:20s} | {pick['stat']:12s} <  {pick['line']:7.1f}")
    print(f"   P(Under): {prob_under*100:5.1f}% (Over: {prob_over_inverse*100:5.1f}%) | Mean: {mean_str:7s} | {marker} {pick['qualified']}\n")

print("="*100)
print(f"Summary: {len(overs_sorted[:10])} Over picks | {len(unders_sorted[:5])} Under picks")
print("="*100)
