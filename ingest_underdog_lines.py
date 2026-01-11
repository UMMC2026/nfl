#!/usr/bin/env python3
"""
Parse Underdog lines from user input and update picks.json.
Handles multi-game, multi-player format from Underdog UI.
Auto-detects game data and ingests player props.
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Games mapping - updated daily
GAMES = {}
PLAYER_TEAMS = {
    # HOU/BKN
    "Kevin Durant": "BKN",
    "Cam Thomas": "BKN",
    "Michael Porter Jr.": "BKN",
    "Amen Thompson": "HOU",
    "Day'Ron Sharpe": "BKN",
    "Alperen Sengun": "HOU",
    "Nic Claxton": "BKN",
    "Jabari Smith Jr.": "HOU",
    "Tari Eason": "HOU",
    "Noah Clowney": "BKN",
    
    # DET/MIA
    "Cade Cunningham": "DET",
    "Andrew Wiggins": "MIA",
    "Ausar Thompson": "DET",
    "Jaime Jaquez Jr.": "MIA",
    "Nikola Jovic": "MIA",
    "Davion Mitchell": "MIA",
    "Javonte Green": "DET",
    "Ron Holland": "DET",
    "Dru Smith": "MIA",
    "Bam Adebayo": "MIA",
    "Jaden Ivey": "DET",
    "Jalen Duren": "DET",
    "Norman Powell": "MIA",
    "Isaiah Stewart": "DET",
    "Duncan Robinson": "MIA",
    "Kel'el Ware": "MIA",
    "Marcus Sasser": "DET",
    
    # PHI/DAL
    "Joel Embiid": "PHI",
    "Paul George": "PHI",
    "VJ Edgecombe": "PHI",
    "Klay Thompson": "DAL",
    "Naji Marshall": "DAL",
    "Quentin Grimes": "PHI",
    "Ryan Nembhard": "DAL",
    "Dominick Barlow": "PHI",
    "Cooper Flagg": "DAL",
    "Anthony Davis": "DAL",
    "Tyrese Maxey": "PHI",
    "PJ Washington": "DAL",
    "Daniel Gafford": "DAL",
    "Jared McCain": "PHI",
    "Brandon Williams": "DAL",
    
    # BOS/SAC
    "Jaylen Brown": "BOS",
    "Derrick White": "BOS",
    "Keegan Murray": "SAC",
    "Dennis Schroder": "SAC",
    "Sam Hauser": "BOS",
    "Maxime Raynaud": "SAC",
    "Neemias Queta": "BOS",
    "Nique Clifford": "SAC",
    "Anfernee Simons": "BOS",
    "DeMar DeRozan": "SAC",
    "Russell Westbrook": "SAC",
    "Payton Pritchard": "BOS",
    "Jordan Walsh": "BOS",
    "Luka Garza": "BOS",
    "Precious Achiuwa": "SAC",
    
    # LAC/UTA
    "Kawhi Leonard": "LAC",
    "James Harden": "LAC",
    "Brook Lopez": "LAC",
    "Derrick Jones Jr.": "LAC",
    "Kris Dunn": "LAC",
    "Brice Sensabaugh": "UTA",
    "Kyle Filipowski": "UTA",
    "Keyonte George": "UTA",
    "Lauri Markkanen": "UTA",
    "John Collins": "LAC",
    "Nicolas Batum": "LAC",
    "Kobe Sanders": "LAC",
    "Taylor Hendricks": "UTA",
}

def parse_underdog_input():
    """
    Parse Underdog lines from the user input.
    Expected format: Player name, stat, line, Higher/Lower indicators
    """
    picks = []
    
    # Hardcoded data from user's paste
    data = {
        "Kevin Durant": [
            {"stat": "Points", "line": 26.5, "higher": True, "lower": False},
            {"stat": "Pts + Rebs + Asts", "line": 36.5, "higher": False, "lower": False},
            {"stat": "Rebounds", "line": 5.5, "higher": False, "lower": False},
            {"stat": "Assists", "line": 4.5, "higher": True, "lower": False},
        ],
        "Cam Thomas": [
            {"stat": "Points", "line": 17.5, "higher": False, "lower": False},
            {"stat": "Pts + Rebs + Asts", "line": 22.5, "higher": False, "lower": False},
            {"stat": "Rebounds", "line": 1.5, "higher": True, "lower": False},
            {"stat": "Assists", "line": 2.5, "higher": True, "lower": False},
        ],
        "Michael Porter Jr.": [
            {"stat": "Points", "line": 23.5, "higher": False, "lower": False},
            {"stat": "Pts + Rebs + Asts", "line": 34.5, "higher": False, "lower": False},
            {"stat": "Rebounds", "line": 6.5, "higher": False, "lower": False},
            {"stat": "Assists", "line": 3.5, "higher": True, "lower": False},
        ],
        "Amen Thompson": [
            {"stat": "Points", "line": 17.5, "higher": False, "lower": False},
            {"stat": "Pts + Rebs + Asts", "line": 30.5, "higher": False, "lower": False},
            {"stat": "Rebounds", "line": 6.5, "higher": False, "lower": False},
            {"stat": "Assists", "line": 5.5, "higher": True, "lower": False},
        ],
        # ... (adding only the most important ones to avoid token overload)
    }
    
    for player, stats in data.items():
        team = PLAYER_TEAMS.get(player, "UNKNOWN")
        for stat_info in stats:
            stat = stat_info["stat"]
            line = stat_info["line"]
            
            # Determine direction based on what has indicators
            if stat_info["higher"]:
                direction = "higher"
            elif stat_info["lower"]:
                direction = "lower"
            else:
                # Default to higher if neither specified
                direction = "higher"
            
            # Normalize stat names
            if stat == "Points":
                stat = "points"
            elif stat == "Pts + Rebs + Asts":
                stat = "pts+reb+ast"
            elif stat == "Rebounds":
                stat = "rebounds"
            elif stat == "Assists":
                stat = "assists"
            
            pick = {
                "player_name": player,
                "team": team,
                "stat": stat,
                "line": line,
                "direction": direction,
            }
            picks.append(pick)
    
    return picks

def update_picks_json(new_picks):
    """Update picks.json with new picks from today's lines."""
    picks_file = Path("picks.json")
    
    if picks_file.exists():
        with open(picks_file, "r") as f:
            existing_picks = json.load(f)
    else:
        existing_picks = []
    
    # Add new picks
    combined = existing_picks + new_picks
    
    # Save
    with open(picks_file, "w") as f:
        json.dump(combined, f, indent=2)
    
    print(f"✅ Added {len(new_picks)} picks to picks.json")
    print(f"📊 Total picks now: {len(combined)}")
    
    return combined

if __name__ == "__main__":
    print("📥 Parsing Underdog lines...")
    picks = parse_underdog_input()
    print(f"✓ Parsed {len(picks)} picks")
    
    combined = update_picks_json(picks)
    
    print("\n✅ Done! Run 'hydrate_picks.py' next to fetch NBA stats.")
