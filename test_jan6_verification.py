"""Demo: Test auto-verification with actual Jan 6 game data"""
import sys
sys.path.insert(0, '.')

from auto_verify_results import verify_pick

print("🧪 TESTING AUTO-VERIFICATION WITH JAN 6 DATA\n")
print("="*80)

# Test picks from last night's games
test_picks = [
    {
        'player': 'Anthony Davis',
        'team': 'LAL',
        'stat': 'points',
        'line': '25.5',
        'direction': 'HIGHER',
        'game_date': '2026-01-06',
        'pick_id': 'test_ad'
    },
    {
        'player': 'LeBron James',
        'team': 'LAL',
        'stat': 'rebounds',
        'line': '7.5',
        'direction': 'HIGHER',
        'game_date': '2026-01-06',
        'pick_id': 'test_lbj'
    },
    {
        'player': 'Trae Young',
        'team': 'ATL',
        'stat': 'assists',
        'line': '10.5',
        'direction': 'LOWER',
        'game_date': '2026-01-06',
        'pick_id': 'test_trae'
    },
]

for pick in test_picks:
    result = verify_pick(pick)
    
    if result:
        print(f"   Result: {result}")

print("\n" + "="*80)
print("✅ Auto-verification test complete")
