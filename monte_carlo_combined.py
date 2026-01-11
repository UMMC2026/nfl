"""Combined Monte Carlo: 3PM + Rebounds + Points picks."""
import json
import numpy as np
from scipy import stats

def bayesian_probability(empirical_rate, sample_size, prior_mean=0.5, prior_std=0.15):
    """Bayesian update using Beta distribution."""
    alpha_prior = ((1 - prior_mean) / prior_std**2 - 1 / prior_mean) * prior_mean**2
    beta_prior = alpha_prior * (1 / prior_mean - 1)
    alpha_prior = max(1, alpha_prior)
    beta_prior = max(1, beta_prior)
    
    hits = int(empirical_rate * sample_size)
    misses = sample_size - hits
    
    alpha_post = alpha_prior + hits
    beta_post = beta_prior + misses
    
    return alpha_post / (alpha_post + beta_post)

def calculate_empirical_rate(recent_values, line, direction):
    """Calculate empirical hit rate from recent game values."""
    if direction == "higher":
        hits = sum(1 for v in recent_values if v > line)
    else:
        hits = sum(1 for v in recent_values if v < line)
    return hits / len(recent_values) if recent_values else 0

# Load all hydrated props
print("Loading hydrated props...")
with open('picks_hydrated_points.json', encoding='utf-8') as f:
    points_picks = json.load(f)

# Use only late game picks (9:10pm - games not started yet)
late_points = [p for p in points_picks if 'Wed 9:10pm' in p.get('game_time', '')]

# Best picks from earlier analysis (manually added since hydration incomplete)
best_picks = [
    # 3PM
    {"player": "Deni Avdija", "stat": "3pm", "line": 1.5, "direction": "higher", "team": "POR",
     "empirical_hit_rate": 1.0, "sample_size": 10, "bayesian_p": 0.749},
    {"player": "Dorian Finney-Smith", "stat": "3pm", "line": 0.5, "direction": "higher", "team": "HOU",
     "empirical_hit_rate": 0.9, "sample_size": 10, "bayesian_p": 0.699},
    
    # Rebounds
    {"player": "AJ Green", "stat": "rebounds", "line": 1.5, "direction": "higher", "team": "MIL",
     "empirical_hit_rate": 1.0, "sample_size": 10, "bayesian_p": 0.749},
    {"player": "Shaedon Sharpe", "stat": "rebounds", "line": 2.5, "direction": "higher", "team": "POR",
     "empirical_hit_rate": 0.9, "sample_size": 10, "bayesian_p": 0.699},
    {"player": "Gary Harris", "stat": "rebounds", "line": 2.5, "direction": "lower", "team": "MIL",
     "empirical_hit_rate": 0.9, "sample_size": 10, "bayesian_p": 0.699},
]

# Process points picks
for p in late_points:
    emp_rate = calculate_empirical_rate(p['recent_values'], p['line'], p['direction'])
    p['empirical_hit_rate'] = emp_rate
    p['sample_size'] = len(p['recent_values'])
    p['bayesian_p'] = bayesian_probability(emp_rate, len(p['recent_values']))

# Add high-probability points picks to best_picks
for p in late_points:
    if p['bayesian_p'] >= 0.65:  # 65%+ Bayesian probability
        best_picks.append(p)

print(f"\nTotal high-conviction picks: {len(best_picks)}")
print(f"  - 3PM: {sum(1 for p in best_picks if p['stat'] == '3pm')}")
print(f"  - Rebounds: {sum(1 for p in best_picks if p['stat'] == 'rebounds')}")
print(f"  - Points: {sum(1 for p in best_picks if p['stat'] == 'points')}")

print("\n" + "="*90)
print("ALL PICKS (sorted by Bayesian probability):")
print("="*90)
print(f"{'Player':<20} {'Stat':<12} {'Empirical':>10} {'Bayesian':>10} {'Team':<6}")
print("-"*90)

best_picks.sort(key=lambda x: x['bayesian_p'], reverse=True)
for p in best_picks:
    print(f"{p['player']:<20} {p['line']:>4}{'+'if p['direction']=='higher' else '-'} {p['stat']:<8} "
          f"{p['empirical_hit_rate']:>9.1%} {p['bayesian_p']:>10.1%} {p.get('team', 'N/A'):<6}")

# Monte Carlo
n_sims = 10000
print(f"\n\nMONTE CARLO (n={n_sims:,}):")
print("="*90)

# Top 3-pick combos
print("\nTOP 3-PICK POWER COMBOS (6x payout):")
print("-"*90)
print(f"{'Combo':<75} {'P(All)':>8} {'E[ROI]':>10}")
print("-"*90)

top_picks = best_picks[:10]  # Use top 10 by Bayesian probability
combos = []

for i in range(len(top_picks)):
    for j in range(i+1, len(top_picks)):
        for k in range(j+1, len(top_picks)):
            p1, p2, p3 = top_picks[i], top_picks[j], top_picks[k]
            prob1, prob2, prob3 = p1['bayesian_p'], p2['bayesian_p'], p3['bayesian_p']
            
            outcomes1 = np.random.binomial(1, prob1, n_sims)
            outcomes2 = np.random.binomial(1, prob2, n_sims)
            outcomes3 = np.random.binomial(1, prob3, n_sims)
            all_hit = outcomes1 * outcomes2 * outcomes3
            
            roi = np.where(all_hit == 1, 5.0, -1.0)
            
            combos.append({
                'combo': f"{p1['player'][:10]} ({p1['stat']}) + {p2['player'][:10]} ({p2['stat']}) + {p3['player'][:10]} ({p3['stat']})",
                'p_all': prob1 * prob2 * prob3,
                'exp_roi': roi.mean(),
                'win_rate': all_hit.mean()
            })

combos.sort(key=lambda x: x['exp_roi'], reverse=True)
for c in combos[:15]:
    print(f"{c['combo']:<75} {c['p_all']:>7.1%} {c['exp_roi']:>9.1%}")

print("\n" + "="*90)
print(f"BEST COMBO: {combos[0]['combo']}")
print(f"  P(All Hit): {combos[0]['p_all']:.1%}")
print(f"  Expected ROI: {combos[0]['exp_roi']:.1%}")
print(f"  Simulated Win Rate: {combos[0]['win_rate']:.1%}")
print("="*90)

# Save results
with open('outputs/monte_carlo_combined_results.json', 'w', encoding='utf-8') as f:
    json.dump({
        'best_picks': best_picks,
        'top_combos': combos[:20]
    }, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: outputs/monte_carlo_combined_results.json")
