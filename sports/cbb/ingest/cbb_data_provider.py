"""
CBB (College Basketball) Data Provider

Borrows from NBA's architecture:
- ESPN API for schedules, rosters, injuries
- Local cache for player averages
- Stat key mapping

Data Sources (priority order):
1. ESPN CBB API (free, reliable) - schedules, rosters, basic stats
2. Local cache for historical stats
3. Line estimation fallback
"""

import json
import ssl
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

# SSL context for compatibility
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# Paths
CBB_DIR = Path(__file__).parent.parent
DATA_DIR = CBB_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"

DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ESPN CBB Base URL
CBB_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from ESPN."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class CBBPlayer:
    """College basketball player info."""
    id: str = ""
    name: str = ""
    team: str = ""
    team_abbr: str = ""
    position: str = ""
    jersey: str = ""
    year: str = ""  # Fr, So, Jr, Sr
    status: str = "Active"  # Active, Out, Injured, Questionable, etc.
    
    # Season averages
    games_played: int = 0
    minutes_per_game: float = 0.0
    points_per_game: float = 0.0
    rebounds_per_game: float = 0.0
    assists_per_game: float = 0.0
    steals_per_game: float = 0.0
    blocks_per_game: float = 0.0
    turnovers_per_game: float = 0.0
    fg_pct: float = 0.0
    three_pt_pct: float = 0.0
    three_pm_per_game: float = 0.0
    
    # Standard deviations (for probability model)
    points_std: float = 5.0
    rebounds_std: float = 2.5
    assists_std: float = 2.0
    three_pm_std: float = 1.0


@dataclass
class CBBTeam:
    """College basketball team info."""
    id: str = ""
    name: str = ""
    abbr: str = ""
    conference: str = ""
    record: str = ""
    ranking: int = 0  # AP ranking, 0 = unranked
    
    # Team stats
    points_per_game: float = 0.0
    points_allowed_per_game: float = 0.0
    pace: float = 70.0  # possessions per game


@dataclass
class CBBGame:
    """College basketball game/matchup."""
    id: str = ""
    home_team: str = ""
    away_team: str = ""
    home_abbr: str = ""
    away_abbr: str = ""
    date: str = ""
    time: str = ""
    status: str = "pre"  # pre, in, post
    venue: str = ""
    spread: float = 0.0  # home team spread
    total: float = 0.0   # over/under
    home_rank: int = 0
    away_rank: int = 0


# =============================================================================
# ESPN CBB FETCHER
# =============================================================================

class ESPNCBBFetcher:
    """Fetch CBB data from ESPN's public APIs."""
    
    # Common team ID mappings (ESPN IDs for major programs)
    TEAM_IDS = {
        "DUKE": "150", "UNC": "153", "KU": "2305", "UK": "96",
        "UCLA": "26", "UVA": "258", "GONZ": "2250", "BAYLOR": "239",
        "PURDUE": "2509", "HOUSTON": "248", "TENN": "2633", "ARIZ": "12",
        "CONN": "41", "MARQ": "269", "CREIGH": "156", "TEXAS": "251",
        "AUBURN": "2", "ALA": "333", "IU": "84", "MSU": "127",
        "MICH": "130", "OSU": "194", "ILL": "356", "IOWA": "2294",
        "WIS": "275", "ORE": "2483", "COLO": "38", "SDSU": "21",
        "FAU": "2226", "MIAMI": "2390", "PITT": "221", "NCST": "152",
        # Add more as needed
    }
    
    def get_todays_games(self) -> List[CBBGame]:
        """Get today's CBB games."""
        data = _fetch_json(f"{CBB_BASE}/scoreboard")
        
        games = []
        for event in data.get("events", []):
            try:
                competition = event.get("competitions", [{}])[0]
                competitors = competition.get("competitors", [])
                
                if len(competitors) < 2:
                    continue
                
                home = next((c for c in competitors if c.get("homeAway") == "home"), None)
                away = next((c for c in competitors if c.get("homeAway") == "away"), None)
                
                if not home or not away:
                    continue
                
                # Get rankings
                home_rank = 0
                away_rank = 0
                if home.get("curatedRank", {}).get("current"):
                    home_rank = home["curatedRank"]["current"]
                if away.get("curatedRank", {}).get("current"):
                    away_rank = away["curatedRank"]["current"]
                
                game = CBBGame(
                    id=event.get("id", ""),
                    home_team=home["team"].get("displayName", ""),
                    away_team=away["team"].get("displayName", ""),
                    home_abbr=home["team"].get("abbreviation", ""),
                    away_abbr=away["team"].get("abbreviation", ""),
                    date=event.get("date", "")[:10],
                    time=event.get("date", "")[11:16] if "T" in event.get("date", "") else "",
                    status=event.get("status", {}).get("type", {}).get("state", "pre"),
                    venue=competition.get("venue", {}).get("fullName", ""),
                    home_rank=home_rank if home_rank and home_rank <= 25 else 0,
                    away_rank=away_rank if away_rank and away_rank <= 25 else 0,
                )
                
                # Get spread/total from odds if available
                odds = competition.get("odds", [])
                if odds:
                    game.spread = float(odds[0].get("spread", 0) or 0)
                    game.total = float(odds[0].get("overUnder", 0) or 0)
                
                games.append(game)
                
            except Exception as e:
                continue
        
        return games
    
    def get_team_roster(self, team_id: str) -> List[CBBPlayer]:
        """Get team roster from ESPN."""
        data = _fetch_json(f"{CBB_BASE}/teams/{team_id}/roster")
        
        players = []
        team_info = data.get("team", {})
        team_name = team_info.get("displayName", "")
        team_abbr = team_info.get("abbreviation", "")
        
        for athlete in data.get("athletes", []):
            try:
                status = "Active"
                injuries = athlete.get("injuries", [])
                if injuries:
                    status = injuries[0].get("status", "Active")
                
                player = CBBPlayer(
                    id=athlete.get("id", ""),
                    name=athlete.get("fullName", ""),
                    team=team_name,
                    team_abbr=team_abbr,
                    position=athlete.get("position", {}).get("abbreviation", ""),
                    jersey=athlete.get("jersey", ""),
                    year=athlete.get("experience", {}).get("abbreviation", ""),
                    status=status,
                )
                players.append(player)
                
            except Exception:
                continue
        
        return players
    
    @staticmethod
    def _current_espn_season() -> int:
        """Return ESPN CBB season year (end-year of academic season).

        ESPN uses the *end* calendar year for CBB seasons.
        Games Aug-Dec belong to next year's season (Aug 2025 → season 2026).
        Games Jan-Jul belong to the current calendar year.
        """
        now = datetime.now()
        return now.year if now.month <= 7 else now.year + 1

    def get_player_stats(self, player_id: str) -> Optional[CBBPlayer]:
        """Get detailed player stats from ESPN (current season).

        NOTE: For CBB, the public site.api athlete endpoints return 404.
        We use the sports.core.api v2 endpoints instead.

        IMPORTANT: We request the *current-season* endpoint
        ``/seasons/{year}/types/2/athletes/{id}/statistics``
        so that averages reflect the current year, NOT career totals.
        Falls back to career stats only when the season endpoint
        returns no data (e.g. freshmen before first game logs post).
        """

        core_base = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
        athlete = _fetch_json(f"{core_base}/athletes/{player_id}?lang=en&region=us")
        if not athlete:
            return None

        name = athlete.get("displayName") or athlete.get("fullName") or ""

        player = CBBPlayer(
            id=str(athlete.get("id", "")),
            name=name,
        )

        # ── Prefer current-season stats (types/2 = regular season) ──
        season_year = self._current_espn_season()
        season_stats_url = (
            f"{core_base}/seasons/{season_year}/types/2"
            f"/athletes/{player_id}/statistics?lang=en&region=us"
        )
        stats_payload = _fetch_json(season_stats_url)

        # Validate the payload actually has stat data
        _has_season_data = bool(
            stats_payload
            and (stats_payload.get("splits") or {}).get("categories")
        )

        if not _has_season_data:
            # Fallback to career endpoint (better than nothing)
            career_url = f"{core_base}/athletes/{player_id}/statistics?lang=en&region=us"
            stats_payload = _fetch_json(career_url)

        if not stats_payload:
            return None

        # Collect candidates by abbreviation (multiple entries can exist: totals + per-game)
        candidates: Dict[str, List[Tuple[str, float]]] = {}
        splits = (stats_payload.get("splits") or {})
        for cat in (splits.get("categories") or []):
            for s in (cat.get("stats") or []):
                abbr = (s.get("abbreviation") or "").strip()
                dn = (s.get("displayName") or s.get("name") or "").strip()
                val = s.get("value")
                if not abbr or val is None:
                    continue
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    continue
                candidates.setdefault(abbr, []).append((dn, fval))

        def _pick(abbr: str) -> float:
            opts = candidates.get(abbr) or []
            if not opts:
                return 0.0
            # Prefer explicit per-game / average entries (avoid totals).
            for dn, v in opts:
                dnl = dn.lower()
                if "per game" in dnl or dnl.startswith("average"):
                    return float(v)
            # Fallback: choose the smallest plausible number (often averages are smaller than totals)
            return float(min(v for _, v in opts))

        # Populate key season averages (per game)
        player.games_played = int(round(_pick("GP")))
        player.minutes_per_game = _pick("MIN")
        player.points_per_game = _pick("PTS")
        player.rebounds_per_game = _pick("REB")
        player.assists_per_game = _pick("AST")
        player.steals_per_game = _pick("STL")
        player.blocks_per_game = _pick("BLK")
        player.turnovers_per_game = _pick("TO")
        player.three_pm_per_game = _pick("3PM")

        return player
    
    def get_player_game_logs(self, player_id: str, limit: int = 15) -> List[Dict]:
        """Fetch recent game logs for a player from ESPN.
        
        Returns list of game dicts with stat keys:
        - points, rebounds, assists, steals, blocks, turnovers
        - three_pointers, field_goals_made, field_goals_attempted
        - free_throws_made, free_throws_attempted, minutes
        - opponent, date, game_id
        
        Args:
            player_id: ESPN player ID
            limit: Number of recent games to fetch (default 15, max 50)
        
        Returns:
            List of game dicts (most recent first)
        """
        core_base = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
        season_year = self._current_espn_season()
        
        # ESPN gamelog endpoint provides game-by-game stats (NOT eventlog)
        gamelog_url = (
            f"{core_base}/athletes/{player_id}/gamelog"
            f"?lang=en&region=us&season={season_year}"
        )
        
        data = _fetch_json(gamelog_url)
        if not data:
            return []
        
        # ESPN returns seasonTypes → categories → events structure
        game_logs = []
        
        for season_type in data.get("seasonTypes", []):
            for category in season_type.get("categories", []):
                events = category.get("events", [])
                
                for event in events[:limit]:  # Limit to recent games
                    try:
                        game_id = event.get("eventId", "")
                        date = event.get("eventDate", "")[:10]  # YYYY-MM-DD
                        
                        # Get opponent
                        opponent_info = event.get("opponent", {})
                        opponent = opponent_info.get("abbreviation", "UNK") if opponent_info else "UNK"
                        
                        # Extract statistics
                        game_stats = {
                            "game_id": game_id,
                            "date": date,
                            "opponent": opponent,
                        }
                        
                        # Parse stat array
                        for stat in event.get("stats", []):
                            abbr = stat.get("abbreviation", "").upper().strip()
                            value = stat.get("value")
                            
                            if value is None:
                                continue
                            
                            try:
                                fval = float(value)
                            except (TypeError, ValueError):
                                continue
                            
                            # Map ESPN abbreviations to our standard keys
                            stat_map = {
                                "PTS": "points",
                                "REB": "rebounds",
                                "AST": "assists",
                                "STL": "steals",
                                "BLK": "blocks",
                                "TO": "turnovers",
                                "3PM": "three_pointers",
                                "FGM": "field_goals_made",
                                "FGA": "field_goals_attempted",
                                "FTM": "free_throws_made",
                                "FTA": "free_throws_attempted",
                                "MIN": "minutes",
                            }
                            
                            mapped_key = stat_map.get(abbr)
                            if mapped_key:
                                game_stats[mapped_key] = fval
                        
                        # Only include games with meaningful stats (at least points)
                        if "points" in game_stats:
                            game_logs.append(game_stats)
                            
                    except Exception as e:
                        # Skip malformed events
                        continue
        
        return game_logs[:limit]  # Ensure we don't exceed limit
    
    def search_team(self, query: str) -> Optional[str]:
        """Search for team ID by name/abbr."""
        query_upper = query.upper().strip()
        
        # Check cached IDs first
        if query_upper in self.TEAM_IDS:
            return self.TEAM_IDS[query_upper]
        
        # Try ESPN search
        data = _fetch_json(f"{CBB_BASE}/teams?limit=500")

        # ESPN has many teams with overlapping substrings (e.g., 'Kentucky' vs
        # 'Eastern Kentucky'). Prefer exact/startswith matches first to avoid
        # false positives.
        exact_candidates: List[Tuple[Tuple[int, int], str]] = []
        contains_candidates: List[Tuple[Tuple[int, int], str]] = []

        for sport in data.get("sports", []):
            for league in sport.get("leagues", []):
                for team in league.get("teams", []):
                    team_info = team.get("team", {}) or {}
                    team_id = team_info.get("id")
                    if not team_id:
                        continue

                    abbr = (team_info.get("abbreviation") or "").upper().strip()
                    display = (team_info.get("displayName") or "").upper().strip()
                    short_display = (team_info.get("shortDisplayName") or "").upper().strip()
                    nickname = (team_info.get("nickname") or "").upper().strip()

                    display_starts = bool(query_upper) and display.startswith(query_upper)

                    # Rank matches (lower is better). Secondary key prefers shorter display name.
                    if query_upper and query_upper == abbr:
                        exact_candidates.append(((0, len(display)), team_id))
                        continue
                    if query_upper and query_upper == display:
                        exact_candidates.append(((1, len(display)), team_id))
                        continue

                    # shortDisplayName can be ambiguous (e.g., 'Kentucky' for 'Eastern Kentucky'),
                    # so only treat it as strong if the full displayName also starts with the query.
                    if query_upper and query_upper == short_display:
                        rank = 2 if display_starts else 6
                        exact_candidates.append(((rank, len(display)), team_id))
                        continue

                    if query_upper and query_upper == nickname:
                        exact_candidates.append(((7, len(display)), team_id))
                        continue

                    # Next-best: startswith on display/shortDisplay
                    if query_upper and display_starts:
                        contains_candidates.append(((10, len(display)), team_id))
                        continue
                    if query_upper and short_display.startswith(query_upper):
                        contains_candidates.append(((12, len(short_display)), team_id))
                        continue

                    # Last resort: substring contains
                    if query_upper and (query_upper in display or query_upper in short_display):
                        contains_candidates.append(((20, len(display)), team_id))

        if exact_candidates:
            exact_candidates.sort(key=lambda t: t[0])
            return exact_candidates[0][1]
        if contains_candidates:
            contains_candidates.sort(key=lambda t: t[0])
            return contains_candidates[0][1]
        return None
    
    def get_team_info(self, team_id: str) -> Optional[CBBTeam]:
        """Get team information."""
        data = _fetch_json(f"{CBB_BASE}/teams/{team_id}")
        
        if not data:
            return None
        
        team_data = data.get("team", {})
        
        team = CBBTeam(
            id=team_data.get("id", ""),
            name=team_data.get("displayName", ""),
            abbr=team_data.get("abbreviation", ""),
            record=team_data.get("record", {}).get("items", [{}])[0].get("summary", ""),
        )
        
        # Get ranking if available
        rank = team_data.get("rank")
        if rank and isinstance(rank, int) and rank <= 25:
            team.ranking = rank
        
        return team


# =============================================================================
# PLAYER STATS CACHE
# =============================================================================

class CBBStatsCache:
    """
    Local cache for CBB player stats.
    
    Since CBB has thousands of players, we cache stats locally.
    Also supports manual overrides for players ESPN doesn't have.
    """
    def __init__(self):
        self.cache_file = CACHE_DIR / "player_stats_cache.json"
        self.override_file = CACHE_DIR / "player_overrides.json"
        self.cache: Dict[str, dict] = {}
        self.overrides: Dict[str, dict] = {}
        self._load_cache()
        self._load_overrides()

    def _load_cache(self):
        """Load cache from disk, migrate old key format, and remove cross-sport keys."""
        if self.cache_file.exists():
            try:
                self.cache = json.loads(self.cache_file.read_text())
                self._migrate_old_keys()
                # Remove all cross-sport keys matching cbb_ncaam_UW_*
                to_remove = [k for k in self.cache if k.startswith("cbb_ncaam_UW_")]
                if to_remove:
                    for k in to_remove:
                        del self.cache[k]
                    self._save_cache()
                    print(f"[CACHE CLEANUP] Removed {len(to_remove)} cross-sport keys (cbb_ncaam_UW_*) from cache.")
            except Exception as e:
                print(f"[CACHE LOAD ERROR] {e}")
                self.cache = {}

    def _migrate_old_keys(self):
        """Migrate old cbb_{name}_{team} keys to new cbb_ncaam_{team}_{name} format."""
        migrated = {}
        needs_migration = False
        for key, value in list(self.cache.items()):
            if key.startswith("cbb_") and not key.startswith("cbb_ncaam_"):
                # Old format: cbb_{name}_{team} or cbb_{name}
                parts = key.split("_")
                # Try to detect old format: last segment is likely team (2-5 uppercase chars)
                if len(parts) >= 3 and parts[-1].isupper() and 2 <= len(parts[-1]) <= 5:
                    team = parts[-1]
                    name = "_".join(parts[1:-1])  # everything between cbb_ and team
                    new_key = f"cbb_ncaam_{team}_{name}"
                    migrated[new_key] = value
                    needs_migration = True
                else:
                    # cbb_{name} with no team → keep as cbb_ncaam_UNK_{name}
                    name = "_".join(parts[1:])
                    new_key = f"cbb_ncaam_UNK_{name}"
                    migrated[new_key] = value
                    needs_migration = True
            else:
                migrated[key] = value
        if needs_migration:
            old_count = len(self.cache)
            self.cache = migrated
            self._save_cache()
            print(f"  [CACHE MIGRATE] Migrated {old_count} keys to cbb_ncaam_ format")
    
    def _load_overrides(self):
        """Load manual overrides from disk."""
        if self.override_file.exists():
            try:
                self.overrides = json.loads(self.override_file.read_text())
            except:
                self.overrides = {}
    
    def _save_cache(self):
        """Save cache to disk."""
        self.cache_file.write_text(json.dumps(self.cache, indent=2))
    
    def _save_overrides(self):
        """Save overrides to disk."""
        self.override_file.write_text(json.dumps(self.overrides, indent=2))
    
    def get_player_stats(self, player_name: str, team_abbr: Optional[str] = None) -> Optional[Dict]:
        """Get player stats from cache or overrides (overrides take priority)."""
        key = self._make_key(player_name, team_abbr)
        
        # Check overrides first (manual entries take priority)
        if key in self.overrides:
            return self.overrides[key]
        
        return self.cache.get(key)
    
    def set_player_stats(self, player_name: str, team_abbr: str, stats: Dict):
        """Store player stats in cache, blocking cross-sport keys."""
        key = self._make_key(player_name, team_abbr)
        # Block cross-sport keys (UW_hannes_steinbach and similar)
        if key == "cbb_ncaam_UW_hannes_steinbach":
            print(f"[CACHE BLOCKED] Refused to write cross-sport key: {key}")
            return
        self.cache[key] = {
            **stats,
            "updated": datetime.now().isoformat(),
        }
        self._save_cache()
    
    def set_override(self, player_name: str, team_abbr: str, stats: Dict):
        """Set manual override for a player."""
        key = self._make_key(player_name, team_abbr)
        self.overrides[key] = {
            **stats,
            "manual": True,
            "updated": datetime.now().isoformat(),
        }
        self._save_overrides()
        print(f"  [OK] Override set for {player_name} ({team_abbr})")
    
    def list_overrides(self) -> Dict[str, dict]:
        """List all manual overrides."""
        return self.overrides
    
    # CBB team abbreviation standardization table
    # Prevents ambiguous codes like "WASH" (Washington vs Washington State)
    CBB_TEAM_NORMALIZE = {
        "WASH": "UW",       # Washington Huskies → UW
        "WSU": "WSU",       # Washington State → WSU
        "WASU": "WSU",
        "WASST": "WSU",
        "OSU": "OHST",      # Ohio State (vs Oregon State "ORST")
        "MSU": "MSUST",     # Michigan State (vs Mississippi State "MSST")
        "USC": "USC",
        "UK": "UK",         # Kentucky
        "UM": "MICH",       # Michigan (vs Miami "MIA")
        "UF": "FLA",        # Florida
        "UT": "TEX",        # Texas (vs Utah "UTAH")
    }

    # Full team name → ESPN abbreviation (OddsAPI uses full names)
    # Generated from ESPN API: site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams
    CBB_FULLNAME_TO_ABBR = {
        # Power conferences + top programs (most likely to appear in props)
        "DUKE BLUE DEVILS": "DUKE", "NORTH CAROLINA TAR HEELS": "UNC",
        "KANSAS JAYHAWKS": "KU", "KENTUCKY WILDCATS": "UK",
        "UCLA BRUINS": "UCLA", "GONZAGA BULLDOGS": "GONZ",
        "PURDUE BOILERMAKERS": "PUR", "HOUSTON COUGARS": "HOU",
        "TENNESSEE VOLUNTEERS": "TENN", "ARIZONA WILDCATS": "ARIZ",
        "UCONN HUSKIES": "CONN", "CONNECTICUT HUSKIES": "CONN",
        "MARQUETTE GOLDEN EAGLES": "MARQ", "CREIGHTON BLUEJAYS": "CREI",
        "TEXAS LONGHORNS": "TEX", "AUBURN TIGERS": "AUB",
        "ALABAMA CRIMSON TIDE": "ALA", "INDIANA HOOSIERS": "IU",
        "MICHIGAN STATE SPARTANS": "MSU", "MICHIGAN WOLVERINES": "MICH",
        "OHIO STATE BUCKEYES": "OSU", "ILLINOIS FIGHTING ILLINI": "ILL",
        "IOWA HAWKEYES": "IOWA", "WISCONSIN BADGERS": "WIS",
        "OREGON DUCKS": "ORE", "COLORADO BUFFALOES": "COLO",
        "SAN DIEGO STATE AZTECS": "SDSU", "FAU OWLS": "FAU",
        "MIAMI HURRICANES": "MIA", "PITTSBURGH PANTHERS": "PITT",
        "NC STATE WOLFPACK": "NCST", "VIRGINIA CAVALIERS": "UVA",
        "BAYLOR BEARS": "BAY", "IOWA STATE CYCLONES": "IASU",
        "TEXAS TECH RED RAIDERS": "TTU", "ARKANSAS RAZORBACKS": "ARK",
        "FLORIDA GATORS": "FLA", "LOUISVILLE CARDINALS": "LOU",
        "SYRACUSE ORANGE": "SYR", "NOTRE DAME FIGHTING IRISH": "ND",
        "VILLANOVA WILDCATS": "VILL", "SETON HALL PIRATES": "HALL",
        "XAVIER MUSKETEERS": "XAV", "PROVIDENCE FRIARS": "PROV",
        "BUTLER BULLDOGS": "BUT", "ST. JOHN'S RED STORM": "SJU",
        "GEORGETOWN HOYAS": "GTWN", "DEPAUL BLUE DEMONS": "DEP",
        "WAKE FOREST DEMON DEACONS": "WAKE", "CLEMSON TIGERS": "CLEM",
        "GEORGIA TECH YELLOW JACKETS": "GT", "BOSTON COLLEGE EAGLES": "BC",
        "LSU TIGERS": "LSU", "MISSISSIPPI STATE BULLDOGS": "MSST",
        "OLE MISS REBELS": "MISS", "VANDERBILT COMMODORES": "VAN",
        "SOUTH CAROLINA GAMECOCKS": "SCAR", "GEORGIA BULLDOGS": "UGA",
        "MISSOURI TIGERS": "MIZ", "TEXAS A&M AGGIES": "TA&M",
        "OKLAHOMA SOONERS": "OU", "OKLAHOMA STATE COWBOYS": "OKST",
        "WEST VIRGINIA MOUNTAINEERS": "WVU", "KANSAS STATE WILDCATS": "KSU",
        "TCU HORNED FROGS": "TCU", "CINCINNATI BEARCATS": "CIN",
        "UCF KNIGHTS": "UCF", "BYU COUGARS": "BYU",
        "COLORADO STATE RAMS": "CSU", "BOISE STATE BRONCOS": "BOIS",
        "MEMPHIS TIGERS": "MEM", "WICHITA STATE SHOCKERS": "WICH",
        "SMU MUSTANGS": "SMU", "TULANE GREEN WAVE": "TULN",
        "STANFORD CARDINAL": "STAN", "CALIFORNIA GOLDEN BEARS": "CAL",
        "WASHINGTON HUSKIES": "UW", "WASHINGTON STATE COUGARS": "WSU",
        "OREGON STATE BEAVERS": "ORST", "UTAH UTES": "UTAH",
        "ARIZONA STATE SUN DEVILS": "ASU", "USC TROJANS": "USC",
        "PENN STATE NITTANY LIONS": "PSU", "MARYLAND TERRAPINS": "MD",
        "RUTGERS SCARLET KNIGHTS": "RUTG", "NEBRASKA CORNHUSKERS": "NEB",
        "MINNESOTA GOLDEN GOPHERS": "MINN", "NORTHWESTERN WILDCATS": "NW",
        "FLORIDA STATE SEMINOLES": "FSU", "VIRGINIA TECH HOKIES": "VT",
        "DAYTON FLYERS": "DAY", "SAINT MARY'S GAELS": "SMC",
        "NEVADA WOLF PACK": "NEV", "NEW MEXICO LOBOS": "UNM",
        "UNLV REBELS": "UNLV", "FRESNO STATE BULLDOGS": "FRES",
        "DRAKE BULLDOGS": "DRKE", "LOYOLA CHICAGO RAMBLERS": "LUC",
        "DAVIDSON WILDCATS": "DAV", "RICHMOND SPIDERS": "RICH",
        "VCU RAMS": "VCU", "SAINT LOUIS BILLIKENS": "SLU",
        "GEORGE MASON PATRIOTS": "GMU", "LA SALLE EXPLORERS": "LAS",
        "RHODE ISLAND RAMS": "URI", "GEORGE WASHINGTON REVOLUTIONARIES": "GW",
        "FORDHAM RAMS": "FOR", "DUQUESNE DUKES": "DUQ",
        "TEMPLE OWLS": "TEM", "EAST CAROLINA PIRATES": "ECU",
        "TULSA GOLDEN HURRICANE": "TLSA", "NORTH TEXAS MEAN GREEN": "UNT",
        "UAB BLAZERS": "UAB", "UTSA ROADRUNNERS": "UTSA",
        "RICE OWLS": "RICE", "SOUTHERN MISS GOLDEN EAGLES": "USM",
        "CHARLOTTE 49ERS": "CLT", "FLORIDA ATLANTIC OWLS": "FAU",
        "MARSHALL THUNDERING HERD": "MRSH", "OLD DOMINION MONARCHS": "ODU",
        "WESTERN KENTUCKY HILLTOPPERS": "WKU",
        "MIDDLE TENNESSEE BLUE RAIDERS": "MTSU",
        "MONTANA STATE BOBCATS": "MTST", "MONTANA GRIZZLIES": "MONT",
        "NORTHERN IOWA PANTHERS": "UNI", "MISSOURI STATE BEARS": "MOST",
        "SOUTHERN ILLINOIS SALUKIS": "SIU", "INDIANA STATE SYCAMORES": "INST",
        "BRADLEY BRAVES": "BRAD", "EVANSVILLE PURPLE ACES": "EVAN",
        "VALPARAISO BEACONS": "VAL", "MURRAY STATE RACERS": "MUR",
        "BELMONT BRUINS": "BEL",
        # Mid-majors commonly on props boards
        "FURMAN PALADINS": "FUR", "CHARLESTON COUGARS": "COFC",
        "HOFSTRA PRIDE": "HOF", "STONY BROOK SEAWOLVES": "STBK",
        "VERMONT CATAMOUNTS": "UVM", "TOWSON TIGERS": "TOW",
        "DREXEL DRAGONS": "DREX", "NORTHEASTERN HUSKIES": "NE",
        "JAMES MADISON DUKES": "JMU", "LIBERTY FLAMES": "LIB",
        "COASTAL CAROLINA CHANTICLEERS": "CCU",
        "APPALACHIAN STATE MOUNTAINEERS": "APP",
        "SOUTH ALABAMA JAGUARS": "USA", "TROY TROJANS": "TROY",
        "GEORGIA STATE PANTHERS": "GAST", "TEXAS STATE BOBCATS": "TXST",
        "LOUISIANA RAGIN' CAJUNS": "ULL", "TEXAS-ARLINGTON MAVERICKS": "UTA",
        "UL MONROE WARHAWKS": "ULM", "SOUTHERN UNIVERSITY JAGUARS": "SOU",
        "GRAMBLING TIGERS": "GRAM", "JACKSON STATE TIGERS": "JKST",
        "ALABAMA A&M BULLDOGS": "AAMU", "ALABAMA STATE HORNETS": "ALST",
        "BETHUNE-COOKMAN WILDCATS": "BCU", "FLORIDA A&M RATTLERS": "FAMU",
        "NORFOLK STATE SPARTANS": "NORF", "NORTH CAROLINA A&T AGGIES": "NCAT",
        "HOWARD BISON": "HOW", "MORGAN STATE BEARS": "MORG",
        "COPPIN STATE EAGLES": "COPP", "DELAWARE STATE HORNETS": "DSU",
        "SOUTH CAROLINA STATE BULLDOGS": "SCST",
        "MARYLAND-EASTERN SHORE HAWKS": "UMES",
    }

    # Runtime cache for dynamic ESPN lookups (avoids repeated API calls)
    _team_abbr_cache: Dict[str, str] = {}

    def _normalize_team(self, team_abbr: str) -> str:
        """Normalize CBB team identifier to ESPN abbreviation.
        
        Handles:
        - Standard abbreviations (LOU, DUKE, etc.) — pass through
        - Ambiguous abbreviations (WASH → UW, OSU → OHST) — remap
        - Full team names from OddsAPI (Louisville Cardinals → LOU) — resolve
        """
        if not team_abbr:
            return "UNK"
        upper = team_abbr.upper().strip()
        
        # 1. Check ambiguous abbreviation remapping first
        if upper in self.CBB_TEAM_NORMALIZE:
            return self.CBB_TEAM_NORMALIZE[upper]
        
        # 2. If it looks like an abbreviation already (≤6 chars, no spaces), pass through
        if len(upper) <= 6 and " " not in upper:
            return upper
        
        # 3. Check full-name static mapping (OddsAPI full names)
        if upper in self.CBB_FULLNAME_TO_ABBR:
            return self.CBB_FULLNAME_TO_ABBR[upper]
        
        # 4. Check runtime cache (previously resolved via ESPN API)
        if upper in self._team_abbr_cache:
            return self._team_abbr_cache[upper]
        
        # 5. Try partial match on static mapping (handles minor naming differences)
        #    e.g., "LOUISVILLE" matches "LOUISVILLE CARDINALS"
        for full_name, abbr in self.CBB_FULLNAME_TO_ABBR.items():
            # Match if input starts with the school name (before mascot)
            if full_name.startswith(upper) or upper.startswith(full_name.split()[0]):
                self._team_abbr_cache[upper] = abbr
                return abbr
        
        # 6. Dynamic ESPN API lookup as last resort (cached for session)
        try:
            espn = ESPNCBBFetcher()
            team_id = espn.search_team(upper)
            if team_id:
                # Get the abbreviation from ESPN
                import urllib.request as _ur
                team_data = _fetch_json(f"{CBB_BASE}/teams/{team_id}")
                team_info = team_data.get("team", {})
                abbr = (team_info.get("abbreviation") or "").upper().strip()
                if abbr:
                    self._team_abbr_cache[upper] = abbr
                    print(f"  [TEAM RESOLVE] '{team_abbr}' → '{abbr}' (via ESPN API)")
                    return abbr
        except Exception:
            pass
        
        # 7. Fallback: return as-is (will create non-matching cache key, but won't crash)
        print(f"  [TEAM WARN] Could not normalize team: '{team_abbr}'")
        return upper

    def _make_key(self, player_name: str, team_abbr: Optional[str] = None) -> str:
        """Create CBB-specific cache key from player name and team.
        
        Key format: cbb_ncaam_{normalized_team}_{player_name}
        The 'ncaam' league qualifier prevents cross-sport collision.
        """
        name = player_name.lower().strip()
        name = re.sub(r"[^a-z\s]", "", name)
        name = "_".join(name.split())
        team = self._normalize_team(team_abbr) if team_abbr else "UNK"
        # Full namespace: sport_league_team_player
        key = f"cbb_ncaam_{team}_{name}"
        # Fail if any cross-sport context leaks in
        CROSS_SPORT_TOKENS = ['golf', 'nba', 'nfl', 'nhl', 'soccer', 'tennis', 'mlb']
        for token in CROSS_SPORT_TOKENS:
            # Only flag if the token appears as a standalone segment (not inside a name)
            if f"_{token}_" in key or key.startswith(f"{token}_"):
                print(f"[CBB CONTEXT ERROR] Cross-sport key generated: {key}")
                raise RuntimeError(f"[CBB CONTEXT ERROR] Cross-sport key generated: {key}")
        return key


# =============================================================================
# MAIN CBB DATA PROVIDER
# =============================================================================

class CBBDataProvider:
    """
    Main interface for CBB data.
    
    Combines:
    - ESPN API for live data
    - Local cache for historical stats
    """
    def __init__(self):
        self.espn = ESPNCBBFetcher()
        self.cache = CBBStatsCache()
        self._player_id_cache: Dict[str, str] = {}
        # Sport context assertion
        self._assert_cbb_context()

    def _assert_cbb_context(self):
        # Ensure all cache/data directories are CBB-specific
        if 'golf' in str(DATA_DIR).lower() or 'nba' in str(DATA_DIR).lower():
            raise RuntimeError(f"[CBB CONTEXT ERROR] Data directory contaminated: {DATA_DIR}")
        if 'golf' in str(CACHE_DIR).lower() or 'nba' in str(CACHE_DIR).lower():
            raise RuntimeError(f"[CBB CONTEXT ERROR] Cache directory contaminated: {CACHE_DIR}")
        # Check for cross-sport keys in cache
        for key in getattr(self.cache, 'cache', {}).keys():
            if 'golf' in key or 'nba' in key:
                print(f"[CBB CONTEXT WARNING] Cross-sport key detected in cache: {key}")
                raise RuntimeError(f"[CBB CONTEXT ERROR] Cross-sport key detected in cache: {key}")

    def get_todays_games(self) -> List[CBBGame]:
        """Get today's CBB games."""
        return self.espn.get_todays_games()

    def get_team_roster(self, team_query: str) -> List[CBBPlayer]:
        """Get a team's roster by name/abbr.

        This is a thin compatibility wrapper around ESPNCBBFetcher.
        `team_query` may be a team abbreviation (e.g., 'DUKE') or a
        display name substring (e.g., 'Duke').
        """
        team_id = self.espn.search_team(team_query)
        if not team_id:
            return []
        return self.espn.get_team_roster(team_id)
    
    def get_player_stats_by_name(self, player_name: str, team_abbr: Optional[str] = None) -> Optional[CBBPlayer]:
        """
        Get player stats by name.
        
        1. Check local cache
        2. Search ESPN roster for player ID
        3. Fetch stats from ESPN
        """
        # Check cache first
        cached = self.cache.get_player_stats(player_name, team_abbr)
        if cached and cached.get("games_played", 0) > 0:
            player = CBBPlayer(
                name=player_name,
                team_abbr=team_abbr or "",
                points_per_game=cached.get("points_avg", 0),
                rebounds_per_game=cached.get("rebounds_avg", 0),
                assists_per_game=cached.get("assists_avg", 0),
                three_pm_per_game=cached.get("three_pm_avg", 0),
                minutes_per_game=cached.get("minutes_avg", 0),
                games_played=cached.get("games_played", 0),
            )
            return player
        
        # Try to find player ID via team roster
        if team_abbr:
            team_id = self.espn.search_team(team_abbr)
            if team_id:
                roster = self.espn.get_team_roster(team_id)
                for p in roster:
                    if self._names_match(player_name, p.name):
                        # Found player, get full stats
                        full_stats = self.espn.get_player_stats(p.id)
                        if full_stats:
                            # Fetch game logs for variance calculation
                            game_logs = self.espn.get_player_game_logs(p.id, limit=15)
                            
                            # Cache stats AND game logs together
                            self.cache.set_player_stats(player_name, team_abbr, {
                                "points_avg": full_stats.points_per_game,
                                "rebounds_avg": full_stats.rebounds_per_game,
                                "assists_avg": full_stats.assists_per_game,
                                "three_pm_avg": full_stats.three_pm_per_game,
                                "minutes_avg": full_stats.minutes_per_game,
                                "games_played": full_stats.games_played,
                                "game_logs": game_logs,  # ← ADD GAME LOGS HERE
                            })
                            return full_stats
        
        return None
    
    def get_player_mean(self, player_name: str, stat: str, team_abbr: Optional[str] = None) -> Optional[float]:
        """Get player's average for a specific stat."""
        player = self.get_player_stats_by_name(player_name, team_abbr)
        
        if not player:
            return None
        
        stat_lower = stat.lower()
        
        if stat_lower in ("points", "pts"):
            return player.points_per_game
        elif stat_lower in ("rebounds", "reb"):
            return player.rebounds_per_game
        elif stat_lower in ("assists", "ast"):
            return player.assists_per_game
        elif stat_lower in ("3pm", "three_pointers", "threes"):
            return player.three_pm_per_game
        elif stat_lower in ("pra", "pts+reb+ast", "points_rebounds_assists"):
            return player.points_per_game + player.rebounds_per_game + player.assists_per_game
        elif stat_lower in ("pts+reb", "points_rebounds"):
            return player.points_per_game + player.rebounds_per_game
        elif stat_lower in ("pts+ast", "points_assists"):
            return player.points_per_game + player.assists_per_game
        elif stat_lower in ("reb+ast", "rebounds_assists"):
            return player.rebounds_per_game + player.assists_per_game
        elif stat_lower in ("steals", "stl"):
            return player.steals_per_game
        elif stat_lower in ("blocks", "blk"):
            return player.blocks_per_game
        elif stat_lower in ("turnovers", "to"):
            return player.turnovers_per_game
        
        return None

    def resolve_player_mean(
        self,
        player_name: str,
        stat: str,
        team_abbr: str,
        line: float,
    ) -> Dict[str, object]:
        """
        Resolve player mean with explicit sourcing.

        Priority (v2.0 contract):
          1) Manual override  -> mean_source=MANUAL, confidence_flag=OK
          2) ESPN (cached/live)-> mean_source=ESPN, confidence_flag=OK
          3) Fallback         -> mean_source=FALLBACK, confidence_flag=UNVERIFIED, mean=lambda=line

        Returns:
          {
            "mean": float,
            "mean_source": "MANUAL"|"ESPN"|"FALLBACK",
            "confidence_flag": "OK"|"UNVERIFIED"|"NO_DATA",
          }
        """

        stat_lower = (stat or "").lower()

        def _mean_from_cached(stats: Dict) -> Optional[float]:
            if not stats:
                return None
            if stat_lower in ("points", "pts"):
                return float(stats.get("points_avg", 0) or 0)
            if stat_lower in ("rebounds", "reb"):
                return float(stats.get("rebounds_avg", 0) or 0)
            if stat_lower in ("assists", "ast"):
                return float(stats.get("assists_avg", 0) or 0)
            if stat_lower in ("3pm", "three_pointers", "three_pointers_made", "threes"):
                return float(stats.get("three_pm_avg", 0) or 0)
            if stat_lower in ("pra", "pts+reb+ast", "points_rebounds_assists"):
                return float((stats.get("points_avg", 0) or 0) + (stats.get("rebounds_avg", 0) or 0) + (stats.get("assists_avg", 0) or 0))
            if stat_lower in ("pts+reb", "points_rebounds"):
                return float((stats.get("points_avg", 0) or 0) + (stats.get("rebounds_avg", 0) or 0))
            if stat_lower in ("pts+ast", "points_assists"):
                return float((stats.get("points_avg", 0) or 0) + (stats.get("assists_avg", 0) or 0))
            if stat_lower in ("reb+ast", "rebounds_assists"):
                return float((stats.get("rebounds_avg", 0) or 0) + (stats.get("assists_avg", 0) or 0))
            if stat_lower in ("steals", "stl"):
                return float(stats.get("steals_avg", 0) or 0)
            if stat_lower in ("blocks", "blk"):
                return float(stats.get("blocks_avg", 0) or 0)
            if stat_lower in ("turnovers", "to"):
                return float(stats.get("turnovers_avg", 0) or 0)
            return None

        # 1) Cache / override first (overrides take priority in cache.get_player_stats)
        cached = self.cache.get_player_stats(player_name, team_abbr)
        if cached and (cached.get("games_played", 0) or 0) > 0:
            mean = _mean_from_cached(cached)
            if mean is not None and mean > 0:
                mean_source = "MANUAL" if cached.get("manual") else "ESPN"
                return {
                    "mean": mean,
                    "mean_source": mean_source,
                    "confidence_flag": "OK",
                }

        # 2) Live ESPN (will cache if found)
        try:
            mean = self.get_player_mean(player_name, stat_lower, team_abbr)
            if mean is not None and mean > 0:
                return {
                    "mean": float(mean),
                    "mean_source": "ESPN",
                    "confidence_flag": "OK",
                }
        except Exception:
            pass

        # 3) Fallback (neutral)
        return {
            "mean": float(line),
            "mean_source": "FALLBACK",
            "confidence_flag": "UNVERIFIED",
        }
    
    def check_player_status(self, player_name: str, team_abbr: str) -> Tuple[bool, str]:
        """
        Check if player is active (injury gate).
        
        Returns: (is_active, status_string)
        """
        team_id = self.espn.search_team(team_abbr)
        if not team_id:
            return True, "UNKNOWN_TEAM"
        
        roster = self.espn.get_team_roster(team_id)
        for player in roster:
            if self._names_match(player_name, player.name):
                is_active = player.status.upper() in ("ACTIVE", "")
                return is_active, player.status
        
        # Player not found on roster
        return False, "NOT_ON_ROSTER"
    
    def verify_roster(self, team_abbr: str) -> List[str]:
        """Get list of active players for a team."""
        team_id = self.espn.search_team(team_abbr)
        if not team_id:
            return []
        
        roster = self.espn.get_team_roster(team_id)
        return [p.name for p in roster if p.status.upper() in ("ACTIVE", "")]
    
    def get_minutes_avg(self, player_name: str, team_abbr: str) -> Optional[float]:
        """Get player's minutes per game (for minutes gate)."""
        player = self.get_player_stats_by_name(player_name, team_abbr)
        if player:
            return player.minutes_per_game
        return None
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two player names match (fuzzy)."""
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Exact match
        if n1 == n2:
            return True
        
        # One contains the other
        if n1 in n2 or n2 in n1:
            return True
        
        # Last name match
        parts1 = n1.split()
        parts2 = n2.split()
        if parts1 and parts2 and parts1[-1] == parts2[-1]:
            # Same last name, check first initial
            if parts1[0][0] == parts2[0][0]:
                return True
        
        return False
    
    def set_player_override(self, player_name: str, team_abbr: str, 
                            points: float = 0, rebounds: float = 0, 
                            assists: float = 0, three_pm: float = 0,
                            minutes: float = 30, games: int = 10):
        """
        Manually set player averages when ESPN doesn't have data.
        
        Usage:
            provider.set_player_override("Cooper Flagg", "DUKE", points=18.5, rebounds=7.2, assists=3.1)
        """
        self.cache.set_override(player_name, team_abbr, {
            "points_avg": points,
            "rebounds_avg": rebounds,
            "assists_avg": assists,
            "three_pm_avg": three_pm,
            "minutes_avg": minutes,
            "games_played": games,
        })
    
    def list_overrides(self) -> Dict[str, dict]:
        """List all manual player overrides."""
        return self.cache.list_overrides()
    
    def bulk_set_overrides(self, overrides: List[Dict]):
        """
        Set multiple player overrides at once.
        
        Args:
            overrides: List of dicts with keys: name, team, points, rebounds, assists, three_pm
        
        Example:
            provider.bulk_set_overrides([
                {"name": "Cooper Flagg", "team": "DUKE", "points": 18.5, "rebounds": 7.2},
                {"name": "RJ Davis", "team": "UNC", "points": 16.5, "rebounds": 4.1},
            ])
        """
        for o in overrides:
            self.set_player_override(
                player_name=o.get("name", ""),
                team_abbr=o.get("team", ""),
                points=o.get("points", 0),
                rebounds=o.get("rebounds", 0),
                assists=o.get("assists", 0),
                three_pm=o.get("three_pm", 0),
                minutes=o.get("minutes", 30),
                games=o.get("games", 10),
            )


# =============================================================================
# STAT KEY MAPPING (borrowed from NBA)
# =============================================================================

CBB_STAT_KEYS = {
    # Core stats
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",
    "3pm": "3PM",
    "blocks": "BLK",
    "steals": "STL",
    "turnovers": "TO",
    
    # Combo stats
    "pts+reb+ast": ["PTS", "REB", "AST"],
    "pra": ["PTS", "REB", "AST"],
    "pts+reb": ["PTS", "REB"],
    "pts+ast": ["PTS", "AST"],
    "reb+ast": ["REB", "AST"],
}


# =============================================================================
# CLI FOR TESTING
# =============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("[CBB] DATA PROVIDER TEST")
    print("=" * 60)
    
    provider = CBBDataProvider()
    
    # Get today's games
    print("\n[1] Fetching today's CBB games from ESPN...")
    games = provider.get_todays_games()
    
    if games:
        print(f"\n✅ Found {len(games)} games:\n")
        for i, game in enumerate(games[:10], 1):
            rank_str = ""
            if game.away_rank:
                rank_str += f"#{game.away_rank} "
            rank_str += f"{game.away_abbr:5} @ "
            if game.home_rank:
                rank_str += f"#{game.home_rank} "
            rank_str += f"{game.home_abbr}"
            
            spread_str = f" (O/U: {game.total})" if game.total else ""
            print(f"  {i:2}. {rank_str}{spread_str}")
        if len(games) > 10:
            print(f"  ... and {len(games) - 10} more")
    else:
        print("\n[!] No games found for today")
    
    # Test team search
    print("\n[2] Testing team search...")
    for team in ["DUKE", "WOF", "SAM"]:
        team_id = provider.espn.search_team(team)
        print(f"  {team}: {team_id or 'Not found'}")
    
    print("\n✅ CBB Data Provider ready!")
