"""Monte Carlo on manually selected high-conviction picks."""
import json
import numpy as np
from scipy import stats

# Best picks from earlier analysis
picks = [
    # 3PM picks (from earlier scored data - 100% and 90% hit rates)
    {"player": "Deni Avdija", "stat": "3pm", "line": 1.5, "direction": "higher", "team": "POR",
     "game_time": "Wed 9:10pm", "empirical_hit_rate": 1.0, "sample_size": 10, "tier": "SLAM"},
    {"player": "Dorian Finney-Smith", "stat": "3pm", "line": 0.5, "direction": "higher", "team": "HOU",
     "game_time": "Wed 9:10pm", "empirical_hit_rate": 0.9, "sample_size": 10, "tier": "STRONG"},
    
    # Rebounds picks (from current analysis)
    {"player": "AJ Green", "stat": "rebounds", "line": 1.5, "direction": "higher", "team": "MIL",
     "game_time": "Wed 9:10pm", "empirical_hit_rate": 1.0, "sample_size": 10, "tier": "SLAM"},
    {"player": "Shaedon Sharpe", "stat": "rebounds", "line": 2.5, "direction": "higher", "team": "POR",
     "game_time": "Wed 9:10pm", "empirical_hit_rate": 0.9, "sample_size": 10, "tier": "STRONG"},
    {"player": "Gary Harris", "stat": "rebounds", "line": 2.5, "direction": "lower", "team": "MIL",
     "game_time": "Wed 9:10pm", "empirical_hit_rate": 0.9, "sample_size": 10, "tier": "STRONG"},
]

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

print("="*90)
print("MONTE CARLO SIMULATION - HIGH CONVICTION PICKS (Late Games)")
print("="*90)

# Add Bayesian probabilities
for pick in picks:
    pick['bayesian_p'] = bayesian_probability(
        pick['empirical_hit_rate'], 
        pick['sample_size']
    )

# Display individual picks
print("\nINDIVIDUAL PICKS:")
print("-"*90)
print(f"{'Player':<20} {'Stat':<12} {'Empirical':>10} {'Bayesian':>10} {'Tier':<8} {'Time'}")
print("-"*90)
for p in picks:
    print(f"{p['player']:<20} {p['line']:>4}+ {p['stat']:<6} "
          f"{p['empirical_hit_rate']:>9.1%} {p['bayesian_p']:>10.1%} "
          f"{p['tier']:<8} {p['game_time']}")

# Monte Carlo simulations
n_sims = 10000

print(f"\n\nMONTE CARLO RESULTS (n={n_sims:,}):")
print("="*90)

# 2-Pick Power Combos
print("\nBEST 2-PICK POWER COMBOS (3x payout):")
print("-"*90)
print(f"{'Combo':<55} {'P(Both)':>8} {'E[ROI]':>10} {'Win%':>8}")
print("-"*90)

combos_2 = []
for i in range(len(picks)):
    for j in range(i+1, len(picks)):
        p1, p2 = picks[i], picks[j]
        prob1, prob2 = p1['bayesian_p'], p2['bayesian_p']
        
        # Simulate
        outcomes1 = np.random.binomial(1, prob1, n_sims)
        outcomes2 = np.random.binomial(1, prob2, n_sims)
        both_hit = outcomes1 * outcomes2
        
        # ROI: 3x payout = $2 profit if both hit, -$1 if either misses
        roi = np.where(both_hit == 1, 2.0, -1.0)
        
        combos_2.append({
            'combo': f"{p1['player']} ({p1['stat']}) + {p2['player']} ({p2['stat']})",
            'p_both': prob1 * prob2,
            'win_rate': both_hit.mean(),
            'exp_roi': roi.mean()
        })

combos_2.sort(key=lambda x: x['exp_roi'], reverse=True)
for c in combos_2[:10]:
    print(f"{c['combo']:<55} {c['p_both']:>7.1%} {c['exp_roi']:>9.1%} {c['win_rate']:>7.1%}")

# 3-Pick Power Combos
print("\n\nBEST 3-PICK POWER COMBOS (6x payout):")
print("-"*90)
print(f"{'Combo':<75} {'P(All)':>8} {'E[ROI]':>10}")
print("-"*90)

combos_3 = []
for i in range(len(picks)):
    for j in range(i+1, len(picks)):
        for k in range(j+1, len(picks)):
            p1, p2, p3 = picks[i], picks[j], picks[k]
            prob1, prob2, prob3 = p1['bayesian_p'], p2['bayesian_p'], p3['bayesian_p']
            
            outcomes1 = np.random.binomial(1, prob1, n_sims)
            outcomes2 = np.random.binomial(1, prob2, n_sims)
            outcomes3 = np.random.binomial(1, prob3, n_sims)
            all_hit = outcomes1 * outcomes2 * outcomes3
            
            # ROI: 6x payout = $5 profit if all hit
            roi = np.where(all_hit == 1, 5.0, -1.0)
            
            combos_3.append({
                'combo': f"{p1['player'][:12]} ({p1['stat']}) + {p2['player'][:12]} ({p2['stat']}) + {p3['player'][:12]} ({p3['stat']})",
                'p_all': prob1 * prob2 * prob3,
                'exp_roi': roi.mean()
            })

combos_3.sort(key=lambda x: x['exp_roi'], reverse=True)
for c in combos_3[:8]:
    print(f"{c['combo']:<75} {c['p_all']:>7.1%} {c['exp_roi']:>9.1%}")

print("\n" + "="*90)
print("RECOMMENDATION: 3-pick combos with 100%+90%+90% empirical rates have ~115% expected ROI")
print("="*90)
