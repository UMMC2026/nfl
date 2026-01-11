"""
ESPN NBA season context helper (per-game season averages).

- Uses ESPN's public basketball API endpoints (no HTML scraping).
- Returns defensive, cache-backed lookups for points / rebounds / assists / PRA.
- Designed as optional context (e.g., sanity-check against nba_api-derived stats).
"""
from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


@dataclass
class ESPNSeasonAverages:
    player: str
    player_id: str
    team: str
    season: str
    points: Optional[float] = None
    rebounds: Optional[float] = None
    assists: Optional[float] = None
    pra: Optional[float] = None


def get_espn_nba_season_avg(player: str, stat: str, season_year: int = 2025) -> Optional[float]:
    avgs = get_espn_nba_season_avgs(player, season_year)
    if not avgs:
        return None
    key = _stat_key(stat)
    if key == "pra":
        return avgs.pra
    return getattr(avgs, key, None)


def get_espn_nba_season_avgs(player: str, season_year: int = 2025) -> Optional[ESPNSeasonAverages]:
    player_id = _resolve_athlete_id(player)
    if not player_id:
        return None

    stats_payload = _fetch_stats(player_id)
    if not stats_payload:
        return None

    values = _extract_stats(stats_payload)
    if not values:
        return None

    season_label = f"{season_year}-{(season_year + 1) % 100:02d}"
    team = values.pop("team", "")

    return ESPNSeasonAverages(
        player=player,
        player_id=player_id,
        team=team,
        season=season_label,
        points=values.get("points"),
        rebounds=values.get("rebounds"),
        assists=values.get("assists"),
        pra=_compute_pra(values),
    )


@lru_cache(maxsize=256)
def _resolve_athlete_id(player: str) -> Optional[str]:
    """Resolve ESPN athlete id via search API."""
    search_term = urllib.parse.quote(player)
    url = (
        "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/athletes"
        f"?limit=50&search={search_term}"
    )
    data = _fetch_json(url)
    for item in data.get("items", []):
        ref = item.get("$ref")
        if not ref:
            continue
        athlete = _fetch_json(ref)
        display = str(athlete.get("displayName", "")).lower()
        if player.lower() in display:
            return str(athlete.get("id"))
    return None


@lru_cache(maxsize=512)
def _fetch_stats(player_id: str) -> Dict:
    url = (
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/"
        f"{player_id}/stats?region=us&lang=en&contentorigin=espn"
    )
    return _fetch_json(url)


def _fetch_json(url: str, timeout: int = 10) -> Dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def _extract_stats(data: Dict) -> Dict[str, Optional[float]]:
    """Pull season per-game averages from ESPN stats payload."""
    stats: Dict[str, Optional[float]] = {"team": None, "points": None, "rebounds": None, "assists": None}

    # Team (if present)
    team = data.get("team") or data.get("athlete", {}).get("team")
    if isinstance(team, dict):
        stats["team"] = team.get("abbreviation") or team.get("displayName")

    # Flatten all stat entries from categories; ESPN schema can vary
    categories = []
    if isinstance(data.get("statistics"), list):
        for entry in data["statistics"]:
            categories.extend(entry.get("categories", []))
    if not categories and isinstance(data.get("splits"), dict):
        categories.extend(data["splits"].get("categories", []))

    aliases = {
        "points": {"pts", "points", "pointspergame", "ppg", "avgpoints"},
        "rebounds": {"reb", "rebs", "rebounds", "reboundspergame", "rpg", "avgrebounds"},
        "assists": {"ast", "asts", "assists", "assistspergame", "apg", "avgassists"},
    }

    for category in categories:
        for stat in category.get("stats", []):
            name = str(stat.get("name") or stat.get("id") or stat.get("label") or "").lower()
            abbr = str(stat.get("abbreviation", "")).lower()
            for key, keys in aliases.items():
                if name in keys or abbr in keys:
                    value = _coerce_float(stat.get("perGameValue") or stat.get("value") or stat.get("displayValue"))
                    if value is not None:
                        stats[key] = value

    return stats


def _coerce_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            cleaned = value.replace(",", "").strip()
            return float(cleaned)
        except ValueError:
            return None
    return None


def _compute_pra(values: Dict[str, Optional[float]]) -> Optional[float]:
    pts = values.get("points")
    rebs = values.get("rebounds")
    ast = values.get("assists")
    if None in (pts, rebs, ast):
        return None
    return float(pts) + float(rebs) + float(ast)


def _stat_key(stat: str) -> str:
    aliases = {
        "pts": "points",
        "points": "points",
        "reb": "rebounds",
        "rebs": "rebounds",
        "rebounds": "rebounds",
        "ast": "assists",
        "asts": "assists",
        "assists": "assists",
        "pts+reb+ast": "pra",
        "pra": "pra",
    }
    return aliases.get(stat.lower(), stat.lower())


__all__ = [
    "ESPNSeasonAverages",
    "get_espn_nba_season_avg",
    "get_espn_nba_season_avgs",
]
