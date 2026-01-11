"""
Ground truth helpers for official NBA stats (preferred over model internals).
- get_nba_last10_avg: last 10 games per-game averages
- get_nba_season_avg: season per-game averages (for role/context)

Uses nba_api (same data powering nba.com stats) to avoid brittle HTML scraping.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Optional

from nba_api.stats.endpoints import leaguedashplayerstats


StatMap = Dict[str, float]


@lru_cache(maxsize=1)
def _fetch_last10() -> Dict[str, StatMap]:
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2025-26",
        per_mode_detailed="PerGame",
        last_n_games=10,
    )
    df = stats.get_data_frames()[0]
    data: Dict[str, StatMap] = {}
    for _, row in df.iterrows():
        data[row["PLAYER_NAME"]] = {
            "team": row["TEAM_ABBREVIATION"],
            "points": float(row["PTS"]),
            "rebounds": float(row["REB"]),
            "assists": float(row["AST"]),
            "pra": float(row["PTS"] + row["REB"] + row["AST"]),
        }
    return data


@lru_cache(maxsize=1)
def _fetch_season() -> Dict[str, StatMap]:
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2025-26",
        per_mode_detailed="PerGame",
    )
    df = stats.get_data_frames()[0]
    data: Dict[str, StatMap] = {}
    for _, row in df.iterrows():
        data[row["PLAYER_NAME"]] = {
            "team": row["TEAM_ABBREVIATION"],
            "points": float(row["PTS"]),
            "rebounds": float(row["REB"]),
            "assists": float(row["AST"]),
            "pra": float(row["PTS"] + row["REB"] + row["AST"]),
        }
    return data


def get_nba_last10_avg(player: str, stat: str) -> Optional[float]:
    stat_map = _fetch_last10().get(player)
    if not stat_map:
        return None
    key = _stat_key(stat)
    return stat_map.get(key)


def get_nba_season_avg(player: str, stat: str) -> Optional[float]:
    stat_map = _fetch_season().get(player)
    if not stat_map:
        return None
    key = _stat_key(stat)
    return stat_map.get(key)


def _stat_key(stat: str) -> str:
    aliases = {
        "pts": "points",
        "points": "points",
        "reb": "rebounds",
        "rebs": "rebounds",
        "rebounds": "rebounds",
        "ast": "assists",
        "assists": "assists",
        "pts+reb+ast": "pra",
        "pra": "pra",
    }
    return aliases.get(stat, stat)


__all__ = [
    "get_nba_last10_avg",
    "get_nba_season_avg",
]
