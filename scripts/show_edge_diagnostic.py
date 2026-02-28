#!/usr/bin/env python3
"""Quick script to display edge diagnostic from latest analysis."""
import json
import sys

# Find latest DIAG file
import glob
files = sorted(glob.glob("outputs/*DIAG*FROM_UD.json"), key=lambda x: x)
if not files:
    print("No DIAG files found")
    sys.exit(1)

latest = files[-1]
print(f"Reading: {latest}")
print("=" * 70)

with open(latest) as f:
    data = json.load(f)

results = data.get('results', [])
leans = [r for r in results if r.get('decision') == 'LEAN']

if not leans:
    print("No LEAN picks found, showing first result")
    leans = results[:1]

for i, p in enumerate(leans[:3]):  # Show first 3 LEAN picks
    print(f"\n[{i+1}] {p['player']} - {p['stat']} {p['direction']} {p['line']}")
    print(f"    Tier: {p.get('tier_label', 'N/A')}")
    print(f"    Summary: {p.get('diagnostic_summary', 'N/A')}")
    
    diag = p.get('edge_diagnostics', {})
    if diag:
        z = diag.get('z_score', {})
        print(f"\n    Z-SCORE DIAGNOSTIC:")
        print(f"      z-score: {z.get('z_score', 'N/A')}")
        print(f"      σ-distance: {z.get('sigma_distance', 'N/A')}")
        print(f"      Edge quality: {z.get('edge_quality', 'N/A')}")
        print(f"      Interpretation: {z.get('interpretation', 'N/A')}")
        
        pen = diag.get('penalties', {})
        print(f"\n    PENALTY BREAKDOWN:")
        print(f"      Raw Probability: {pen.get('raw_probability', 'N/A')}%")
        for detail in pen.get('penalty_details', []):
            print(f"        {detail}")
        print(f"      Final Probability: {pen.get('final_probability', 'N/A')}%")
        
        tier = diag.get('tier', {})
        print(f"\n    TIER:")
        print(f"      {tier.get('tier', 'N/A')} ({tier.get('tier_floor', 'N/A')}%-{tier.get('tier_ceiling', 'N/A') or '100'}%)")
    print("-" * 70)

print(f"\nTotal results: {len(results)}")
print(f"LEAN picks: {len(leans)}")
