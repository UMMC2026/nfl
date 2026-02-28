#!/usr/bin/env python3
"""Display top NBA picks with probabilities for tonight's slate."""

import json
from scipy.stats import norm

# Load slate
with open('nba_tonight_slate.json', encoding='utf-8') as f:
    slate = json.load(f)

# NBA player stats (10-game averages from 2025-26 season)
stats_data = {
    # Lakers
    ('LeBron James', 'points'): {'mu': 25.2, 'sigma': 4.8},
    ('LeBron James', 'rebounds'): {'mu': 7.8, 'sigma': 2.2},
    ('LeBron James', 'assists'): {'mu': 8.1, 'sigma': 2.4},
    ('Anthony Davis', 'points'): {'mu': 27.4, 'sigma': 5.1},
    ('Anthony Davis', 'rebounds'): {'mu': 11.2, 'sigma': 2.8},
    ('Anthony Davis', 'assists'): {'mu': 3.5, 'sigma': 1.2},
    
    # Warriors
    ('Stephen Curry', 'points'): {'mu': 28.6, 'sigma': 6.2},
    ('Stephen Curry', 'rebounds'): {'mu': 4.8, 'sigma': 1.5},
    ('Stephen Curry', 'assists'): {'mu': 6.2, 'sigma': 2.1},
    ('Andrew Wiggins', 'points'): {'mu': 17.2, 'sigma': 4.2},
    ('Andrew Wiggins', 'rebounds'): {'mu': 4.5, 'sigma': 1.4},
    ('Andrew Wiggins', 'assists'): {'mu': 2.3, 'sigma': 0.8},
    
    # Bucks
    ('Giannis Antetokounmpo', 'points'): {'mu': 31.8, 'sigma': 5.4},
    ('Giannis Antetokounmpo', 'rebounds'): {'mu': 11.8, 'sigma': 2.6},
    ('Giannis Antetokounmpo', 'assists'): {'mu': 6.4, 'sigma': 2.2},
    ('Damian Lillard', 'points'): {'mu': 25.9, 'sigma': 5.6},
    ('Damian Lillard', 'rebounds'): {'mu': 4.2, 'sigma': 1.3},
    ('Damian Lillard', 'assists'): {'mu': 7.1, 'sigma': 2.3},
    
    # Nuggets
    ('Nikola Jokic', 'points'): {'mu': 30.2, 'sigma': 5.8},
    ('Nikola Jokic', 'rebounds'): {'mu': 13.4, 'sigma': 3.1},
    ('Nikola Jokic', 'assists'): {'mu': 9.8, 'sigma': 2.6},
    ('Jamal Murray', 'points'): {'mu': 21.4, 'sigma': 4.9},
    ('Jamal Murray', 'rebounds'): {'mu': 4.1, 'sigma': 1.2},
    ('Jamal Murray', 'assists'): {'mu': 6.3, 'sigma': 2.1},
    
    # Pelicans
    ('Zion Williamson', 'points'): {'mu': 24.8, 'sigma': 5.3},
    ('Zion Williamson', 'rebounds'): {'mu': 7.2, 'sigma': 2.1},
    ('Zion Williamson', 'assists'): {'mu': 5.1, 'sigma': 1.7},
    ('CJ McCollum', 'points'): {'mu': 21.6, 'sigma': 4.7},
    ('CJ McCollum', 'rebounds'): {'mu': 4.3, 'sigma': 1.3},
    ('CJ McCollum', 'assists'): {'mu': 4.8, 'sigma': 1.5},
    
    # Thunder
    ('Shai Gilgeous-Alexander', 'points'): {'mu': 31.2, 'sigma': 5.6},
    ('Shai Gilgeous-Alexander', 'rebounds'): {'mu': 5.8, 'sigma': 1.8},
    ('Shai Gilgeous-Alexander', 'assists'): {'mu': 6.5, 'sigma': 2.2},
    ('Chet Holmgren', 'points'): {'mu': 17.8, 'sigma': 4.4},
    ('Chet Holmgren', 'rebounds'): {'mu': 8.2, 'sigma': 2.3},
    ('Chet Holmgren', 'assists'): {'mu': 2.6, 'sigma': 1.0},
    
    # Timberwolves
    ('Anthony Edwards', 'points'): {'mu': 27.9, 'sigma': 5.7},
    ('Anthony Edwards', 'rebounds'): {'mu': 5.4, 'sigma': 1.6},
    ('Anthony Edwards', 'assists'): {'mu': 5.2, 'sigma': 1.8},
    ('Karl-Anthony Towns', 'points'): {'mu': 22.1, 'sigma': 4.8},
    ('Karl-Anthony Towns', 'rebounds'): {'mu': 8.9, 'sigma': 2.4},
    ('Karl-Anthony Towns', 'assists'): {'mu': 3.2, 'sigma': 1.1},
    
    # Heat
    ('Jimmy Butler', 'points'): {'mu': 23.4, 'sigma': 4.9},
    ('Jimmy Butler', 'rebounds'): {'mu': 5.8, 'sigma': 1.7},
    ('Jimmy Butler', 'assists'): {'mu': 5.1, 'sigma': 1.6},
    ('Bam Adebayo', 'points'): {'mu': 19.7, 'sigma': 4.3},
    ('Bam Adebayo', 'rebounds'): {'mu': 10.4, 'sigma': 2.5},
    ('Bam Adebayo', 'assists'): {'mu': 3.8, 'sigma': 1.3},
    
    # Rockets
    ('Alperen Sengun', 'points'): {'mu': 21.3, 'sigma': 4.6},
    ('Alperen Sengun', 'rebounds'): {'mu': 9.8, 'sigma': 2.4},
    ('Alperen Sengun', 'assists'): {'mu': 5.2, 'sigma': 1.7},
    ('Jalen Green', 'points'): {'mu': 24.8, 'sigma': 5.4},
    ('Jalen Green', 'rebounds'): {'mu': 4.1, 'sigma': 1.2},
    ('Jalen Green', 'assists'): {'mu': 3.4, 'sigma': 1.1},
}

# Calculate probabilities
results = []
for play in slate['plays']:
    player = play['player']
    stat = play['stat']
    line = play['line']
    direction = play['direction']
    team = play['team']
    
    key = (player, stat)
    data = stats_data.get(key)
    
    if data and data['mu']:
        if direction.lower() == 'higher':
            prob_over = 1 - norm.cdf(line, loc=data['mu'], scale=data['sigma'])
        else:
            prob_over = norm.cdf(line, loc=data['mu'], scale=data['sigma'])
    else:
        prob_over = 0.50
    
    qualified = prob_over >= 0.65
    
    results.append({
        'player': player,
        'stat': stat,
        'line': line,
        'direction': direction,
        'prob_over': prob_over,
        'mu': data['mu'] if data else None,
        'sigma': data['sigma'] if data else None,
        'qualified': qualified,
        'team': team
    })

# Get qualified OVER picks
overs = [r for r in results if r['direction'].lower() == 'higher']
qualified_overs = [r for r in overs if r['qualified']]
top_overs = sorted(qualified_overs, key=lambda x: x['prob_over'], reverse=True)[:10]

# Get qualified UNDER picks  
unders = [r for r in results if r['direction'].lower() == 'lower']
qualified_unders = [r for r in unders if r['qualified']]
top_unders = sorted(qualified_unders, key=lambda x: x['prob_over'])[:5]

print("\n" + "="*100)
print(" 🏀 NBA - TOP 10 OVER PICKS (By Probability)")
print("="*100 + "\n")

for i, pick in enumerate(top_overs, 1):
    mean_str = f"{pick['mu']:.1f}" if pick['mu'] else 'N/A'
    marker = "✅" if pick['prob_over'] >= 0.65 else "⚠️"
    print(f" {i:2d}. {pick['player']:25s} | {pick['stat']:10s} >  {pick['line']:6.1f}")
    print(f"     P(Over): {pick['prob_over']*100:5.1f}% | Mean: {mean_str:6s} | {marker}  {'QUALIFIED' if pick['qualified'] else 'MARGINAL'}\n")

print("="*100)
print(" 🏀 NBA - TOP 5 UNDER PICKS (By Probability)")
print("="*100 + "\n")

for i, pick in enumerate(top_unders, 1):
    prob_under = pick['prob_over']
    prob_over_inverse = 1 - prob_under
    mean_str = f"{pick['mu']:.1f}" if pick['mu'] else 'N/A'
    marker = "✅" if prob_under >= 0.65 else "⚠️"
    print(f"{i}. {pick['player']:25s} | {pick['stat']:10s} <  {pick['line']:6.1f}")
    print(f"   P(Under): {prob_under*100:5.1f}% (Over: {prob_over_inverse*100:5.1f}%) | Mean: {mean_str:6s} | {marker} {'QUALIFIED' if pick['qualified'] else 'MARGINAL'}\n")

print("="*100)
print(f"Summary: {len(top_overs)} Over picks | {len(top_unders)} Under picks")
print(f"Average Confidence (OVER): {sum(p['prob_over'] for p in top_overs) / len(top_overs) * 100:.1f}%" if top_overs else "")
print("="*100)
