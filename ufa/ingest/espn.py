"""
ESPN Data Fetcher - Real NFL rosters and stats from ESPN's public APIs.

Fetches verified:
- Team rosters with depth chart positions
- Player season/game stats
- Injury status and designations
- Weekly matchup data
"""

import json
import ssl
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


# SSL context for Python 3.14 compatibility
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from URL using urllib."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


@dataclass
class PlayerInfo:
    """Verified player information from ESPN."""
    id: str
    name: str
    team: str
    team_abbr: str
    position: str
    jersey: str
    status: str  # Active, Injured Reserve, Out, Questionable, etc.
    depth_chart_order: int = 1
    
    # Season stats
    pass_yards: float = 0.0
    pass_tds: float = 0.0
    rush_yards: float = 0.0
    rush_tds: float = 0.0
    receptions: float = 0.0
    rec_yards: float = 0.0
    rec_tds: float = 0.0
    
    # Per-game averages
    games_played: int = 0
    pass_ypg: float = 0.0
    rush_ypg: float = 0.0
    rec_ypg: float = 0.0
    rec_pg: float = 0.0


@dataclass
class TeamInfo:
    """Team information from ESPN."""
    id: str
    name: str
    abbr: str
    record: str = ""
    
    # Defensive rankings (1 = best, 32 = worst)
    rush_def_rank: int = 16
    pass_def_rank: int = 16
    points_allowed_rank: int = 16


@dataclass 
class GameInfo:
    """Game/matchup information."""
    id: str
    week: int
    home_team: str
    away_team: str
    date: str
    status: str  # pre, in, post


class ESPNFetcher:
    """Fetches real NFL data from ESPN's public APIs."""
    
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
    CORE_URL = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
    
    # Team ID mapping
    TEAM_IDS = {
        "ARI": "22", "ATL": "1", "BAL": "33", "BUF": "2",
        "CAR": "29", "CHI": "3", "CIN": "4", "CLE": "5",
        "DAL": "6", "DEN": "7", "DET": "8", "GB": "9",
        "HOU": "34", "IND": "11", "JAX": "30", "KC": "12",
        "LAC": "24", "LAR": "14", "LV": "13", "MIA": "15",
        "MIN": "16", "NE": "17", "NO": "18", "NYG": "19",
        "NYJ": "20", "PHI": "21", "PIT": "23", "SEA": "26",
        "SF": "25", "TB": "27", "TEN": "10", "WAS": "28"
    }
    
    POSITION_PRIORITY = {
        "QB": 1, "RB": 2, "WR": 3, "TE": 4, "K": 5
    }
    
    def __init__(self, season: int = 2025):
        self.season = season
        self._cache: dict = {}
        self._leaders_cache: dict = {}
    
    def close(self):
        """Close the fetcher (no-op for urllib)."""
        pass
    
    def _get_all_leaders(self) -> dict[str, dict]:
        """Fetch and cache all league leaders with real stats."""
        if self._leaders_cache:
            return self._leaders_cache
        
        url = f"{self.CORE_URL}/seasons/{self.season}/types/2/leaders"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error fetching leaders: {e}")
            return {}
        
        # Build lookup by player name -> stats
        for cat in data.get('categories', []):
            cat_name = cat.get('name', '')
            
            for leader in cat.get('leaders', []):
                athlete_ref = leader.get('athlete', {}).get('$ref', '')
                team_ref = leader.get('team', {}).get('$ref', '')
                value = leader.get('value', 0)
                
                if not athlete_ref:
                    continue
                
                # Fetch athlete info
                try:
                    athlete = _fetch_json(athlete_ref)
                    name = athlete.get('displayName', '')
                    player_id = athlete.get('id', '')
                    
                    # Get team abbr
                    team_abbr = ""
                    if team_ref:
                        team_data = _fetch_json(team_ref)
                        team_abbr = team_data.get('abbreviation', '')
                    
                    if name not in self._leaders_cache:
                        self._leaders_cache[name] = {
                            'id': player_id,
                            'team': team_abbr,
                            'stats': {}
                        }
                    
                    self._leaders_cache[name]['stats'][cat_name] = value
                    
                except Exception:
                    continue
        
        return self._leaders_cache
    
    def get_team_roster(self, team_abbr: str) -> list[PlayerInfo]:
        """
        Fetch full roster for a team with stats from current season.
        
        Args:
            team_abbr: Team abbreviation (e.g., 'PIT', 'CLE')
            
        Returns:
            List of PlayerInfo objects
        """
        team_id = self.TEAM_IDS.get(team_abbr.upper())
        if not team_id:
            raise ValueError(f"Unknown team: {team_abbr}")
        
        # Use the season-specific roster endpoint
        url = f"{self.BASE_URL}/teams/{team_id}/roster?season={self.season}"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error fetching roster for {team_abbr}: {e}")
            return []
        
        players = []
        team_name = data.get("team", {}).get("displayName", team_abbr)
        
        for group in data.get("athletes", []):
            position_group = group.get("position", "")
            
            for athlete in group.get("items", []):
                player = self._parse_player(athlete, team_abbr, team_name, position_group)
                if player:
                    players.append(player)
        
        # Now fetch actual season stats for key players
        self._enrich_with_season_stats(players, team_abbr)
        
        return players
    
    def _enrich_with_season_stats(self, players: list[PlayerInfo], team_abbr: str):
        """Fetch and add season stats for starters from gamelog endpoint."""
        # Only fetch stats for starters (depth_chart_order <= 2)
        starters = [p for p in players 
                    if p.position in ["QB", "RB", "WR", "TE"] 
                    and p.depth_chart_order <= 2]
        
        for player in starters[:12]:  # Max 12 players to avoid timeout
            try:
                stats = self._get_player_season_totals(player.id)
                if stats:
                    player.pass_yards = stats.get("pass_yards", 0)
                    player.pass_tds = stats.get("pass_tds", 0)
                    player.rush_yards = stats.get("rush_yards", 0)
                    player.rush_tds = stats.get("rush_tds", 0)
                    player.receptions = stats.get("receptions", 0)
                    player.rec_yards = stats.get("rec_yards", 0)
                    player.rec_tds = stats.get("rec_tds", 0)
                    player.games_played = stats.get("games", 0)
            except Exception:
                pass
    
    def _get_player_season_totals(self, player_id: str) -> dict:
        """Get season totals from gamelog endpoint."""
        url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/gamelog"
        
        data = _fetch_json(url)
        if not data:
            return {}
        
        stats = {}
        labels = data.get("labels", [])
        
        # Navigate to season totals: seasonTypes[0].categories[0].totals
        for st in data.get("seasonTypes", []):
            if "Regular" not in st.get("displayName", ""):
                continue
            
            for cat in st.get("categories", []):
                totals = cat.get("totals", [])
                events = cat.get("events", [])
                stats["games"] = max(stats.get("games", 0), len(events))
                
                # Map totals to labels - labels are in order for the stat categories
                # REC, TGTS, YDS(rec), AVG, TD(rec), LNG, CAR, YDS(rush), AVG, LNG, TD(rush)...
                for i, val in enumerate(totals):
                    if i >= len(labels):
                        break
                    
                    label = labels[i].upper()
                    
                    # Convert to float
                    try:
                        val = float(str(val).replace(",", ""))
                    except:
                        continue
                    
                    # Handle duplicate labels by position
                    if label == "REC":
                        stats["receptions"] = val
                    elif label == "CAR":
                        stats["rush_attempts"] = val
                    elif label == "CMP":
                        stats["completions"] = val
                    elif label == "ATT":
                        stats["pass_attempts"] = val
                    elif label == "YDS":
                        # First YDS is receiving/passing, second is rushing
                        if "rec_yards" not in stats and "pass_yards" not in stats:
                            # Determine by position context
                            if stats.get("receptions", 0) > 0:
                                stats["rec_yards"] = val
                            elif stats.get("completions", 0) > 0:
                                stats["pass_yards"] = val
                            else:
                                stats["rec_yards"] = val  # default to receiving
                        elif "rush_yards" not in stats:
                            stats["rush_yards"] = val
                    elif label == "TD":
                        # First TD is receiving/passing, subsequent is rushing
                        if "rec_tds" not in stats and "pass_tds" not in stats:
                            if stats.get("receptions", 0) > 0:
                                stats["rec_tds"] = val
                            elif stats.get("completions", 0) > 0:
                                stats["pass_tds"] = val
                            else:
                                stats["rec_tds"] = val
                        elif "rush_tds" not in stats:
                            stats["rush_tds"] = val
        
        return stats
    
    def get_team_season_stats(self, team_abbr: str) -> list[PlayerInfo]:
        """
        Get all players with season stats for a team.
        Fetches roster then enriches with gamelog stats.
        """
        team_abbr = team_abbr.upper()
        roster = self.get_team_roster(team_abbr)
        
        # Filter to players with stats
        players = [p for p in roster if p.pass_yards > 0 or p.rush_yards > 0 or p.rec_yards > 0]
        
        # Calculate per-game averages
        for player in players:
            games = max(player.games_played, 1)
            player.pass_ypg = player.pass_yards / games
            player.rush_ypg = player.rush_yards / games
            player.rec_ypg = player.rec_yards / games
            player.rec_pg = player.receptions / games
        
        return players
    
    def get_player_stats(self, player_id: str) -> dict:
        """Fetch detailed stats for a specific player."""
        url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/stats"
        
        try:
            return _fetch_json(url)
        except Exception as e:
            print(f"Error fetching stats for player {player_id}: {e}")
            return {}
    
    def get_season_leaders(self, stat_type: str = "passing") -> list[dict]:
        """
        Get league leaders for a stat category.
        
        Args:
            stat_type: One of 'passingYards', 'rushingYards', 'receivingYards', 
                       'receptions', 'passingTouchdowns', 'rushingTouchdowns', etc.
            
        Returns:
            List of player stat dicts
        """
        url = f"{self.CORE_URL}/seasons/{self.season}/types/2/leaders"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error fetching leaders: {e}")
            return []
        
        # Map common names to API names
        stat_map = {
            "passing": "passingYards",
            "rushing": "rushingYards", 
            "receiving": "receivingYards",
            "receptions": "receptions",
        }
        stat_key = stat_map.get(stat_type.lower(), stat_type)
        
        leaders = []
        for category in data.get("categories", []):
            if category.get("name", "") == stat_key:
                for leader in category.get("leaders", []):
                    athlete_ref = leader.get("athlete", {}).get("$ref", "")
                    team_ref = leader.get("team", {}).get("$ref", "")
                    
                    name = ""
                    team_abbr = ""
                    player_id = ""
                    
                    if athlete_ref:
                        try:
                            athlete = _fetch_json(athlete_ref)
                            name = athlete.get("displayName", "")
                            player_id = athlete.get("id", "")
                        except:
                            continue
                    
                    if team_ref:
                        try:
                            team_data = _fetch_json(team_ref)
                            team_abbr = team_data.get("abbreviation", "")
                        except:
                            pass
                    
                    leaders.append({
                        "id": player_id,
                        "name": name,
                        "team": team_abbr,
                        "value": leader.get("value", 0),
                        "stat": leader.get("displayValue", "")
                    })
        
        return leaders
    
    def get_player_gamelog(self, player_id: str, limit: int = 5) -> list[dict]:
        """
        Get recent game-by-game stats for a player.
        
        Args:
            player_id: ESPN player ID
            limit: Number of recent games to fetch
            
        Returns:
            List of game stat dicts
        """
        full_url = f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}/gamelog?season={self.season}"
        
        try:
            data = _fetch_json(full_url)
        except Exception as e:
            print(f"Error fetching gamelog for {player_id}: {e}")
            return []
        
        # Consolidate per-game stats across categories by eventId
        from ufa.ingest.stat_map import ESPN_NFL_LABEL_MAP, ESPN_LABEL_SYNONYMS

        season_types = data.get("seasonTypes", [])
        by_event: dict[str, dict] = {}

        for st in season_types:
            for cat in st.get("categories", []):
                cat_name = cat.get("name", "").lower() or cat.get("displayName", "").lower()
                events = cat.get("events", [])
                labels = cat.get("labels", [])

                for event in events:
                    ev_id = str(event.get("eventId", event.get("id", "")))
                    if not ev_id:
                        # Fallback: build a composite key
                        ev_id = f"wk{event.get('week', 0)}_{event.get('opponent', {}).get('abbreviation', '')}_{event.get('gameDate', '')}"

                    entry = by_event.setdefault(ev_id, {
                        "week": event.get("week", 0),
                        "opponent": event.get("opponent", {}).get("abbreviation", ""),
                        "homeAway": event.get("homeAway", ""),
                        "result": event.get("gameResult", ""),
                        "date": event.get("gameDate", ""),
                        "stats": {}
                    })

                    # Map stats using labels anchored to category
                    raw_stats = event.get("stats", [])
                    for i, raw_val in enumerate(raw_stats):
                        if i >= len(labels):
                            break
                        raw_label = str(labels[i]).upper()
                        # Normalize label synonyms
                        norm_label = ESPN_LABEL_SYNONYMS.get(raw_label, raw_label)

                        key = ESPN_NFL_LABEL_MAP.get((cat_name, norm_label))
                        if not key:
                            # Skip labels we don't currently track
                            continue

                        # Convert value to float when possible
                        try:
                            val = float(str(raw_val).replace(",", ""))
                        except Exception:
                            continue

                        entry["stats"][key] = val

        # Produce sorted consolidated games and apply limit
        consolidated = list(by_event.values())
        consolidated.sort(key=lambda g: (g.get("week", 0), g.get("date", "")))

        return consolidated[-limit:]
    
    def search_player(self, name: str) -> Optional[dict]:
        """
        Search for a player by name and get their ESPN ID and basic info.
        
        Args:
            name: Player name to search
            
        Returns:
            Dict with id, name, team, position
        """
        from urllib.parse import quote
        encoded_name = quote(name)
        url = f"https://site.api.espn.com/apis/common/v3/search?query={encoded_name}&limit=5&mode=prefix&type=player&sport=football&league=nfl"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error searching for {name}: {e}")
            return None
        
        # Find NFL players in results
        for group in data.get("groups", []):
            if group.get("displayName") == "Athletes":
                for item in group.get("items", []):
                    player_name = item.get("displayName", "")
                    if name.lower() in player_name.lower():
                        return {
                            "id": item.get("id", ""),
                            "name": player_name,
                            "team": item.get("description", "").split(" - ")[0] if item.get("description") else "",
                            "position": item.get("description", "").split(" - ")[-1] if item.get("description") else ""
                        }
        
        return None
    
    def get_player_stats_by_name(self, player_name: str) -> Optional[PlayerInfo]:
        """
        Get season stats for a specific player by name.
        Uses search + athlete endpoint.
        """
        # First search for player
        search_result = self.search_player(player_name)
        if not search_result:
            return None
        
        player_id = search_result.get("id")
        if not player_id:
            return None
        
        # Get full athlete data
        url = f"https://site.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{player_id}?season={self.season}"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error fetching {player_name} stats: {e}")
            return None
        
        athlete = data.get("athlete", {})
        team = athlete.get("team", {})
        
        player = PlayerInfo(
            id=str(athlete.get("id", "")),
            name=athlete.get("displayName", player_name),
            team=team.get("displayName", ""),
            team_abbr=team.get("abbreviation", ""),
            position=athlete.get("position", {}).get("abbreviation", ""),
            jersey=str(athlete.get("jersey", "")),
            status="Active"
        )
        
        # Parse statistics from splits
        stats = data.get("athlete", {}).get("statsSummary", {}).get("statistics", [])
        for stat in stats:
            stat_name = stat.get("name", "")
            value = stat.get("value", 0)
            
            if stat_name == "passingYards":
                player.pass_yards = value
            elif stat_name == "passingTouchdowns":
                player.pass_tds = value
            elif stat_name == "rushingYards":
                player.rush_yards = value
            elif stat_name == "rushingTouchdowns":
                player.rush_tds = value
            elif stat_name == "receptions":
                player.receptions = value
            elif stat_name == "receivingYards":
                player.rec_yards = value
            elif stat_name == "receivingTouchdowns":
                player.rec_tds = value
        
        return player
    
    def get_week_schedule(self, week: Optional[int] = None, season: int = 2024) -> list[GameInfo]:
        """
        Fetch games for a specific week.
        
        Args:
            week: NFL week number (1-18). None = current week.
            season: NFL season year
            
        Returns:
            List of GameInfo objects
        """
        url = f"{self.BASE_URL}/scoreboard?seasontype=2"
        if week:
            url += f"&week={week}"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error fetching schedule: {e}")
            return []
        
        games = []
        for event in data.get("events", []):
            game = self._parse_game(event)
            if game:
                games.append(game)
        
        return games
    
    def get_team_stats(self, team_abbr: str) -> TeamInfo:
        """Fetch team statistics including defensive rankings."""
        team_id = self.TEAM_IDS.get(team_abbr.upper())
        if not team_id:
            raise ValueError(f"Unknown team: {team_abbr}")
        
        url = f"{self.BASE_URL}/teams/{team_id}"
        
        try:
            data = _fetch_json(url)
        except Exception as e:
            print(f"Error fetching team stats for {team_abbr}: {e}")
            return TeamInfo(id=team_id, name=team_abbr, abbr=team_abbr)
        
        team_data = data.get("team", {})
        
        return TeamInfo(
            id=team_id,
            name=team_data.get("displayName", team_abbr),
            abbr=team_abbr,
            record=team_data.get("record", {}).get("items", [{}])[0].get("summary", "")
        )
    
    def get_starters(self, team_abbr: str) -> dict[str, PlayerInfo]:
        """
        Get verified starters for each position.
        
        Returns dict like {"QB": PlayerInfo, "RB1": PlayerInfo, ...}
        """
        roster = self.get_team_roster(team_abbr)
        
        starters: dict[str, PlayerInfo] = {}
        position_counts: dict[str, int] = {}
        
        # Sort by depth chart order
        roster.sort(key=lambda p: (
            self.POSITION_PRIORITY.get(p.position, 99),
            p.depth_chart_order
        ))
        
        for player in roster:
            if player.status not in ["Active", "Questionable", "Probable"]:
                continue
            
            pos = player.position
            if pos not in position_counts:
                position_counts[pos] = 0
            
            position_counts[pos] += 1
            count = position_counts[pos]
            
            # Only keep starters (first at position) or key backups
            if pos == "QB" and count == 1:
                starters["QB"] = player
            elif pos == "RB" and count <= 2:
                starters[f"RB{count}"] = player
            elif pos == "WR" and count <= 3:
                starters[f"WR{count}"] = player
            elif pos == "TE" and count == 1:
                starters["TE"] = player
        
        return starters
    
    def get_injury_report(self, team_abbr: str) -> list[PlayerInfo]:
        """Get players on injury report for a team."""
        roster = self.get_team_roster(team_abbr)
        
        injured = [
            p for p in roster
            if p.status in ["Out", "Injured Reserve", "Doubtful", "Questionable", "Probable"]
        ]
        
        return injured
    
    def _parse_player(self, athlete: dict, team_abbr: str, team_name: str, position_group: str) -> Optional[PlayerInfo]:
        """Parse ESPN athlete JSON into PlayerInfo."""
        try:
            player_id = athlete.get("id", "")
            full_name = athlete.get("fullName", athlete.get("displayName", "Unknown"))
            
            # Get position from athlete data or fallback to group
            position = athlete.get("position", {}).get("abbreviation", position_group)
            
            # Get injury status
            status = "Active"
            injuries = athlete.get("injuries", [])
            if injuries:
                status = injuries[0].get("status", "Active")
            
            # Get jersey number
            jersey = athlete.get("jersey", "")
            
            # Get depth chart order if available
            depth = athlete.get("depthChartOrder", 1)
            
            player = PlayerInfo(
                id=player_id,
                name=full_name,
                team=team_name,
                team_abbr=team_abbr.upper(),
                position=position,
                jersey=jersey,
                status=status,
                depth_chart_order=depth
            )
            
            # Parse stats if available
            stats = athlete.get("statistics", {})
            if stats:
                self._add_player_stats(player, stats)
            
            return player
            
        except Exception as e:
            print(f"Error parsing player: {e}")
            return None
    
    def _add_player_stats(self, player: PlayerInfo, stats: dict):
        """Add season stats to player from ESPN stats object."""
        # ESPN stats format varies, handle common patterns
        splits = stats.get("splits", {})
        categories = splits.get("categories", [])
        
        for cat in categories:
            cat_name = cat.get("name", "")
            stat_list = cat.get("stats", [])
            
            for stat in stat_list:
                name = stat.get("name", "")
                value = stat.get("value", 0)
                
                if cat_name == "passing":
                    if name == "passingYards":
                        player.pass_yards = value
                    elif name == "passingTouchdowns":
                        player.pass_tds = value
                elif cat_name == "rushing":
                    if name == "rushingYards":
                        player.rush_yards = value
                    elif name == "rushingTouchdowns":
                        player.rush_tds = value
                elif cat_name == "receiving":
                    if name == "receptions":
                        player.receptions = value
                    elif name == "receivingYards":
                        player.rec_yards = value
                    elif name == "receivingTouchdowns":
                        player.rec_tds = value
                elif cat_name == "general":
                    if name == "gamesPlayed":
                        player.games_played = int(value)
        
        # Calculate per-game averages
        if player.games_played > 0:
            player.pass_ypg = player.pass_yards / player.games_played
            player.rush_ypg = player.rush_yards / player.games_played
            player.rec_ypg = player.rec_yards / player.games_played
            player.rec_pg = player.receptions / player.games_played
    
    def _parse_game(self, event: dict) -> Optional[GameInfo]:
        """Parse ESPN event JSON into GameInfo."""
        try:
            game_id = event.get("id", "")
            
            competitions = event.get("competitions", [])
            if not competitions:
                return None
            
            comp = competitions[0]
            competitors = comp.get("competitors", [])
            
            home_team = ""
            away_team = ""
            
            for team in competitors:
                abbr = team.get("team", {}).get("abbreviation", "")
                if team.get("homeAway") == "home":
                    home_team = abbr
                else:
                    away_team = abbr
            
            # Get week from season info
            week = event.get("week", {}).get("number", 0)
            
            # Get game status
            status_type = event.get("status", {}).get("type", {}).get("name", "pre")
            
            # Get date
            date_str = event.get("date", "")
            
            return GameInfo(
                id=game_id,
                week=week,
                home_team=home_team,
                away_team=away_team,
                date=date_str,
                status=status_type
            )
            
        except Exception as e:
            print(f"Error parsing game: {e}")
            return None


def fetch_game_players(home_team: str, away_team: str) -> dict[str, list[PlayerInfo]]:
    """
    Convenience function to fetch rosters for both teams in a matchup.
    
    Args:
        home_team: Home team abbreviation
        away_team: Away team abbreviation
        
    Returns:
        Dict with team abbrs as keys and player lists as values
    """
    fetcher = ESPNFetcher()
    try:
        return {
            home_team: fetcher.get_team_roster(home_team),
            away_team: fetcher.get_team_roster(away_team)
        }
    finally:
        fetcher.close()


def get_verified_starters_for_games(games: list[tuple[str, str]]) -> dict[str, dict[str, PlayerInfo]]:
    """
    Get verified starters for multiple games.
    
    Args:
        games: List of (away_team, home_team) tuples
        
    Returns:
        Dict with team abbrs as keys and starter dicts as values
    """
    fetcher = ESPNFetcher()
    result = {}
    
    try:
        teams = set()
        for away, home in games:
            teams.add(away)
            teams.add(home)
        
        for team in teams:
            print(f"Fetching {team} roster...")
            result[team] = fetcher.get_starters(team)
    finally:
        fetcher.close()
    
    return result


if __name__ == "__main__":
    # Test the fetcher
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    
    console = Console()
    fetcher = ESPNFetcher(season=2024)
    
    console.print("\n[bold cyan]═══ ESPN NFL DATA FETCHER TEST (2024 Season) ═══[/]\n")
    
    # Get current week schedule
    console.print("[yellow]Fetching current week schedule...[/]")
    games = fetcher.get_week_schedule()
    
    if games:
        table = Table(title="Week 17 Games")
        table.add_column("Away", style="cyan")
        table.add_column("@", style="dim")
        table.add_column("Home", style="green")
        table.add_column("Status")
        
        for game in games[:8]:
            table.add_row(game.away_team, "@", game.home_team, game.status.replace("STATUS_", ""))
        
        console.print(table)
    
    # Get league leaders with REAL 2024 stats
    console.print("\n[yellow]Fetching 2024 Season Leaders (REAL STATS)...[/]\n")
    
    for stat_type in ["rushing", "passing", "receiving"]:
        leaders = fetcher.get_season_leaders(stat_type)
        if leaders:
            console.print(f"[bold]{stat_type.upper()} Leaders:[/]")
            for i, leader in enumerate(leaders[:5], 1):
                console.print(f"  {i}. {leader['name']} ({leader['team']}) - {leader['stat']}")
            console.print()
    
    # Get players with stats for specific teams
    console.print("[yellow]Fetching team player stats...[/]\n")
    
    for team in ["PIT", "CLE", "JAX", "IND"]:
        players = fetcher.get_team_season_stats(team)
        
        if players:
            table = Table(title=f"{team} Players with 2024 Stats")
            table.add_column("Player", style="white", width=22)
            table.add_column("Pos", style="cyan", width=4)
            table.add_column("Rush", style="green", justify="right")
            table.add_column("Rec", style="blue", justify="right")
            table.add_column("Rec Yds", style="blue", justify="right")
            table.add_column("Pass", style="magenta", justify="right")
            
            # Sort by total yards
            players.sort(key=lambda p: p.rush_yards + p.rec_yards + p.pass_yards, reverse=True)
            
            for player in players[:8]:
                table.add_row(
                    player.name,
                    player.position,
                    str(int(player.rush_yards)) if player.rush_yards else "-",
                    str(int(player.receptions)) if player.receptions else "-",
                    str(int(player.rec_yards)) if player.rec_yards else "-",
                    str(int(player.pass_yards)) if player.pass_yards else "-"
                )
            
            console.print(table)
            console.print()
    
    fetcher.close()
    console.print("[green]✓ ESPN data fetch complete with REAL 2024 stats![/]")
