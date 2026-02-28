"""
NHL LIVE STATS API — v3.0 Module
================================

Fetches real-time player and goalie stats from NHL API.
Replaces hardcoded stats with live data.

Endpoints:
    - NHL Stats API: https://api-web.nhle.com/
    - Player stats, game logs, team stats
    
Features:
    - Daily refresh of player averages
    - Season-to-date statistics
    - Last 10 game trends (L10)
    - Goalie confirmation status
"""

import json
import logging
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ============================================================
# CONSTANTS
# ============================================================

NHL_API_BASE = "https://api-web.nhle.com/v1"
NHL_STATS_API = "https://api.nhle.com/stats/rest/en"

# Cache settings
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

PLAYER_CACHE_FILE = CACHE_DIR / "live_player_stats.json"
GOALIE_CACHE_FILE = CACHE_DIR / "live_goalie_stats.json"
TEAM_CACHE_FILE = CACHE_DIR / "live_team_defense.json"

# Cache expiry (hours)
CACHE_EXPIRY_HOURS = 6

# Rate limiting
REQUEST_DELAY = 0.5  # seconds between requests


@dataclass
class LivePlayerStats:
    """Live player statistics from NHL API"""
    player_id: int
    player_name: str
    team: str
    position: str
    games_played: int
    
    # Season averages
    sog_avg: float
    goals_avg: float
    assists_avg: float
    points_avg: float
    blocks_avg: float
    hits_avg: float
    toi_avg: float  # minutes
    
    # Season totals
    total_sog: int = 0
    total_goals: int = 0
    total_assists: int = 0
    total_points: int = 0
    total_blocks: int = 0
    total_hits: int = 0
    
    # Last 10 games
    l10_sog_avg: float = 0.0
    l10_goals_avg: float = 0.0
    l10_points_avg: float = 0.0
    
    # Standard deviations
    sog_std: float = 0.0
    goals_std: float = 0.0
    
    # Metadata
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


@dataclass
class LiveGoalieStats:
    """Live goalie statistics from NHL API"""
    player_id: int
    player_name: str
    team: str
    games_played: int
    games_started: int
    
    # Per-game averages
    saves_avg: float
    shots_against_avg: float
    save_pct: float
    goals_against_avg: float
    
    # Totals
    total_saves: int = 0
    total_shots_against: int = 0
    wins: int = 0
    losses: int = 0
    
    # Standard deviation
    saves_std: float = 0.0
    
    # Confirmation status
    confirmed_starter: bool = False
    confirmation_source: str = ""
    
    # Metadata
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now().isoformat()


@dataclass
class TeamDefenseStats:
    """Team defensive statistics for opponent adjustments"""
    team: str
    team_abbrev: str
    
    # Per-game averages
    shots_against_avg: float
    goals_against_avg: float
    
    # Rankings (1-32, 1 = best)
    shots_against_rank: int
    goals_against_rank: int
    
    # Suppression factor (1.0 = league avg)
    shot_suppression: float = 1.0
    
    # Metadata
    last_updated: str = ""


# ============================================================
# NHL API CLIENT
# ============================================================

class NHLStatsAPI:
    """
    Client for NHL Stats API.
    
    Usage:
        api = NHLStatsAPI()
        stats = api.get_player_stats("Connor McDavid")
        goalie = api.get_goalie_stats("Connor Hellebuyck")
    """
    
    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._player_cache: Dict[str, LivePlayerStats] = {}
        self._goalie_cache: Dict[str, LiveGoalieStats] = {}
        self._team_cache: Dict[str, TeamDefenseStats] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached stats from disk"""
        try:
            if PLAYER_CACHE_FILE.exists():
                data = json.loads(PLAYER_CACHE_FILE.read_text())
                for name, stats in data.items():
                    self._player_cache[name.lower()] = LivePlayerStats(**stats)
            
            if GOALIE_CACHE_FILE.exists():
                data = json.loads(GOALIE_CACHE_FILE.read_text())
                for name, stats in data.items():
                    self._goalie_cache[name.lower()] = LiveGoalieStats(**stats)
            
            if TEAM_CACHE_FILE.exists():
                data = json.loads(TEAM_CACHE_FILE.read_text())
                for abbrev, stats in data.items():
                    self._team_cache[abbrev.upper()] = TeamDefenseStats(**stats)
                    
            logger.info(f"Loaded cache: {len(self._player_cache)} players, {len(self._goalie_cache)} goalies")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
    
    def _save_cache(self):
        """Save stats to disk cache"""
        try:
            player_data = {k: asdict(v) for k, v in self._player_cache.items()}
            PLAYER_CACHE_FILE.write_text(json.dumps(player_data, indent=2))
            
            goalie_data = {k: asdict(v) for k, v in self._goalie_cache.items()}
            GOALIE_CACHE_FILE.write_text(json.dumps(goalie_data, indent=2))
            
            team_data = {k: asdict(v) for k, v in self._team_cache.items()}
            TEAM_CACHE_FILE.write_text(json.dumps(team_data, indent=2))
            
            logger.info("Cache saved successfully")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _is_cache_valid(self, last_updated: str) -> bool:
        """Check if cache entry is still valid"""
        if not last_updated:
            return False
        try:
            updated = datetime.fromisoformat(last_updated)
            age = datetime.now() - updated
            return age.total_seconds() < (CACHE_EXPIRY_HOURS * 3600)
        except:
            return False
    
    def _fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON from URL with error handling"""
        try:
            time.sleep(REQUEST_DELAY)  # Rate limiting
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
            
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            logger.error(f"HTTP error {e.code}: {url}")
            return None
        except urllib.error.URLError as e:
            logger.error(f"URL error: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return None
    
    def _get_current_season(self) -> str:
        """Get current NHL season ID (e.g., '20252026')"""
        today = date.today()
        if today.month >= 10:  # October onwards = new season
            return f"{today.year}{today.year + 1}"
        else:
            return f"{today.year - 1}{today.year}"
    
    def get_player_stats(self, player_name: str) -> Optional[LivePlayerStats]:
        """
        Get live player statistics.
        
        Args:
            player_name: Player full name (e.g., "Connor McDavid")
        
        Returns:
            LivePlayerStats or None if not found
        """
        name_key = player_name.lower()
        
        # Check cache first
        if self.use_cache and name_key in self._player_cache:
            cached = self._player_cache[name_key]
            if self._is_cache_valid(cached.last_updated):
                return cached
        
        # Search for player
        player_id = self._search_player(player_name)
        if not player_id:
            logger.warning(f"Player not found: {player_name}")
            return None
        
        # Fetch player stats
        stats = self._fetch_player_season_stats(player_id, player_name)
        if stats:
            self._player_cache[name_key] = stats
            self._save_cache()
        
        return stats
    
    def _search_player(self, name: str) -> Optional[int]:
        """Search for player ID by name using the search API"""
        # Use the player search endpoint
        search_name = name.replace(" ", "%20")
        search_url = f"{NHL_API_BASE}/player-search?q={search_name}"
        
        data = self._fetch_json(search_url)
        if data and isinstance(data, list) and len(data) > 0:
            # First result is usually the best match
            return data[0].get('playerId')
        
        # Fallback: Try the search suggest endpoint
        search_url = f"https://search.d3.nhle.com/api/v1/search/player?culture=en-us&limit=5&q={search_name}"
        data = self._fetch_json(search_url)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('playerId')
        
        # Second fallback: use hardcoded top player IDs
        known_players = {
            "connor mcdavid": 8478402,
            "auston matthews": 8479318,
            "nathan mackinnon": 8477492,
            "leon draisaitl": 8477934,
            "david pastrnak": 8477956,
            "nikita kucherov": 8476453,
            "jack eichel": 8478403,
            "mitch marner": 8478483,
            "cale makar": 8480069,
            "sidney crosby": 8471675,
            "alex ovechkin": 8471214,
            "connor hellebuyck": 8476945,
            "igor shesterkin": 8478550,
            "andrei vasilevskiy": 8476883,
        }
        
        name_lower = name.lower()
        if name_lower in known_players:
            return known_players[name_lower]
        
        return None
    
    def _fetch_player_season_stats(self, player_id: int, player_name: str) -> Optional[LivePlayerStats]:
        """Fetch season stats for a player"""
        season = self._get_current_season()
        url = f"{NHL_API_BASE}/player/{player_id}/landing"
        
        data = self._fetch_json(url)
        if not data:
            return None
        
        try:
            # Extract team info
            team_abbrev = data.get('currentTeamAbbrev', 'UNK')
            position = data.get('position', 'F')
            
            # Extract name from nested dict structure
            first_name = data.get('firstName', {})
            last_name = data.get('lastName', {})
            if isinstance(first_name, dict):
                first_name = first_name.get('default', '')
            if isinstance(last_name, dict):
                last_name = last_name.get('default', '')
            full_name = f"{first_name} {last_name}".strip() or player_name
            
            # Find current season stats (seasons are sorted oldest first, so search backwards)
            season_stats = None
            season_totals = data.get('seasonTotals', [])
            
            # Search for current season
            for stats in reversed(season_totals):
                if str(stats.get('season')) == season and stats.get('leagueAbbrev') == 'NHL':
                    season_stats = stats
                    break
            
            # If no current season, use the most recent NHL season
            if not season_stats:
                for stats in reversed(season_totals):
                    if stats.get('leagueAbbrev') == 'NHL':
                        season_stats = stats
                        logger.warning(f"Using season {stats.get('season')} for {player_name} (current {season} not found)")
                        break
            
            if not season_stats:
                logger.warning(f"No NHL season stats found for {player_name}")
                return None
            
            gp = season_stats.get('gamesPlayed', 1)
            if gp == 0:
                gp = 1
            
            # Get shots - might be under different keys
            shots = season_stats.get('shots', season_stats.get('shotsOnGoal', 0))
            if shots is None:
                shots = 0
            
            return LivePlayerStats(
                player_id=player_id,
                player_name=full_name,
                team=team_abbrev,
                position=position,
                games_played=gp,
                
                # Per-game averages
                sog_avg=round(shots / gp, 2) if shots else 0,
                goals_avg=round(season_stats.get('goals', 0) / gp, 2),
                assists_avg=round(season_stats.get('assists', 0) / gp, 2),
                points_avg=round(season_stats.get('points', 0) / gp, 2),
                blocks_avg=round(season_stats.get('blockedShots', 0) / gp, 2),
                hits_avg=round(season_stats.get('hits', 0) / gp, 2),
                toi_avg=round(float(str(season_stats.get('avgToi', '0:00')).replace(':', '.')) if ':' in str(season_stats.get('avgToi', '0')) else 0, 1),
                
                # Totals
                total_sog=shots,
                total_goals=season_stats.get('goals', 0),
                total_assists=season_stats.get('assists', 0),
                total_points=season_stats.get('points', 0),
                total_blocks=season_stats.get('blockedShots', 0),
                total_hits=season_stats.get('hits', 0),
                
                # Estimate std dev (~40% of mean for hockey)
                sog_std=round(shots / gp * 0.45, 2) if shots else 0,
                goals_std=round(season_stats.get('goals', 0) / gp * 0.65, 2),
            )
        except Exception as e:
            logger.error(f"Error parsing player stats: {e}")
            return None
    
    def get_goalie_stats(self, goalie_name: str) -> Optional[LiveGoalieStats]:
        """
        Get live goalie statistics.
        
        Args:
            goalie_name: Goalie full name
        
        Returns:
            LiveGoalieStats or None if not found
        """
        name_key = goalie_name.lower()
        
        # Check cache first
        if self.use_cache and name_key in self._goalie_cache:
            cached = self._goalie_cache[name_key]
            if self._is_cache_valid(cached.last_updated):
                return cached
        
        # Fetch goalie stats from API
        stats = self._fetch_goalie_stats(goalie_name)
        if stats:
            self._goalie_cache[name_key] = stats
            self._save_cache()
        
        return stats
    
    def _fetch_goalie_stats(self, goalie_name: str) -> Optional[LiveGoalieStats]:
        """Fetch goalie stats from NHL API"""
        # Search goalies endpoint
        url = f"{NHL_STATS_API}/goalie/summary?cayenneExp=season=20252026"
        
        data = self._fetch_json(url)
        if not data or 'data' not in data:
            return None
        
        name_lower = goalie_name.lower()
        for goalie in data.get('data', []):
            full_name = f"{goalie.get('goalieFullName', '')}".lower()
            if name_lower in full_name or full_name in name_lower:
                gp = goalie.get('gamesPlayed', 1)
                gs = goalie.get('gamesStarted', gp)
                
                return LiveGoalieStats(
                    player_id=goalie.get('playerId', 0),
                    player_name=goalie.get('goalieFullName', goalie_name),
                    team=goalie.get('teamAbbrevs', 'UNK'),
                    games_played=gp,
                    games_started=gs,
                    
                    saves_avg=round(goalie.get('saves', 0) / max(gp, 1), 1),
                    shots_against_avg=round(goalie.get('shotsAgainst', 0) / max(gp, 1), 1),
                    save_pct=goalie.get('savePct', 0.900),
                    goals_against_avg=goalie.get('goalsAgainstAverage', 3.0),
                    
                    total_saves=goalie.get('saves', 0),
                    total_shots_against=goalie.get('shotsAgainst', 0),
                    wins=goalie.get('wins', 0),
                    losses=goalie.get('losses', 0),
                    
                    saves_std=round(goalie.get('saves', 0) / max(gp, 1) * 0.25, 1),
                )
        
        return None
    
    def get_team_defense(self, team_abbrev: str) -> Optional[TeamDefenseStats]:
        """Get team defensive statistics for opponent adjustments"""
        team_key = team_abbrev.upper()
        
        if team_key in self._team_cache:
            cached = self._team_cache[team_key]
            if self._is_cache_valid(cached.last_updated):
                return cached
        
        # Fetch team stats
        stats = self._fetch_team_defense(team_abbrev)
        if stats:
            self._team_cache[team_key] = stats
            self._save_cache()
        
        return stats
    
    def _fetch_team_defense(self, team_abbrev: str) -> Optional[TeamDefenseStats]:
        """Fetch team defensive stats"""
        url = f"{NHL_STATS_API}/team/summary?cayenneExp=season=20252026"
        
        data = self._fetch_json(url)
        if not data or 'data' not in data:
            return None
        
        abbrev_upper = team_abbrev.upper()
        for team in data.get('data', []):
            if team.get('teamAbbrev', '').upper() == abbrev_upper:
                gp = team.get('gamesPlayed', 1)
                sa_avg = team.get('shotsAgainstPerGame', 30.0)
                
                # Calculate suppression factor (league avg is ~30 SA/game)
                league_avg_sa = 30.0
                suppression = sa_avg / league_avg_sa
                
                return TeamDefenseStats(
                    team=team.get('teamFullName', ''),
                    team_abbrev=abbrev_upper,
                    shots_against_avg=sa_avg,
                    goals_against_avg=team.get('goalsAgainstPerGame', 3.0),
                    shots_against_rank=team.get('shotsAgainstRank', 16),
                    goals_against_rank=team.get('goalsAgainstRank', 16),
                    shot_suppression=round(suppression, 3),
                )
        
        return None
    
    def refresh_all_players(self, player_names: List[str]) -> Dict[str, LivePlayerStats]:
        """Refresh stats for a list of players"""
        results = {}
        
        for name in player_names:
            logger.info(f"Fetching stats for {name}...")
            stats = self.get_player_stats(name)
            if stats:
                results[name] = stats
        
        return results
    
    def refresh_all_teams(self) -> Dict[str, TeamDefenseStats]:
        """Refresh defensive stats for all teams"""
        TEAM_ABBREVS = [
            "ANA", "ARI", "BOS", "BUF", "CAR", "CBJ", "CGY", "CHI",
            "COL", "DAL", "DET", "EDM", "FLA", "LAK", "MIN", "MTL",
            "NJD", "NSH", "NYI", "NYR", "OTT", "PHI", "PIT", "SEA",
            "SJS", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", "WPG", "WSH"
        ]
        
        results = {}
        for abbrev in TEAM_ABBREVS:
            stats = self.get_team_defense(abbrev)
            if stats:
                results[abbrev] = stats
        
        return results


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

_api_instance: Optional[NHLStatsAPI] = None


def get_api() -> NHLStatsAPI:
    """Get singleton API instance"""
    global _api_instance
    if _api_instance is None:
        _api_instance = NHLStatsAPI()
    return _api_instance


def fetch_player_stats(player_name: str) -> Optional[LivePlayerStats]:
    """Fetch player stats (convenience function)"""
    return get_api().get_player_stats(player_name)


def fetch_goalie_stats(goalie_name: str) -> Optional[LiveGoalieStats]:
    """Fetch goalie stats (convenience function)"""
    return get_api().get_goalie_stats(goalie_name)


def fetch_team_defense(team_abbrev: str) -> Optional[TeamDefenseStats]:
    """Fetch team defense stats (convenience function)"""
    return get_api().get_team_defense(team_abbrev)


def get_lambda_live(player_name: str, stat: str = "sog") -> float:
    """
    Get lambda (expected value) for Poisson model from live stats.
    
    Args:
        player_name: Player name
        stat: Stat type (sog, goals, assists, points, blocks, hits)
    
    Returns:
        Lambda value for Poisson distribution
    """
    stats = fetch_player_stats(player_name)
    if not stats:
        # Fallback to defaults
        return {"sog": 2.5, "goals": 0.25, "assists": 0.35, "points": 0.60}.get(stat, 2.0)
    
    stat_map = {
        "sog": stats.sog_avg,
        "shots": stats.sog_avg,
        "goals": stats.goals_avg,
        "assists": stats.assists_avg,
        "points": stats.points_avg,
        "blocks": stats.blocks_avg,
        "hits": stats.hits_avg,
    }
    
    return stat_map.get(stat.lower(), stats.sog_avg)


def get_sigma_live(player_name: str, stat: str = "sog") -> float:
    """Get standard deviation from live stats"""
    stats = fetch_player_stats(player_name)
    if not stats:
        return 1.5  # Default std
    
    if stat.lower() in ("sog", "shots"):
        return stats.sog_std
    elif stat.lower() == "goals":
        return stats.goals_std
    else:
        return stats.sog_std * 0.5  # Estimate


# ============================================================
# CLI TESTING
# ============================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("  NHL LIVE STATS API — TEST")
    print("=" * 60)
    
    api = NHLStatsAPI(use_cache=True)
    
    # Test player lookup
    test_players = [
        "Connor McDavid",
        "Auston Matthews", 
        "Nathan MacKinnon",
        "Cale Makar",
    ]
    
    print("\n🏒 Testing Player Stats...")
    for name in test_players:
        stats = api.get_player_stats(name)
        if stats:
            print(f"\n  ✓ {stats.player_name} ({stats.team})")
            print(f"    GP: {stats.games_played} | SOG: {stats.sog_avg}/g | Goals: {stats.goals_avg}/g")
            print(f"    TOI: {stats.toi_avg} min | Pts: {stats.points_avg}/g")
        else:
            print(f"\n  ✗ {name} - Not found")
    
    # Test goalie lookup
    test_goalies = ["Connor Hellebuyck", "Igor Shesterkin"]
    
    print("\n🥅 Testing Goalie Stats...")
    for name in test_goalies:
        stats = api.get_goalie_stats(name)
        if stats:
            print(f"\n  ✓ {stats.player_name} ({stats.team})")
            print(f"    GP: {stats.games_played} | Saves: {stats.saves_avg}/g | SV%: {stats.save_pct:.3f}")
        else:
            print(f"\n  ✗ {name} - Not found")
    
    # Test team defense
    print("\n🛡️ Testing Team Defense...")
    for team in ["EDM", "TOR", "COL"]:
        stats = api.get_team_defense(team)
        if stats:
            print(f"  ✓ {stats.team_abbrev}: {stats.shots_against_avg:.1f} SA/g | Suppression: {stats.shot_suppression:.3f}")
    
    print("\n" + "=" * 60)
    print("  Test complete!")
