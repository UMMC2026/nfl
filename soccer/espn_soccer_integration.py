"""
ESPN Soccer Stats Integration - FREE (No API Key Required)
Fetches real-time player statistics from ESPN's public soccer APIs

SETUP:
    No setup required - ESPN APIs are public and free
    
USAGE:
    from espn_soccer_integration import fetch_soccer_stats_for_slate
    
    player_names = ["Mohamed Salah", "Erling Haaland"]
    stats = fetch_soccer_stats_for_slate(player_names)
"""

import json
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# SSL context
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

# ESPN Soccer API Endpoints (Major Leagues)
LEAGUES = {
    "EPL": "eng.1",      # English Premier League
    "LaLiga": "esp.1",   # Spanish La Liga
    "SerieA": "ita.1",   # Italian Serie A
    "Bundesliga": "ger.1", # German Bundesliga
    "Ligue1": "fra.1",   # French Ligue 1
    "UCL": "uefa.2",     # UEFA Champions League
    "UEL": "uefa.3",     # UEFA Europa League
}


def _fetch_json(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from URL using urllib."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Warning: Failed to fetch {url}: {e}")
        return {}


def search_player(player_name: str) -> Optional[Dict]:
    """
    Search for a player across major European leagues.
    
    Returns:
        Player data dict with id, name, team, position
        None if not found
    """
    player_lower = player_name.lower()
    
    # Search through major leagues
    for league_name, league_id in LEAGUES.items():
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/scoreboard"
        data = _fetch_json(url)
        
        if not data or 'events' not in data:
            continue
            
        # Check each match for the player
        for event in data.get('events', []):
            for competitor in event.get('competitions', [{}])[0].get('competitors', []):
                team = competitor.get('team', {})
                team_id = team.get('id')
                
                if not team_id:
                    continue
                
                # Fetch team roster
                roster_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/teams/{team_id}/roster"
                roster_data = _fetch_json(roster_url)
                
                if not roster_data or 'athletes' not in roster_data:
                    continue
                
                # Search through roster
                for athlete in roster_data.get('athletes', []):
                    athlete_name = athlete.get('displayName', '').lower()
                    
                    if player_lower in athlete_name or athlete_name in player_lower:
                        return {
                            'player': athlete,
                            'team': team,
                            'league': league_name,
                            'league_id': league_id
                        }
    
    return None


def get_player_stats(player_id: str, league_id: str) -> Optional[Dict]:
    """
    Fetch player statistics from ESPN.
    
    Args:
        player_id: ESPN player ID
        league_id: ESPN league ID (e.g., "eng.1")
    
    Returns:
        Stats dict with season statistics
        None if error
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_id}/athletes/{player_id}/statistics"
    
    data = _fetch_json(url)
    
    if not data or 'statistics' not in data:
        return None
    
    return data.get('statistics', {})


def parse_player_stats(player_data: Dict, stats_data: Optional[Dict]) -> Dict:
    """
    Parse ESPN player stats into standardized format.
    
    Returns:
        Dict with per-game averages for Monte Carlo analysis
    """
    player = player_data.get('player', {})
    team = player_data.get('team', {})
    
    # Initialize stats
    result = {
        'player_name': player.get('displayName'),
        'team': team.get('displayName'),
        'position': player.get('position', {}).get('abbreviation', 'UNK'),
        'games_played': 0,
        'avg_goals': 0.0,
        'avg_assists': 0.0,
        'avg_shots': 0.0,
        'avg_shots_on_target': 0.0,
        'avg_tackles': 0.0,
        'avg_fouls': 0.0,
        'avg_passes': 0.0,
        'last_updated': datetime.now().isoformat()
    }
    
    if not stats_data:
        return result
    
    # Parse season stats
    for category in stats_data.get('splits', {}).get('categories', []):
        cat_name = category.get('name', '').lower()
        stats = category.get('stats', [])
        
        for stat in stats:
            stat_name = stat.get('name', '').lower()
            value = stat.get('value', 0)
            
            try:
                value = float(value)
            except:
                continue
            
            # Map ESPN stats to our format
            if 'appearances' in stat_name or 'games played' in stat_name:
                result['games_played'] = int(value)
            elif 'goals' in stat_name and 'against' not in stat_name:
                result['avg_goals'] = value
            elif 'assists' in stat_name:
                result['avg_assists'] = value
            elif 'shots on target' in stat_name or 'shots on goal' in stat_name:
                result['avg_shots_on_target'] = value
            elif 'total shots' in stat_name or stat_name == 'shots':
                result['avg_shots'] = value
            elif 'tackles' in stat_name:
                result['avg_tackles'] = value
            elif 'fouls' in stat_name and 'committed' in stat_name:
                result['avg_fouls'] = value
            elif 'passes' in stat_name and 'completed' in stat_name:
                result['avg_passes'] = value
    
    # Convert totals to per-game averages if needed
    games = result['games_played']
    if games > 0:
        # Check if stats are already averages or totals
        # ESPN usually provides season totals, so we divide
        if result['avg_goals'] > 5:  # Likely a total
            result['avg_goals'] = round(result['avg_goals'] / games, 2)
        if result['avg_assists'] > 5:
            result['avg_assists'] = round(result['avg_assists'] / games, 2)
        if result['avg_shots'] > 10:
            result['avg_shots'] = round(result['avg_shots'] / games, 2)
        if result['avg_shots_on_target'] > 5:
            result['avg_shots_on_target'] = round(result['avg_shots_on_target'] / games, 2)
        if result['avg_tackles'] > 10:
            result['avg_tackles'] = round(result['avg_tackles'] / games, 2)
        if result['avg_fouls'] > 5:
            result['avg_fouls'] = round(result['avg_fouls'] / games, 2)
        if result['avg_passes'] > 100:
            result['avg_passes'] = round(result['avg_passes'] / games, 2)
    
    return result


def fetch_soccer_stats_for_slate(player_names: List[str]) -> Dict[str, Dict]:
    """
    Main function to fetch stats for multiple players.
    
    Args:
        player_names: List of player names to fetch
    
    Returns:
        Dict mapping player name -> stats dict
    """
    results = {}
    
    print(f"\nFetching ESPN stats for {len(player_names)} players...")
    
    for i, player_name in enumerate(player_names, 1):
        print(f"  [{i}/{len(player_names)}] Searching for {player_name}...")
        
        # Search for player
        player_data = search_player(player_name)
        
        if not player_data:
            print(f"    Warning: Player not found in major leagues")
            results[player_name] = {
                'player_name': player_name,
                'error': 'NOT_FOUND',
                'games_played': 0,
                'avg_goals': 0.0,
                'avg_assists': 0.0,
                'avg_shots': 0.0,
                'avg_shots_on_target': 0.0,
                'avg_tackles': 0.0
            }
            continue
        
        # Get player stats
        player = player_data['player']
        player_id = player.get('id')
        league_id = player_data.get('league_id')
        
        print(f"    Found in {player_data['league']} - {player_data['team']['displayName']}")
        
        stats_data = get_player_stats(player_id, league_id)
        
        # Parse and store
        parsed_stats = parse_player_stats(player_data, stats_data)
        results[player_name] = parsed_stats
        
        print(f"    Avg Goals: {parsed_stats['avg_goals']}, Assists: {parsed_stats['avg_assists']}, Shots: {parsed_stats['avg_shots']}")
    
    return results


def test_espn_connection():
    """Test ESPN soccer API with sample players."""
    print("="*60)
    print("ESPN SOCCER STATS FETCHER - TEST MODE")
    print("="*60)
    print()
    print("Testing ESPN Soccer API (FREE - No API Key)...")
    print("Searching for: Mohamed Salah, Erling Haaland, Harry Kane")
    print()
    
    test_players = ["Mohamed Salah", "Erling Haaland", "Harry Kane"]
    
    stats = fetch_soccer_stats_for_slate(test_players)
    
    if not stats:
        print("ERROR: Failed to fetch stats")
        return
    
    print()
    print("SUCCESS - Stats Retrieved")
    print("="*60)
    print()
    print("RESULTS")
    print("="*60)
    
    for player, data in stats.items():
        print(f"\n{player}:")
        print(f"  Team: {data.get('team', 'Unknown')}")
        print(f"  Position: {data.get('position', 'Unknown')}")
        print(f"  Games: {data.get('games_played', 0)}")
        print(f"  Avg Goals: {data.get('avg_goals', 0.0)}")
        print(f"  Avg Shots on Target: {data.get('avg_shots_on_target', 0.0)}")
        print(f"  Avg Assists: {data.get('avg_assists', 0.0)}")
        print(f"  Avg Tackles: {data.get('avg_tackles', 0.0)}")


if __name__ == "__main__":
    test_espn_connection()
