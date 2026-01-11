#!/usr/bin/env python3
"""
Update calibration_history.csv with actual game results
"""

import csv
import sys
from pathlib import Path
from datetime import datetime

def load_history():
    """Load calibration history"""
    history_file = Path("calibration_history.csv")
    if not history_file.exists():
        print("❌ calibration_history.csv not found")
        return None, None
    
    with open(history_file, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    return fieldnames, rows

def save_history(fieldnames, rows):
    """Save updated history"""
    history_file = Path("calibration_history.csv")
    with open(history_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Saved {len(rows)} picks to calibration_history.csv")

def update_pick(rows, pick_id, actual_value):
    """Update a specific pick with actual result"""
    for row in rows:
        if row['pick_id'] == pick_id:
            # Parse line and direction
            line = float(row['line'])
            direction = row['direction']
            actual = float(actual_value)
            
            # Determine outcome
            if direction == 'HIGHER':
                outcome = 'HIT' if actual > line else 'MISS'
            else:  # LOWER
                outcome = 'HIT' if actual < line else 'MISS'
            
            # Update row
            row['actual_value'] = str(actual_value)
            row['outcome'] = outcome
            row['result_posted_at'] = datetime.utcnow().isoformat() + 'Z'
            
            player = row['player_name']
            stat = row['stat_category']
            
            symbol = "✅" if outcome == "HIT" else "❌"
            print(f"{symbol} {player} {stat} {direction} {line}: {actual} → {outcome}")
            return True
    
    print(f"⚠️  Pick ID not found: {pick_id}")
    return False

def bulk_update_from_file(rows, results_file):
    """Update multiple picks from CSV file
    
    Format: pick_id,actual_value
    """
    results_path = Path(results_file)
    if not results_path.exists():
        print(f"❌ Results file not found: {results_file}")
        return 0
    
    updated = 0
    with open(results_path, 'r') as f:
        reader = csv.DictReader(f)
        for result_row in reader:
            pick_id = result_row.get('pick_id')
            actual_value = result_row.get('actual_value')
            
            if pick_id and actual_value:
                if update_pick(rows, pick_id, actual_value):
                    updated += 1
    
    return updated

def show_pending_picks(rows, date=None):
    """Show picks that need results"""
    pending = [r for r in rows if not r.get('outcome')]
    
    if date:
        pending = [r for r in pending if r.get('slate_date') == date]
    
    if not pending:
        print(f"✅ No pending picks" + (f" for {date}" if date else ""))
        return
    
    print(f"\n📋 PENDING RESULTS" + (f" - {date}" if date else "") + f" ({len(pending)} picks):\n")
    
    # Group by date
    by_date = {}
    for p in pending:
        d = p.get('slate_date', 'Unknown')
        if d not in by_date:
            by_date[d] = []
        by_date[d].append(p)
    
    for d in sorted(by_date.keys()):
        picks = by_date[d]
        print(f"\n{d} ({len(picks)} picks):")
        for p in picks[:20]:  # Show first 20
            player = p.get('player_name', 'Unknown')
            stat = p.get('stat_category', '?')
            direction = p.get('direction', '?')
            line = p.get('line', '?')
            pick_id = p.get('pick_id', '?')
            print(f"   {player:25s} {stat:12s} {direction:6s} {line:6s} | ID: {pick_id}")

def main():
    if len(sys.argv) < 2:
        print("""
📊 UPDATE RESULTS TOOL

Usage:
  # Show pending picks
  python update_results.py show [DATE]
  
  # Update single pick
  python update_results.py update PICK_ID ACTUAL_VALUE
  
  # Bulk update from CSV file
  python update_results.py bulk RESULTS_FILE.csv
  
Examples:
  python update_results.py show 2026-01-02
  python update_results.py update pick_2026010201_og_anunoby_points 22.0
  python update_results.py bulk jan02_results.csv
  
Results file format (CSV):
  pick_id,actual_value
  pick_2026010201_og_anunoby_points,22.0
  pick_2026010201_giannis_antetokounmpo_rebounds,14.0
        """)
        return
    
    fieldnames, rows = load_history()
    if not rows:
        return
    
    command = sys.argv[1]
    
    if command == "show":
        date_filter = sys.argv[2] if len(sys.argv) > 2 else None
        show_pending_picks(rows, date=date_filter)
    
    elif command == "update":
        if len(sys.argv) < 4:
            print("❌ Usage: python update_results.py update PICK_ID ACTUAL_VALUE")
            return
        
        pick_id = sys.argv[2]
        actual_value = sys.argv[3]
        
        if update_pick(rows, pick_id, actual_value):
            save_history(fieldnames, rows)
    
    elif command == "bulk":
        if len(sys.argv) < 3:
            print("❌ Usage: python update_results.py bulk RESULTS_FILE.csv")
            return
        
        results_file = sys.argv[2]
        updated = bulk_update_from_file(rows, results_file)
        
        if updated > 0:
            save_history(fieldnames, rows)
            print(f"\n✅ Updated {updated} picks")
    
    else:
        print(f"❌ Unknown command: {command}")
        print("   Valid commands: show, update, bulk")

if __name__ == "__main__":
    main()
