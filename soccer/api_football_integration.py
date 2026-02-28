"""
API-Football Soccer Integration
Fetches real-time player statistics from API-Football (RapidAPI)

This module provides automated player stats fetching to replace manual data entry.
Integrates with the existing soccer props pipeline.

SETUP:
    1. Get API key from: https://rapidapi.com/api-sports/api/api-football
    2. Set environment variable: RAPIDAPI_KEY=your_key_here
    3. Or create .env file with RAPIDAPI_KEY

USAGE:
    from api_football_soccer_integration import fetch_soccer_stats_for_slate
    
    player_names = ["Mohamed Salah", "Erling Haaland"]
    stats = fetch_soccer_stats_for_slate(player_names)
"""

import os
import requests
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


# API Configuration
RAPIDAPI_HOST = "v3.football.api-sports.io"
RAPIDAPI_BASE_URL = f"https://{RAPIDAPI_HOST}"


def get_api_key() -> Optional[str]:
    """Get RapidAPI key from environment variable or .env file."""
    # Try environment variable first
    api_key = os.environ.get('RAPIDAPI_KEY')
    
    if not api_key:
        # Try .env file
        env_file = Path(__file__).parent.parent / '.env'
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith('RAPIDAPI_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                    break
    
    return api_key


def search_player(player_name: str, api_key: str) -> Optional[Dict]:
    """
    Search for a player by name using API-Football.
    
    Returns:
        Player data dict with id, name, team, etc.
        None if not found or API error
    """
    url = f"{RAPIDAPI_BASE_URL}/players"
    
    headers = {
        "x-apisports-key": api_key
    }
    
    # Search by player name (current season)
    # API requires league - prioritize top 5 European leagues first
    priority_leagues = [39, 140, 135, 78, 61]  # Big 5: EPL, La Liga, Serie A, Bundesliga, Ligue 1
    other_leagues = [94, 88, 203, 307, 262, 71, 253]  # Other major leagues
    
    # Build search terms: PRIORITIZE LAST NAME (more unique)
    search_terms = []
    if ' ' in player_name:
        parts = player_name.split()
        last_name = parts[-1]
        # Last name first (most unique identifier for soccer players)
        search_terms.append(last_name)
        # Then full name as fallback
        search_terms.append(player_name)
    else:
        # Single name (like Neymar)
        search_terms.append(player_name)
    
    # Search priority leagues first (most common)
    for search_term in search_terms:
        for league_id in priority_leagues:
            params = {
                "search": search_term,
                "league": league_id,
                "season": "2024"
            }
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                if 'response' in data and len(data['response']) > 0:
                    return data['response'][0]
            except Exception:
                continue
        
        # If not found in priority leagues, try others
        for league_id in other_leagues:
            params = {
                "search": search_term,
                "league": league_id,
                "season": "2024"
            }
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # API-Football returns results in data.response array
                if 'response' in data and len(data['response']) > 0:
                    # Return first match (closest name)
                    return data['response'][0]
            except Exception:
                continue
    
    return None


def get_player_stats(player_id: int, season: str, api_key: str) -> Optional[Dict]:
    """
    Fetch detailed player statistics from API-Football.
    
    Args:
        player_id: API-Football player ID
        season: Season year (e.g., "2024")
        api_key: RapidAPI key
    
    Returns:
        Stats dict or None if error
    """
    url = f"{RAPIDAPI_BASE_URL}/players"
    
    headers = {
        "x-apisports-key": api_key
    }
    
    params = {
        "id": player_id,
        "season": season
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'response' in data and len(data['response']) > 0:
            return data['response'][0]
        
        return None
        
    except Exception as e:
        print(f"  ⚠️  API error fetching stats for player {player_id}: {e}")
        return None


def parse_player_stats(api_data: Dict) -> Dict:
    """
    Parse API-Football response into soccer props format.
    
    API-Football returns nested structure:
    {
      "player": {...},
      "statistics": [
        {
          "team": {...},
          "league": {...},
          "games": {...},
          "goals": {...},
          "shots": {...},
          "tackles": {...},
          ...
        }
      ]
    }
    
    We aggregate across all competitions and calculate averages.
    """
    player_info = api_data.get('player', {})
    statistics = api_data.get('statistics', [])
    
    if not statistics:
        return {}
    
    # Aggregate stats across all competitions
    total_games = 0
    total_goals = 0
    total_assists = 0
    total_shots = 0
    total_shots_on = 0
    total_tackles = 0
    total_fouls = 0
    total_passes = 0
    total_key_passes = 0
    
    for stat in statistics:
        games = stat.get('games', {})
        goals = stat.get('goals', {})
        passes_data = stat.get('passes', {})
        tackles_data = stat.get('tackles', {})
        fouls_data = stat.get('fouls', {})
        shots_data = stat.get('shots', {})
        
        # Count games played
        appearances = games.get('appearences', 0) or 0
        total_games += appearances
        
        # Goals and assists
        total_goals += goals.get('total', 0) or 0
        total_assists += goals.get('assists', 0) or 0
        
        # Shots
        total_shots += shots_data.get('total', 0) or 0
        total_shots_on += shots_data.get('on', 0) or 0
        
        # Tackles
        total_tackles += tackles_data.get('total', 0) or 0
        
        # Fouls
        total_fouls += fouls_data.get('committed', 0) or 0
        
        # Passes
        total_passes += passes_data.get('total', 0) or 0
        total_key_passes += passes_data.get('key', 0) or 0
    
    # Calculate per-game averages
    if total_games == 0:
        total_games = 1  # Avoid division by zero
    
    parsed_stats = {
        'player': player_info.get('name', 'Unknown'),
        'team': statistics[0].get('team', {}).get('name', 'Unknown') if statistics else 'Unknown',
        'position': player_info.get('position', 'Unknown'),
        'games_played': total_games,
        
        # Per-game averages (for props)
        'avg_goals': round(total_goals / total_games, 2),
        'avg_assists': round(total_assists / total_games, 2),
        'avg_shots': round(total_shots / total_games, 2),
        'avg_shots_on_target': round(total_shots_on / total_games, 2),
        'avg_tackles': round(total_tackles / total_games, 2),
        'avg_fouls': round(total_fouls / total_games, 2),
        'avg_passes': round(total_passes / total_games, 2),
        'avg_key_passes': round(total_key_passes / total_games, 2),
        
        # Raw totals (for reference)
        'total_goals': total_goals,
        'total_assists': total_assists,
        'total_shots': total_shots,
        'total_shots_on_target': total_shots_on,
        'total_tackles': total_tackles,
        
        # Metadata
        'data_source': 'api_football',
        'last_updated': datetime.now().isoformat(),
        'season': '2024'
    }
    
    return parsed_stats


def fetch_soccer_stats_for_slate(player_names: List[str], season: str = "2024") -> Dict[str, Dict]:
    """
    Fetch stats for multiple players from API-Football.
    
    Args:
        player_names: List of player names to fetch
        season: Season year (default: "2024")
    
    Returns:
        Dict mapping player name to stats dict
        
    Example:
        >>> players = ["Mohamed Salah", "Erling Haaland"]
        >>> stats = fetch_soccer_stats_for_slate(players)
        >>> print(stats["Mohamed Salah"]["avg_goals"])
        0.82
    """
    api_key = get_api_key()
    
    if not api_key:
        print("\n⚠️  ERROR: RapidAPI key not found!")
        print("   Set environment variable: RAPIDAPI_KEY=your_key")
        print("   Or create .env file with RAPIDAPI_KEY=your_key")
        return {}
    
    print(f"\n⚽ Fetching stats from API-Football...")
    print(f"   API Host: {RAPIDAPI_HOST}")
    print(f"   Season: {season}")
    print(f"   Players: {len(player_names)}")
    
    results = {}
    
    for i, player_name in enumerate(player_names, 1):
        print(f"\n[{i}/{len(player_names)}] Fetching {player_name}...")
        
        # Step 1: Search for player (returns stats in same response!)
        player_data = search_player(player_name, api_key)
        
        if not player_data:
            print(f"  ❌ Player not found: {player_name}")
            continue
        
        player_info = player_data.get('player', {})
        player_id = player_info.get('id')
        
        if not player_id:
            print(f"  ❌ No player ID for: {player_name}")
            continue
        
        print(f"  ✓ Found: {player_info.get('name')} (ID: {player_id})")
        
        # Step 2: Check if search already returned stats (it usually does!)
        if player_data.get('statistics'):
            # Use stats from search response directly
            parsed = parse_player_stats(player_data)
        else:
            # Fallback: Fetch detailed stats via separate call
            stats_data = get_player_stats(player_id, season, api_key)
            if not stats_data:
                print(f"  ❌ Stats not available")
                continue
            parsed = parse_player_stats(stats_data)
        
        if parsed:
            results[player_name] = parsed
            print(f"  ✓ Stats fetched: {parsed['avg_goals']} goals/game, {parsed['avg_shots_on_target']} SOT/game")
        else:
            print(f"  ❌ Failed to parse stats")
    
    print(f"\n✅ Fetched stats for {len(results)}/{len(player_names)} players")
    
    return results

def test_api_connection() -> bool:
    """
    Test API-Football connection with a known player.
    
    Returns:
        True if API is working, False otherwise
    """
    api_key = get_api_key()
    
    if not api_key:
        print("❌ No API key found in environment")
        print("   Set: $env:RAPIDAPI_KEY='your_key'")
        return False
    
    print("\n🧪 Testing API-Football connection...")
    print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"   Host: {RAPIDAPI_HOST}")
    
    # Test with a direct API call
    try:
        headers = {"x-apisports-key": api_key}
        params = {"search": "Salah", "league": 39, "season": "2024"}  # EPL
        response = requests.get(f"{RAPIDAPI_BASE_URL}/players", headers=headers, params=params, timeout=10)
        
        print(f"   Response: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('response'):
                player = data['response'][0]['player']
                print(f"✅ API connection successful!")
                print(f"   Test player found: {player['name']}")
                return True
            else:
                print(f"⚠️  API returned no results (check season/league)")
                print(f"   Response: {data}")
                return False
        else:
            print(f"❌ API error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
        print(f"✅ API connection successful!")
        print(f"   Test player: {player_info.get('name')}")
        print(f"   Player ID: {player_info.get('id')}")
        return True
    else:
        print("❌ API connection failed")
        return False


if __name__ == "__main__":
    # Test mode - fetch stats for sample players
    print("="*60)
    print("API-FOOTBALL SOCCER STATS FETCHER - TEST MODE")
    print("="*60)
    
    # Test connection first
    if not test_api_connection():
        print("\n⚠️  Setup your RapidAPI key first!")
        exit(1)
    
    # Fetch stats for sample players
    test_players = [
        "Mohamed Salah",
        "Erling Haaland",
        "Harry Kane"
    ]
    
    stats = fetch_soccer_stats_for_slate(test_players)
    
    # Display results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    for player, data in stats.items():
        print(f"\n{player}:")
        print(f"  Team: {data.get('team')}")
        print(f"  Position: {data.get('position')}")
        print(f"  Games: {data.get('games_played')}")
        print(f"  Avg Goals: {data.get('avg_goals')}")
        print(f"  Avg Shots on Target: {data.get('avg_shots_on_target')}")
        print(f"  Avg Assists: {data.get('avg_assists')}")
        print(f"  Avg Tackles: {data.get('avg_tackles')}")
