#!/usr/bin/env python3
"""
Standardize new picks to match old schema.
"""

import json

h = json.load(open('picks_hydrated.json'))

# Fix new picks (141+) to have 'player' key instead of 'player_name'
for i in range(140, len(h)):
    if 'player_name' in h[i]:
        h[i]['player'] = h[i].pop('player_name')
    
    # Add missing fields if needed
    if 'league' not in h[i]:
        h[i]['league'] = 'NBA'
    if 'recent_values' not in h[i]:
        h[i]['recent_values'] = []

# Save
with open('picks_hydrated.json', 'w') as f:
    json.dump(h, f, indent=2)

print(f"✅ Standardized {len(h)} picks")
print(f"First new pick keys: {list(h[140].keys())}")
