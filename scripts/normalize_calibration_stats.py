"""
Normalize stat names in calibration_history.csv to consolidate duplicates.

Mappings:
  points → pts, rebounds → reb, assists → ast
  pts+reb+ast → pra, ast+reb → reb+ast
  steals → stl, blocks → blk, turnovers → tov
  3ptm/threes → 3pm, receptions → recs, receiving yards → rec yards
"""
import csv
from pathlib import Path
import shutil
from datetime import datetime

STAT_NORMALIZE = {
    'points': 'pts',
    'rebounds': 'reb', 
    'assists': 'ast',
    'steals': 'stl',
    'blocks': 'blk',
    'turnovers': 'tov',
    'pts+reb+ast': 'pra',
    'ast+reb': 'reb+ast',
    '3ptm': '3pm',
    'threes': '3pm',
    'receptions': 'recs',
    'receiving yards': 'rec yards',
}

def normalize_stats(dry_run=True):
    cal_file = Path(__file__).parent.parent / "calibration_history.csv"
    
    if not cal_file.exists():
        print("No calibration_history.csv found")
        return
    
    with open(cal_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    
    changes = 0
    for row in rows:
        stat = row.get('stat', '').lower().strip()
        if stat in STAT_NORMALIZE:
            new_stat = STAT_NORMALIZE[stat]
            if not dry_run:
                row['stat'] = new_stat
            print(f"  {stat:15} → {new_stat}")
            changes += 1
    
    print(f"\nTotal changes: {changes}")
    
    if dry_run:
        print("\n[DRY RUN] No changes written. Run with --execute to apply.")
    else:
        # Backup first
        backup = cal_file.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        shutil.copy(cal_file, backup)
        print(f"\nBackup created: {backup}")
        
        # Write normalized data
        with open(cal_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✓ Normalized {changes} stat names in calibration_history.csv")

if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    normalize_stats(dry_run=dry_run)
