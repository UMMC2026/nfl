"""Detailed analysis of points props."""
import json
import numpy as np

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

# Load points picks
with open('picks_hydrated_points.json', encoding='utf-8') as f:
    points_picks = json.load(f)

print("="*100)
print("DETAILED POINTS PROPS ANALYSIS")
print("="*100)

# Process all picks
for p in points_picks:
    emp_rate = calculate_empirical_rate(p['recent_values'], p['line'], p['direction'])
    p['empirical_hit_rate'] = emp_rate
    p['sample_size'] = len(p['recent_values'])
    p['bayesian_p'] = bayesian_probability(emp_rate, len(p['recent_values']))
    
    # Calculate stats
    recent = p['recent_values']
    p['mean'] = np.mean(recent)
    p['median'] = np.median(recent)
    p['std'] = np.std(recent)

# Sort by Bayesian probability
points_picks.sort(key=lambda x: x['bayesian_p'], reverse=True)

print(f"\nALL POINTS PROPS (sorted by Bayesian probability):")
print("-"*100)
print(f"{'Player':<20} {'Line':>6} {'Dir':<6} {'Emp%':>7} {'Bay%':>7} {'Mean':>6} {'Med':>5} {'Std':>5} {'Recent 10 Games'}")
print("-"*100)

for p in points_picks:
    recent_str = str(p['recent_values'][:10])
    print(f"{p['player']:<20} {p['line']:>6.1f} {p['direction']:<6} "
          f"{p['empirical_hit_rate']:>6.1%} {p['bayesian_p']:>6.1%} "
          f"{p['mean']:>6.1f} {p['median']:>5.1f} {p['std']:>5.1f} {recent_str}")

print("\n" + "="*100)
print("THRESHOLD ANALYSIS:")
print("="*100)

thresholds = [0.75, 0.70, 0.65, 0.60, 0.55]
for t in thresholds:
    count = sum(1 for p in points_picks if p['bayesian_p'] >= t)
    print(f"  Bayesian >= {t:.0%}: {count} picks")
    if count > 0 and t >= 0.65:
        print(f"    → {', '.join([p['player'] for p in points_picks if p['bayesian_p'] >= t])}")

print("\n" + "="*100)
print("LATE GAME PICKS (Wed 9:10pm - Still Playable):")
print("="*100)

late_picks = [p for p in points_picks if 'Wed 9:10pm' in p.get('game_time', '')]
late_picks.sort(key=lambda x: x['bayesian_p'], reverse=True)

print(f"{'Player':<20} {'Line':>6} {'Dir':<6} {'Emp%':>7} {'Bay%':>7} {'Game Time'}")
print("-"*100)
for p in late_picks:
    print(f"{p['player']:<20} {p['line']:>6.1f} {p['direction']:<6} "
          f"{p['empirical_hit_rate']:>6.1%} {p['bayesian_p']:>6.1%} {p['game_time']}")

# Compare to 3PM and rebounds thresholds
print("\n" + "="*100)
print("COMPARISON TO OTHER STATS:")
print("="*100)
print("  3PM picks: 100% and 90% empirical → 74.9% and 69.9% Bayesian (SLAM/STRONG tiers)")
print("  Rebounds picks: 100% and 90% empirical → 74.9% and 69.9% Bayesian (SLAM/STRONG tiers)")
print(f"  Best points pick: {points_picks[0]['player']} → {points_picks[0]['bayesian_p']:.1%} Bayesian")
print("\n  Points props need higher empirical hit rates to compete!")
print("="*100)
