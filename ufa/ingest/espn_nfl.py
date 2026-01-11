"""
ESPN NFL Data Fetcher - Real rosters and stats from ESPN's public APIs.

ESPN provides free, public endpoints for NFL data including:
- Team rosters with player status (Active, IR, PUP, etc.)
- Player game logs with verified statistics
- Depth charts and starter information
- Live game data and injuries

This module fetches real, verifiable data - no mock data.
"""

import httpx
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
from functools import lru_cache

# ESPN API Base URLs
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
ESPN_CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"

# NFL Team ID mapping (ESPN IDs)
NFL_TEAMS = {
    "ARI": 22, "ATL": 1, "BAL": 33, "BUF": 2, "CAR": 29, "CHI": 3,
    "CIN": 4, "CLE": 5, "DAL": 6, "DEN": 7, "DET": 8, "GB": 9,
    "HOU": 34, "IND": 11, "JAX": 30, "KC": 12, "LAC": 24, "LAR": 14,
    "LV": 13, "MIA": 15, "MIN": 16, "NE": 17, "NO": 18, "NYG": 19,
    "NYJ": 20, "PHI": 21, "PIT": 23, "SEA": 26, "SF": 25, "TB": 27,
    "TEN": 10, "WAS": 28
}

# Reverse mapping
TEAM_BY_ID = {v: k for k, v in NFL_TEAMS.items()}


@dataclass
class PlayerStatus:
    """Player roster status from ESPN."""
    player_id: str
    name: str
    team: str
    position: str
    jersey: str
    status: str  # Active, Injured Reserve, Questionable, Out, etc.
    is_starter: bool
    depth_order: int  # 1 = starter, 2 = backup, etc.
    injury_status: Optional[str] = None
    injury_detail: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[int] = None
    experience: Optional[int] = None


@dataclass
class GameLog:
    """Single game statistics for a player."""
    game_id: str
    date: str
    week: int
    opponent: str
    home_away: str  # "vs" or "@"
    result: str  # "W 24-17" or "L 10-20"
    stats: dict  # Position-specific stats


@dataclass
class PlayerProfile:
    """Complete player profile with recent stats."""
    player_id: str
    name: str
    team: str
    position: str
    status: PlayerStatus
    game_logs: list[GameLog] = field(default_factory=list)
    season_totals: dict = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


class ESPNFetcher:
    """
    Fetches real NFL data from ESPN's public APIs.
    
    All data is verified from ESPN - no mock or fabricated data.
    """
    
    def __init__(self, timeout: float = 10.0):
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._cache = {}
    
    def __del__(self):
        self.client.close()
    
    def get_team_roster(self, team: str) -> list[PlayerStatus]:
        """
        Fetch current roster for a team with player statuses.
        
        Args:
            team: Team abbreviation (e.g., "PIT", "CLE", "JAX")
            
        Returns:
            List of PlayerStatus objects for all rostered players
        """
        team_id = NFL_TEAMS.get(team.upper())
        if not team_id:
            raise ValueError(f"Unknown team: {team}. Valid: {list(NFL_TEAMS.keys())}")
        
        url = f"{ESPN_BASE}/teams/{team_id}/roster"
        resp = self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        players = []
        
        # ESPN roster is grouped by position groups
        for group in data.get("athletes", []):
            position_group = group.get("position", "")
            
            for athlete in group.get("items", []):
                # Get player details
                player_id = athlete.get("id", "")
                full_name = athlete.get("fullName", "")
                jersey = athlete.get("jersey", "")
                position = athlete.get("position", {}).get("abbreviation", position_group)
                
                # Status info
                status_info = athlete.get("status", {})
                status_type = status_info.get("type", "active")
                status_name = status_info.get("name", "Active")
                
                # Injury info
                injuries = athlete.get("injuries", [])
                injury_status = None
                injury_detail = None
                if injuries:
                    injury = injuries[0]
                    injury_status = injury.get("status", "")
                    injury_detail = injury.get("type", {}).get("description", "")
                
                # Determine if starter (depth = 1)
                depth = athlete.get("depth", 99)
                is_starter = depth == 1
                
                players.append(PlayerStatus(
                    player_id=player_id,
                    name=full_name,
                    team=team.upper(),
                    position=position,
                    jersey=jersey,
                    status=status_name,
                    is_starter=is_starter,
                    depth_order=depth,
                    injury_status=injury_status,
                    injury_detail=injury_detail,
                    height=athlete.get("displayHeight"),
                    weight=athlete.get("weight"),
                    experience=athlete.get("experience", {}).get("years")
                ))
        
        return players
    
    def get_depth_chart(self, team: str) -> dict[str, list[PlayerStatus]]:
        """
        Fetch official depth chart for a team.
        
        Args:
            team: Team abbreviation
            
        Returns:
            Dict mapping position -> list of players in depth order
        """
        team_id = NFL_TEAMS.get(team.upper())
        if not team_id:
            raise ValueError(f"Unknown team: {team}")
        
        url = f"{ESPN_BASE}/teams/{team_id}/depthcharts"
        resp = self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        depth_chart = {}
        
        for item in data.get("items", []):
            # Each item is a formation/position group
            for position in item.get("positions", {}).values():
                pos_name = position.get("position", {}).get("abbreviation", "")
                
                players_at_pos = []
                for athlete in position.get("athletes", []):
                    player = athlete.get("athlete", {})
                    slot = athlete.get("slot", 99)
                    
                    players_at_pos.append(PlayerStatus(
                        player_id=str(player.get("id", "")),
                        name=player.get("displayName", ""),
                        team=team.upper(),
                        position=pos_name,
                        jersey=player.get("jersey", ""),
                        status="Active",
                        is_starter=(slot == 1),
                        depth_order=slot
                    ))
                
                if pos_name and players_at_pos:
                    # Sort by depth order
                    players_at_pos.sort(key=lambda x: x.depth_order)
                    depth_chart[pos_name] = players_at_pos
        
        return depth_chart
    
    def get_qb_starter(self, team: str) -> Optional[PlayerStatus]:
        """Get the starting QB for a team from depth chart."""
        depth = self.get_depth_chart(team)
        qbs = depth.get("QB", [])
        if qbs:
            return qbs[0]  # First QB is starter
        return None
    
    def get_player_gamelog(self, player_id: str, season: int = 2024) -> list[GameLog]:
        """
        Fetch game-by-game stats for a player.
        
        Args:
            player_id: ESPN player ID
            season: NFL season year (2024, 2023, etc.)
            
        Returns:
            List of GameLog objects with per-game stats
        """
        url = f"{ESPN_BASE}/athletes/{player_id}/gamelog?season={season}"
        resp = self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        game_logs = []
        
        # Parse game log data
        events = data.get("events", [])
        stats_section = data.get("seasonTypes", [])
        
        for season_type in stats_section:
            for category in season_type.get("categories", []):
                events_data = category.get("events", [])
                
                for event in events_data:
                    game_id = event.get("eventId", "")
                    week = event.get("week", 0)
                    
                    # Get opponent and result
                    opponent = event.get("opponent", {}).get("abbreviation", "")
                    home_away = event.get("homeAway", "")
                    result = event.get("gameResult", "")
                    
                    # Parse stats
                    stats = {}
                    for stat in event.get("stats", []):
                        stat_name = stat.get("abbreviation", stat.get("name", ""))
                        stat_value = stat.get("value", 0)
                        if stat_name:
                            stats[stat_name] = stat_value
                    
                    game_logs.append(GameLog(
                        game_id=game_id,
                        date=event.get("gameDate", ""),
                        week=week,
                        opponent=opponent,
                        home_away="vs" if home_away == "home" else "@",
                        result=result,
                        stats=stats
                    ))
        
        return game_logs
    
    def search_player(self, name: str) -> list[dict]:
        """
        Search for a player by name.
        
        Args:
            name: Player name to search
            
        Returns:
            List of matching player dicts with id, name, team, position
        """
        # ESPN search endpoint
        url = f"https://site.web.api.espn.com/apis/common/v3/search?query={name}&type=player&sport=football&league=nfl"
        resp = self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        results = []
        for item in data.get("items", []):
            if item.get("type") == "player":
                results.append({
                    "id": item.get("id"),
                    "name": item.get("displayName"),
                    "team": item.get("teamShortName"),
                    "position": item.get("position")
                })
        
        return results
    
    def get_player_stats(self, player_name: str, stat_type: str, last_n: int = 10) -> list[float]:
        """
        Get recent stat values for a player.
        
        Args:
            player_name: Full player name (e.g., "Jonathan Taylor")
            stat_type: Stat type ("rush_yards", "receptions", "rec_yards", "pass_yards", etc.)
            last_n: Number of recent games to include
            
        Returns:
            List of stat values from recent games
        """
        # Search for player
        matches = self.search_player(player_name)
        if not matches:
            raise ValueError(f"Player not found: {player_name}")
        
        # Use first match
        player_id = matches[0]["id"]
        
        # Get game log
        game_logs = self.get_player_gamelog(player_id, season=2024)
        
        # Map stat type to ESPN abbreviation
        stat_map = {
            "rush_yards": ["RYDS", "RushYds", "YDS"],
            "rush_attempts": ["CAR", "ATT", "RushAtt"],
            "rush_td": ["RTD", "TD"],
            "receptions": ["REC"],
            "rec_yards": ["RECYDS", "YDS"],
            "rec_td": ["RECTD", "TD"],
            "targets": ["TAR", "TGT"],
            "pass_yards": ["PYDS", "YDS"],
            "pass_td": ["PTD", "TD"],
            "pass_attempts": ["ATT"],
            "completions": ["CMP"],
            "interceptions": ["INT"],
            "sacks": ["SCK", "SACKS"],
            "tackles": ["TOT", "TOTAL", "COMB"],
            "solo_tackles": ["SOLO"],
        }
        
        espn_keys = stat_map.get(stat_type.lower(), [stat_type.upper()])
        
        values = []
        for log in game_logs[:last_n]:
            # Try each possible key
            value = None
            for key in espn_keys:
                if key in log.stats:
                    value = float(log.stats[key])
                    break
            
            if value is not None:
                values.append(value)
        
        return values
    
    def get_week_schedule(self, week: int, season: int = 2024) -> list[dict]:
        """
        Get all games for a specific NFL week.
        
        Args:
            week: NFL week number (1-18)
            season: Season year
            
        Returns:
            List of game dicts with teams, date, time, etc.
        """
        url = f"{ESPN_BASE}/scoreboard?week={week}&seasontype=2&dates={season}"
        resp = self.client.get(url)
        resp.raise_for_status()
        data = resp.json()
        
        games = []
        for event in data.get("events", []):
            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])
            
            home = away = None
            for team in competitors:
                if team.get("homeAway") == "home":
                    home = team.get("team", {}).get("abbreviation")
                else:
                    away = team.get("team", {}).get("abbreviation")
            
            games.append({
                "game_id": event.get("id"),
                "name": event.get("name"),
                "date": event.get("date"),
                "home": home,
                "away": away,
                "status": event.get("status", {}).get("type", {}).get("name")
            })
        
        return games
    
    def validate_starter(self, player_name: str, team: str, position: str) -> tuple[bool, str]:
        """
        Validate if a player is the current starter at their position.
        
        Args:
            player_name: Player's full name
            team: Team abbreviation
            position: Position abbreviation (QB, RB, WR, etc.)
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            depth = self.get_depth_chart(team)
            
            # Check depth chart at position
            players = depth.get(position, [])
            if not players:
                return False, f"No depth chart found for {position} on {team}"
            
            # Check if player is on roster
            for player in players:
                if player_name.lower() in player.name.lower() or player.name.lower() in player_name.lower():
                    if player.is_starter:
                        return True, f"✓ VERIFIED STARTER: {player.name} ({team} {position})"
                    else:
                        starter = players[0] if players else None
                        return False, f"✗ NOT STARTER: {player_name} is depth #{player.depth_order}. Starter: {starter.name if starter else 'Unknown'}"
            
            # Player not found in depth chart
            starter = players[0] if players else None
            return False, f"✗ NOT ON DEPTH CHART: {player_name}. {position} starter: {starter.name if starter else 'Unknown'}"
            
        except Exception as e:
            return False, f"Could not verify: {str(e)}"


# Singleton for reuse
_fetcher: Optional[ESPNFetcher] = None

def get_espn_fetcher() -> ESPNFetcher:
    """Get or create ESPN fetcher singleton."""
    global _fetcher
    if _fetcher is None:
        _fetcher = ESPNFetcher()
    return _fetcher


def validate_player_starters(players: list[dict]) -> dict[str, dict]:
    """
    Validate multiple players against ESPN depth charts.
    
    Args:
        players: List of dicts with "name", "team", "position" keys
        
    Returns:
        Dict mapping player name -> validation result
    """
    fetcher = get_espn_fetcher()
    results = {}
    
    for player in players:
        name = player.get("name", "")
        team = player.get("team", "")
        pos = player.get("position", "")
        
        is_valid, msg = fetcher.validate_starter(name, team, pos)
        results[name] = {
            "valid": is_valid,
            "message": msg,
            "team": team,
            "position": pos
        }
    
    return results


def get_verified_starters_for_teams(teams: list[str]) -> dict[str, dict]:
    """
    Get verified starters for all skill positions on given teams.
    
    Args:
        teams: List of team abbreviations
        
    Returns:
        Dict mapping team -> position -> starter info
    """
    fetcher = get_espn_fetcher()
    result = {}
    
    skill_positions = ["QB", "RB", "WR", "TE"]
    
    for team in teams:
        try:
            depth = fetcher.get_depth_chart(team.upper())
            result[team.upper()] = {}
            
            for pos in skill_positions:
                players = depth.get(pos, [])
                if players:
                    starter = players[0]
                    result[team.upper()][pos] = {
                        "name": starter.name,
                        "player_id": starter.player_id,
                        "depth": starter.depth_order
                    }
        except Exception as e:
            result[team.upper()] = {"error": str(e)}
    
    return result


if __name__ == "__main__":
    # Test the fetcher
    fetcher = ESPNFetcher()
    
    print("=== Week 17 Games ===")
    games = fetcher.get_week_schedule(17, 2024)
    for game in games:
        print(f"  {game['away']} @ {game['home']} - {game['status']}")
    
    print("\n=== Testing QB Starters ===")
    test_teams = ["PIT", "CLE", "JAX", "IND"]
    for team in test_teams:
        qb = fetcher.get_qb_starter(team)
        if qb:
            print(f"  {team}: {qb.name} (#{qb.jersey})")
        else:
            print(f"  {team}: Could not determine QB")
    
    print("\n=== Validated Skill Position Starters ===")
    starters = get_verified_starters_for_teams(test_teams)
    for team, positions in starters.items():
        print(f"\n  {team}:")
        for pos, info in positions.items():
            if isinstance(info, dict) and "name" in info:
                print(f"    {pos}: {info['name']}")
