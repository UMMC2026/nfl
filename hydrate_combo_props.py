"""Hydrate combo props (PRA, reb+ast) with NBA data."""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ufa.ingest.hydrate import hydrate_recent_values

# Load combo props
with open('inputs/jan8_combo_props.json', encoding='utf-8') as f:
    props = json.load(f)

print(f"Hydrating {len(props)} combo props...")
print()

hydrated = []
success = 0
fail = 0

for i, p in enumerate(props, 1):
    player = p['player']
    stat = p['stat']
    line = p['line']
    direction = p['direction']
    
    try:
        # Hydrate with NBA game logs
        recent_values = hydrate_recent_values(
            league="NBA",
            player=player,
            stat_key=stat,
            nba_season="2024-25"
        )
        
        if recent_values:
            p['recent_values'] = recent_values
            hydrated.append(p)
            print(f"[{i}/{len(props)}] {player} {line} {stat} {direction}: OK")
            success += 1
        else:
            print(f"[{i}/{len(props)}] {player} {line} {stat} {direction}: SKIP (no data)")
            fail += 1
            
    except Exception as e:
        print(f"[{i}/{len(props)}] {player} {line} {stat} {direction}: FAIL ({str(e)[:50]})")
        fail += 1

# Save hydrated props
output_file = 'picks_hydrated_combo.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(hydrated, f, indent=2, ensure_ascii=False)

print()
print(f"SUCCESS: {success}/{len(props)}")
print(f"FAILED: {fail}/{len(props)}")
print(f"Saved to: {output_file}")
