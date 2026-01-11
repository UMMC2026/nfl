#!/usr/bin/env python3
"""
Remove LaMelo Ball from Jan 8 slate (OUT tonight)
Rebuild portfolio and regenerate enhanced narrative
"""

import json
from pathlib import Path

# Load current slate
with open('outputs/jan8_complete_slate.json', 'r') as f:
    slate = json.load(f)

# Count before
before_count = len(slate['picks'])
ball_count = sum(1 for p in slate['picks'] if p['player'] == 'LaMelo Ball')

print(f"Original slate: {before_count} picks")
print(f"LaMelo Ball picks: {ball_count}")
print("")

# Remove all LaMelo Ball picks
slate['picks'] = [p for p in slate['picks'] if p['player'] != 'LaMelo Ball']

# Save updated slate
with open('outputs/jan8_complete_slate.json', 'w') as f:
    json.dump(slate, f, indent=2)

print(f"✅ Updated slate: {len(slate['picks'])} picks ({ball_count} removed)")
print("   Saved to: outputs/jan8_complete_slate.json")
print("")

# Also check and update qualified picks if they exist
qualified_file = Path('outputs/jan8_qualified_picks.json')
if qualified_file.exists():
    with open(qualified_file, 'r') as f:
        qualified = json.load(f)
    
    before_qual = len(qualified)
    qualified = [p for p in qualified if p.get('player') != 'LaMelo Ball']
    
    with open(qualified_file, 'w') as f:
        json.dump(qualified, f, indent=2)
    
    print(f"✅ Updated qualified picks: {len(qualified)} picks")
    print("")

print("="*80)
print("NEXT STEPS:")
print("="*80)
print("1. Run: python build_final_portfolio.py")
print("2. Run: python create_enhanced_telegram.py")
print("3. Run: python split_and_send.py")
