#!/usr/bin/env python3
"""
Remove LaMelo Ball from primary edges file
"""

import json

# Load primary edges
with open('outputs/jan8_primary_edges_complete.json', 'r') as f:
    data = json.load(f)

# Count before
before = len(data['primary_edges'])
ball_picks = [p for p in data['primary_edges'] if p.get('player') == 'LaMelo Ball']

print(f"Before: {before} primary edges")
print(f"LaMelo Ball picks found: {len(ball_picks)}")
for pick in ball_picks:
    print(f"   - {pick['player']} {pick['stat']} {pick['line']}+ ({pick['final_prob']:.0%})")
print("")

# Remove LaMelo Ball
data['primary_edges'] = [p for p in data['primary_edges'] if p.get('player') != 'LaMelo Ball']

# Save
with open('outputs/jan8_primary_edges_complete.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"✅ After: {len(data['primary_edges'])} primary edges")
print(f"   Removed: {before - len(data['primary_edges'])} LaMelo Ball picks")
