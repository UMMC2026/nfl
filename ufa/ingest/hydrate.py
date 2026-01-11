from typing import List
from datetime import datetime
from ufa.config import settings

def hydrate_recent_values(league: str, player: str, stat_key: str, *, team: str | None=None,
                          nba_season: str | None=None, nfl_seasons: list[int] | None=None,
                          cfb_year: int | None=None, cfb_season_type: str="regular",
                          last_n: int=10) -> List[float]:
    """
    League-agnostic hydration wrapper.
    - NBA: uses nba_api (recommended)
    - NFL: uses nflreadpy (recommended)
    - CFB: uses CollegeFootballData API (requires token)
    """
    league_u = league.strip().upper()


    if league_u == "NBA":
        if not nba_season:
            raise ValueError("nba_season required (e.g., '2024-25').")
        from ufa.ingest.nba import nba_recent_values
        return nba_recent_values(player, stat_key, season=nba_season, last_n=last_n)

    if league_u == "NFL":
            from ufa.ingest.stat_map import NFL_STAT_KEYS
            # Patch: skip direct hydration for composite stats (e.g., rush_rec_tds, rush_rec_yds)
            from engine.stat_derivation import COMPOSITE_MAP
            if stat_key in COMPOSITE_MAP:
                # Composite stat: skip direct hydration, signal to caller to derive
                return None
            if stat_key not in NFL_STAT_KEYS:
                raise ValueError(f"NFL hydration only supports atomic stats: {list(NFL_STAT_KEYS.keys())}. Got: {stat_key}")
            # If caller didn't specify seasons, attempt a pragmatic multi-season
            # default window (last two seasons). This increases chance of
            # returning recent_values for players with sparse data.
            if not nfl_seasons:
                current_year = datetime.utcnow().year
                nfl_seasons = [current_year - 1, current_year - 2]
            from ufa.ingest.nfl import nfl_recent_values
            return nfl_recent_values(player, stat_key, seasons=nfl_seasons, last_n=last_n)

    if league_u == "CFB":
        if not team or cfb_year is None:
            raise ValueError("CFB requires team and cfb_year.")
        if not settings.cfbd_api_key:
            raise ValueError("CFBD_API_KEY missing. Put it in .env (see .env.example).")
        from ufa.ingest.cfb import cfb_recent_values
        return cfb_recent_values(player, team, stat_key, year=cfb_year, season_type=cfb_season_type, last_n=last_n)

    raise ValueError("Unsupported league. Use NBA, NFL, or CFB.")
