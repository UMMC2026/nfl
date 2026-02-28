#!/usr/bin/env python3
"""Convert Wednesday's Underdog slate to JSON format"""

import json

# Parse the pasted slate
slate_text = """
Sam Merrill CLE - G @ PHI Wed 6:10pm 12 Points More
Peyton Watson DEN - G @ DAL Wed 8:40pm 30 PRA More
Tyrese Maxey PHI - G vs CLE Wed 6:10pm 27.5 Points More
Trey Murphy NOP - F vs BKN Wed 7:10pm 29 PRA More
VJ Edgecombe PHI - G vs CLE Wed 6:10pm 5.5 Assists More
Donovan Mitchell CLE - G @ PHI Wed 6:10pm 19.5 Points More
Brandon Ingram TOR - F @ IND Wed 6:10pm 7.5 Rebounds More
Peyton Watson DEN - G @ DAL Wed 8:40pm 3.5 Assists More
Joel Embiid PHI - C-F vs CLE Wed 6:10pm 19.5 Points More
Michael Porter BKN - F @ NOP Wed 7:10pm 26.5 Points More
Andrew Nembhard IND - G-F vs TOR Wed 6:10pm 3.5 Rebounds More
Jalen Brunson NYK - G @ SAC Wed 9:10pm 24.5 Points More
Michael Porter BKN - F @ NOP Wed 7:10pm 37.5 PRA More
Sam Merrill CLE - G @ PHI Wed 6:10pm 17 PRA More
Trey Murphy NOP - F vs BKN Wed 7:10pm 19.5 Points More
"""

# Identify games
games = [
    {"away": "CLE", "home": "PHI", "time": "Wed 6:10pm"},
    {"away": "DEN", "home": "DAL", "time": "Wed 8:40pm"},
    {"away": "BKN", "home": "NOP", "time": "Wed 7:10pm"},
    {"away": "TOR", "home": "IND", "time": "Wed 6:10pm"},
    {"away": "NYK", "home": "SAC", "time": "Wed 9:10pm"},
]

# Parse props
plays = []

lines = [
    ("Sam Merrill", "CLE", "points", 12.0, "higher"),
    ("Peyton Watson", "DEN", "pra", 30.0, "higher"),
    ("Tyrese Maxey", "PHI", "points", 27.5, "higher"),
    ("Trey Murphy", "NOP", "pra", 29.0, "higher"),
    ("VJ Edgecombe", "PHI", "assists", 5.5, "higher"),
    ("Donovan Mitchell", "CLE", "points", 19.5, "higher"),
    ("Brandon Ingram", "TOR", "rebounds", 7.5, "higher"),
    ("Peyton Watson", "DEN", "assists", 3.5, "higher"),
    ("Joel Embiid", "PHI", "points", 19.5, "higher"),
    ("Michael Porter", "BKN", "points", 26.5, "higher"),
    ("Andrew Nembhard", "IND", "rebounds", 3.5, "higher"),
    ("Jalen Brunson", "NYK", "points", 24.5, "higher"),
    ("Michael Porter", "BKN", "pra", 37.5, "higher"),
    ("Sam Merrill", "CLE", "pra", 17.0, "higher"),
    ("Trey Murphy", "NOP", "points", 19.5, "higher"),
]

for player, team, stat, line, direction in lines:
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

# Save to file
with open('nba_wed_slate.json', 'w', encoding='utf-8') as f:
    json.dump(slate, indent=2, fp=f)

print(f"✅ Converted {len(plays)} props from {len(games)} games")
print(f"📄 Saved to: nba_wed_slate.json")

# Display summary
print(f"\n📋 GAMES:")
for game in games:
    print(f"   {game['away']} @ {game['home']} ({game['time']})")

print(f"\n📊 PROPS BREAKDOWN:")
stats = {}
for play in plays:
    stat = play['stat']
    stats[stat] = stats.get(stat, 0) + 1
print(f"   Points: {stats.get('points', 0)}")
print(f"   PRA: {stats.get('pra', 0)}")
print(f"   Assists: {stats.get('assists', 0)}")
print(f"   Rebounds: {stats.get('rebounds', 0)}")
