"""
CBB Player Stats Ingestion

Normalizes:
- Minutes
- Possessions (pace-adjusted)
- Home/away + travel days
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json

RAW_DATA_DIR = Path("data/cbb/raw")


import csv

def ingest_player_stats(
    date: str,
    team_filter: Optional[str] = None,
    min_minutes: float = 0.0
) -> List[Dict]:
    """
    Ingest player box score stats for a given date.
    
    Args:
        date: Date string in YYYY-MM-DD format
        team_filter: Optional team abbreviation to filter
        min_minutes: Minimum minutes played to include
        
    Returns:
        List of player stat dictionaries with normalized fields
    """

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = RAW_DATA_DIR / f"player_stats_{date.replace('-', '')}.json"
    csv_path = RAW_DATA_DIR / f"player_stats_{date.replace('-', '')}.csv"

    if cache_path.exists():
        with open(cache_path) as f:
            players = json.load(f)
    else:
        # TODO: Implement actual data fetching
        players = []

    # Filter by team if specified
    if team_filter:
        players = [p for p in players if p.get("team") == team_filter]

    # Filter by minimum minutes
    players = [p for p in players if p.get("minutes", 0) >= min_minutes]


    # Save as CSV as well as JSON
    if players:
        # Save JSON (overwrite to ensure up-to-date)
        with open(cache_path, "w") as f:
            json.dump(players, f, indent=2)
        # Save CSV
        with open(csv_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=players[0].keys())
            writer.writeheader()
            for row in players:
                writer.writerow(row)

        # --- Automated daily snapshot for fallback recall ---
        import os
        fallback_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_path = os.path.join(fallback_dir, 'player_stats.json')
        # Use player_name as key for fast lookup
        fallback_data = {}
        for p in players:
            key = p.get('player_name', '').lower().replace(' ', '_')
            fallback_data[key] = p
        with open(fallback_path, 'w') as f:
            json.dump(fallback_data, f, indent=2)

    return players


def normalize_player_stats(raw_stats: Dict) -> Dict:
    """
    Normalize raw player stats to standard schema.
    
    CBB-specific normalization:
    - Pace adjustment based on team tempo
    - Usage proxy calculation
    - Foul rate computation
    """
    normalized = {
        "player_id": raw_stats.get("player_id"),
        "player_name": raw_stats.get("player_name"),
        "team": raw_stats.get("team"),
        "opponent": raw_stats.get("opponent"),
        "game_id": raw_stats.get("game_id"),
        "date": raw_stats.get("date"),
        "home_away": raw_stats.get("home_away", "unknown"),
        
        # Core stats
        "minutes": raw_stats.get("minutes", 0),
        "points": raw_stats.get("points", 0),
        "rebounds": raw_stats.get("rebounds", 0),
        "assists": raw_stats.get("assists", 0),
        
        # Shooting
        "fgm": raw_stats.get("fgm", 0),
        "fga": raw_stats.get("fga", 0),
        "fg3m": raw_stats.get("fg3m", 0),
        "fg3a": raw_stats.get("fg3a", 0),
        "ftm": raw_stats.get("ftm", 0),
        "fta": raw_stats.get("fta", 0),
        
        # Other
        "steals": raw_stats.get("steals", 0),
        "blocks": raw_stats.get("blocks", 0),
        "turnovers": raw_stats.get("turnovers", 0),
        "fouls": raw_stats.get("fouls", 0),
    }
    
    # Calculate usage proxy (CBB-specific)
    # Usage = (FGA + 0.44*FTA + TOV) / minutes
    minutes = normalized["minutes"] or 1
    usage_proxy = (
        normalized["fga"] + 
        0.44 * normalized["fta"] + 
        normalized["turnovers"]
    ) / minutes
    normalized["usage_proxy"] = round(usage_proxy, 3)
    
    # Foul rate (critical in CBB)
    normalized["foul_rate"] = round(normalized["fouls"] / minutes, 3)
    
    return normalized
