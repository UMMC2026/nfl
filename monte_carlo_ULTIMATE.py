"""ULTIMATE Monte Carlo: ALL stat types combined."""
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

# Load ALL hydrated props
all_picks = []

# Pre-validated rebounds picks from earlier
rebounds_picks = [
    {"player": "AJ Green", "team": "MIL", "stat": "rebounds", "line": 1.5, "direction": "higher",
     "empirical_hit_rate": 1.0, "bayesian_p": 0.749, "game_time": "Wed 9:10pm"},
    {"player": "Shaedon Sharpe", "team": "POR", "stat": "rebounds", "line": 2.5, "direction": "higher",
     "empirical_hit_rate": 0.9, "bayesian_p": 0.699, "game_time": "Wed 9:10pm"},
    {"player": "Gary Harris", "team": "MIL", "stat": "rebounds", "line": 2.5, "direction": "lower",
     "empirical_hit_rate": 0.9, "bayesian_p": 0.699, "game_time": "Wed 9:10pm"},
]
all_picks.extend(rebounds_picks)

# Load new 3PM + assists
with open('picks_hydrated_late_3pm_assists.json', encoding='utf-8') as f:
    new_picks = json.load(f)
    all_picks.extend(new_picks)

# Load combo stats (PRA, reb+ast)
try:
    with open('picks_hydrated_combo.json', encoding='utf-8') as f:
        combo_picks = json.load(f)
        all_picks.extend(combo_picks)
except FileNotFoundError:
    pass

print(f"Total picks loaded: {len(all_picks)}")

# Calculate empirical and Bayesian probabilities for new picks
for p in all_picks:
    if 'empirical_hit_rate' not in p:
        emp_rate = calculate_empirical_rate(p['recent_values'], p['line'], p['direction'])
        p['empirical_hit_rate'] = emp_rate
        p['sample_size'] = len(p['recent_values'])
        p['bayesian_p'] = bayesian_probability(emp_rate, len(p['recent_values']))

# Filter to 65%+ Bayesian (SLAM + STRONG tiers)
threshold = 0.65
qualified_picks = [p for p in all_picks if p['bayesian_p'] >= threshold]

print(f"\nPicks >= {threshold:.0%} Bayesian probability: {len(qualified_picks)}")

# Count by stat type
stat_counts = {}
for p in qualified_picks:
    stat = p['stat']
    stat_counts[stat] = stat_counts.get(stat, 0) + 1

print("\nBreakdown by stat type:")
for stat, count in sorted(stat_counts.items(), key=lambda x: -x[1]):
    print(f"  {stat}: {count}")

# Sort and display top picks
qualified_picks.sort(key=lambda x: x['bayesian_p'], reverse=True)

print("\n" + "="*105)
print("TOP QUALIFIED PICKS (>=65% Bayesian):")
print("="*105)
print(f"{'Player':<22} {'Stat':<12} {'Line':>6} {'Dir':<6} {'Emp%':>7} {'Bay%':>7} {'Team':<4} {'Goblin/Demon'}")
print("-"*105)

for p in qualified_picks[:30]:
    marker = ""
    if p.get('goblin'): marker = "GOBLIN"
    elif p.get('demon'): marker = "DEMON"
    print(f"{p['player']:<22} {p['stat']:<12} {p['line']:>6.1f} {p['direction']:<6} "
          f"{p['empirical_hit_rate']:>6.1%} {p['bayesian_p']:>6.1%} {p['team']:<4} {marker}")

# Run Monte Carlo on top combos
print("\n" + "="*105)
print("MONTE CARLO SIMULATION (n=10,000):")
print("="*105)

def monte_carlo_combo(picks_list, n_sims=10000):
    """Run Monte Carlo simulation on a combo."""
    p_values = [p['bayesian_p'] for p in picks_list]
    hits = 0
    for _ in range(n_sims):
        if all(np.random.random() < p for p in p_values):
            hits += 1
    return hits / n_sims

# Generate all 3-pick combos from top 20 picks
top_picks = qualified_picks[:20]
combos_3 = list(combinations(top_picks, 3))

print(f"Analyzing {len(combos_3)} three-pick combos from top 20 picks...")

results = []
for combo in combos_3:
    p_theo = np.prod([p['bayesian_p'] for p in combo])
    p_sim = monte_carlo_combo(combo, n_sims=10000)
    
    # 3-pick power: 6x payout
    ev_roi = (p_sim * 6 - 1) * 100
    
    # Check diversity (prefer multi-stat combos)
    stats = [p['stat'] for p in combo]
    stat_diversity = len(set(stats))
    
    results.append({
        'combo': combo,
        'p_theoretical': p_theo,
        'p_simulated': p_sim,
        'ev_roi': ev_roi,
        'stat_diversity': stat_diversity
    })

# Sort by EV
results.sort(key=lambda x: x['ev_roi'], reverse=True)

print("\nTOP 30 THREE-PICK POWER COMBOS (6x payout):")
print("-"*105)
print(f"{'Combo':<78} {'P(All)':>7} {'E[ROI]':>8} {'Stats'}")
print("-"*105)

for r in results[:30]:
    combo_str = " + ".join([f"{p['player'][:12]} ({p['stat'][:3]})" for p in r['combo']])
    stats_str = f"{r['stat_diversity']}/3"
    print(f"{combo_str:<78} {r['p_theoretical']:>6.1%} {r['ev_roi']:>7.1f}% {stats_str}")

# Best overall
best_overall = results[0]

# Best diverse (3 different stats)
best_diverse = next((r for r in results if r['stat_diversity'] == 3), None)

print("\n" + "="*105)
print("BEST OVERALL COMBO:")
print("="*105)
for p in best_overall['combo']:
    marker = "GOBLIN" if p.get('goblin') else ("DEMON" if p.get('demon') else "")
    print(f"  {p['player']:<22} {p['line']:>4.1f}{p['direction'][0]} {p['stat']:<12} ({p['bayesian_p']:.1%}) {marker}")
print(f"\nP(All Hit): {best_overall['p_theoretical']:.1%}")
print(f"Expected ROI: {best_overall['ev_roi']:+.1f}%")
print(f"Simulated Win Rate: {best_overall['p_simulated']:.1%}")

if best_diverse and best_diverse != best_overall:
    print("\n" + "="*105)
    print("BEST DIVERSIFIED COMBO (3 different stats):")
    print("="*105)
    for p in best_diverse['combo']:
        marker = "GOBLIN" if p.get('goblin') else ("DEMON" if p.get('demon') else "")
        print(f"  {p['player']:<22} {p['line']:>4.1f}{p['direction'][0]} {p['stat']:<12} ({p['bayesian_p']:.1%}) {marker}")
    print(f"\nP(All Hit): {best_diverse['p_theoretical']:.1%}")
    print(f"Expected ROI: {best_diverse['ev_roi']:+.1f}%")
    print(f"Simulated Win Rate: {best_diverse['p_simulated']:.1%}")

print("="*105)

# Save results
output = {
    'qualified_picks': qualified_picks[:30],
    'top_combos': [
        {
            'picks': [
                {'player': p['player'], 'stat': p['stat'], 'line': p['line'], 
                 'direction': p['direction'], 'bayesian_p': p['bayesian_p'],
                 'goblin': p.get('goblin', False), 'demon': p.get('demon', False)}
                for p in r['combo']
            ],
            'p_theoretical': r['p_theoretical'],
            'p_simulated': r['p_simulated'],
            'ev_roi': r['ev_roi'],
            'stat_diversity': r['stat_diversity']
        }
        for r in results[:30]
    ]
}

with open('outputs/monte_carlo_ULTIMATE.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nResults saved to: outputs/monte_carlo_ULTIMATE.json")
