#!/usr/bin/env python3
"""
Test SDG with a player that HAS data in STATS_DICT.
"""
import sys
sys.path.insert(0, '.')

from risk_first_analyzer import (
    analyze_prop_with_gates, 
    HAS_STAT_DEVIATION_GATE,
    get_stat_params,
    STATS_DICT
)

print("=" * 60)
print("SDG INTEGRATION TEST - REAL PLAYER DATA")
print("=" * 60)

print(f"\nSDG Module Loaded: {HAS_STAT_DEVIATION_GATE}")
print(f"Players in STATS_DICT: {len(STATS_DICT)}")

# Get a player from the cache
if STATS_DICT:
    player = list(STATS_DICT.keys())[0]
    stats_for_player = STATS_DICT[player]
    stat = list(stats_for_player.keys())[0]
    mu, sigma = stats_for_player[stat]
    
    print(f"\nTest Player: {player}")
    print(f"Test Stat: {stat}")
    print(f"Raw mu: {mu}, sigma: {sigma}")
    
    # Test case 1: Line exactly at mean (should trigger HEAVY SDG penalty)
    line_at_mean = round(mu, 1)
    print(f"\n--- TEST 1: Line at mean ({line_at_mean}) ---")
    
    result1 = analyze_prop_with_gates(
        prop={
            'player': player,
            'stat': stat,
            'line': line_at_mean,
            'direction': 'higher',
            'team': 'PHI',
            'opponent': 'NYK',
        },
        verbose=True
    )
    
    print(f"\nSDG Result: {result1.get('sdg_result')}")
    print(f"SDG Multiplier: {result1.get('sdg_multiplier')}")
    print(f"SDG Penalty Applied: {result1.get('sdg_penalty_applied')}")
    
    # Test case 2: Line 2 sigma away (should PASS SDG)
    line_far = round(mu + 2 * sigma, 1)
    print(f"\n--- TEST 2: Line 2σ away ({line_far}) ---")
    
    result2 = analyze_prop_with_gates(
        prop={
            'player': player,
            'stat': stat,
            'line': line_far,
            'direction': 'lower',
            'team': 'PHI',
            'opponent': 'NYK',
        },
        verbose=True
    )
    
    print(f"\nSDG Result: {result2.get('sdg_result')}")
    print(f"SDG Multiplier: {result2.get('sdg_multiplier')}")
    print(f"SDG Penalty Applied: {result2.get('sdg_penalty_applied')}")
    
    # Show context warnings
    print("\n--- CONTEXT WARNINGS ---")
    for i, r in enumerate([result1, result2], 1):
        warnings = r.get('context_warnings', [])
        sdg_warnings = [w for w in warnings if 'SDG' in str(w)]
        print(f"Test {i}: {sdg_warnings if sdg_warnings else 'No SDG warnings'}")
else:
    print("ERROR: STATS_DICT is empty!")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
