#!/usr/bin/env python
"""Monte Carlo simulation for NBA picks."""
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from sports_quant.simulation.monte_carlo import run_monte_carlo

# Load hydrated picks
with open('picks_dec30_nba_full_filled.json', 'r') as f:
    picks = json.load(f)

print('='*80)
print('        MONTE CARLO SIMULATION - DEC 30 NBA SLATE (10,000 ITERATIONS)')
print('='*80)
print()

results = []
for pick in picks:
    vals = pick.get('recent_values', [])
    if len(vals) < 3:
        continue
    
    mean = np.mean(vals)
    var = np.var(vals)
    line = pick['line']
    direction = pick['direction']
    
    # Run simulation
    sim = run_monte_carlo(line, mean, var, dist='normal', n_sims=10000, clip_min=0)
    
    # Get probability based on direction
    prob = sim['p_over'] if direction == 'higher' else sim['p_under']
    
    results.append({
        'player': pick['player'],
        'stat': pick['stat'],
        'line': line,
        'direction': direction,
        'mean': mean,
        'std': np.std(vals),
        'prob': prob,
        'p05': sim['tail_risk']['p05'],
        'p95': sim['tail_risk']['p95'],
        'edge': mean - line if direction == 'higher' else line - mean
    })

# Sort by probability
results.sort(key=lambda x: x['prob'], reverse=True)

# Print top plays
print('TOP 15 PLAYS BY MONTE CARLO PROBABILITY')
print('-'*80)
print(f"{'Player':<20} {'Stat':<12} {'Play':<8} {'Line':>6} {'Avg':>7} {'Std':>6} {'P(Hit)':>8} {'Edge':>7}")
print('-'*80)

for r in results[:15]:
    play = 'OVER' if r['direction'] == 'higher' else 'UNDER'
    print(f"{r['player']:<20} {r['stat']:<12} {play:<8} {r['line']:>6.1f} {r['mean']:>7.1f} {r['std']:>6.1f} {r['prob']*100:>7.1f}% {r['edge']:>+6.1f}")

print()
print('='*80)
print('PLAYS BY CONFIDENCE TIER')
print('='*80)

# Tier breakdown
slam = [r for r in results if r['prob'] >= 0.85]
strong = [r for r in results if 0.70 <= r['prob'] < 0.85]
lean = [r for r in results if 0.60 <= r['prob'] < 0.70]
risky = [r for r in results if r['prob'] < 0.50]

print(f'\nSLAM PLAYS (85%+): {len(slam)}')
for r in slam:
    play = 'O' if r['direction'] == 'higher' else 'U'
    print(f"  {r['player']} {play}{r['line']} {r['stat']} - {r['prob']*100:.1f}% (avg: {r['mean']:.1f})")

print(f'\nSTRONG PLAYS (70-85%): {len(strong)}')
for r in strong[:10]:
    play = 'O' if r['direction'] == 'higher' else 'U'
    print(f"  {r['player']} {play}{r['line']} {r['stat']} - {r['prob']*100:.1f}% (avg: {r['mean']:.1f})")

print(f'\nLEAN PLAYS (60-70%): {len(lean)}')
for r in lean[:8]:
    play = 'O' if r['direction'] == 'higher' else 'U'
    print(f"  {r['player']} {play}{r['line']} {r['stat']} - {r['prob']*100:.1f}% (avg: {r['mean']:.1f})")

print(f'\nAVOID (Under 50%): {len(risky)}')
for r in risky[:5]:
    play = 'O' if r['direction'] == 'higher' else 'U'
    print(f"  {r['player']} {play}{r['line']} {r['stat']} - {r['prob']*100:.1f}%")

# Parlay simulation
print()
print('='*80)
print('PARLAY SIMULATION (Combined Probability)')
print('='*80)

# Best 3-leg
top3 = results[:3]
p3 = np.prod([r['prob'] for r in top3])
print(f'\nBEST 3-LEG POWER ({p3*100:.1f}% combined):')
for r in top3:
    play = 'O' if r['direction'] == 'higher' else 'U'
    print(f"  {r['player']} {play}{r['line']} {r['stat']} ({r['prob']*100:.0f}%)")
print(f'  Expected payout: 6x -> EV = {p3 * 6 - 1:+.2f} units')

# Best 5-leg from 75%+ plays
top5_pool = [r for r in results if r['prob'] >= 0.70][:5]
if len(top5_pool) >= 5:
    p5 = np.prod([r['prob'] for r in top5_pool])
    print(f'\nBEST 5-LEG POWER ({p5*100:.1f}% combined):')
    for r in top5_pool:
        play = 'O' if r['direction'] == 'higher' else 'U'
        print(f"  {r['player']} {play}{r['line']} {r['stat']} ({r['prob']*100:.0f}%)")
    print(f'  Expected payout: 20x -> EV = {p5 * 20 - 1:+.2f} units')

# Diversified 3-leg (different games)
print(f'\nDIVERSIFIED 3-LEG (diff teams):')
used_teams = set()
div3 = []
for r in results:
    # Get team from pick (need to look it up)
    team = next((p['team'] for p in picks if p['player'] == r['player']), None)
    if team and team not in used_teams:
        div3.append(r)
        used_teams.add(team)
    if len(div3) >= 3:
        break

p_div3 = np.prod([r['prob'] for r in div3])
for r in div3:
    play = 'O' if r['direction'] == 'higher' else 'U'
    team = next((p['team'] for p in picks if p['player'] == r['player']), '???')
    print(f"  [{team}] {r['player']} {play}{r['line']} {r['stat']} ({r['prob']*100:.0f}%)")
print(f'  Combined: {p_div3*100:.1f}% -> EV = {p_div3 * 6 - 1:+.2f} units')

print()
print('='*80)
