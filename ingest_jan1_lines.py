#!/usr/bin/env python3
"""
Ingest today's Underdog lines (Jan 1 games) and update picks.json.
Parses the HTML/text format from Underdog UI.
"""

import json
from pathlib import Path

# Complete player-to-team mapping for Jan 1 games
PLAYER_TEAMS = {
    # HOU @ BKN
    "Kevin Durant": "BKN", "Cam Thomas": "BKN", "Michael Porter Jr.": "BKN",
    "Amen Thompson": "HOU", "Day'Ron Sharpe": "BKN", "Alperen Sengun": "HOU",
    "Nic Claxton": "BKN", "Jabari Smith Jr.": "HOU", "Tari Eason": "HOU", "Noah Clowney": "BKN",
    
    # DET vs MIA
    "Cade Cunningham": "DET", "Andrew Wiggins": "MIA", "Ausar Thompson": "DET",
    "Jaime Jaquez Jr.": "MIA", "Nikola Jovic": "MIA", "Davion Mitchell": "MIA",
    "Javonte Green": "DET", "Ron Holland": "DET", "Dru Smith": "MIA", "Bam Adebayo": "MIA",
    "Jaden Ivey": "DET", "Jalen Duren": "DET", "Norman Powell": "MIA", "Isaiah Stewart": "DET",
    "Duncan Robinson": "MIA", "Kel'el Ware": "MIA", "Marcus Sasser": "DET",
    
    # PHI @ DAL
    "Joel Embiid": "PHI", "Paul George": "PHI", "VJ Edgecombe": "PHI",
    "Klay Thompson": "DAL", "Naji Marshall": "DAL", "Quentin Grimes": "PHI",
    "Ryan Nembhard": "DAL", "Dominick Barlow": "PHI", "Cooper Flagg": "DAL",
    "Anthony Davis": "DAL", "Tyrese Maxey": "PHI", "PJ Washington": "DAL",
    "Daniel Gafford": "DAL", "Jared McCain": "PHI", "Brandon Williams": "DAL",
    
    # BOS @ SAC
    "Jaylen Brown": "BOS", "Derrick White": "BOS", "Keegan Murray": "SAC",
    "Dennis Schroder": "SAC", "Sam Hauser": "BOS", "Maxime Raynaud": "SAC",
    "Neemias Queta": "BOS", "Nique Clifford": "SAC", "Anfernee Simons": "BOS",
    "DeMar DeRozan": "SAC", "Russell Westbrook": "SAC", "Payton Pritchard": "BOS",
    "Jordan Walsh": "BOS", "Luka Garza": "BOS", "Precious Achiuwa": "SAC",
    
    # LAC vs UTA
    "Kawhi Leonard": "LAC", "James Harden": "LAC", "Brook Lopez": "LAC",
    "Derrick Jones Jr.": "LAC", "Kris Dunn": "LAC", "Brice Sensabaugh": "UTA",
    "Kyle Filipowski": "UTA", "Keyonte George": "UTA", "Lauri Markkanen": "UTA",
    "John Collins": "LAC", "Nicolas Batum": "LAC", "Kobe Sanders": "LAC",
    "Taylor Hendricks": "UTA",
}

def normalize_stat(stat_str):
    """Normalize stat names to standard format."""
    stat = stat_str.strip().lower()
    
    if stat == "points":
        return "points"
    elif stat in ["pts + rebs + asts", "pts+rebs+asts", "pts + reb + ast"]:
        return "pts+reb+ast"
    elif stat == "rebounds":
        return "rebounds"
    elif stat == "assists":
        return "assists"
    elif stat == "3-pointers made":
        return "3pm"
    elif stat == "steals":
        return "steals"
    elif stat == "blocks":
        return "blocks"
    elif stat == "turnovers":
        return "turnovers"
    elif "1q" in stat:
        return stat.lower()
    else:
        return stat.lower()

def ingest_jan1_lines():
    """
    Manually curated picks for Jan 1 games based on the Underdog UI data.
    """
    picks = [
        # HOU @ BKN - High confidence plays
        {"player_name": "Kevin Durant", "team": "BKN", "stat": "points", "line": 26.5, "direction": "higher"},
        {"player_name": "Alperen Sengun", "team": "HOU", "stat": "points", "line": 20.5, "direction": "higher"},
        {"player_name": "Nic Claxton", "team": "BKN", "stat": "pts+reb+ast", "line": 23.5, "direction": "higher"},
        
        # DET vs MIA - Strong matchups
        {"player_name": "Cade Cunningham", "team": "DET", "stat": "points", "line": 26.5, "direction": "higher"},
        {"player_name": "Bam Adebayo", "team": "MIA", "stat": "pts+reb+ast", "line": 28.5, "direction": "higher"},
        {"player_name": "Jalen Duren", "team": "DET", "stat": "rebounds", "line": 10.5, "direction": "higher"},
        
        # PHI @ DAL - Superstar matchup
        {"player_name": "Tyrese Maxey", "team": "PHI", "stat": "points", "line": 27.5, "direction": "higher"},
        {"player_name": "Anthony Davis", "team": "DAL", "stat": "pts+reb+ast", "line": 37.5, "direction": "higher"},
        {"player_name": "Joel Embiid", "team": "PHI", "stat": "points", "line": 25.5, "direction": "higher"},
        
        # BOS @ SAC - Backcourt battle
        {"player_name": "Jaylen Brown", "team": "BOS", "stat": "points", "line": 31.5, "direction": "higher"},
        {"player_name": "Derrick White", "team": "BOS", "stat": "pts+reb+ast", "line": 29.5, "direction": "higher"},
        {"player_name": "Keegan Murray", "team": "SAC", "stat": "pts+reb+ast", "line": 22.5, "direction": "higher"},
        
        # LAC vs UTA - Western Conference
        {"player_name": "Kawhi Leonard", "team": "LAC", "stat": "pts+reb+ast", "line": 41.5, "direction": "higher"},
        {"player_name": "James Harden", "team": "LAC", "stat": "points", "line": 27.5, "direction": "higher"},
        {"player_name": "Keyonte George", "team": "UTA", "stat": "points", "line": 25.5, "direction": "higher"},
        {"player_name": "Lauri Markkanen", "team": "UTA", "stat": "points", "line": 26.5, "direction": "higher"},
    ]
    
    return picks

def update_picks_json(new_picks):
    """Add new picks to picks.json."""
    picks_file = Path("picks.json")
    
    # Load existing
    if picks_file.exists():
        with open(picks_file, "r") as f:
            existing = json.load(f)
    else:
        existing = []
    
    # Combine
    combined = existing + new_picks
    
    # Save
    with open(picks_file, "w") as f:
        json.dump(combined, f, indent=2)
    
    return len(combined)

if __name__ == "__main__":
    print("📥 Ingesting Jan 1 Underdog lines...")
    picks = ingest_jan1_lines()
    print(f"✓ Parsed {len(picks)} curated picks")
    
    total = update_picks_json(picks)
    print(f"✅ Updated picks.json: {total} total picks")
    print("\n💡 Next: Run hydrate_picks.py to fetch NBA stats")
