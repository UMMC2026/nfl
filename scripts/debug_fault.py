"""Debug script to find the fault in the calibration pipeline"""
import json
from pathlib import Path

# Load the latest RISK_FIRST output
f = open('outputs/THUREND_RISK_FIRST_20260129_FROM_UD.json')
d = json.load(f)
results = d.get('results', [])

# Count by status/decision (the REAL tier)
statuses = {}
for r in results:
    s = r.get('status', r.get('decision', 'UNKNOWN'))
    statuses[s] = statuses.get(s, 0) + 1

print('=== STATUS DISTRIBUTION (THE REAL TIER) ===')
for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
    print(f'{s}: {c}')

# Get the actual confidence values
confs = [r.get('status_confidence', r.get('effective_confidence', 0)) for r in results]
print()
print('=== CONFIDENCE STATS ===')
print(f'Min: {min(confs):.1f}%')
print(f'Max: {max(confs):.1f}%')
print(f'Avg: {sum(confs)/len(confs):.1f}%')
above_55 = len([c for c in confs if c > 55])
above_65 = len([c for c in confs if c > 65])
print(f'Above 55% (LEAN+): {above_55} / {len(confs)}')
print(f'Above 65% (STRONG+): {above_65} / {len(confs)}')

# Find the HIGHEST confidence plays
sorted_results = sorted(results, key=lambda x: x.get('status_confidence', 0), reverse=True)
print()
print('=== TOP 10 BY CONFIDENCE ===')
for r in sorted_results[:10]:
    player = r.get('player', 'UNK')
    stat = r.get('stat', '?')
    direction = r.get('direction', '?')
    line = r.get('line', 0)
    conf = r.get('status_confidence', 0)
    status = r.get('status', 'UNK')
    print(f"{player} | {stat} {direction} {line} | {conf:.1f}% | {status}")

# Find PLAY/LEAN/STRONG picks
plays = [r for r in results if r.get('status') in ['PLAY', 'LEAN', 'STRONG', 'SLAM']]
print()
print(f'=== PLAYABLE PICKS: {len(plays)} ===')
for p in plays[:10]:
    player = p.get('player', 'UNK')
    stat = p.get('stat', '?')
    direction = p.get('direction', '?')
    line = p.get('line', 0)
    conf = p.get('status_confidence', 0)
    status = p.get('status', 'UNK')
    print(f"{player} | {stat} {direction} {line} | {conf:.1f}% | {status}")
