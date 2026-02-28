"""
CBB Game Stats Ingestion

RULE: Only ingest FINAL games.
If game.status != "FINAL": BLOCK_LEARNING
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json

# Output directory for raw data
RAW_DATA_DIR = Path("data/cbb/raw")


def ingest_game_stats(
    date: str,
    source: str = "sportsreference",
    force_refresh: bool = False
) -> List[Dict]:
    """
    Ingest game stats for a given date.
    
    Args:
        date: Date string in YYYY-MM-DD format
        source: Data source (sportsreference, espn)
        force_refresh: Re-fetch even if cached
        
    Returns:
        List of game stat dictionaries
        
    IMPORTANT: Only returns FINAL games. In-progress games are filtered.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    cache_path = RAW_DATA_DIR / f"game_stats_{date.replace('-', '')}.json"
    
    if cache_path.exists() and not force_refresh:
        with open(cache_path) as f:
            return json.load(f)
    
    # TODO: Implement actual data fetching
    # For now, return empty list as scaffold
    games = []
    
    # Filter to FINAL only
    final_games = [g for g in games if g.get("status") == "FINAL"]
    
    # Cache results
    with open(cache_path, "w") as f:
        json.dump(final_games, f, indent=2)
    
    return final_games


def validate_game_status(game: Dict) -> bool:
    """
    Validate game is FINAL before allowing learning.
    
    HARD RULE: Never learn from in-progress games.
    """
    status = game.get("status", "").upper()
    if status != "FINAL":
        print(f"[BLOCK] Game {game.get('game_id')} status={status}, not FINAL")
        return False
    return True
