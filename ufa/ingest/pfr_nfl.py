"""
Pro-Football-Reference (PFR) NFL ingestion with local caching and throttling.

Provides a thin HTML scraper to fetch player game logs for a given season.
- Uses local cache to avoid repeated network calls and mitigate rate limits (HTTP 429)
- Adds randomized delay and simple backoff
- Parses per-game passing, rushing, and receiving stats into normalized keys

Note: PFR page/ID formats can vary. This client performs a search then resolves
player page and gamelog for the target season. Parsing aims for robustness but
may need tweaks for edge cases.
"""

from __future__ import annotations
import os
import time
import random
from pathlib import Path
from typing import Optional, List, Dict
import urllib.parse
import urllib.request
import ssl
from bs4 import BeautifulSoup

# SSL context
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

CACHE_DIR = Path("cache/pfr")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://www.pro-football-reference.com"
SEARCH_URL = BASE + "/search/search.fcgi?search={query}"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Normalized keys
STAT_KEYS = {
    "pass_yds": "pass_yds",
    "pass_tds": "pass_tds",
    "rush_yds": "rush_yds",
    "rush_tds": "rush_tds",
    "rec_yds": "rec_yds",
    "receptions": "receptions",
    "rec_tds": "rec_tds",
}

class PFRClient:
    def __init__(self, min_delay: float = 1.0, max_delay: float = 2.5):
        self.min_delay = min_delay
        self.max_delay = max_delay

    def _delay(self):
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, context=_ctx, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return CACHE_DIR / f"{safe}.html"

    def _get_cached(self, key: str) -> Optional[str]:
        p = self._cache_path(key)
        if p.exists():
            try:
                return p.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def _set_cache(self, key: str, html: str):
        p = self._cache_path(key)
        try:
            p.write_text(html, encoding="utf-8")
        except Exception:
            pass

    def search_player(self, name: str) -> Optional[str]:
        """Return relative player page URL (e.g., '/players/L/LawrTr01.htm')."""
        q = urllib.parse.quote(name)
        url = SEARCH_URL.format(query=q)
        cache_key = f"search_{q}"
        html = self._get_cached(cache_key)
        if not html:
            self._delay()
            html = self._fetch(url)
            self._set_cache(cache_key, html)
        soup = BeautifulSoup(html, "lxml")
        # First result link to a player
        for a in soup.select("div.search-item-url a"):
            href = a.get("href", "")
            if href.startswith("/players/") and href.endswith(".htm"):
                return href
        # Fallback: any link in results
        for a in soup.select("a"):
            href = a.get("href", "")
            if href.startswith("/players/") and href.endswith(".htm"):
                return href
        return None

    def _gamelog_url_for(self, player_href: str, season: int) -> str:
        # Example player href: '/players/L/LawrTr01.htm' -> '/players/L/LawrTr01/gamelog/{season}/'
        base = player_href.replace(".htm", "")
        return BASE + f"{base}/gamelog/{season}/"

    def fetch_player_gamelog(self, name: str, season: int = 2024) -> List[Dict]:
        """Fetch consolidated per-game stats from PFR with caching and return last N games."""
        player_href = self.search_player(name)
        if not player_href:
            return []
        gl_url = self._gamelog_url_for(player_href, season)
        cache_key = f"gamelog_{player_href}_{season}"
        html = self._get_cached(cache_key)
        if not html:
            self._delay()
            try:
                html = self._fetch(gl_url)
            except Exception:
                # crude backoff
                time.sleep(3.0)
                html = self._fetch(gl_url)
            self._set_cache(cache_key, html)
        return self._parse_gamelog_html(html)

    def _parse_gamelog_html(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, "lxml")
        # PFR uses tables with id like 'passing', 'rushing_and_receiving'
        # We'll iterate rows with data-stat attributes.
        rows = soup.select("table#games tbody tr")
        games: Dict[str, Dict] = {}
        for tr in rows:
            if tr.get("id", "").startswith("games.") is False:
                # skip separators
                continue
            week = tr.select_one("th[data-stat='week_num']")
            opp = tr.select_one("td[data-stat='opp']")
            date = tr.select_one("td[data-stat='game_date']")
            game_key = tr.get("id", "")
            g = games.setdefault(game_key, {
                "week": int(week.text) if week and week.text.isdigit() else 0,
                "opponent": opp.text.strip() if opp else "",
                "date": date.text.strip() if date else "",
                "stats": {}
            })
            # Passing
            pyds = tr.select_one("td[data-stat='pass_yds']")
            ptd = tr.select_one("td[data-stat='pass_td']")
            # Rushing
            ryds = tr.select_one("td[data-stat='rush_yds']")
            rtd = tr.select_one("td[data-stat='rush_td']")
            ratt = tr.select_one("td[data-stat='rush_att']")
            # Receiving
            rec = tr.select_one("td[data-stat='rec']")
            recyds = tr.select_one("td[data-stat='rec_yds']")
            rectd = tr.select_one("td[data-stat='rec_td']")
            tgt = tr.select_one("td[data-stat='targets']")

            def _to_float(tag):
                try:
                    return float(tag.text.replace(",", "")) if tag and tag.text.strip() != "" else 0.0
                except Exception:
                    return 0.0

            # Populate normalized keys
            if pyds: g["stats"]["pass_yds"] = _to_float(pyds)
            if ptd: g["stats"]["pass_tds"] = _to_float(ptd)
            if ryds: g["stats"]["rush_yds"] = _to_float(ryds)
            if rtd: g["stats"]["rush_tds"] = _to_float(rtd)
            if ratt: g["stats"]["rush_attempts"] = _to_float(ratt)
            if rec: g["stats"]["receptions"] = _to_float(rec)
            if recyds: g["stats"]["rec_yds"] = _to_float(recyds)
            if rectd: g["stats"]["rec_tds"] = _to_float(rectd)
            if tgt: g["stats"]["targets"] = _to_float(tgt)

        # Return list sorted by week
        out = list(games.values())
        out.sort(key=lambda x: x.get("week", 0))
        return out


if __name__ == "__main__":
    client = PFRClient()
    for name in ["Trevor Lawrence", "Michael Pittman Jr.", "Najee Harris", "George Pickens"]:
        gl = client.fetch_player_gamelog(name, season=2024)
        print(name, "- games:", len(gl))
        if gl:
            print("  last:", gl[-1])
