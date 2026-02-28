"""
SDG Backtest Tool
=================
Run Stat Deviation Gate on historical slates to see how it would have filtered picks.

Usage:
    python tools/sdg_backtest.py outputs/FILENAME_RISK_FIRST.json
    python tools/sdg_backtest.py  # Uses most recent slate
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.stat_deviation_gate import stat_deviation_gate, apply_sdg_to_pick


def backtest_slate(filepath: str, top_n: int = 30):
    """Run SDG on a historical slate and show results."""
    
    with open(filepath) as f:
        data = json.load(f)
    
    results = data.get("results", [])
    
    print("\n" + "="*70)
    print(f"SDG BACKTEST: {Path(filepath).name}")
    print("="*70)
    print(f"\nTotal picks in slate: {len(results)}")
    
    # Run SDG on each pick
    sdg_results = []
    for pick in results:
        mu = pick.get("mu")
        sigma = pick.get("sigma")
        line = pick.get("line")
        
        # Skip if missing data
        if mu is None or sigma is None or line is None:
            continue
        if sigma <= 0:
            continue
            
        stat = pick.get("stat", "unknown")
        player = pick.get("player", "Unknown")
        direction = pick.get("direction", "?")
        prob = pick.get("model_confidence", pick.get("probability", 0))
        status = pick.get("status", pick.get("decision", "?"))
        
        # Calculate SDG
        mult, desc, details = stat_deviation_gate(mu, sigma, line, stat)
        z_stat = details.get("z_stat", 0)
        penalty = details.get("penalty", "none")
        
        sdg_results.append({
            "player": player,
            "stat": stat,
            "direction": direction,
            "line": line,
            "mu": mu,
            "sigma": sigma,
            "z_stat": z_stat,
            "sdg_penalty": penalty,
            "sdg_mult": mult,
            "orig_prob": prob,
            "adj_prob": prob * mult if prob else 0,
            "orig_status": status,
        })
    
    print(f"Picks with μ/σ data: {len(sdg_results)}")
    
    # Summary stats
    penalties = defaultdict(int)
    for r in sdg_results:
        penalties[r["sdg_penalty"]] += 1
    
    print(f"\n📊 SDG SUMMARY:")
    print(f"   HEAVY penalty (z<0.25): {penalties['heavy']} picks ({100*penalties['heavy']/len(sdg_results):.1f}%)")
    print(f"   MEDIUM penalty (z<0.50): {penalties['medium']} picks ({100*penalties['medium']/len(sdg_results):.1f}%)")
    print(f"   PASS (z≥0.50): {penalties['none']} picks ({100*penalties['none']/len(sdg_results):.1f}%)")
    
    # Show worst offenders (lowest z_stat)
    sorted_by_z = sorted(sdg_results, key=lambda x: abs(x["z_stat"]))
    
    print(f"\n🚨 COIN FLIPS (Would be penalized by SDG):")
    print("-"*70)
    print(f"{'Player':<20} {'Stat':<8} {'Dir':<6} {'Line':>6} {'μ':>6} {'σ':>5} {'z':>6} {'Pen':<8}")
    print("-"*70)
    
    shown = 0
    for r in sorted_by_z:
        if r["sdg_penalty"] != "none" and shown < top_n:
            print(f"{r['player']:<20} {r['stat']:<8} {r['direction']:<6} {r['line']:>6.1f} {r['mu']:>6.1f} {r['sigma']:>5.1f} {r['z_stat']:>+6.2f} {r['sdg_penalty'].upper():<8}")
            shown += 1
    
    # Show best edges (highest |z_stat|)
    sorted_by_z_desc = sorted(sdg_results, key=lambda x: abs(x["z_stat"]), reverse=True)
    
    print(f"\n✅ GOOD EDGES (SDG PASS):")
    print("-"*70)
    print(f"{'Player':<20} {'Stat':<8} {'Dir':<6} {'Line':>6} {'μ':>6} {'σ':>5} {'z':>6} {'Status':<8}")
    print("-"*70)
    
    shown = 0
    for r in sorted_by_z_desc:
        if r["sdg_penalty"] == "none" and shown < 15:
            print(f"{r['player']:<20} {r['stat']:<8} {r['direction']:<6} {r['line']:>6.1f} {r['mu']:>6.1f} {r['sigma']:>5.1f} {r['z_stat']:>+6.2f} {r['orig_status']:<8}")
            shown += 1
    
    # Impact analysis
    would_reject = sum(1 for r in sdg_results 
                       if r["sdg_penalty"] == "heavy" 
                       and r["orig_prob"] 
                       and r["orig_prob"] * 0.70 < 55)
    
    print(f"\n📈 IMPACT ANALYSIS:")
    print(f"   Picks that would drop below 55% threshold: {would_reject}")
    print(f"   (These would be REJECTED after SDG penalty)")
    
    return sdg_results


def find_latest_slate():
    """Find the most recent RISK_FIRST JSON file."""
    outputs_dir = Path("outputs")
    risk_first_files = list(outputs_dir.glob("*RISK_FIRST*.json"))
    if not risk_first_files:
        return None
    return max(risk_first_files, key=lambda p: p.stat().st_mtime)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        latest = find_latest_slate()
        if latest:
            filepath = str(latest)
            print(f"Using latest slate: {filepath}")
        else:
            print("No slate files found. Provide a filepath.")
            sys.exit(1)
    
    backtest_slate(filepath)
