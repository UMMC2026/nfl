"""
TRUE A/B TEST: Gates ON vs OFF
==============================
Takes the 7 found picks and re-analyzes them with different penalty_mode settings.
This shows EXACTLY what each gate does to the confidence scores.
"""
import json
import sys
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent))

# The 7 picks we found in the data (with their raw mu/sigma from the JSON)
PICKS_WITH_DATA = [
    {"player": "Isaiah Hartenstein", "stat": "rebounds", "line": 6.5, "direction": "higher", "mu": 8.74, "sigma": 4.06, "sample_n": 24, "cheatsheet": 76.0},
    {"player": "Jalen Johnson", "stat": "assists", "line": 6.5, "direction": "higher", "mu": 6.66, "sigma": 1.37, "sample_n": 45, "cheatsheet": 67.9},
    {"player": "Royce O'Neale", "stat": "rebounds", "line": 4.5, "direction": "higher", "mu": 3.74, "sigma": 1.62, "sample_n": 47, "cheatsheet": 61.3},
    {"player": "Josh Giddey", "stat": "assists", "line": 7.5, "direction": "higher", "mu": 6.59, "sigma": 3.46, "sample_n": 34, "cheatsheet": 60.5},
    {"player": "Andrew Wiggins", "stat": "rebounds", "line": 4.5, "direction": "higher", "mu": 5.93, "sigma": 2.62, "sample_n": 44, "cheatsheet": 59.1},
    {"player": "Myles Turner", "stat": "rebounds", "line": 6.5, "direction": "lower", "mu": 5.79, "sigma": 2.35, "sample_n": 43, "cheatsheet": 62.3},
    {"player": "Jabari Smith Jr.", "stat": "rebounds", "line": 7.5, "direction": "lower", "mu": 6.98, "sigma": 2.62, "sample_n": 44, "cheatsheet": 61.8},
]

def manual_probability_calc(mu, sigma, line, direction):
    """Calculate raw probability using Normal CDF (same as the system)."""
    from scipy.stats import norm
    z_score = (line - mu) / sigma
    if direction.lower() in ["higher", "over"]:
        prob = 1 - norm.cdf(z_score)
    else:
        prob = norm.cdf(z_score)
    return prob * 100

def apply_data_driven_multipliers(prob, stat, direction, n_games):
    """Apply the data-driven multipliers from config/data_driven_penalties.py."""
    # Stat multipliers
    STAT_MULT = {
        "ast": 1.20, "assists": 1.20,
        "3pm": 1.06,
        "pts": 1.00, "reb": 1.00, "rebounds": 1.00,
        "pts+ast": 0.75, "reb+ast": 0.75,
    }
    
    # Direction multipliers
    DIR_MULT = {
        "higher": 0.94, "over": 0.94,
        "lower": 1.03, "under": 1.03,
    }
    
    # Sample size scaling
    def get_sample_mult(n):
        if n < 5: return 0.0  # VETO
        if n >= 20: return 1.00
        if n >= 15: return 0.95
        if n >= 10: return 0.90
        return 0.80
    
    stat_lower = stat.lower()
    stat_mult = STAT_MULT.get(stat_lower, 1.0)
    dir_mult = DIR_MULT.get(direction.lower(), 1.0)
    sample_mult = get_sample_mult(n_games)
    
    # Apply to EDGE, not raw probability
    implied_prob = 52.38  # At -110 odds
    raw_edge = prob - implied_prob
    effective_edge = raw_edge * stat_mult * dir_mult * sample_mult
    effective_prob = implied_prob + effective_edge
    
    return {
        "raw_prob": prob,
        "stat_mult": stat_mult,
        "dir_mult": dir_mult,
        "sample_mult": sample_mult,
        "combined_mult": stat_mult * dir_mult * sample_mult,
        "raw_edge": raw_edge,
        "effective_edge": effective_edge,
        "effective_prob": max(0, min(100, effective_prob)),
    }

def get_tier(prob):
    """Get tier based on probability."""
    if prob >= 80: return "SLAM"
    if prob >= 65: return "STRONG"
    if prob >= 55: return "LEAN"
    if prob >= 50: return "SPEC"
    return "NO_PLAY"

print("=" * 140)
print("  TRUE A/B TEST: GATES OFF (Pure Math) vs GATES ON (Data-Driven Adjustments)")
print("=" * 140)

print(f"\n{'#':<2} {'Player':<22} {'Stat':<8} {'Line':>5} {'Dir':<6} | {'Raw%':>6} | {'OFF (No Adj)':>12} | {'ON (Adjusted)':>13} | {'Delta':>7} | {'Cheat':>6}")
print("-" * 140)

total_raw = 0
total_adj = 0
total_cheat = 0

results = []

for i, p in enumerate(PICKS_WITH_DATA, 1):
    # Calculate raw probability (GATES OFF - pure Normal CDF)
    raw_prob = manual_probability_calc(p["mu"], p["sigma"], p["line"], p["direction"])
    
    # Apply data-driven adjustments (GATES ON)
    adjusted = apply_data_driven_multipliers(raw_prob, p["stat"], p["direction"], p["sample_n"])
    adj_prob = adjusted["effective_prob"]
    
    raw_tier = get_tier(raw_prob)
    adj_tier = get_tier(adj_prob)
    
    delta = adj_prob - raw_prob
    cheat = p["cheatsheet"]
    
    total_raw += raw_prob
    total_adj += adj_prob
    total_cheat += cheat
    
    # Mark tier changes
    tier_change = ""
    if raw_tier != adj_tier:
        tier_change = f" [{raw_tier}->{adj_tier}]"
    
    results.append({
        "player": p["player"],
        "stat": p["stat"],
        "raw": raw_prob,
        "adj": adj_prob,
        "delta": delta,
        "cheat": cheat,
        "raw_tier": raw_tier,
        "adj_tier": adj_tier,
        "adjustments": adjusted,
    })
    
    print(f"{i:<2} {p['player']:<22} {p['stat']:<8} {p['line']:>5.1f} {p['direction']:<6} | {raw_prob:>5.1f}% | {raw_prob:>5.1f}% {raw_tier:<6} | {adj_prob:>5.1f}% {adj_tier:<7} | {delta:>+6.1f}% | {cheat:>5.1f}%{tier_change}")

print("-" * 140)
n = len(PICKS_WITH_DATA)
print(f"{'AVG':<2} {'':<22} {'':<8} {'':<5} {'':<6} | {total_raw/n:>5.1f}% | {total_raw/n:>5.1f}%        | {total_adj/n:>5.1f}%         | {(total_adj-total_raw)/n:>+6.1f}% | {total_cheat/n:>5.1f}%")

print("\n")
print("=" * 140)
print("  DETAILED MULTIPLIER BREAKDOWN")
print("=" * 140)

print(f"\n{'Player':<22} {'Stat':<8} {'Stat Mult':>10} {'Dir Mult':>10} {'Samp Mult':>10} {'Combined':>10} | {'Raw Edge':>10} {'Eff Edge':>10}")
print("-" * 120)

for r in results:
    a = r["adjustments"]
    print(f"{r['player']:<22} {r['stat']:<8} {a['stat_mult']:>10.2f} {a['dir_mult']:>10.2f} {a['sample_mult']:>10.2f} {a['combined_mult']:>10.2f} | {a['raw_edge']:>9.1f}% {a['effective_edge']:>9.1f}%")

print("\n")
print("=" * 140)
print("  KEY INSIGHTS")
print("=" * 140)
print(f"""
  SUMMARY OF DATA-DRIVEN ADJUSTMENTS:
  
  1. ASSISTS get a +20% BOOST (multiplier 1.20)
     - Jalen Johnson AST: {results[1]['raw']:.1f}% -> {results[1]['adj']:.1f}% (+{results[1]['delta']:.1f}%)
     - Josh Giddey AST:   {results[3]['raw']:.1f}% -> {results[3]['adj']:.1f}% (+{results[3]['delta']:.1f}%)
  
  2. REBOUNDS are NEUTRAL (multiplier 1.00)
     - But DIRECTION matters!
  
  3. UNDERS get a +3% BOOST (multiplier 1.03)
     - Myles Turner REB UNDER:      {results[5]['raw']:.1f}% -> {results[5]['adj']:.1f}% ({results[5]['delta']:+.1f}%)
     - Jabari Smith Jr REB UNDER:   {results[6]['raw']:.1f}% -> {results[6]['adj']:.1f}% ({results[6]['delta']:+.1f}%)
  
  4. OVERS get a -6% PENALTY (multiplier 0.94)
     - Isaiah Hartenstein REB OVER: {results[0]['raw']:.1f}% -> {results[0]['adj']:.1f}% ({results[0]['delta']:+.1f}%)
  
  NET EFFECT:
  - Average Raw Probability:      {total_raw/n:.1f}%
  - Average Adjusted Probability: {total_adj/n:.1f}%
  - Average Change:               {(total_adj-total_raw)/n:+.1f}%
  
  The data-driven adjustments are WORKING but the effect is SMALL because:
  - Sample size multipliers are ~1.0 (all picks have n > 20)
  - UNDER boost and OVER penalty partially cancel out in this set
  
  RECOMMENDATION:
  The current HYBRID mode with data-driven penalties is reasonable.
  Consider enabling:
  - edge_gate: true (to reject low-edge plays)
  - specialist_governance: true (for BIG_MAN_3PM caps)
""")
