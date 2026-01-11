"""
Sleeper API minimal client (read-only).
- Fetch user by username or user_id
- Fetch leagues for a user for a sport/season
- Build avatar URLs (full-size and thumbnail)

Rate limit guidance: stay under 1000 requests/minute.
This client performs simple backoff on HTTP errors.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Union
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://api.sleeper.app/v1"
AVATAR_BASE = "https://sleepercdn.com/avatars"
USER_AGENT = "UNDERDOG-ANALYSIS/1.0 (+https://github.com/user)"

class SleeperError(Exception):
    pass


def _get(url: str, timeout: int = 20) -> Union[Dict[str, Any], List[Any]]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            try:
                return json.loads(data.decode("utf-8"))
            except Exception as je:
                raise SleeperError(f"Failed to parse JSON from {url}: {je}")
    except HTTPError as he:
        # simple backoff for rate limits or transient errors
        if he.code in (429, 500, 502, 503, 504):
            time.sleep(0.5)
        raise SleeperError(f"HTTP {he.code} for {url}: {he.reason}")
    except URLError as ue:
        raise SleeperError(f"Network error for {url}: {ue}")


def get_user(identifier: str) -> Dict[str, Any]:
    """Fetch a Sleeper user by username or user_id.

    Raises SleeperError if the response is null/None or not a dict.
    """
    url = f"{BASE_URL}/user/{identifier}"
    data = _get(url)
    if isinstance(data, dict):
        return data
    # Sleeper returns JSON null for unknown users; json.loads -> None
    raise SleeperError(f"User not found or invalid response for identifier '{identifier}'")


def get_user_leagues(user_id: str, sport: str = "nfl", season: str = "2018") -> List[Dict[str, Any]]:
    """Fetch leagues for a user for given sport and season."""
    url = f"{BASE_URL}/user/{user_id}/leagues/{sport}/{season}"
    data = _get(url)
    if isinstance(data, list):
        return data  # type: ignore[return-value]
    raise SleeperError(f"Unexpected leagues payload type: {type(data)}")


def avatar_url(avatar_id: Optional[str], thumb: bool = False) -> Optional[str]:
    if not avatar_id:
        return None
    suffix = "thumbs" if thumb else ""
    if suffix:
        return f"{AVATAR_BASE}/thumbs/{avatar_id}"
    return f"{AVATAR_BASE}/{avatar_id}"
