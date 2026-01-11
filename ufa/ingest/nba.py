from typing import List
from ufa.ingest.stat_map import NBA_STAT_KEYS

def nba_recent_values(player_name: str, stat_key: str, season: str, last_n: int = 10) -> List[float]:
    """
    Pull recent NBA game log values using `nba_api`.
    Supports both single stats (points, rebounds) and combo stats (pts+reb+ast).
    """
    try:
        from nba_api.stats.static import players
        from nba_api.stats.endpoints import playergamelog
    except Exception as e:
        raise RuntimeError("nba_api not installed. Run: pip install -r requirements-extras.txt") from e

    col = NBA_STAT_KEYS.get(stat_key)
    if not col:
        raise ValueError(f"Unsupported NBA stat_key: {stat_key}. Use one of {list(NBA_STAT_KEYS.keys())}")

    matches = players.find_players_by_full_name(player_name)
    if not matches:
        raise ValueError(f"NBA player not found: {player_name}")

    pid = int(matches[0]["id"])
    gl = playergamelog.PlayerGameLog(player_id=pid, season=season)
    df = gl.get_data_frames()[0]

    # Handle combo stats (list of columns to sum) vs single stats (string)
    if isinstance(col, list):
        for c in col:
            if c not in df.columns:
                raise ValueError(f"Column {c} not found in gamelog. Columns: {list(df.columns)}")
        vals = df[col].head(last_n).sum(axis=1).astype(float).tolist()
    else:
        if col not in df.columns:
            raise ValueError(f"Column {col} not found in gamelog. Columns: {list(df.columns)}")
        vals = df[col].head(last_n).astype(float).tolist()
    
    if len(vals) < 2:
        raise ValueError("Not enough games returned.")
    return vals
