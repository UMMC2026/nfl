#!/usr/bin/env python3
"""
FULL WEDNESDAY NBA SLATE ANALYSIS
Monte Carlo (10k trials) + Bayesian (Normal CDF) + Team Defense/Offense Stats
79 props across 7 games
"""

import json
import numpy as np
from scipy.stats import norm
from datetime import datetime

# Load slate
with open('nba_full_slate.json') as f:
    slate = json.load(f)

# Team stats
TEAM_DEFENSE = {
    'PHI': {'rank': 9, 'rating': 109.5}, 'CLE': {'rank': 1, 'rating': 106.5},
    'IND': {'rank': 20, 'rating': 113.7}, 'TOR': {'rank': 23, 'rating': 114.5},
    'CHI': {'rank': 21, 'rating': 113.2}, 'UTA': {'rank': 28, 'rating': 117.2},
    'NOP': {'rank': 16, 'rating': 111.8}, 'BKN': {'rank': 25, 'rating': 115.2},
    'DAL': {'rank': 13, 'rating': 110.8}, 'DEN': {'rank': 12, 'rating': 110.5},
    'SAC': {'rank': 17, 'rating': 112.3}, 'NYK': {'rank': 7, 'rating': 108.9},
    'LAC': {'rank': 10, 'rating': 109.8}, 'WAS': {'rank': 29, 'rating': 118.5},
}

# Player stats (10-game averages)
stats = {
    ('Joel Embiid', 'points'): (28.4, 6.5), ('Joel Embiid', 'rebounds'): (10.8, 2.9), ('Joel Embiid', 'assists'): (4.6, 1.9),
    ('Donovan Mitchell', 'points'): (24.6, 5.9), ('Donovan Mitchell', 'rebounds'): (4.5, 1.6), ('Donovan Mitchell', 'assists'): (4.8, 2.1),
    ('Tyrese Maxey', 'points'): (26.8, 6.2), ('Tyrese Maxey', 'rebounds'): (3.4, 1.3), ('Tyrese Maxey', 'assists'): (6.9, 2.4),
    ('Paul George', 'points'): (18.2, 5.3), ('Paul George', 'rebounds'): (6.1, 2.0), ('Paul George', 'assists'): (4.8, 1.9),
    ('Evan Mobley', 'points'): (16.9, 4.5), ('Evan Mobley', 'rebounds'): (9.8, 2.6), ('Evan Mobley', 'assists'): (2.8, 1.2),
    ('Darius Garland', 'points'): (20.1, 5.4), ('Darius Garland', 'assists'): (6.8, 2.3),
    ('Jarrett Allen', 'points'): (13.2, 3.8), ('Jarrett Allen', 'rebounds'): (10.4, 2.7),
    ('Sam Merrill', 'points'): (11.2, 4.8),
    
    ('Brandon Ingram', 'points'): (22.4, 5.4), ('Brandon Ingram', 'rebounds'): (6.1, 2.0), ('Brandon Ingram', 'assists'): (5.6, 2.2),
    ('Pascal Siakam', 'points'): (21.7, 5.2), ('Pascal Siakam', 'rebounds'): (8.1, 2.4), ('Pascal Siakam', 'assists'): (4.2, 1.7),
    ('Scottie Barnes', 'points'): (19.8, 4.9), ('Scottie Barnes', 'rebounds'): (8.9, 2.5), ('Scottie Barnes', 'assists'): (6.1, 2.3),
    ('Andrew Nembhard', 'points'): (11.3, 3.9), ('Andrew Nembhard', 'assists'): (5.4, 2.0),
    
    ('Nikola Vucevic', 'points'): (20.1, 4.9), ('Nikola Vucevic', 'rebounds'): (10.2, 2.6), ('Nikola Vucevic', 'assists'): (3.2, 1.1),
    ('Keyonte George', 'points'): (24.3, 5.8), ('Keyonte George', 'assists'): (7.2, 2.5),
    ('Coby White', 'points'): (18.9, 4.7), ('Coby White', 'assists'): (4.9, 1.8),
    
    ('Zion Williamson', 'points'): (24.8, 5.3), ('Zion Williamson', 'rebounds'): (7.2, 2.1), ('Zion Williamson', 'assists'): (5.1, 1.7),
    ('Michael Porter Jr.', 'points'): (24.3, 5.8), ('Michael Porter Jr.', 'rebounds'): (7.2, 2.3), ('Michael Porter Jr.', 'assists'): (2.4, 1.0),
    ('Trey Murphy III', 'points'): (18.7, 5.1), ('Trey Murphy III', 'rebounds'): (5.2, 1.8),
    ('Cam Thomas', 'points'): (21.5, 6.3),
    ('Nic Claxton', 'points'): (11.8, 3.6), ('Nic Claxton', 'rebounds'): (8.9, 2.5),
    
    ('Jamal Murray', 'points'): (21.4, 4.9), ('Jamal Murray', 'rebounds'): (4.1, 1.2), ('Jamal Murray', 'assists'): (6.3, 2.1),
    ('Cooper Flagg', 'points'): (21.2, 5.4), ('Cooper Flagg', 'rebounds'): (7.4, 2.3), ('Cooper Flagg', 'assists'): (5.2, 1.9),
    ('Peyton Watson', 'points'): (9.8, 4.2), ('Peyton Watson', 'rebounds'): (5.4, 2.1), ('Peyton Watson', 'assists'): (2.1, 1.0),
    ('Aaron Gordon', 'points'): (15.6, 4.3), ('Aaron Gordon', 'rebounds'): (6.9, 2.2),
    
    ('Jalen Brunson', 'points'): (25.2, 5.7), ('Jalen Brunson', 'rebounds'): (3.6, 1.4), ('Jalen Brunson', 'assists'): (7.8, 2.5),
    ('Karl-Anthony Towns', 'points'): (22.1, 4.8), ('Karl-Anthony Towns', 'rebounds'): (11.9, 2.8),
    ('DeMar DeRozan', 'points'): (21.3, 4.9), ('DeMar DeRozan', 'assists'): (4.1, 1.5),
    ('Russell Westbrook', 'points'): (11.8, 4.2), ('Russell Westbrook', 'rebounds'): (5.2, 1.8), ('Russell Westbrook', 'assists'): (6.9, 2.4),
    ('Zach LaVine', 'points'): (22.4, 5.6),
    
    ('Kawhi Leonard', 'points'): (24.6, 5.8), ('Kawhi Leonard', 'rebounds'): (6.2, 2.0), ('Kawhi Leonard', 'assists'): (4.1, 1.6),
    ('James Harden', 'points'): (21.5, 5.4), ('James Harden', 'rebounds'): (6.8, 2.2), ('James Harden', 'assists'): (9.2, 2.7),
    ('Alex Sarr', 'points'): (14.2, 4.5), ('Alex Sarr', 'rebounds'): (8.4, 2.6),
}

def mc_sim(mu, sigma, line, direction, trials=10000):
    """Monte Carlo simulation"""
    samples = np.random.normal(mu, sigma, trials)
    hits = np.sum(samples > line) if direction == 'higher' else np.sum(samples < line)
    return hits / trials

# Analyze all props
results = []
for play in slate['plays']:
    key = (play['player'], play['stat'])
    if key not in stats:
        continue
    
    mu, sigma = stats[key]
    line = play['line']
    direction = play['direction']
    
    # Bayesian (analytical)
    bayesian = (1 - norm.cdf(line, mu, sigma)) if direction == 'higher' else norm.cdf(line, mu, sigma)
    
    # Monte Carlo (simulation)
    mc_prob = mc_sim(mu, sigma, line, direction)
    
    # Get opponent defense
    opponent = None
    for game in slate['games']:
        if play['team'] == game['home']:
            opponent = game['away']
        elif play['team'] == game['away']:
            opponent = game['home']
    
    opp_def = TEAM_DEFENSE.get(opponent, {})
    
    if mc_prob >= 0.65:
        results.append({
            'player': play['player'],
            'team': play['team'],
            'opponent': opponent,
            'stat': play['stat'],
            'line': line,
            'direction': direction,
            'mu': mu,
            'sigma': sigma,
            'bayesian': bayesian,
            'mc': mc_prob,
            'opp_def_rank': opp_def.get('rank', 'N/A'),
            'opp_def_rating': opp_def.get('rating', 'N/A')
        })

results.sort(key=lambda x: x['mc'], reverse=True)

# Display results
print('\n' + '=' * 100)
print('TOP 15 PICKS - WEDNESDAY NBA - Monte Carlo + Bayesian')
print('=' * 100)
print()

for i, r in enumerate(results[:15], 1):
    emoji = 'HOT' if r['mc'] >= 0.80 else ('YES' if r['mc'] >= 0.70 else 'OK')
    print(f"{emoji} #{i:2d} | MC: {r['mc']*100:5.1f}% | BAY: {r['bayesian']*100:5.1f}%")
    print(f"       {r['player']:20s} ({r['team']}) | {r['stat'].upper()} {r['direction'].upper()} {r['line']}")
    print(f"       μ={r['mu']:.1f} σ={r['sigma']:.1f} | vs {r['opponent']} (Def #{r['opp_def_rank']})")
    print()

print(f"📊 Total qualified picks (≥65%): {len(results)}")
print(f"📈 Average confidence: {np.mean([r['mc'] for r in results[:15]])*100:.1f}%")

# Save to file
output_file = f"outputs/TOP_15_WEDNESDAY_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('=' * 100 + '\n')
    f.write('🔥 TOP 15 PICKS - WEDNESDAY NBA\n')
    f.write('Monte Carlo (10k trials) + Bayesian (Normal CDF) + Team Defense Rankings\n')
    f.write('=' * 100 + '\n\n')
    
    for i, r in enumerate(results[:15], 1):
        f.write(f"#{i:2d} | Monte Carlo: {r['mc']*100:.1f}% | Bayesian: {r['bayesian']*100:.1f}%\n")
        f.write(f"     {r['player']} ({r['team']}) vs {r['opponent']} (Def Rank #{r['opp_def_rank']})\n")
        f.write(f"     {r['stat'].upper()} {r['direction'].upper()} {r['line']}\n")
        f.write(f"     Mean: {r['mu']:.1f} | Std Dev: {r['sigma']:.1f}\n\n")
    
    f.write(f"\nTotal qualified picks (≥65%): {len(results)}\n")

print(f"\n💾 Saved to: {output_file}")
