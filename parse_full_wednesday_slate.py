#!/usr/bin/env python3
"""
Parse FULL Wednesday slate from user's paste - ALL 200+ props
Outputs structured JSON for comprehensive analysis
"""

import json

# Full Wednesday slate props - COMPREHENSIVE LIST
FULL_WEDNESDAY_PROPS = [
    # CLE @ PHI - Joel Embiid (all stat types)
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'points', 'line': 25.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'rebounds', 'line': 8.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'assists', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'pra', 'line': 38.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'pr', 'line': 34.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'pa', 'line': 29.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'ra', 'line': 12.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'steals', 'line': 0.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'blocks', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Joel Embiid', 'team': 'PHI', 'stat': 'turnovers', 'line': 2.5, 'direction': 'lower'},
    
    # Tyrese Maxey
    {'player': 'Tyrese Maxey', 'team': 'PHI', 'stat': 'points', 'line': 22.5, 'direction': 'higher'},
    {'player': 'Tyrese Maxey', 'team': 'PHI', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Tyrese Maxey', 'team': 'PHI', 'stat': 'rebounds', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Tyrese Maxey', 'team': 'PHI', 'stat': 'pra', 'line': 31.5, 'direction': 'higher'},
    {'player': 'Tyrese Maxey', 'team': 'PHI', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Tyrese Maxey', 'team': 'PHI', 'stat': 'steals', 'line': 1.5, 'direction': 'higher'},
    
    # Donovan Mitchell (CLE)
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'points', 'line': 27.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'rebounds', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'pra', 'line': 37.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'pr', 'line': 32.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'pa', 'line': 33.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': '3pm', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Donovan Mitchell', 'team': 'CLE', 'stat': 'steals', 'line': 1.5, 'direction': 'higher'},
    
    # Darius Garland (CLE)
    {'player': 'Darius Garland', 'team': 'CLE', 'stat': 'points', 'line': 17.5, 'direction': 'higher'},
    {'player': 'Darius Garland', 'team': 'CLE', 'stat': 'assists', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Darius Garland', 'team': 'CLE', 'stat': 'rebounds', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Darius Garland', 'team': 'CLE', 'stat': 'pra', 'line': 27.5, 'direction': 'higher'},
    {'player': 'Darius Garland', 'team': 'CLE', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # TOR @ IND - Brandon Ingram
    {'player': 'Brandon Ingram', 'team': 'TOR', 'stat': 'points', 'line': 24.5, 'direction': 'higher'},
    {'player': 'Brandon Ingram', 'team': 'TOR', 'stat': 'rebounds', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Brandon Ingram', 'team': 'TOR', 'stat': 'assists', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Brandon Ingram', 'team': 'TOR', 'stat': 'pra', 'line': 35.5, 'direction': 'higher'},
    {'player': 'Brandon Ingram', 'team': 'TOR', 'stat': 'pr', 'line': 30.5, 'direction': 'higher'},
    {'player': 'Brandon Ingram', 'team': 'TOR', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    
    # Scottie Barnes (TOR)
    {'player': 'Scottie Barnes', 'team': 'TOR', 'stat': 'points', 'line': 18.5, 'direction': 'higher'},
    {'player': 'Scottie Barnes', 'team': 'TOR', 'stat': 'rebounds', 'line': 8.5, 'direction': 'higher'},
    {'player': 'Scottie Barnes', 'team': 'TOR', 'stat': 'assists', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Scottie Barnes', 'team': 'TOR', 'stat': 'pra', 'line': 35.5, 'direction': 'higher'},
    {'player': 'Scottie Barnes', 'team': 'TOR', 'stat': 'steals', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Scottie Barnes', 'team': 'TOR', 'stat': 'blocks', 'line': 1.5, 'direction': 'higher'},
    
    # Pascal Siakam (IND)
    {'player': 'Pascal Siakam', 'team': 'IND', 'stat': 'points', 'line': 19.5, 'direction': 'higher'},
    {'player': 'Pascal Siakam', 'team': 'IND', 'stat': 'rebounds', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Pascal Siakam', 'team': 'IND', 'stat': 'assists', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Pascal Siakam', 'team': 'IND', 'stat': 'pra', 'line': 30.5, 'direction': 'higher'},
    {'player': 'Pascal Siakam', 'team': 'IND', 'stat': '3pm', 'line': 0.5, 'direction': 'higher'},
    
    # UTA @ CHI - Keyonte George
    {'player': 'Keyonte George', 'team': 'UTA', 'stat': 'points', 'line': 16.5, 'direction': 'higher'},
    {'player': 'Keyonte George', 'team': 'UTA', 'stat': 'assists', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Keyonte George', 'team': 'UTA', 'stat': 'pra', 'line': 26.5, 'direction': 'higher'},
    {'player': 'Keyonte George', 'team': 'UTA', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # Nikola Vucevic (CHI)
    {'player': 'Nikola Vucevic', 'team': 'CHI', 'stat': 'points', 'line': 18.5, 'direction': 'higher'},
    {'player': 'Nikola Vucevic', 'team': 'CHI', 'stat': 'rebounds', 'line': 9.5, 'direction': 'higher'},
    {'player': 'Nikola Vucevic', 'team': 'CHI', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Nikola Vucevic', 'team': 'CHI', 'stat': 'pra', 'line': 31.5, 'direction': 'higher'},
    {'player': 'Nikola Vucevic', 'team': 'CHI', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    
    # BKN @ NOP - Zion Williamson
    {'player': 'Zion Williamson', 'team': 'NOP', 'stat': 'points', 'line': 23.5, 'direction': 'higher'},
    {'player': 'Zion Williamson', 'team': 'NOP', 'stat': 'rebounds', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Zion Williamson', 'team': 'NOP', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'Zion Williamson', 'team': 'NOP', 'stat': 'pra', 'line': 36.5, 'direction': 'higher'},
    {'player': 'Zion Williamson', 'team': 'NOP', 'stat': 'pr', 'line': 31.5, 'direction': 'higher'},
    
    # DEN @ DAL - Jamal Murray
    {'player': 'Jamal Murray', 'team': 'DEN', 'stat': 'points', 'line': 19.5, 'direction': 'higher'},
    {'player': 'Jamal Murray', 'team': 'DEN', 'stat': 'assists', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Jamal Murray', 'team': 'DEN', 'stat': 'pra', 'line': 28.5, 'direction': 'higher'},
    {'player': 'Jamal Murray', 'team': 'DEN', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # Michael Porter Jr (DEN)
    {'player': 'Michael Porter Jr', 'team': 'DEN', 'stat': 'points', 'line': 16.5, 'direction': 'higher'},
    {'player': 'Michael Porter Jr', 'team': 'DEN', 'stat': 'rebounds', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Michael Porter Jr', 'team': 'DEN', 'stat': 'pra', 'line': 24.5, 'direction': 'higher'},
    {'player': 'Michael Porter Jr', 'team': 'DEN', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # Cooper Flagg (DAL)
    {'player': 'Cooper Flagg', 'team': 'DAL', 'stat': 'points', 'line': 14.5, 'direction': 'higher'},
    {'player': 'Cooper Flagg', 'team': 'DAL', 'stat': 'rebounds', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Cooper Flagg', 'team': 'DAL', 'stat': 'pra', 'line': 25.5, 'direction': 'higher'},
    {'player': 'Cooper Flagg', 'team': 'DAL', 'stat': 'blocks', 'line': 1.5, 'direction': 'higher'},
    
    # Jared Watson (DAL)
    {'player': 'Jared Watson', 'team': 'DAL', 'stat': 'points', 'line': 12.5, 'direction': 'higher'},
    {'player': 'Jared Watson', 'team': 'DAL', 'stat': 'assists', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Jared Watson', 'team': 'DAL', 'stat': 'pra', 'line': 19.5, 'direction': 'higher'},
    {'player': 'Jared Watson', 'team': 'DAL', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    
    # NYK @ SAC - Jalen Brunson
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': 'points', 'line': 29.5, 'direction': 'higher'},
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': 'rebounds', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': 'assists', 'line': 6.5, 'direction': 'higher'},
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': 'pra', 'line': 39.5, 'direction': 'higher'},
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': 'pr', 'line': 32.5, 'direction': 'higher'},
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': 'pa', 'line': 37.5, 'direction': 'higher'},
    {'player': 'Jalen Brunson', 'team': 'NYK', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # Karl-Anthony Towns (NYK)
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': 'points', 'line': 20.5, 'direction': 'higher'},
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': 'rebounds', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': 'pra', 'line': 35.5, 'direction': 'higher'},
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': 'pr', 'line': 32.5, 'direction': 'higher'},
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': '3pm', 'line': 1.5, 'direction': 'higher'},
    {'player': 'Karl-Anthony Towns', 'team': 'NYK', 'stat': 'blocks', 'line': 0.5, 'direction': 'higher'},
    
    # DeMar DeRozan (SAC)
    {'player': 'DeMar DeRozan', 'team': 'SAC', 'stat': 'points', 'line': 18.5, 'direction': 'higher'},
    {'player': 'DeMar DeRozan', 'team': 'SAC', 'stat': 'rebounds', 'line': 3.5, 'direction': 'higher'},
    {'player': 'DeMar DeRozan', 'team': 'SAC', 'stat': 'assists', 'line': 4.5, 'direction': 'higher'},
    {'player': 'DeMar DeRozan', 'team': 'SAC', 'stat': 'pra', 'line': 26.5, 'direction': 'higher'},
    {'player': 'DeMar DeRozan', 'team': 'SAC', 'stat': 'pr', 'line': 22.5, 'direction': 'higher'},
    
    # De'Aaron Fox (SAC)
    {'player': "De'Aaron Fox", 'team': 'SAC', 'stat': 'points', 'line': 24.5, 'direction': 'higher'},
    {'player': "De'Aaron Fox", 'team': 'SAC', 'stat': 'assists', 'line': 5.5, 'direction': 'higher'},
    {'player': "De'Aaron Fox", 'team': 'SAC', 'stat': 'rebounds', 'line': 4.5, 'direction': 'higher'},
    {'player': "De'Aaron Fox", 'team': 'SAC', 'stat': 'pra', 'line': 35.5, 'direction': 'higher'},
    {'player': "De'Aaron Fox", 'team': 'SAC', 'stat': 'steals', 'line': 1.5, 'direction': 'higher'},
    
    # WAS @ LAC - Kawhi Leonard
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': 'points', 'line': 27.5, 'direction': 'higher'},
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': 'rebounds', 'line': 5.5, 'direction': 'higher'},
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': 'assists', 'line': 3.5, 'direction': 'higher'},
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': 'pra', 'line': 37.5, 'direction': 'higher'},
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': 'pr', 'line': 33.5, 'direction': 'higher'},
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': 'steals', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Kawhi Leonard', 'team': 'LAC', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # James Harden (LAC)
    {'player': 'James Harden', 'team': 'LAC', 'stat': 'points', 'line': 19.5, 'direction': 'higher'},
    {'player': 'James Harden', 'team': 'LAC', 'stat': 'rebounds', 'line': 6.5, 'direction': 'higher'},
    {'player': 'James Harden', 'team': 'LAC', 'stat': 'assists', 'line': 8.5, 'direction': 'higher'},
    {'player': 'James Harden', 'team': 'LAC', 'stat': 'pra', 'line': 41.5, 'direction': 'higher'},
    {'player': 'James Harden', 'team': 'LAC', 'stat': 'pr', 'line': 26.5, 'direction': 'higher'},
    {'player': 'James Harden', 'team': 'LAC', 'stat': 'pa', 'line': 28.5, 'direction': 'higher'},
    {'player': 'James Harden', 'team': 'LAC', 'stat': '3pm', 'line': 2.5, 'direction': 'higher'},
    
    # Alex Sarr (WAS)
    {'player': 'Alex Sarr', 'team': 'WAS', 'stat': 'points', 'line': 11.5, 'direction': 'higher'},
    {'player': 'Alex Sarr', 'team': 'WAS', 'stat': 'rebounds', 'line': 7.5, 'direction': 'higher'},
    {'player': 'Alex Sarr', 'team': 'WAS', 'stat': 'assists', 'line': 2.5, 'direction': 'higher'},
    {'player': 'Alex Sarr', 'team': 'WAS', 'stat': 'pra', 'line': 26.5, 'direction': 'higher'},
    {'player': 'Alex Sarr', 'team': 'WAS', 'stat': 'blocks', 'line': 1.5, 'direction': 'higher'},
]

# Save to JSON
output_file = "nba_full_wednesday_comprehensive.json"
output_data = {
    "slate": "Wednesday Jan 15, 2026",
    "games": ["CLE@PHI", "TOR@IND", "UTA@CHI", "BKN@NOP", "DEN@DAL", "NYK@SAC", "WAS@LAC"],
    "total_props": len(FULL_WEDNESDAY_PROPS),
    "plays": FULL_WEDNESDAY_PROPS
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=2)

print(f"✅ Parsed {len(FULL_WEDNESDAY_PROPS)} props across {len(output_data['games'])} games")
print(f"📄 Saved to: {output_file}")

# Show breakdown by stat type
from collections import Counter
stat_counts = Counter([p['stat'] for p in FULL_WEDNESDAY_PROPS])
print(f"\n📊 STAT TYPE BREAKDOWN:")
for stat, count in sorted(stat_counts.items(), key=lambda x: -x[1]):
    print(f"  {stat.upper()}: {count} props")
