"""
ESPN Roster Fetcher — Reliable Alternative to stats.nba.com

Fetches NBA rosters via ESPN's public API (never blocks, no auth required).
Replaces nba_api calls that are being blocked by stats.nba.com.

ESPN API endpoint:
https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster

ESPN Team IDs (30 teams):
ATL=1, BOS=2, BKN=17, CHA=30, CHI=4, CLE=5, DAL=6, DEN=7, DET=8,
GSW=9, HOU=10, IND=11, LAC=12, LAL=13, MEM=29, MIA=14, MIL=15,
MIN=16, NOP=3, NYK=18, OKC=25, ORL=19, PHI=20, PHX=21, POR=22,
SAC=23, SAS=24, TOR=28, UTA=26, WAS=27

Usage:
    from sources.espn_roster_fetcher import fetch_all_nba_rosters, build_player_team_map
    
    rosters = fetch_all_nba_rosters()
    player_team_map = build_player_team_map(rosters)
    
    print(f"Loaded {len(player_team_map)} active NBA players")
    team = player_team_map.get("LeBron James")
"""

import requests
import time
from typing import Dict, List, Optional

# ESPN Team ID Mapping (ESPN ID → 3-letter code)
ESPN_TEAM_MAP = {
    1: "ATL",   # Atlanta Hawks
    2: "BOS",   # Boston Celtics
    17: "BKN",  # Brooklyn Nets
    30: "CHA",  # Charlotte Hornets
    4: "CHI",   # Chicago Bulls
    5: "CLE",   # Cleveland Cavaliers
    6: "DAL",   # Dallas Mavericks
    7: "DEN",   # Denver Nuggets
    8: "DET",   # Detroit Pistons
    9: "GSW",   # Golden State Warriors
    10: "HOU",  # Houston Rockets
    11: "IND",  # Indiana Pacers
    12: "LAC",  # LA Clippers
    13: "LAL",  # Los Angeles Lakers
    29: "MEM",  # Memphis Grizzlies
    14: "MIA",  # Miami Heat
    15: "MIL",  # Milwaukee Bucks
    16: "MIN",  # Minnesota Timberwolves
    3: "NOP",   # New Orleans Pelicans
    18: "NYK",  # New York Knicks
    25: "OKC",  # Oklahoma City Thunder
    19: "ORL",  # Orlando Magic
    20: "PHI",  # Philadelphia 76ers
    21: "PHX",  # Phoenix Suns
    22: "POR",  # Portland Trail Blazers
    23: "SAC",  # Sacramento Kings
    24: "SAS",  # San Antonio Spurs
    28: "TOR",  # Toronto Raptors
    26: "UTA",  # Utah Jazz
    27: "WAS"   # Washington Wizards
}

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"


def get_team_roster(espn_team_id: int, team_code: str) -> List[Dict]:
    """
    Fetch roster for a single team from ESPN API.
    
    Args:
        espn_team_id: ESPN's numeric team ID (1-30)
        team_code: 3-letter team abbreviation (ATL, BOS, etc.)
    
    Returns:
        List of player dicts with keys: name, team, position, jersey, status
        Returns empty list on failure (never raises exception)
    """
    url = f"{ESPN_BASE_URL}/teams/{espn_team_id}/roster"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        athletes = data.get("athletes", [])
        roster = []
        
        # ESPN API: athletes is a FLAT list (not nested position groups)
        for player in athletes:
            # Extract player details
            full_name = player.get("fullName", "")
            jersey = player.get("jersey", "")
            
            # Get position (if available)
            player_position = player.get("position", {})
            if isinstance(player_position, dict):
                position = player_position.get("abbreviation", "")
            else:
                position = ""
            
            # Get injury status
            injuries = player.get("injuries", [])
            status = "ACTIVE"
            if injuries:
                injury_status = injuries[0].get("status", "")
                if injury_status in ["Out", "OUT"]:
                    status = "OUT"
                elif injury_status in ["Day-To-Day", "Questionable"]:
                    status = "DTD"
            
            roster.append({
                "name": full_name,
                "team": team_code,
                "position": position,
                "jersey": jersey,
                "status": status
            })
        
        return roster
    
    except requests.RequestException as e:
        print(f"[ESPN] Failed to fetch {team_code} roster: {e}")
        return []
    except (KeyError, ValueError) as e:
        print(f"[ESPN] Failed to parse {team_code} roster: {e}")
        return []


def fetch_all_nba_rosters(delay_ms: int = 100, verbose: bool = True) -> Dict[str, List[Dict]]:
    """
    Fetch rosters for all 30 NBA teams from ESPN API.
    
    Args:
        delay_ms: Delay between requests in milliseconds (default 100ms)
        verbose: Print progress messages
    
    Returns:
        Dict mapping team code → list of player dicts
        Example: {"LAL": [{"name": "LeBron James", "team": "LAL", ...}]}
    """
    if verbose:
        print(f"[ESPN] Fetching rosters for all 30 NBA teams...")
    
    rosters = {}
    success_count = 0
    
    for espn_id, team_code in ESPN_TEAM_MAP.items():
        roster = get_team_roster(espn_id, team_code)
        
        if roster:
            rosters[team_code] = roster
            success_count += 1
            if verbose:
                print(f"[ESPN] ✓ {team_code}: {len(roster)} players")
        else:
            if verbose:
                print(f"[ESPN] ✗ {team_code}: Failed")
        
        # Rate limiting (be nice to ESPN)
        time.sleep(delay_ms / 1000.0)
    
    if verbose:
        print(f"[ESPN] Complete: {success_count}/30 teams fetched")
    
    return rosters


def build_player_team_map(rosters: Dict[str, List[Dict]]) -> Dict[str, str]:
    """
    Build a player name → team code mapping from roster data.
    
    Args:
        rosters: Dict from fetch_all_nba_rosters()
    
    Returns:
        Dict mapping player name → team code
        Example: {"LeBron James": "LAL", "Stephen Curry": "GSW"}
    """
    player_team_map = {}
    
    for team_code, roster in rosters.items():
        for player in roster:
            player_name = player["name"]
            player_team_map[player_name] = team_code
    
    return player_team_map


def get_active_players(rosters: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Get all active (non-injured) players from roster data.
    
    Args:
        rosters: Dict from fetch_all_nba_rosters()
    
    Returns:
        List of all active player dicts
    """
    active_players = []
    
    for roster in rosters.values():
        for player in roster:
            if player["status"] == "ACTIVE":
                active_players.append(player)
    
    return active_players


def get_injured_players(rosters: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """
    Get all injured players grouped by injury status.
    
    Args:
        rosters: Dict from fetch_all_nba_rosters()
    
    Returns:
        Dict with keys "OUT" and "DTD" mapping to lists of player dicts
    """
    injured = {"OUT": [], "DTD": []}
    
    for roster in rosters.values():
        for player in roster:
            if player["status"] in ["OUT", "DTD"]:
                injured[player["status"]].append(player)
    
    return injured


if __name__ == "__main__":
    # Test ESPN roster fetcher
    print("=" * 60)
    print("ESPN Roster Fetcher — Test Run")
    print("=" * 60)
    
    rosters = fetch_all_nba_rosters(verbose=True)
    
    print("\n" + "=" * 60)
    print("Statistics")
    print("=" * 60)
    
    player_team_map = build_player_team_map(rosters)
    active_players = get_active_players(rosters)
    injured = get_injured_players(rosters)
    
    print(f"Total players: {len(player_team_map)}")
    print(f"Active players: {len(active_players)}")
    print(f"Injured OUT: {len(injured['OUT'])}")
    print(f"Injured DTD: {len(injured['DTD'])}")
    
    print("\n" + "=" * 60)
    print("Sample Players by Team")
    print("=" * 60)
    
    for team_code in ["LAL", "GSW", "BOS", "MIA", "DEN"]:
        if team_code in rosters:
            roster = rosters[team_code]
            print(f"\n{team_code} ({len(roster)} players):")
            for player in roster[:5]:  # Show first 5
                print(f"  {player['name']:<25} {player['position']:<5} [{player['status']}]")
    
    print("\n" + "=" * 60)
    print("Player Lookup Test")
    print("=" * 60)
    
    test_players = ["LeBron James", "Stephen Curry", "Nikola Jokic", "Giannis Antetokounmpo"]
    for player_name in test_players:
        team = player_team_map.get(player_name, "NOT_FOUND")
        print(f"{player_name:<25} → {team}")
