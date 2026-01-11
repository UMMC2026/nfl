"""Add Jan 6 signals to calibration for verification"""
import json
import csv
from pathlib import Path
from datetime import datetime

# Load Jan 6 signals
signals_file = Path("output/signals_latest.json")
with open(signals_file) as f:
    signals = json.load(f)

print(f"Loading {len(signals)} signals from {signals_file}")

# Create calibration rows for Jan 6
rows = []
for i, signal in enumerate(signals):
    pick_id = signal.get('edge_id', f"jan6_{i}")
    
    row = {
        'pick_id': pick_id,
        'game_date': '2026-01-06',
        'player': signal['player'],
        'team': signal['team'],
        'opponent': signal['opponent'],
        'stat': signal['stat'],
        'line': signal['line'],
        'direction': signal['direction'],
        'probability': signal['probability'],
        'tier': signal.get('confidence_tier', 'LEAN'),
        'actual_value': '',
        'outcome': '',
        'added_utc': datetime.utcnow().isoformat()
    }
    
    rows.append(row)

# Write to separate file
fieldnames = ['pick_id', 'game_date', 'player', 'team', 'opponent', 'stat', 'line', 
              'direction', 'probability', 'tier', 'actual_value', 'outcome', 'added_utc']

output_file = Path("calibration_jan6.csv")
with open(output_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Created {output_file} with {len(rows)} picks")
print(f"\nTo verify results, run:")
print(f"  python auto_verify_results.py 2026-01-06 --file calibration_jan6.csv")
