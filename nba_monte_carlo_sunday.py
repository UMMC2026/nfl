"""NBA Sunday Monte Carlo Entry Builder"""
import json
from pathlib import Path
from scipy.stats import norm

# Load slate
slate = json.loads(Path('outputs/NBA_SLATE_20260118.json').read_text())
props = slate['plays']

# Load stats - format is a list of {player, stat, mu, sigma}
stats_files = list(Path('outputs/stats_cache').glob('nba_mu_sigma_*.json'))
if not stats_files:
    print("No stats cache found!")
    exit(1)
stats_file = sorted(stats_files)[-1]
stats_raw = json.loads(stats_file.read_text())

# Convert stats list to nested dict {player: {stat: {mu, sigma}}}
stats = {}
for entry in stats_raw.get('stats', []):
    player = entry.get('player')
    stat = entry.get('stat')
    if player and stat:
        if player not in stats:
            stats[player] = {}
        stats[player][stat] = {'mu': entry.get('mu', 0), 'sigma': entry.get('sigma', 1)}

print('='*70)
print('NBA SUNDAY JAN 18 - MONTE CARLO ENTRY BUILDER')
print('NOP @ HOU | BKN @ CHI | CHA @ DEN')
print('='*70)
print(f'Stats: {stats_file.name}')
print(f'Players in cache: {len(stats)}')
print('='*70)

# Calculate probabilities for each prop
edges = []
for p in props:
    player = p['player']
    stat = p['stat']
    line = p['line']
    direction = p['direction']
    team = p.get('team', 'UNK')
    
    # Only single stats for now
    if stat not in ['points', 'rebounds', 'assists']:
        continue
    
    player_stats = stats.get(player, {})
    stat_data = player_stats.get(stat, {})
    mu = stat_data.get('mu', 0)
    sigma = stat_data.get('sigma', 1)
    
    if mu > 0 and sigma > 0:
        # Calculate probability using Normal CDF
        z = (line - mu) / sigma
        if direction == 'higher':
            prob = 1 - norm.cdf(z)  # P(X > line)
            edge = mu - line
        else:
            prob = norm.cdf(z)  # P(X < line)
            edge = line - mu
        
        edges.append({
            'player': player,
            'team': team,
            'stat': stat,
            'line': line,
            'direction': direction,
            'mu': mu,
            'sigma': sigma,
            'edge': edge,
            'prob': prob,
            'z': z if direction == 'lower' else -z
        })

# Sort by probability
edges.sort(key=lambda x: x['prob'], reverse=True)

print('\nTOP PICKS BY PROBABILITY:')
print('-'*70)
# Import canonical thresholds
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shared.config import implied_tier
for i, e in enumerate(edges[:15], 1):
    dir_str = 'OVER' if e['direction'] == 'higher' else 'UNDER'
    prob_pct = e['prob'] * 100
    tier = implied_tier(e['prob'], 'NBA')
    print(f"{i:2}. {e['player']:<18} {e['stat']:<8} {dir_str:<5} {e['line']:<5} | P={prob_pct:>5.1f}% {tier:<8} | mu={e['mu']:.1f} edge={e['edge']:+.1f}")

# Build 3-leg power entries
print('\n' + '='*70)
print('MONTE CARLO: TOP 3-LEG POWER ENTRIES')
print('(Requires 2+ teams)')
print('='*70)

from itertools import combinations

# Filter to plays with > 55% probability
viable = [e for e in edges if e['prob'] >= 0.55]
print(f'\nViable picks (>55%): {len(viable)}')

# Generate all 3-leg combos
entries = []
for combo in combinations(viable, 3):
    teams = set(e['team'] for e in combo)
    if len(teams) < 2:
        continue  # Need 2+ teams
    
    # Check no duplicate players
    players = [e['player'] for e in combo]
    if len(players) != len(set(players)):
        continue
    
    # Calculate combined probability
    combined_prob = 1.0
    for e in combo:
        combined_prob *= e['prob']
    
    # Power 3-leg payout = 6x
    ev = (combined_prob * 6) - 1
    
    entries.append({
        'legs': combo,
        'prob': combined_prob,
        'ev': ev,
        'teams': teams
    })

# Sort by EV
entries.sort(key=lambda x: x['ev'], reverse=True)

print(f'Total 3-leg entries: {len(entries)}')
print('\nTOP 5 ENTRIES BY EV:')
print('-'*70)

for i, entry in enumerate(entries[:5], 1):
    print(f"\nEntry #{i} | EV: {entry['ev']:+.3f} | Win Prob: {entry['prob']*100:.1f}%")
    for leg in entry['legs']:
        dir_str = 'OVER' if leg['direction'] == 'higher' else 'UNDER'
        print(f"  - {leg['player']} ({leg['team']}) {leg['stat']} {dir_str} {leg['line']} [{leg['prob']*100:.0f}%]")

# Summary
print('\n' + '='*70)
print('RECOMMENDED PLAYS:')
print('='*70)
slams = [e for e in edges if e['prob'] >= 0.75]
strongs = [e for e in edges if 0.65 <= e['prob'] < 0.75]

if slams:
    print('\nSLAM (>=75%):')
    for e in slams:
        dir_str = 'OVER' if e['direction'] == 'higher' else 'UNDER'
        print(f"  {e['player']} {e['stat']} {dir_str} {e['line']} ({e['prob']*100:.0f}%)")

if strongs:
    print('\nSTRONG (65-74%):')
    for e in strongs:
        dir_str = 'OVER' if e['direction'] == 'higher' else 'UNDER'
        print(f"  {e['player']} {e['stat']} {dir_str} {e['line']} ({e['prob']*100:.0f}%)")
