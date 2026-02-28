#!/usr/bin/env python3
"""
Test SDG with real player data from latest slate.
"""
import json
import sys
sys.path.insert(0, '.')

# Load latest analysis
latest_file = 'outputs/WAS_LAL_RISK_FIRST_20260130_FROM_UD.json'
try:
    with open(latest_file, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"File not found: {latest_file}")
    sys.exit(1)

picks = data.get('results', data.get('edges', data.get('picks', [])))
print(f"Total picks in latest slate: {len(picks)}")

# Check for SDG fields in existing picks
sdg_count = 0
for p in picks[:5]:
    player = p.get('player', 'Unknown')
    stat = p.get('stat', 'Unknown')
    mu = p.get('mu')
    sigma = p.get('sigma')
    line = p.get('line')
    sdg_result = p.get('sdg_result')
    
    print(f"\n{player} {stat}:")
    print(f"  mu={mu}, sigma={sigma}, line={line}")
    print(f"  sdg_result={sdg_result}")
    
    if sdg_result:
        sdg_count += 1

print(f"\n\nPicks with SDG result: {sdg_count}/{len(picks[:5])}")

# Now run the analyzer on a real pick to see if SDG works
print("\n" + "=" * 60)
print("LIVE ANALYSIS TEST")
print("=" * 60)

from risk_first_analyzer import analyze_prop_with_gates

# Use first pick's data
if picks:
    p = picks[0]
    test_prop = {
        'player': p.get('player'),
        'stat': p.get('stat'),
        'line': p.get('line'),
        'direction': p.get('direction', 'higher'),
        'team': p.get('team', 'LAL'),
        'opponent': p.get('opponent', 'GSW'),
    }
    
    print(f"\nRe-analyzing: {test_prop['player']} {test_prop['stat']} > {test_prop['line']}")
    
    result = analyze_prop_with_gates(prop=test_prop, verbose=True)
    
    print(f"\nSDG Fields in NEW analysis:")
    print(f"  sdg_result: {result.get('sdg_result')}")
    print(f"  sdg_multiplier: {result.get('sdg_multiplier')}")
    print(f"  sdg_penalty_applied: {result.get('sdg_penalty_applied')}")
