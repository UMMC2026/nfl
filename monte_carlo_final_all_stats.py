"""Final Monte Carlo analysis combining ALL stat types."""
import json
import numpy as np
from itertools import combinations

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
all_picks = []

# Load combo props (NEW)
try:
    with open('picks_hydrated_combo.json', encoding='utf-8') as f:
        combo_picks = json.load(f)
        all_picks.extend(combo_picks)
        print(f"Loaded {len(combo_picks)} combo props")
except FileNotFoundError:
    print("No combo props found")

print(f"\nTotal picks loaded: {len(all_picks)}")

# Filter to late games only (9:10pm)
late_picks = [p for p in all_picks if 'Wed 9:10pm' in p.get('game_time', '')]
print(f"Late game picks (Wed 9:10pm): {len(late_picks)}")

# Calculate empirical and Bayesian probabilities
for p in late_picks:
    emp_rate = calculate_empirical_rate(p['recent_values'], p['line'], p['direction'])
    p['empirical_hit_rate'] = emp_rate
    p['sample_size'] = len(p['recent_values'])
    p['bayesian_p'] = bayesian_probability(emp_rate, len(p['recent_values']))

# Add pre-validated high-conviction picks from earlier analysis
high_conviction_picks = [
    {"player": "Deni Avdija", "team": "POR", "stat": "3pm", "line": 1.5, "direction": "higher",
     "empirical_hit_rate": 1.0, "bayesian_p": 0.749, "game_time": "Wed 9:10pm"},
    {"player": "Dorian Finney-Smith", "team": "HOU", "stat": "3pm", "line": 0.5, "direction": "higher",
     "empirical_hit_rate": 0.9, "bayesian_p": 0.699, "game_time": "Wed 9:10pm"},
    {"player": "AJ Green", "team": "MIL", "stat": "rebounds", "line": 1.5, "direction": "higher",
     "empirical_hit_rate": 1.0, "bayesian_p": 0.749, "game_time": "Wed 9:10pm"},
    {"player": "Shaedon Sharpe", "team": "POR", "stat": "rebounds", "line": 2.5, "direction": "higher",
     "empirical_hit_rate": 0.9, "bayesian_p": 0.699, "game_time": "Wed 9:10pm"},
    {"player": "Gary Harris", "team": "MIL", "stat": "rebounds", "line": 2.5, "direction": "lower",
     "empirical_hit_rate": 0.9, "bayesian_p": 0.699, "game_time": "Wed 9:10pm"},
]

# Combine with new picks
combined_picks = high_conviction_picks + late_picks

# Filter to 60%+ Bayesian (lowered threshold to include more combo stats)
threshold = 0.60
qualified_picks = [p for p in combined_picks if p['bayesian_p'] >= threshold]

print(f"\nPicks >= {threshold:.0%} Bayesian probability: {len(qualified_picks)}")

# Count by stat type
stat_counts = {}
for p in qualified_picks:
    stat = p['stat']
    stat_counts[stat] = stat_counts.get(stat, 0) + 1

print("\nBreakdown by stat type:")
for stat, count in sorted(stat_counts.items(), key=lambda x: -x[1]):
    print(f"  {stat}: {count}")

# Sort and display all qualified picks
qualified_picks.sort(key=lambda x: x['bayesian_p'], reverse=True)

print("\n" + "="*100)
print("ALL QUALIFIED PICKS (sorted by Bayesian probability):")
print("="*100)
print(f"{'Player':<20} {'Stat':<12} {'Line':>6} {'Dir':<6} {'Emp%':>7} {'Bay%':>7} {'Team':<4}")
print("-"*100)

for p in qualified_picks:
    print(f"{p['player']:<20} {p['stat']:<12} {p['line']:>6.1f} {p['direction']:<6} "
          f"{p['empirical_hit_rate']:>6.1%} {p['bayesian_p']:>6.1%} {p['team']:<4}")

# Run Monte Carlo on top combos
print("\n" + "="*100)
print("MONTE CARLO SIMULATION (n=10,000):")
print("="*100)

def monte_carlo_combo(picks_list, n_sims=10000):
    """Run Monte Carlo simulation on a combo."""
    p_values = [p['bayesian_p'] for p in picks_list]
    hits = 0
    for _ in range(n_sims):
        if all(np.random.random() < p for p in p_values):
            hits += 1
    return hits / n_sims

# Generate all 3-pick combos from top 15 picks
top_picks = qualified_picks[:15]
combos_3 = list(combinations(top_picks, 3))

print(f"Analyzing {len(combos_3)} three-pick combos...")

results = []
for combo in combos_3:
    p_theo = np.prod([p['bayesian_p'] for p in combo])
    p_sim = monte_carlo_combo(combo, n_sims=10000)
    
    # 3-pick power: 6x payout ($1 → $6 if all hit, $0 if any miss)
    ev_roi = (p_sim * 6 - 1) * 100
    
    results.append({
        'combo': combo,
        'p_theoretical': p_theo,
        'p_simulated': p_sim,
        'ev_roi': ev_roi
    })

# Sort by EV
results.sort(key=lambda x: x['ev_roi'], reverse=True)

print("\nTOP 20 THREE-PICK POWER COMBOS (6x payout):")
print("-"*100)
print(f"{'Combo':<75} {'P(All)':>7} {'E[ROI]':>8}")
print("-"*100)

for r in results[:20]:
    combo_str = " + ".join([f"{p['player'][:10]} ({p['stat']})" for p in r['combo']])
    print(f"{combo_str:<75} {r['p_theoretical']:>6.1%} {r['ev_roi']:>7.1f}%")

# Save results
best_combo = results[0]
print("\n" + "="*100)
print("BEST COMBO:")
print("="*100)
for p in best_combo['combo']:
    print(f"  {p['player']} {p['line']} {p['direction']} {p['stat']} ({p['bayesian_p']:.1%})")
print(f"\nP(All Hit): {best_combo['p_theoretical']:.1%}")
print(f"Expected ROI: {best_combo['ev_roi']:+.1f}%")
print(f"Simulated Win Rate: {best_combo['p_simulated']:.1%}")
print("="*100)

# Save to JSON
output = {
    'all_qualified_picks': qualified_picks,
    'top_combos': [
        {
            'picks': [
                {'player': p['player'], 'stat': p['stat'], 'line': p['line'], 
                 'direction': p['direction'], 'bayesian_p': p['bayesian_p']}
                for p in r['combo']
            ],
            'p_theoretical': r['p_theoretical'],
            'p_simulated': r['p_simulated'],
            'ev_roi': r['ev_roi']
        }
        for r in results[:20]
    ]
}

with open('outputs/monte_carlo_final_all_stats.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: outputs/monte_carlo_final_all_stats.json")
