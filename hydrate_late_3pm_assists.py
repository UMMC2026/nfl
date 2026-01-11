"""Hydrate 3PM and assists props for late games."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ufa.ingest.hydrate import hydrate_recent_values

with open('inputs/jan8_late_3pm_assists.json', encoding='utf-8') as f:
    props = json.load(f)

print(f"Hydrating {len(props)} props (3PM + assists for late games)...")
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
        recent_values = hydrate_recent_values(
            league="NBA",
            player=player,
            stat_key=stat,
            nba_season="2024-25"
        )
        
        if recent_values:
            p['recent_values'] = recent_values
            hydrated.append(p)
            print(f"[{i}/{len(props)}] {player:<25} {line:>4} {stat:<8} {direction:<6}: OK")
            success += 1
        else:
            print(f"[{i}/{len(props)}] {player:<25} {line:>4} {stat:<8} {direction:<6}: SKIP")
            fail += 1
            
    except Exception as e:
        print(f"[{i}/{len(props)}] {player:<25} {line:>4} {stat:<8} {direction:<6}: FAIL ({str(e)[:40]})")
        fail += 1

output_file = 'picks_hydrated_late_3pm_assists.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(hydrated, f, indent=2, ensure_ascii=False)

print()
print(f"SUCCESS: {success}/{len(props)}")
print(f"FAILED: {fail}/{len(props)}")
print(f"Saved to: {output_file}")
