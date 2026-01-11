"""
NFL_STAT_HYDRATOR v1 — Play-by-Play Based (Stub)

This module defines the interface for NFL stat hydration.
All NFL props must be hydrated here, using play-by-play or team-context aggregation.

Returns a structured response for every prop, with a clear 'not implemented' flag.
"""


from typing import Dict, Any, Optional
import os
import pandas as pd
import numpy as np

class HydrationError(Exception):
    pass

NFLFASTR_PATH = os.environ.get("NFLFASTR_CSV", "nflfastR_play_by_play_2025.csv")
STAT_MAP = {
    "pass_yds": "passing_yards",
    "rush_yds": "rushing_yards",
    "rec_yds": "receiving_yards",
    "pass_tds": "passing_tds",
    "rush_tds": "rushing_tds",
    "rec_tds": "receiving_tds",
    "receptions": "receptions"
}

def hydrate_nfl_stat(player: str, stat: str, team: Optional[str] = None, season: Optional[int] = None, games: int = 10) -> Dict[str, Any]:
    """
    NFL stat hydrator using nflfastR play-by-play CSVs.
    Args:
        player: Player name
        stat: Stat key (e.g., 'pass_yds')
        team: Team code (optional)
        season: Year (optional)
        games: Number of games to aggregate (default 10)
    Returns:
        Dict with keys: player, stat, samples, mean, std_dev, source, implemented
    """
    print(f"[NFL_STAT_HYDRATOR] Hydrating {player} / {stat} / {team} / {season}")
    if stat not in STAT_MAP:
        raise HydrationError(f"Stat {stat} not supported for NFL hydration.")
    if not os.path.exists(NFLFASTR_PATH):
        raise HydrationError(f"nflfastR CSV not found at {NFLFASTR_PATH}. Download from https://www.nflfastr.com/.")

    df = pd.read_csv(NFLFASTR_PATH)
    # Filter by season if provided
    if season:
        if "season" in df.columns:
            df = df[df["season"] == season]
    # Normalize player name columns
    player_cols = [c for c in df.columns if "player_name" in c or "receiver_player_name" in c or "rusher_player_name" in c or "passer_player_name" in c]
    # Try to match player name in any relevant column
    player_mask = np.zeros(len(df), dtype=bool)
    for col in player_cols:
        player_mask |= df[col].fillna("").str.lower() == player.lower()
    df_player = df[player_mask]
    if df_player.empty:
        return {
            "player": player,
            "stat": stat,
            "samples": 0,
            "mean": None,
            "std_dev": None,
            "source": "pbp_aggregated",
            "implemented": True,
            "note": f"No data found for {player} in nflfastR."
        }
    # Aggregate by game
    if "game_id" in df_player.columns:
        group = df_player.groupby("game_id")[STAT_MAP[stat]].sum().sort_index(ascending=False)
    else:
        group = df_player[STAT_MAP[stat]]
    last_n = group.head(games)
    samples = last_n.count()
    mean = last_n.mean() if samples > 0 else None
    std_dev = last_n.std(ddof=0) if samples > 1 else None
    return {
        "player": player,
        "stat": stat,
        "samples": int(samples),
        "mean": float(mean) if mean is not None else None,
        "std_dev": float(std_dev) if std_dev is not None else None,
        "source": "pbp_aggregated",
        "implemented": True,
        "note": None if samples > 0 else f"No data found for {player} in nflfastR."
    }
