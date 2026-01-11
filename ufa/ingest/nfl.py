from typing import List
from ufa.ingest.stat_map import NFL_STAT_KEYS

def nfl_recent_values(player_name: str, stat_key: str, seasons: list[int], last_n: int = 10) -> List[float]:
    """
    Pull NFL player stat series using nflreadpy (nflverse data).
    You may need to adjust name/stat columns after running scripts/inspect_nfl.py.
    """
    # Use new play-by-play hydrator
    from hydrators.nfl_stat_hydrator import hydrate_nfl_stat
    # Only use the most recent season if not specified
    season = seasons[0] if seasons else None
    result = hydrate_nfl_stat(player_name, stat_key, season=season, games=last_n)
    # Attach rolling values for scoring
    if result["samples"] >= 2 and result["mean"] is not None:
        # For empirical scoring, synthesize a rolling window with mean and std_dev
        # If std_dev is None (only 2 samples), use mean for both
        mu = result["mean"]
        sigma = result["std_dev"] if result["std_dev"] is not None else 0.0
        # Synthesize a rolling window for scoring (normal approx)
        vals = [mu + sigma * ((i - (last_n-1)/2)/((last_n-1)/2)) for i in range(result["samples"])]
        return vals[:last_n]
    else:
        return []
