#!/usr/bin/env python3
"""
Verify SDG (Stat Deviation Gate) is properly integrated into main analysis.
"""

import sys
sys.path.insert(0, '.')

from risk_first_analyzer import analyze_prop_with_gates, HAS_STAT_DEVIATION_GATE

print("=" * 60)
print("SDG INTEGRATION VERIFICATION")
print("=" * 60)

print(f"\nSDG Module Loaded: {HAS_STAT_DEVIATION_GATE}")

if not HAS_STAT_DEVIATION_GATE:
    print("ERROR: SDG module not loaded!")
    sys.exit(1)

# Test with a pick that should trigger SDG (line ≈ expected mean)
# Simulate a player averaging ~25 points
test_cases = [
    # (player, stat, line, team, opponent, expected_sdg_penalty)
    ("Test Star", "PTS", 25.5, "LAL", "GSW", "may_trigger"),  # Line close to typical star average
    ("Test Player", "3PM", 2.5, "BOS", "MIA", "may_trigger"),  # 3PM close to average
]

for player, stat, line, team, opponent, expected in test_cases:
    print(f"\n--- Testing: {player} {stat} > {line} ---")
    
    result = analyze_prop_with_gates(
        prop={
            'player': player,
            'stat': stat,
            'line': line,
            'direction': 'higher',
            'team': team,
            'opponent': opponent,
        },
        verbose=False
    )
    
    # Check for SDG fields
    sdg_result = result.get('sdg_result')
    sdg_multiplier = result.get('sdg_multiplier', 1.0)
    sdg_penalty_applied = result.get('sdg_penalty_applied', False)
    
    print(f"  SDG Result Present: {sdg_result is not None}")
    print(f"  SDG Multiplier: {sdg_multiplier}")
    print(f"  SDG Penalty Applied: {sdg_penalty_applied}")
    
    if sdg_result:
        print(f"  SDG Z-Stat: {sdg_result.get('z_stat', 'N/A')}")
        print(f"  SDG Penalty Level: {sdg_result.get('penalty_level', 'N/A')}")
        print(f"  mu: {sdg_result.get('mu')}, sigma: {sdg_result.get('sigma')}, line: {sdg_result.get('line')}")
    
    # Check context warnings for SDG
    warnings = result.get('context_warnings', [])
    sdg_warnings = [w for w in warnings if 'SDG' in w]
    if sdg_warnings:
        print(f"  SDG Warnings: {sdg_warnings}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
print("\nIf SDG Result is present and shows z_stat values, SDG is integrated!")
