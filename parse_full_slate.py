#!/usr/bin/env python3
"""Parse full Wednesday NBA slate and run comprehensive analysis"""

import json

# Core props from the full slate (focusing on main players and core stats)
props = [
    # CLE @ PHI
    ("Joel Embiid", "PHI", "points", 25.5, "higher"),
    ("Joel Embiid", "PHI", "rebounds", 8.5, "higher"),
    ("Joel Embiid", "PHI", "assists", 3.5, "higher"),
    ("Donovan Mitchell", "CLE", "points", 27.5, "higher"),
    ("Donovan Mitchell", "CLE", "rebounds", 4.5, "higher"),
    ("Donovan Mitchell", "CLE", "assists", 5.5, "higher"),
    ("Tyrese Maxey", "PHI", "points", 27.5, "higher"),
    ("Tyrese Maxey", "PHI", "rebounds", 4.5, "higher"),
    ("Tyrese Maxey", "PHI", "assists", 6.5, "higher"),
    ("Paul George", "PHI", "points", 15.5, "higher"),
    ("Paul George", "PHI", "rebounds", 5.5, "higher"),
    ("Paul George", "PHI", "assists", 3.5, "higher"),
    ("Evan Mobley", "CLE", "points", 17.5, "higher"),
    ("Evan Mobley", "CLE", "rebounds", 8.5, "higher"),
    ("Evan Mobley", "CLE", "assists", 3.5, "higher"),
    ("Darius Garland", "CLE", "points", 17.5, "higher"),
    ("Darius Garland", "CLE", "assists", 6.5, "higher"),
    ("Jarrett Allen", "CLE", "points", 12.5, "higher"),
    ("Jarrett Allen", "CLE", "rebounds", 9.5, "higher"),
    ("Sam Merrill", "CLE", "points", 12.5, "higher"),
    
    # TOR @ IND
    ("Brandon Ingram", "TOR", "points", 24.5, "higher"),
    ("Brandon Ingram", "TOR", "rebounds", 6.5, "higher"),
    ("Brandon Ingram", "TOR", "assists", 3.5, "higher"),
    ("Pascal Siakam", "IND", "points", 23.5, "higher"),
    ("Pascal Siakam", "IND", "rebounds", 7.5, "higher"),
    ("Pascal Siakam", "IND", "assists", 3.5, "higher"),
    ("Scottie Barnes", "TOR", "points", 20.5, "higher"),
    ("Scottie Barnes", "TOR", "rebounds", 8.5, "higher"),
    ("Scottie Barnes", "TOR", "assists", 5.5, "higher"),
    ("Andrew Nembhard", "IND", "points", 17.5, "higher"),
    ("Andrew Nembhard", "IND", "assists", 7.5, "higher"),
    
    # UTA @ CHI
    ("Nikola Vucevic", "CHI", "points", 17.5, "higher"),
    ("Nikola Vucevic", "CHI", "rebounds", 9.5, "higher"),
    ("Nikola Vucevic", "CHI", "assists", 3.5, "higher"),
    ("Keyonte George", "UTA", "points", 26.5, "higher"),
    ("Keyonte George", "UTA", "assists", 6.5, "higher"),
    ("Coby White", "CHI", "points", 20.5, "higher"),
    ("Coby White", "CHI", "assists", 4.5, "higher"),
    
    # BKN @ NOP
    ("Zion Williamson", "NOP", "points", 22.5, "higher"),
    ("Zion Williamson", "NOP", "rebounds", 5.5, "higher"),
    ("Zion Williamson", "NOP", "assists", 3.5, "higher"),
    ("Michael Porter Jr.", "BKN", "points", 26.5, "higher"),
    ("Michael Porter Jr.", "BKN", "rebounds", 7.5, "higher"),
    ("Michael Porter Jr.", "BKN", "assists", 3.5, "higher"),
    ("Trey Murphy III", "NOP", "points", 21.5, "higher"),
    ("Trey Murphy III", "NOP", "rebounds", 5.5, "higher"),
    ("Cam Thomas", "BKN", "points", 16.5, "higher"),
    ("Nic Claxton", "BKN", "points", 13.5, "higher"),
    ("Nic Claxton", "BKN", "rebounds", 7.5, "higher"),
    
    # DEN @ DAL
    ("Jamal Murray", "DEN", "points", 26.5, "higher"),
    ("Jamal Murray", "DEN", "rebounds", 4.5, "higher"),
    ("Jamal Murray", "DEN", "assists", 8.5, "higher"),
    ("Cooper Flagg", "DAL", "points", 22.5, "higher"),
    ("Cooper Flagg", "DAL", "rebounds", 6.5, "higher"),
    ("Cooper Flagg", "DAL", "assists", 4.5, "higher"),
    ("Peyton Watson", "DEN", "points", 20.5, "higher"),
    ("Peyton Watson", "DEN", "rebounds", 6.5, "higher"),
    ("Peyton Watson", "DEN", "assists", 2.5, "higher"),
    ("Aaron Gordon", "DEN", "points", 18.5, "higher"),
    ("Aaron Gordon", "DEN", "rebounds", 6.5, "higher"),
    
    # NYK @ SAC
    ("Jalen Brunson", "NYK", "points", 29.5, "higher"),
    ("Jalen Brunson", "NYK", "rebounds", 3.5, "higher"),
    ("Jalen Brunson", "NYK", "assists", 6.5, "higher"),
    ("Karl-Anthony Towns", "NYK", "points", 20.5, "higher"),
    ("Karl-Anthony Towns", "NYK", "rebounds", 11.5, "higher"),
    ("DeMar DeRozan", "SAC", "points", 19.5, "higher"),
    ("DeMar DeRozan", "SAC", "assists", 4.5, "higher"),
    ("Russell Westbrook", "SAC", "points", 15.5, "higher"),
    ("Russell Westbrook", "SAC", "rebounds", 5.5, "higher"),
    ("Russell Westbrook", "SAC", "assists", 6.5, "higher"),
    ("Zach LaVine", "SAC", "points", 20.5, "higher"),
    
    # WAS @ LAC
    ("Kawhi Leonard", "LAC", "points", 27.5, "higher"),
    ("Kawhi Leonard", "LAC", "rebounds", 5.5, "higher"),
    ("Kawhi Leonard", "LAC", "assists", 3.5, "higher"),
    ("James Harden", "LAC", "points", 27.5, "higher"),
    ("James Harden", "LAC", "rebounds", 5.5, "higher"),
    ("James Harden", "LAC", "assists", 8.5, "higher"),
    ("Alex Sarr", "WAS", "points", 16.5, "higher"),
    ("Alex Sarr", "WAS", "rebounds", 7.5, "higher"),
]

# Create slate JSON
games = [
    {"away": "CLE", "home": "PHI", "time": "6:00PM CST"},
    {"away": "TOR", "home": "IND", "time": "6:00PM CST"},
    {"away": "UTA", "home": "CHI", "time": "7:00PM CST"},
    {"away": "BKN", "home": "NOP", "time": "7:00PM CST"},
    {"away": "DEN", "home": "DAL", "time": "8:30PM CST"},
    {"away": "NYK", "home": "SAC", "time": "9:00PM CST"},
    {"away": "WAS", "home": "LAC", "time": "9:30PM CST"},
]

plays = []
for player, team, stat, line, direction in props:
    plays.append({
        "player": player,
        "team": team,
        "stat": stat,
        "line": line,
        "direction": direction
    })

slate = {
    "date": "2026-01-14",
    "games": games,
    "plays": plays
}

with open('nba_full_slate.json', 'w', encoding='utf-8') as f:
    json.dump(slate, indent=2, fp=f)

print(f"✅ Created full slate with {len(plays)} props from {len(games)} games")
print(f"📄 Saved to: nba_full_slate.json")
