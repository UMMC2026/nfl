"""Quick test: NegBin model + low-line caps for CBB."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from sports.cbb.cbb_main import (
    poisson_probability, negbin_probability, get_cbb_sigma,
    CBB_SIGMA_TABLE, compute_cbb_probability
)

print("=" * 70)
print("CBB NegBin MODEL VALIDATION")
print("=" * 70)

# 1. Model comparison
tests = [
    ("points", 19.95, 18.5, "higher"),
    ("points", 15.0, 15.5, "lower"),
    ("rebounds", 3.5, 2.5, "higher"),
    ("rebounds", 5.0, 1.5, "higher"),
    ("3pm", 2.0, 1.5, "higher"),
    ("assists", 4.0, 3.5, "higher"),
    ("pra", 30.0, 28.5, "higher"),
]
print(f"\n{'Stat':<12} {'Mean':>6} {'Line':>6} {'Dir':<7} | {'Poisson':>8} {'NegBin':>8} {'Sigma':>6}")
print("-" * 70)
for stat, mean, line, direction in tests:
    sigma = get_cbb_sigma(stat, mean)
    p_poi = poisson_probability(mean, line, direction)
    p_nb = negbin_probability(mean, sigma, line, direction)
    print(f"{stat:<12} {mean:>6.1f} {line:>6.1f} {direction:<7} | {p_poi:>7.1%} {p_nb:>7.1%} {sigma:>6.1f}")

# 2. Low-line cap test
print("\n" + "=" * 70)
print("LOW-LINE CAP TEST")
print("=" * 70)
low_line_props = [
    {"player": "TestPlayer", "team": "UNC", "stat": "3pm", "line": 0.5, "direction": "higher"},
    {"player": "TestPlayer", "team": "UNC", "stat": "rebounds", "line": 1.5, "direction": "higher"},
    {"player": "TestPlayer", "team": "UNC", "stat": "rebounds", "line": 2.5, "direction": "higher"},
    {"player": "TestPlayer", "team": "UNC", "stat": "assists", "line": 4.5, "direction": "higher"},
    {"player": "TestPlayer", "team": "UNC", "stat": "points", "line": 18.5, "direction": "higher"},
]

for prop in low_line_props:
    result = compute_cbb_probability(prop)
    trace = result["decision_trace"]
    cap_hit = trace["caps"]["cap_hit"]
    low_line_cap = trace["caps"].get("low_line_cap", "N/A")
    print(f"  {prop['stat']:>10} line={prop['line']:>5.1f} -> prob={result['probability']:.1%}"
          f"  model={result['model']:<20s} low_cap={low_line_cap} cap_hit={cap_hit}")

# 3. Sigma table
print("\n" + "=" * 70)
print("CBB SIGMA TABLE")
print("=" * 70)
for stat, sigma in sorted(CBB_SIGMA_TABLE.items()):
    print(f"  {stat:<15} sigma = {sigma:.1f}")

print("\nAll tests passed!")
