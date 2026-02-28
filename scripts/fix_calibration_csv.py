#!/usr/bin/env python3
"""
Fix corrupted calibration_history.csv rows where team abbreviation 
was inserted in the wrong column, shifting all data.

Expected format: date,player,stat,line,direction,predicted_prob,decision,actual_result,role,gate_warnings,stat_type
Corrupted format: date,player,TEAM,stat,line,direction,predicted_prob,actual_value,hit,decision
"""
import csv
from pathlib import Path
from datetime import datetime

TEAM_ABBREVS = {
    'ATL', 'BKN', 'BOS', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
    'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
}

VALID_STATS = {
    'points', 'pts', 'assists', 'ast', 'rebounds', 'reb', '3pm', '3ptm', 'threes',
    'steals', 'stl', 'blocks', 'blk', 'turnovers', 'tov',
    'pts+reb+ast', 'pra', 'pts+ast', 'pts+reb', 'reb+ast',
    '1h_points', '1h_assists', '1h_rebounds', '1h_3pm',
    'fantasy_score', 'double_double', 'triple_double'
}

def fix_calibration_csv(dry_run=True):
    csv_path = Path("calibration_history.csv")
    if not csv_path.exists():
        print("❌ calibration_history.csv not found")
        return
    
    # Read all rows
    with open(csv_path, 'r', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    
    print(f"Original header: {header}")
    print(f"Total rows: {len(rows)}")
    
    # Expected header
    expected_header = ['date', 'player', 'stat', 'line', 'direction', 
                       'predicted_prob', 'decision', 'actual_result', 
                       'role', 'gate_warnings', 'stat_type']
    
    fixed_rows = []
    corrupted_count = 0
    
    for i, row in enumerate(rows):
        if len(row) < 3:
            fixed_rows.append(row)
            continue
            
        # Check if stat column (index 2) contains a team abbreviation
        stat_val = row[2].upper().strip() if len(row) > 2 else ''
        
        if stat_val in TEAM_ABBREVS:
            # This row is corrupted - team is in stat position
            # Original: date,player,TEAM,stat,line,direction,predicted_prob,actual_value,hit,decision
            # Fixed:    date,player,stat,line,direction,predicted_prob,decision,actual_result,...
            corrupted_count += 1
            
            if len(row) >= 10:
                # Map corrupted columns to correct positions
                fixed_row = [
                    row[0],      # date
                    row[1],      # player
                    row[3],      # stat (was in position 3)
                    row[4],      # line (was in position 4)
                    row[5],      # direction (was in position 5)
                    row[6],      # predicted_prob (was in position 6)
                    row[9] if len(row) > 9 else '',  # decision (was in position 9)
                    'hit' if row[8] == '1' else 'miss' if row[8] == '0' else '',  # actual_result from hit column
                    '',          # role
                    '',          # gate_warnings
                    ''           # stat_type
                ]
                if dry_run:
                    print(f"  Row {i+2}: CORRUPTED -> {row[1]} | {stat_val}(team) | {row[3]}(stat)")
                fixed_rows.append(fixed_row)
            else:
                print(f"  Row {i+2}: CORRUPTED but too short to fix: {row}")
                fixed_rows.append(row)
        else:
            # Row is OK
            fixed_rows.append(row)
    
    print(f"\n📊 Found {corrupted_count} corrupted rows")
    
    if dry_run:
        print("\n🔍 DRY RUN - No changes made")
        print("   Run with --execute to apply fixes")
    else:
        # Backup original
        backup_path = csv_path.with_suffix(f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        csv_path.rename(backup_path)
        print(f"\n📦 Backup saved to: {backup_path}")
        
        # Write fixed CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(expected_header)
            writer.writerows(fixed_rows)
        
        print(f"✅ Fixed CSV saved to: {csv_path}")
        print(f"   Total rows: {len(fixed_rows)}")

if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    fix_calibration_csv(dry_run=dry_run)
