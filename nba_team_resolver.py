"""nba_team_resolver.py

Best-effort current-team resolver for NBA players.

Why this exists:
- Slates pasted from Underdog can sometimes contain UI/paste artifacts where a player
  appears under the wrong team card. If we trust that text, we can label a player
  as HOU/OKC incorrectly.

This resolver uses nba_api to fetch the authoritative current TEAM_ABBREVIATION.
It is designed to be:
- best-effort (never raises to callers)
- cached in-memory per process

NOTE:
- This is not a "today's active roster" gate; it's a sanity check for team assignment.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional, Tuple


def _try_import_nba_api():
    try:
        from nba_api.stats.static import players as nba_players
        from nba_api.stats.endpoints import commonplayerinfo
        return nba_players, commonplayerinfo
    except Exception:
        return None, None


def _resolve_player_id(player_name: str, nba_players) -> Optional[int]:
    matches = nba_players.find_players_by_full_name(player_name)
    if not matches:
        # Fallback: try last token
        tokens = [t for t in player_name.replace("-", " ").split(" ") if t]
        if tokens:
            matches = nba_players.find_players_by_full_name(tokens[-1])

    if not matches:
        return None

    active = [m for m in matches if m.get("is_active")]
    pick = active[0] if active else matches[0]
    pid = pick.get("id")
    return int(pid) if pid is not None else None


@lru_cache(maxsize=2048)
def resolve_current_team_abbr(player_name: str) -> Optional[str]:
    """Return TEAM_ABBREVIATION for the player, or None if unavailable."""
    if not player_name or not isinstance(player_name, str):
        return None

    nba_players, commonplayerinfo = _try_import_nba_api()
    if nba_players is None or commonplayerinfo is None:
        return None

    try:
        pid = _resolve_player_id(player_name, nba_players)
        if pid is None:
            return None

        info = commonplayerinfo.CommonPlayerInfo(player_id=pid)
        df = info.get_data_frames()[0]
        if df is None or df.empty:
            return None

        # nba_api columns can vary slightly; TEAM_ABBREVIATION is typical.
        team = None
        if "TEAM_ABBREVIATION" in df.columns:
            team = df.loc[0, "TEAM_ABBREVIATION"]
        elif "TEAM" in df.columns:
            team = df.loc[0, "TEAM"]

        if team is None:
            return None

        s = str(team).strip().upper()
        return s[:3] if s else None

    except Exception:
        return None


def normalize_team_code(team: Optional[str]) -> Optional[str]:
    if not team or not isinstance(team, str):
        return None
    s = team.strip().upper()
    if not s:
        return None

    # Normalize punctuation / separators commonly seen in feed data.
    s_norm = (
        s.replace(".", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("  ", " ")
        .strip()
    )

    # Full-name / city-name mappings (Odds API uses official team names).
    # Prefer explicit mappings to avoid incorrect 3-letter prefixes like
    # GOLDEN STATE -> GOL (should be GSW) or LOS ANGELES -> LOS (LAC/LAL).
    FULL_NAME_PREFIX = {
        "ATLANTA": "ATL",
        "BOSTON": "BOS",
        "BROOKLYN": "BKN",
        "CHARLOTTE": "CHA",
        "CHICAGO": "CHI",
        "CLEVELAND": "CLE",
        "DALLAS": "DAL",
        "DENVER": "DEN",
        "DETROIT": "DET",
        "GOLDEN STATE": "GSW",
        "HOUSTON": "HOU",
        "INDIANA": "IND",
        "MEMPHIS": "MEM",
        "MIAMI": "MIA",
        "MILWAUKEE": "MIL",
        "MINNESOTA": "MIN",
        "NEW ORLEANS": "NOP",
        "NEW YORK": "NYK",
        "OKLAHOMA CITY": "OKC",
        "ORLANDO": "ORL",
        "PHILADELPHIA": "PHI",
        "PHOENIX": "PHX",
        "PORTLAND": "POR",
        "SACRAMENTO": "SAC",
        "SAN ANTONIO": "SAS",
        "TORONTO": "TOR",
        "UTAH": "UTA",
        "WASHINGTON": "WAS",
    }

    # LA teams need explicit disambiguation.
    if s_norm.startswith("LOS ANGELES CLIPPERS") or s_norm.startswith("LA CLIPPERS"):
        return "LAC"
    if s_norm.startswith("LOS ANGELES LAKERS") or s_norm.startswith("LA LAKERS"):
        return "LAL"

    # Handle full-name prefixes safely.
    for prefix, abbr in FULL_NAME_PREFIX.items():
        if s_norm.startswith(prefix):
            return abbr

    # IMPORTANT: some data sources use legacy/odd 3-letter codes (e.g., NEW for Knicks).
    if s_norm.startswith("NEW JERSEY"):
        return "BKN"

    # Handle known 3-letter aliases (only when the token is exactly 3 chars).
    if len(s_norm) == 3:
        alias = {
            "NEW": "NYK",  # legacy Knicks code used by some schedules
            "LOS": "LAC",  # legacy Clippers code used by some schedules
            "NJN": "BKN",  # legacy Nets
            "NOH": "NOP",  # legacy Hornets/Pelicans
            "NOK": "NOP",  # legacy New Orleans
            "SEA": "OKC",  # legacy Sonics
            "PHO": "PHX",  # legacy Suns
        }.get(s_norm)
        if alias:
            return alias

    return s_norm[:3]


def matchup_teams_from_prop(prop: dict) -> Optional[Tuple[str, str]]:
    """Return (away, home) team codes if present on the prop."""
    if not isinstance(prop, dict):
        return None
    away = normalize_team_code(prop.get("matchup_away") or None)
    home = normalize_team_code(prop.get("matchup_home") or None)
    if away and home:
        return away, home
    return None
