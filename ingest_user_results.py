#!/usr/bin/env python3
"""
Ingest user betting results into calibration_history.csv
"""

import csv
from pathlib import Path
from datetime import datetime

print('='*70)
print('  CALIBRATION INGESTION — Adding your 99 results')
print('='*70)

# Your results data
results = [
    {'player': 'Ayo Dosunmu', 'stat': '3PM', 'line': 1.5, 'direction': 'UNDER', 'actual': 2, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Coby White', 'stat': '3PM', 'line': 2.5, 'direction': 'UNDER', 'actual': 5, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Cody Williams', 'stat': '3PM', 'line': 0.5, 'direction': 'UNDER', 'actual': 0, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Alperen Sengun', 'stat': 'PRA', 'line': 34.5, 'direction': 'UNDER', 'actual': 25, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Cade Cunningham', 'stat': 'PRA', 'line': 38.5, 'direction': 'UNDER', 'actual': 21, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jaden Ivey', 'stat': 'PRA', 'line': 12.5, 'direction': 'UNDER', 'actual': 11, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Evan Mobley', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'actual': 49, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Precious Achiuwa', 'stat': 'PRA', 'line': 13.5, 'direction': 'UNDER', 'actual': 14, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Zach LaVine', 'stat': 'PRA', 'line': 23.5, 'direction': 'UNDER', 'actual': 10, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Ausar Thompson', 'stat': 'REB', 'line': 5.5, 'direction': 'OVER', 'actual': 5, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Domantas Sabonis', 'stat': 'BLK+STL', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Duncan Robinson', 'stat': 'PRA', 'line': 16.5, 'direction': 'OVER', 'actual': 14, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Malik Monk', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 3, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Derik Queen', 'stat': 'AST', 'line': 4.5, 'direction': 'OVER', 'actual': 1, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'actual': 3, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Julian Champagnie', 'stat': 'PTS', 'line': 11.0, 'direction': 'OVER', 'actual': 13, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Saddiq Bey', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 10, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Zion Williamson', 'stat': 'AST', 'line': 2.5, 'direction': 'OVER', 'actual': 4, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jaden McDaniels', 'stat': 'PRA', 'line': 25.5, 'direction': 'OVER', 'actual': 7, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Kyren Williams', 'stat': 'Recs', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Matthew Stafford', 'stat': 'Rush Yards', 'line': 0.5, 'direction': 'OVER', 'actual': 16, 'result': 'WON', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Tyler Higbee', 'stat': 'Rec Yards', 'line': 19.5, 'direction': 'OVER', 'actual': 12, 'result': 'LOST', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Scottie Barnes', 'stat': '2-PT Att', 'line': 12.5, 'direction': 'OVER', 'actual': 6, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Julian Champagnie', 'stat': 'PTS', 'line': 12.5, 'direction': 'OVER', 'actual': 13, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Kayshon Boutte', 'stat': 'Rec Yards', 'line': 31.5, 'direction': 'OVER', 'actual': 6, 'result': 'LOST', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'RJ Harvey', 'stat': 'Rush Yards', 'line': 40.5, 'direction': 'OVER', 'actual': 37, 'result': 'LOST', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Ausar Thompson', 'stat': 'PRA', 'line': 20.5, 'direction': 'OVER', 'actual': 16, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'DeMar DeRozan', 'stat': 'PTS+AST', 'line': 24.5, 'direction': 'OVER', 'actual': 20, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 33.5, 'direction': 'OVER', 'actual': 27, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Tobias Harris', 'stat': 'PRA', 'line': 21.5, 'direction': 'OVER', 'actual': 21, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Cooper Kupp', 'stat': 'Recs', 'line': 3.0, 'direction': 'UNDER', 'actual': 4, 'result': 'LOST', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Kyren Williams', 'stat': 'Recs', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Blake Corum', 'stat': 'Rec Yards', 'line': 0.5, 'direction': 'OVER', 'actual': 24, 'result': 'WON', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Colby Parkinson', 'stat': 'Recs', 'line': 1.5, 'direction': 'OVER', 'actual': 3, 'result': 'WON', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Terrance Ferguson', 'stat': 'Recs', 'line': 0.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NFL', 'date': '2026-01-29'},
    {'player': 'Dylan Harper', 'stat': 'PTS', 'line': 11.5, 'direction': 'OVER', 'actual': 5, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Dylan Harper', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 6, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Harrison Barnes', 'stat': '2-PT Made', 'line': 1.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Luke Kornet', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'OVER', 'actual': 6, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Victor Wembanyama', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Yves Missi', 'stat': 'FG Made', 'line': 2.5, 'direction': 'OVER', 'actual': 4, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Dailyn Swain', 'stat': 'PTS', 'line': 14.5, 'direction': 'UNDER', 'actual': 29, 'result': 'LOST', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Otega Oweh', 'stat': 'PTS', 'line': 17.5, 'direction': 'UNDER', 'actual': 18, 'result': 'LOST', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Tramon Mark', 'stat': 'PTS', 'line': 14.5, 'direction': 'UNDER', 'actual': 12, 'result': 'WON', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Cayden Vasko', 'stat': 'REB', 'line': 4.5, 'direction': 'UNDER', 'actual': 2, 'result': 'WON', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Dylan Faulkner', 'stat': 'REB', 'line': 7.5, 'direction': 'UNDER', 'actual': 4, 'result': 'WON', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Kahmare Holmes', 'stat': 'REB', 'line': 5.5, 'direction': 'OVER', 'actual': 4, 'result': 'LOST', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Nils Machowski', 'stat': 'REB', 'line': 4.5, 'direction': 'OVER', 'actual': 4, 'result': 'LOST', 'league': 'CBB', 'date': '2026-01-29'},
    {'player': 'Madison Keys', 'stat': 'Total Games', 'line': 20.5, 'direction': 'OVER', 'actual': 19, 'result': 'LOST', 'league': 'Tennis', 'date': '2026-01-29'},
    {'player': 'Paula Badosa', 'stat': 'Aces', 'line': 3.5, 'direction': 'OVER', 'actual': 4, 'result': 'WON', 'league': 'Tennis', 'date': '2026-01-29'},
    {'player': 'Amen Thompson', 'stat': 'PRA', 'line': 24.5, 'direction': 'OVER', 'actual': 32, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Clint Capela', 'stat': 'PRA', 'line': 8.5, 'direction': 'UNDER', 'actual': 8, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': "De'Aaron Fox", 'stat': 'AST', 'line': 3.5, 'direction': 'OVER', 'actual': 5, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Kevin Durant', 'stat': 'PTS', 'line': 24.5, 'direction': 'OVER', 'actual': 18, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Tari Eason', 'stat': 'PRA', 'line': 15.5, 'direction': 'OVER', 'actual': 13, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Anfernee Simons', 'stat': 'PTS', 'line': 13.5, 'direction': 'OVER', 'actual': 9, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jaylen Brown', 'stat': 'PTS', 'line': 24.5, 'direction': 'OVER', 'actual': 30, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Neemias Queta', 'stat': 'PTS', 'line': 8.5, 'direction': 'OVER', 'actual': 17, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'CJ McCollum', 'stat': 'PTS', 'line': 16.5, 'direction': 'OVER', 'actual': 15, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Ausar Thompson', 'stat': 'PTS', 'line': 10.5, 'direction': 'UNDER', 'actual': 12, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Yves Missi', 'stat': 'PTS', 'line': 4.5, 'direction': 'OVER', 'actual': 4, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'AJ Green', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 6, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Corey Kispert', 'stat': '3PM', 'line': 0.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Kyle Kuzma', 'stat': '3PM', 'line': 0.5, 'direction': 'OVER', 'actual': 1, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Bobby Portis', 'stat': 'PTS', 'line': 11.5, 'direction': 'OVER', 'actual': 19, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'CJ McCollum', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Duncan Robinson', 'stat': 'PTS', 'line': 10.5, 'direction': 'OVER', 'actual': 15, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Bam Adebayo', 'stat': 'AST', 'line': 3.5, 'direction': 'OVER', 'actual': 3, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Al Horford', 'stat': 'PRA', 'line': 9.5, 'direction': 'OVER', 'actual': 20, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Bam Adebayo', 'stat': 'REB+AST', 'line': 11.5, 'direction': 'OVER', 'actual': 15, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jimmy Butler', 'stat': 'PTS', 'line': 19.5, 'direction': 'OVER', 'actual': 17, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Norman Powell', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jalen Johnson', 'stat': 'AST', 'line': 7.5, 'direction': 'UNDER', 'actual': 6, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Kevin Porter', 'stat': 'PRA', 'line': 28.5, 'direction': 'UNDER', 'actual': 22, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Nickeil Alexander-Walker', 'stat': 'PTS', 'line': 19.5, 'direction': 'OVER', 'actual': 32, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-29'},
    {'player': 'Jaylen Brown', 'stat': '3PM', 'line': 1.0, 'direction': 'OVER', 'actual': 1, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Jaden McDaniels', 'stat': 'PTS+AST', 'line': 16.5, 'direction': 'OVER', 'actual': 17, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Matas Buzelis', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Marcus Smart', 'stat': 'PTS', 'line': 9.5, 'direction': 'OVER', 'actual': 12, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Amen Thompson', 'stat': 'PTS+AST', 'line': 23.5, 'direction': 'UNDER', 'actual': 22, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Rudy Gobert', 'stat': 'REB', 'line': 11.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Alperen Sengun', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'UNDER', 'actual': 39, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Domantas Sabonis', 'stat': 'PRA', 'line': 31.5, 'direction': 'UNDER', 'actual': 30, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Kyle Kuzma', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 8, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Ryan Rollins', 'stat': 'PRA', 'line': 32.5, 'direction': 'UNDER', 'actual': 36, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Aaron Wiggins', 'stat': 'REB', 'line': 3.5, 'direction': 'OVER', 'actual': 5, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Jaden Ivey', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 2, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Kelly Oubre Jr.', 'stat': 'REB', 'line': 5.5, 'direction': 'UNDER', 'actual': 4, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Bobby Portis', 'stat': 'REB', 'line': 8.5, 'direction': 'UNDER', 'actual': 12, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Tobias Harris', 'stat': '3PM', 'line': 1.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Duncan Robinson', 'stat': '3PM', 'line': 2.5, 'direction': 'OVER', 'actual': 0, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Isaiah Collier', 'stat': 'PTS', 'line': 13.5, 'direction': 'UNDER', 'actual': 12, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Isaiah Stewart', 'stat': 'PTS', 'line': 7.5, 'direction': 'UNDER', 'actual': 7, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Jonas Valanciunas', 'stat': 'PTS', 'line': 12.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Kyle Filipowski', 'stat': 'PTS+AST', 'line': 15.5, 'direction': 'UNDER', 'actual': 10, 'result': 'WON', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Kris Dunn', 'stat': 'PTS+AST', 'line': 9.5, 'direction': 'UNDER', 'actual': 16, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Lauri Markkanen', 'stat': 'PTS+AST', 'line': 25.5, 'direction': 'OVER', 'actual': 23, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Jonas Valanciunas', 'stat': 'AST+REB', 'line': 10.5, 'direction': 'UNDER', 'actual': 17, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
    {'player': 'Jeremiah Fears', 'stat': 'REB', 'line': 2.5, 'direction': 'OVER', 'actual': 2, 'result': 'LOST', 'league': 'NBA', 'date': '2026-01-28'},
]

print(f'Total results to add: {len(results)}')

# Load existing calibration
cal_file = Path('calibration_history.csv')
existing_rows = []
existing_ids = set()

fieldnames = ['pick_id', 'game_date', 'player', 'team', 'opponent', 'stat', 'line', 
              'direction', 'probability', 'tier', 'actual_value', 'outcome', 'added_utc', 'league', 'source']

if cal_file.exists():
    with open(cal_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_rows.append(row)
            existing_ids.add(row.get('pick_id', ''))
    print(f'Existing calibration records: {len(existing_rows)}')

# Add new results
added = 0
for r in results:
    # Create unique pick_id
    player_clean = r['player'].replace(' ', '_').replace("'", "").lower()
    pick_id = f"{r['date'].replace('-', '')}_{player_clean}_{r['stat'].lower().replace('+', '_')}_{r['direction'].lower()}"
    
    if pick_id in existing_ids:
        continue
    
    outcome = 'HIT' if r['result'] == 'WON' else 'MISS'
    
    new_row = {
        'pick_id': pick_id,
        'game_date': r['date'],
        'player': r['player'],
        'team': '',
        'opponent': '',
        'stat': r['stat'],
        'line': r['line'],
        'direction': r['direction'],
        'probability': '',  # User picks, no system probability
        'tier': 'USER',  # Mark as user picks
        'actual_value': r['actual'],
        'outcome': outcome,
        'added_utc': datetime.utcnow().isoformat(),
        'league': r['league'],
        'source': 'user_results_jan28-29'
    }
    
    existing_rows.append(new_row)
    existing_ids.add(pick_id)
    added += 1

print(f'Added {added} new records')

# Write back
with open(cal_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(existing_rows)

print(f'✅ Calibration history updated: {len(existing_rows)} total records')

# Summary stats
resolved = [r for r in existing_rows if r.get('outcome') in ('HIT', 'MISS')]
hits = [r for r in resolved if r.get('outcome') == 'HIT']
print(f'\n📊 CALIBRATION SUMMARY:')
print(f'   Resolved picks: {len(resolved)}')
if resolved:
    print(f'   Hit rate: {len(hits)}/{len(resolved)} ({len(hits)/len(resolved)*100:.1f}%)')
else:
    print('   No resolved picks')

# Breakdown by league
print(f'\n📈 BY LEAGUE:')
leagues = {}
for r in resolved:
    league = r.get('league', 'unknown')
    if league not in leagues:
        leagues[league] = {'hits': 0, 'total': 0}
    leagues[league]['total'] += 1
    if r.get('outcome') == 'HIT':
        leagues[league]['hits'] += 1

for league, stats in sorted(leagues.items()):
    pct = stats['hits'] / stats['total'] * 100 if stats['total'] > 0 else 0
    print(f'   {league}: {stats["hits"]}/{stats["total"]} ({pct:.1f}%)')
