"""Add today's signals to calibration_history.csv for tracking"""
import json
import csv
from pathlib import Path
from datetime import datetime

signals_file = Path("output/signals_latest.json")
calibration_file = Path("calibration_history.csv")

# Load signals
with open(signals_file) as f:
    signals = json.load(f)

print(f"Loading {len(signals)} signals from {signals_file}")

# Load existing calibration history
existing_ids = set()
rows = []
fieldnames = ['pick_id', 'game_date', 'player', 'team', 'opponent', 'stat', 'line', 
              'direction', 'probability', 'tier', 'actual_value', 'outcome', 'added_utc']

if calibration_file.exists():
    with open(calibration_file, 'r', newline='') as f:
        reader = csv.DictReader(f)
        # Keep only the fields we want
        for row in reader:
            filtered_row = {k: row.get(k, '') for k in fieldnames}
            rows.append(filtered_row)
            existing_ids.add(row.get('pick_id', ''))

print(f"Found {len(existing_ids)} existing picks in calibration history")

# Add new picks
added = 0
for signal in signals:
    # Generate pick_id from edge_id or construct it
    if 'edge_id' in signal:
        pick_id = signal['edge_id']
    else:
        # Construct pick_id: game_date + player + stat
        pick_id = f"{signal.get('game_date', '2026-01-07').replace('-', '')}_{signal['player'].replace(' ', '_').lower()}_{signal['stat']}"
    
    if pick_id in existing_ids:
        continue  # Skip duplicates
    
    # Create calibration row
    row = {
        'pick_id': pick_id,
        'game_date': signal.get('game_date', '2026-01-07'),
        'player': signal['player'],
        'team': signal['team'],
        'opponent': signal['opponent'],
        'stat': signal['stat'],
        'line': signal['line'],
        'direction': signal['direction'],
        'probability': signal['probability'],
        'tier': signal.get('confidence_tier', 'LEAN'),
        'actual_value': '',  # Will be filled by auto_verify_results.py
        'outcome': '',  # Will be filled by auto_verify_results.py
        'added_utc': datetime.utcnow().isoformat()
    }
    
    rows.append(row)
    added += 1

print(f"Adding {added} new picks to calibration history")

# Write back (remove old fieldnames definition since it's defined earlier)
with open(calibration_file, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Calibration history updated: {len(rows)} total picks")
