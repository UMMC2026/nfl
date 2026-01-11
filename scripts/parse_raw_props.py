"""
Parse raw sportsbook UI text into normalized CSV
Handles pasted Underdog Fantasy slate format
"""
import re
import csv
from datetime import datetime
from pathlib import Path

# Configuration
DATE = "2026-01-07"
RAW_FILE = Path(f"data/raw/raw_props_{DATE}.txt")
OUT_FILE = Path(f"data/raw/raw_props_{DATE}.csv")
SNAPSHOT_TIME = datetime.now().strftime("%H:%M")

# Patterns
GAME_RE = re.compile(r"([A-Z]{2,4})\s+@\s+([A-Z]{2,4})")
STAT_RE = re.compile(r"([\d.]+)\s+(Points?|Rebounds?|Assists?|Pts \+ Rebs \+ Asts|3-Pointers? Made|Steals?|Blocks?|Turnovers?)", re.I)
DIRECTION_RE = re.compile(r"(Higher|Lower)", re.I)

# Core stats only (filter noise)
CORE_STATS = {
    "points", "point", 
    "rebounds", "rebound",
    "assists", "assist",
    "pts + rebs + asts"
}

rows = []
current_game = None
current_player = None
line_buffer = []

def normalize_stat(stat):
    """Normalize stat names to canonical form"""
    stat_lower = stat.lower()
    if "pts + rebs + asts" in stat_lower or "pra" in stat_lower:
        return "pts+reb+ast"
    elif "point" in stat_lower:
        return "points"
    elif "rebound" in stat_lower:
        return "rebounds"
    elif "assist" in stat_lower:
        return "assists"
    elif "3-pointer" in stat_lower or "3pm" in stat_lower:
        return "3pm"
    return stat_lower

def is_core_stat(stat):
    """Check if stat is in core set"""
    stat_lower = stat.lower()
    return any(core in stat_lower for core in CORE_STATS)

print(f"📖 Reading: {RAW_FILE}")

if not RAW_FILE.exists():
    print(f"❌ File not found: {RAW_FILE}")
    print(f"   Create this file and paste raw sportsbook UI text into it")
    exit(1)

with RAW_FILE.open(encoding="utf-8") as f:
    lines = f.readlines()

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # Detect game header (e.g., "DEN @ BOS")
    game_match = GAME_RE.search(line)
    if game_match:
        current_game = f"{game_match.group(1)}@{game_match.group(2)}"
        continue
    
    # Detect player name (capitalized words, 2-4 words, no numbers)
    if (re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$", line) and 
        not any(char.isdigit() for char in line) and
        line not in ["Higher", "Lower", "More picks"]):
        current_player = line
        line_buffer = []
        continue
    
    # Detect stat line (e.g., "30.5 Points")
    stat_match = STAT_RE.search(line)
    if stat_match and current_game and current_player:
        value = float(stat_match.group(1))
        stat = stat_match.group(2)
        
        # Only process CORE stats
        if not is_core_stat(stat):
            continue
        
        # Look for direction on same line or next
        direction_match = DIRECTION_RE.search(line)
        if direction_match:
            direction = direction_match.group(1).capitalize()
        else:
            # Default to Lower (most common in dataset)
            direction = "Lower"
        
        # Extract team from game
        teams = current_game.split("@")
        # Simple heuristic: if away team, use teams[0], else teams[1]
        team = "UNK"  # Will be resolved in daily_pipeline
        opponent = "UNK"
        
        rows.append([
            DATE,
            current_game,
            current_player,
            team,
            opponent,
            normalize_stat(stat),
            value,
            direction,
            SNAPSHOT_TIME
        ])

print(f"📊 Parsed {len(rows)} core props")

# Write output
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "date",
        "game",
        "player",
        "team",
        "opponent",
        "stat",
        "line",
        "direction",
        "snapshot_time"
    ])
    writer.writerows(rows)

print(f"✅ Output: {OUT_FILE}")
print(f"   Total CORE props: {len(rows)}")
print(f"   Games: {len(set(r[1] for r in rows))}")
print(f"   Players: {len(set(r[2] for r in rows))}")
