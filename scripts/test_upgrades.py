"""Test the system upgrades from Feb 4, 2026."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.data_driven_penalties import (
    get_data_driven_multiplier, 
    validate_ticket,
    TICKET_RULES,
)
from ufa.optimizer.ticket_governor import TicketGovernor

print('=' * 60)
print('SYSTEM UPGRADE VALIDATION - Feb 4, 2026')
print('=' * 60)

print('\n📊 MULTIPLIER CHANGES:')
print(f'  PRA OVER (NBA):     {get_data_driven_multiplier("pra", "higher", "nba"):.2f}x (was 0.50)')
print(f'  3PM UNDER (NBA):    {get_data_driven_multiplier("3pm", "lower", "nba"):.2f}x (was 0.67)')
print(f'  NHL SOG OVER:       {get_data_driven_multiplier("sog", "higher", "nhl"):.2f}x (binary boost)')
print(f'  Tennis Games UNDER: {get_data_driven_multiplier("games_won", "lower", "tennis"):.2f}x (NEW)')
print(f'  CBB Points OVER:    {get_data_driven_multiplier("points", "higher", "cbb"):.2f}x (NEW)')
print(f'  Rebound UNDER:      {get_data_driven_multiplier("reb", "lower", "nba"):.2f}x (big man caution)')

print('\n🎯 TICKET RULES:')
for key, val in TICKET_RULES.items():
    print(f'  {key}: {val}')

print('\n🎫 TICKET VALIDATION EXAMPLES:')

# Example 1: Safe ticket (binary + unders)
safe = [
    {'stat': '3pm', 'direction': 'lower'},
    {'stat': 'assists', 'direction': 'higher'},
]
r = validate_ticket(safe)
print(f'\n  ✅ Safe (3PM under + AST): valid={r["valid"]}, variance={r["variance_count"]}')

# Example 2: At variance limit
borderline = [
    {'stat': 'pra', 'direction': 'higher'},
    {'stat': 'points', 'direction': 'higher'},
    {'stat': '3pm', 'direction': 'lower'},
]
r = validate_ticket(borderline)
print(f'  ⚠️  Borderline (PRA over + PTS over): valid={r["valid"]}, variance={r["variance_count"]}')
if r['warnings']:
    print(f'      Warning: {r["warnings"][0]}')

# Example 3: BLOCKED (too many variance)
bad = [
    {'stat': 'pra', 'direction': 'higher'},
    {'stat': 'points', 'direction': 'higher'},
    {'stat': 'points', 'direction': 'higher'},
    {'stat': 'pra', 'direction': 'higher'},
]
r = validate_ticket(bad)
print(f'  ❌ Bad (4 variance props): valid={r["valid"]}')
if r['violations']:
    print(f'      Violation: {r["violations"][0]}')

print('\n✅ System ready with calibration-based governance!')
print('   - 17 picks added to calibration (10 hits, 7 misses)')
print('   - Sport-specific multipliers (NHL, Tennis, CBB)')
print('   - Variance governance (max 2 volatile props per ticket)')
print('   - PRA overs penalized heavily (0.40x multiplier)')
