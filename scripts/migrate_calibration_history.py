"""
Migration Script - Convert Old calibration_history.csv to New Schema
Handles the 597 existing picks and migrates them to enhanced schema
"""
import sys
import csv
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

def migrate_calibration_history():
    """Migrate old calibration_history.csv to new enhanced schema"""
    
    old_file = Path("calibration_history.csv")
    backup_file = Path(f"calibration_history.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    new_file = Path("calibration/picks.csv")
    
    print("\n" + "=" * 70)
    print("CALIBRATION HISTORY MIGRATION")
    print("=" * 70)
    print()
    
    if not old_file.exists():
        print("❌ No calibration_history.csv found")
        print("   Nothing to migrate.")
        return
    
    # Backup old file
    print(f"Creating backup: {backup_file.name}")
    import shutil
    shutil.copy(old_file, backup_file)
    print("✅ Backup created")
    print()
    
    # Read old format
    print("Reading old calibration_history.csv...")
    with open(old_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        old_rows = list(reader)
    
    print(f"Found {len(old_rows)} picks in old format")
    print()
    
    # Convert to new format
    print("Converting to new schema...")
    migrated = 0
    skipped = 0
    
    new_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(new_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = [
            'pick_id', 'date', 'sport', 'player', 'stat', 'line', 
            'direction', 'probability', 'tier', 'actual', 'hit', 'brier',
            # New fields (will be empty for migrated data)
            'team', 'opponent', 'game_id',
            'lambda_player', 'lambda_calculation', 'gap', 'z_score',
            'prob_raw', 'prob_stat_capped', 'prob_global_capped', 'cap_applied',
            'model_version', 'edge', 'edge_type'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in old_rows:
            # Skip empty rows
            if not row.get('player') or not row.get('stat'):
                skipped += 1
                continue
            
            # Generate pick_id if missing
            pick_id = row.get('pick_id', '')
            if not pick_id:
                import uuid
                pick_id = str(uuid.uuid4())
            
            # Convert to new schema (preserve old data, add defaults for new fields)
            new_row = {
                'pick_id': pick_id,
                'date': row.get('game_date', '') or row.get('added_utc', '') or datetime.now().isoformat(),
                'sport': row.get('league', 'nba').lower() or row.get('sport', 'nba').lower(),
                'player': row.get('player', ''),
                'stat': row.get('stat', ''),
                'line': row.get('line', '0'),
                'direction': row.get('direction', '').lower(),
                'probability': row.get('probability', '0'),
                'tier': row.get('tier', 'UNKNOWN'),
                'actual': row.get('actual_value', '') or row.get('actual', ''),
                'hit': 'True' if row.get('outcome', '').upper() == 'HIT' else 'False' if row.get('outcome') else '',
                'brier': '',  # Will be calculated if hit is known
                # New fields (empty for migrated data - will be populated on next analysis)
                'team': row.get('team', 'UNK'),
                'opponent': row.get('opponent', 'UNK'),
                'game_id': '',
                'lambda_player': '0',
                'lambda_calculation': 'MIGRATED_FROM_OLD_SCHEMA',
                'gap': '0',
                'z_score': '0',
                'prob_raw': row.get('probability', '0'),
                'prob_stat_capped': row.get('probability', '0'),
                'prob_global_capped': row.get('probability', '0'),
                'cap_applied': 'unknown',
                'model_version': 'pre_v2.1.4',
                'edge': '0',
                'edge_type': 'MIGRATED'
            }
            
            writer.writerow(new_row)
            migrated += 1
    
    print(f"✅ Migrated {migrated} picks")
    print(f"⚠️  Skipped {skipped} empty rows")
    print()
    
    # Summary
    print("=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"Original file: {old_file}")
    print(f"Backup saved: {backup_file}")
    print(f"New file: {new_file}")
    print()
    print(f"Total migrated: {migrated}")
    print(f"Skipped (empty): {skipped}")
    print()
    
    print("⚠️  NOTE: Migrated picks have placeholder lambda values (0)")
    print("   These will be populated when you run new analyses.")
    print()
    
    print("Next steps:")
    print("  1. Enable tracking: $env:ENABLE_CALIBRATION_TRACKING='1'")
    print("  2. Run new slate analysis to start capturing lambda values")
    print("  3. Old picks can still be used for win rate analysis")
    print()
    
    return migrated


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate calibration_history.csv to new schema")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be migrated without doing it")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No files will be modified\n")
        old_file = Path("calibration_history.csv")
        if old_file.exists():
            import csv
            with open(old_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            print(f"Would migrate {len(rows)} rows from calibration_history.csv")
            print(f"Would create backup: calibration_history.backup_TIMESTAMP.csv")
            print(f"Would create: calibration/picks.csv with enhanced schema")
        else:
            print("No calibration_history.csv found")
    else:
        migrate_calibration_history()
