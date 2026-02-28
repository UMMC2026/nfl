"""Quick test of NBA team context + game situation integration."""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

os.environ["SOFTGATES"] = "1"

from nba_game_situation import set_game_situation
from risk_first_analyzer import analyze_prop_with_gates
from nba_team_context import get_matchup_summary

# Set up game situations
print('=== SETTING UP GAME SITUATIONS ===')
set_game_situation('CLE', '2026-01-16', is_home=False, days_rest=0, 
                   is_back_to_back=True, opponent='PHI', opponent_b2b=False)
set_game_situation('PHI', '2026-01-16', is_home=True, days_rest=2,
                   is_back_to_back=False, opponent='CLE', opponent_b2b=True)
print('CLE: Away, B2B')
print('PHI: Home, Opp B2B')

# Test matchup summary
print('\n=== MATCHUP SUMMARY ===')
print('CLE @ PHI:')
print(get_matchup_summary('CLE', 'PHI'))

# Test Mitchell points on B2B away
print('\n=== MITCHELL POINTS (CLE B2B @ PHI) ===')
test_prop = {
    'player': 'Donovan Mitchell',
    'team': 'CLE',
    'opponent': 'PHI',
    'stat': 'points',
    'line': 24.5,
    'direction': 'higher'
}
result = analyze_prop_with_gates(test_prop)
print(f"mu_raw: {result.get('mu_raw', 'N/A')}")
print(f"mu_adj: {result.get('mu', 'N/A')}")
print(f"pace_factor: {result.get('pace_factor', 1.0):.3f}")
print(f"matchup_factor: {result.get('matchup_factor', 1.0):.3f}")
print(f"situation_factor: {result.get('situation_factor', 1.0):.3f}")
print(f"context_notes: {result.get('context_notes', [])}")
print(f"decision: {result.get('decision', 'N/A')}")
print(f"confidence: {result.get('effective_confidence', 0):.1f}%")

# Test Embiid at home vs tired opponent
print('\n=== EMBIID POINTS (PHI HOME vs CLE B2B) ===')
test_prop2 = {
    'player': 'Joel Embiid',
    'team': 'PHI',
    'opponent': 'CLE',
    'stat': 'points',
    'line': 28.5,
    'direction': 'higher'
}
result2 = analyze_prop_with_gates(test_prop2)
print(f"mu_raw: {result2.get('mu_raw', 'N/A')}")
print(f"mu_adj: {result2.get('mu', 'N/A')}")
print(f"pace_factor: {result2.get('pace_factor', 1.0):.3f}")
print(f"matchup_factor: {result2.get('matchup_factor', 1.0):.3f}")
print(f"situation_factor: {result2.get('situation_factor', 1.0):.3f}")
print(f"context_notes: {result2.get('context_notes', [])}")
print(f"decision: {result2.get('decision', 'N/A')}")
print(f"confidence: {result2.get('effective_confidence', 0):.1f}%")
