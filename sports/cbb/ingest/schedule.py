"""
CBB Schedule Fetching

Provides today's games and schedule context.
"""
from datetime import datetime, date
from typing import Dict, List, Optional
import json
from pathlib import Path

SCHEDULE_DIR = Path("data/cbb/schedules")


def fetch_schedule(
    target_date: Optional[str] = None,
    conference_filter: Optional[str] = None
) -> List[Dict]:
    """
    Fetch CBB games for a given date.
    
    Args:
        target_date: Date string YYYY-MM-DD (defaults to today)
        conference_filter: Optional conference to filter (e.g., "ACC", "Big Ten")
        
    Returns:
        List of game dictionaries with context flags
    """
    if target_date is None:
        target_date = date.today().isoformat()
    
    SCHEDULE_DIR.mkdir(parents=True, exist_ok=True)
    
    # TODO: Implement actual schedule fetching
    games = []
    
    # Add context flags to each game
    for game in games:
        game["context"] = compute_game_context(game)
    
    # Filter by conference if specified
    if conference_filter:
        games = [
            g for g in games 
            if g.get("home_conference") == conference_filter 
            or g.get("away_conference") == conference_filter
        ]
    
    return games


def compute_game_context(game: Dict) -> Dict:
    """
    Compute CBB-specific game context flags.
    
    Context factors:
    - Conference vs non-conference
    - Back-to-back travel
    - Early season vs late season
    - Rivalry game flag
    """
    home_conf = game.get("home_conference", "")
    away_conf = game.get("away_conference", "")
    
    is_conference = home_conf == away_conf and home_conf != ""
    
    return {
        "is_conference_game": is_conference,
        "is_neutral_site": game.get("neutral_site", False),
        "spread": game.get("spread", 0),
        "over_under": game.get("over_under", 0),
        "blowout_risk": abs(game.get("spread", 0)) > 15,
    }


def get_today_games() -> List[Dict]:
    """Convenience wrapper for today's games."""
    return fetch_schedule(date.today().isoformat())
