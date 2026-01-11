"""
Ground Truth Data Loader - Official NBA Stats (Last 10 Games)
Authoritative single source of player averages before any analysis.
Fails fast and explicit if data unavailable.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from nba_api.stats.endpoints import leaguedashplayerstats


@lru_cache(maxsize=1)
def load_official_last10_stats() -> Dict[str, Dict[str, float]]:
    """
    Fetch official NBA per-game averages for LAST 10 GAMES (current season).
    
    Returns:
        {
            "Player Name": {
                "team": "LAL",
                "points": 18.5,
                "rebounds": 7.2,
                "assists": 3.1,
                "pra": 28.8,
                "games_played": 10,
            },
            ...
        }
    
    Raises:
        RuntimeError: if nba_api fails or returns no data.
    """
    try:
        stats = leaguedashplayerstats.LeagueDashPlayerStats(
            season="2025-26",
            per_mode_detailed="PerGame",
            last_n_games=10,
        )
        df = stats.get_data_frames()[0]
        
        if df.empty:
            raise RuntimeError("NBA API returned empty dataset for 2025-26 Last 10 Games")
        
        official: Dict[str, Dict[str, float]] = {}
        for _, row in df.iterrows():
            player_name = str(row["PLAYER_NAME"])
            official[player_name] = {
                "team": str(row["TEAM_ABBREVIATION"]),
                "points": float(row["PTS"]),
                "rebounds": float(row["REB"]),
                "assists": float(row["AST"]),
                "pra": float(row["PTS"] + row["REB"] + row["AST"]),
                "games_played": int(row.get("GP", 10)),
            }
        
        print(f"✅ Loaded official Last 10 Games stats for {len(official)} players from NBA API")
        return official
    
    except Exception as e:
        raise RuntimeError(
            f"CRITICAL: Could not fetch official NBA Last 10 Games stats: {e}\n"
            f"System requires authoritative nba_api data. Verify:\n"
            f"  - nba_api is installed (pip install nba_api)\n"
            f"  - Network connectivity is available\n"
            f"  - NBA API is not rate-limited"
        )


def get_official_avg(player: str, stat: str, official_stats: Dict) -> Optional[float]:
    """
    Look up official average for a player and stat.
    
    Args:
        player: Player display name
        stat: one of 'points', 'rebounds', 'assists', 'pts+reb+ast', 'pra'
        official_stats: dict from load_official_last10_stats()
    
    Returns:
        Official Last 10 Games average, or None if player/stat not found.
    """
    player_data = official_stats.get(player)
    if not player_data:
        return None
    
    stat_key_map = {
        "points": "points",
        "pts": "points",
        "rebounds": "rebounds",
        "reb": "rebounds",
        "rebs": "rebounds",
        "assists": "assists",
        "ast": "assists",
        "asts": "assists",
        "pts+reb+ast": "pra",
        "pra": "pra",
    }
    
    key = stat_key_map.get(stat.lower())
    if not key:
        return None
    
    return player_data.get(key)


def validate_pick_against_official(
    player: str,
    stat: str,
    line: float,
    direction: str,
    official_stats: Dict,
) -> tuple[bool, Optional[str], Optional[float]]:
    """
    Hard rule: Reject or warn if official average contradicts the pick.
    
    Args:
        player: Player name
        stat: Stat key
        line: Prop line
        direction: 'higher' or 'lower'
        official_stats: dict from load_official_last10_stats()
    
    Returns:
        (is_valid, rejection_reason, official_avg)
        - is_valid: True if pick passes; False if hard rejection
        - rejection_reason: None if valid, else explanation
        - official_avg: The official average (for logging)
    """
    official_avg = get_official_avg(player, stat, official_stats)
    
    if official_avg is None:
        # Player/stat not found in official data—cannot validate
        return True, None, None
    
    # Hard rule: OVER picks where official avg < line are illogical
    if direction == "higher" and official_avg < line:
        return (
            False,
            f"Official avg {official_avg:.1f} < line {line:.1f} (OVER pick is mathematically weak)",
            official_avg,
        )
    
    # Hard rule: UNDER picks where official avg > line are illogical
    if direction == "lower" and official_avg > line:
        return (
            False,
            f"Official avg {official_avg:.1f} > line {line:.1f} (UNDER pick is mathematically weak)",
            official_avg,
        )
    
    return True, None, official_avg


def save_ground_truth_report(official_stats: Dict, output_path: str = "outputs/ground_truth_official.json"):
    """Persist official stats for audit trail."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source": "NBA API leaguedashplayerstats (Last 10 Games, Season 2025-26)",
                "total_players": len(official_stats),
                "players": official_stats,
            },
            f,
            indent=2,
        )
    print(f"💾 Saved official stats report: {output_path}")


__all__ = [
    "load_official_last10_stats",
    "get_official_avg",
    "validate_pick_against_official",
    "save_ground_truth_report",
]
