"""
Clean calibration history: relabel pre-governance LEAN picks (prob < 55%) as 'USER' tier.

These 46 picks were labeled LEAN before the 55% governance gate was enforced.
They contaminate the LEAN calibration metrics. Relabeling them as USER (user-selected, 
not model-recommended) preserves the data without deleting it.

Run with --dry-run first to preview changes.
"""
import csv
import sys
import shutil
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
CSV_PATH = 'calibration_history.csv'

# Read all rows
rows = []
fieldnames = None
with open(CSV_PATH, 'r', newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        rows.append(row)

print(f'Total rows: {len(rows)}')

# Find contaminated LEAN picks
relabeled = 0
for row in rows:
    if (row.get('league', '').upper() == 'NBA' and 
        row.get('tier', '').upper() == 'LEAN'):
        prob = float(row.get('probability', 0))
        if prob < 55.0:
            if not DRY_RUN:
                row['tier'] = 'USER'  # Relabel from LEAN to USER
            relabeled += 1
            hit = row.get('outcome', '').strip().upper() == 'HIT'
            print(f'  {"[DRY] " if DRY_RUN else ""}Relabel: {row.get("player","?")} '
                  f'{row.get("stat","?")} {row.get("direction","?")} '
                  f'prob={prob:.1f}% outcome={row.get("outcome","?")} -> USER')

print(f'\nTotal relabeled: {relabeled}')

if DRY_RUN:
    print('\n[DRY RUN] No changes written. Run without --dry-run to apply.')
else:
    # Backup first
    backup_path = f'calibration_history.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    shutil.copy2(CSV_PATH, backup_path)
    print(f'Backup created: {backup_path}')
    
    # Write cleaned data
    with open(CSV_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f'Cleaned data written to {CSV_PATH}')

# Show updated LEAN stats
lean_remaining = [r for r in rows if r.get('league','').upper() == 'NBA' and r.get('tier','').upper() == 'LEAN']
if lean_remaining:
    hits = sum(1 for r in lean_remaining if r.get('outcome','').strip().upper() == 'HIT')
    print(f'\nRemaining NBA LEAN: {hits}/{len(lean_remaining)} = {hits/len(lean_remaining)*100:.1f}%')
else:
    print('\nNo LEAN picks remaining (all were contaminated)')
