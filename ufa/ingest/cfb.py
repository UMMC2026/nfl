from typing import List
import os
import requests
from ufa.ingest.stat_map import CFB_STAT_KEYS
from ufa.config import settings

BASE = "https://api.collegefootballdata.com"

def _auth_headers():
    key = settings.cfbd_api_key or os.getenv("CFBD_API_KEY")
    if not key:
        raise ValueError("Missing CFBD_API_KEY in environment.")
    return {"Authorization": f"Bearer {key}"}

def cfb_recent_values(player_name: str, team: str, stat_key: str, year: int, season_type: str="regular", last_n: int=10) -> List[float]:
    """
    Uses CollegeFootballData `/games/players` endpoint response structure.
    Returns last_n values for a given player/stat.
    """
    key = CFB_STAT_KEYS.get(stat_key)
    if not key:
        raise ValueError(f"Unsupported CFB stat_key: {stat_key}. Use one of {list(CFB_STAT_KEYS.keys())}")
    category, abbrev = key

    url = f"{BASE}/games/players"
    params = {"year": year, "team": team, "category": category, "seasonType": season_type}

    r = requests.get(url, params=params, headers=_auth_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()

    vals: List[float] = []
    for game in data:
        for t in game.get("teams", []):
            if t.get("school") != team:
                continue
            for cat in t.get("categories", []):
                if (cat.get("name") or "").lower() != category.lower():
                    continue
                for typ in cat.get("types", []):
                    if (typ.get("abbreviation") or "").upper() != abbrev.upper():
                        continue
                    for ath in typ.get("athletes", []):
                        if (ath.get("name") or "").lower() == player_name.lower():
                            try:
                                vals.append(float(ath.get("stat")))
                            except Exception:
                                pass

    vals = vals[:last_n]
    if len(vals) < 2:
        raise ValueError("Not enough CFB games found. Check name/team/year.")
    return vals
