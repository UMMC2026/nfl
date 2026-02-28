"""
API-SPORTS TENNIS CONNECTOR
Live data integration for player stats, rankings, and match results

API Documentation: https://api-sports.io/documentation/tennis/v1
Rate Limit: 30 requests/minute, 100 requests/day (free tier)

SOP v2.1 Compliant - Data Layer
"""

import requests
import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os


# ============================================================================
# SECTION 1: CONFIGURATION
# ============================================================================

@dataclass
class APIConfig:
    """API-Sports configuration"""
    api_key: str
    base_url: str = "https://api-tennis.p.rapidapi.com"  # RapidAPI endpoint
    daily_limit: int = 100
    rate_limit_per_minute: int = 30
    
    @classmethod
    def from_file(cls, config_path: str = None) -> 'APIConfig':
        """Load config from JSON file"""
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "api_keys.json"
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        return cls(
            api_key=config['api_sports']['key'],
            base_url="https://api-tennis.p.rapidapi.com",  # Use RapidAPI
            daily_limit=config['api_sports'].get('daily_limit', 100),
            rate_limit_per_minute=config['api_sports'].get('rate_limit_per_minute', 30)
        )


# ============================================================================
# SECTION 2: API CLIENT
# ============================================================================

class APISportsTennisClient:
    """
    Client for API-Sports Tennis API.
    
    Handles:
    - Rate limiting
    - Request caching
    - Error handling
    - Response parsing
    """
    
    def __init__(self, config: APIConfig = None):
        if config is None:
            config = APIConfig.from_file()
        
        self.config = config
        self.headers = {
            'x-rapidapi-key': config.api_key,
            'x-rapidapi-host': 'api-tennis.p.rapidapi.com'
        }
        
        # Rate limiting
        self.requests_today = 0
        self.last_request_time = 0
        self.request_times = []
        
        # Cache
        self.cache_dir = Path(__file__).parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        now = time.time()
        
        # Check daily limit
        if self.requests_today >= self.config.daily_limit:
            raise Exception(f"Daily API limit reached ({self.config.daily_limit})")
        
        # Check per-minute limit (sliding window)
        self.request_times = [t for t in self.request_times if now - t < 60]
        if len(self.request_times) >= self.config.rate_limit_per_minute:
            sleep_time = 60 - (now - self.request_times[0])
            if sleep_time > 0:
                print(f"  Rate limit: waiting {sleep_time:.1f}s...")
                time.sleep(sleep_time)
        
        self.request_times.append(now)
        self.requests_today += 1
    
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request to API"""
        self._rate_limit()
        
        url = f"{self.config.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if data.get('errors'):
                raise Exception(f"API Error: {data['errors']}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            raise
    
    def _cache_get(self, cache_key: str, max_age_hours: int = 24) -> Optional[Dict]:
        """Get cached response if fresh"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=max_age_hours):
                with open(cache_file, 'r') as f:
                    return json.load(f)
        
        return None
    
    def _cache_set(self, cache_key: str, data: Dict):
        """Save response to cache"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, 'w') as f:
            json.dump(data, f)
    
    # ----- API Endpoints -----
    
    def get_player(self, player_id: int = None, name: str = None) -> Dict:
        """
        Get player information.
        
        Args:
            player_id: API-Sports player ID
            name: Player name to search
        """
        cache_key = f"player_{player_id or name}"
        cached = self._cache_get(cache_key, max_age_hours=168)  # 1 week
        if cached:
            return cached
        
        params = {}
        if player_id:
            params['id'] = player_id
        if name:
            params['search'] = name
        
        data = self._get('players', params)
        
        if data.get('response'):
            self._cache_set(cache_key, data)
        
        return data
    
    def get_player_statistics(
        self, 
        player_id: int, 
        season: int = None
    ) -> Dict:
        """
        Get player statistics for a season.
        
        Includes: aces, double faults, serve %, break points, etc.
        """
        if season is None:
            season = datetime.now().year
        
        cache_key = f"player_stats_{player_id}_{season}"
        cached = self._cache_get(cache_key, max_age_hours=24)
        if cached:
            return cached
        
        data = self._get('players/statistics', {
            'id': player_id,
            'season': season
        })
        
        if data.get('response'):
            self._cache_set(cache_key, data)
        
        return data
    
    def get_rankings(self, type: str = 'atp') -> Dict:
        """
        Get current ATP or WTA rankings.
        
        Args:
            type: 'atp' or 'wta'
        """
        cache_key = f"rankings_{type}"
        cached = self._cache_get(cache_key, max_age_hours=24)
        if cached:
            return cached
        
        data = self._get('rankings', {'type': type})
        
        if data.get('response'):
            self._cache_set(cache_key, data)
        
        return data
    
    def get_games(
        self, 
        date: str = None, 
        player_id: int = None,
        season: int = None
    ) -> Dict:
        """
        Get games/matches.
        
        Args:
            date: Format YYYY-MM-DD
            player_id: Filter by player
            season: Filter by season year
        """
        params = {}
        if date:
            params['date'] = date
        if player_id:
            params['player'] = player_id
        if season:
            params['season'] = season
        
        cache_key = f"games_{date or 'all'}_{player_id or 'all'}_{season or 'all'}"
        cached = self._cache_get(cache_key, max_age_hours=1)  # Short cache for live games
        if cached and not date:  # Don't cache today's games long
            return cached
        
        data = self._get('games', params)
        
        if data.get('response'):
            self._cache_set(cache_key, data)
        
        return data
    
    def get_game_statistics(self, game_id: int) -> Dict:
        """Get detailed statistics for a specific game"""
        cache_key = f"game_stats_{game_id}"
        cached = self._cache_get(cache_key, max_age_hours=168)  # Long cache for completed games
        if cached:
            return cached
        
        data = self._get('games/statistics', {'id': game_id})
        
        if data.get('response'):
            self._cache_set(cache_key, data)
        
        return data
    
    def search_player(self, name: str) -> List[Dict]:
        """Search for players by name"""
        data = self.get_player(name=name)
        return data.get('response', [])
    
    def get_head_to_head(self, player1_id: int, player2_id: int) -> Dict:
        """Get head-to-head record between two players"""
        cache_key = f"h2h_{min(player1_id, player2_id)}_{max(player1_id, player2_id)}"
        cached = self._cache_get(cache_key, max_age_hours=24)
        if cached:
            return cached
        
        data = self._get('games/h2h', {
            'h2h': f"{player1_id}-{player2_id}"
        })
        
        if data.get('response'):
            self._cache_set(cache_key, data)
        
        return data


# ============================================================================
# SECTION 3: DATABASE SYNC
# ============================================================================

class TennisAPISync:
    """
    Sync API-Sports data to local SQLite database.
    
    Integrates with tennis_csv_importer.py database schema.
    """
    
    def __init__(self, db_path: str = None, api_client: APISportsTennisClient = None):
        if db_path is None:
            db_path = Path(__file__).parent / "tennis_stats.db"
        
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        self.api = api_client or APISportsTennisClient()
        
        # Player ID mapping (API ID -> local ID)
        self.player_map = {}
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def sync_player(self, player_name: str) -> Optional[Dict]:
        """
        Sync a player's data from API to database.
        
        Returns player info dict or None if not found.
        """
        print(f"\n[SYNC] Searching for {player_name}...")
        
        # Search API
        players = self.api.search_player(player_name)
        
        if not players:
            print(f"  ❌ Player not found in API")
            return None
        
        # Find best match
        player = None
        for p in players:
            if player_name.lower() in p.get('name', '').lower():
                player = p
                break
        
        if not player:
            player = players[0]  # Take first result
        
        print(f"  ✓ Found: {player.get('name')} (ID: {player.get('id')})")
        
        # Get/create in local DB
        cursor = self.conn.cursor()
        
        # Check if exists
        cursor.execute(
            "SELECT player_id FROM players WHERE player_name = ?",
            (player.get('name'),)
        )
        row = cursor.fetchone()
        
        if row:
            local_id = row['player_id']
            print(f"  ✓ Already in database (ID: {local_id})")
        else:
            # Insert new
            cursor.execute(
                "INSERT INTO players (player_name, country, hand) VALUES (?, ?, ?)",
                (player.get('name'), player.get('country', {}).get('code'), None)
            )
            self.conn.commit()
            local_id = cursor.lastrowid
            print(f"  ✓ Added to database (ID: {local_id})")
        
        # Map API ID to local ID
        self.player_map[player.get('id')] = local_id
        
        return {
            'api_id': player.get('id'),
            'local_id': local_id,
            'name': player.get('name'),
            'country': player.get('country', {}).get('name'),
            'rank': player.get('rank')
        }
    
    def sync_player_stats(self, player_name: str, season: int = None) -> Dict:
        """
        Sync player statistics from API.
        
        Returns stats summary.
        """
        if season is None:
            season = datetime.now().year
        
        # First sync player
        player_info = self.sync_player(player_name)
        if not player_info:
            return None
        
        print(f"\n[SYNC] Getting {season} statistics for {player_name}...")
        
        try:
            stats_data = self.api.get_player_statistics(player_info['api_id'], season)
            
            if not stats_data.get('response'):
                print(f"  ❌ No statistics available")
                return None
            
            stats = stats_data['response'][0] if stats_data['response'] else {}
            
            # Parse stats
            summary = {
                'player': player_info['name'],
                'season': season,
                'matches_played': stats.get('games', {}).get('played', 0),
                'matches_won': stats.get('games', {}).get('won', 0),
                'aces_total': stats.get('statistics', {}).get('aces'),
                'double_faults_total': stats.get('statistics', {}).get('double_faults'),
                'first_serve_pct': stats.get('statistics', {}).get('first_serve_percentage'),
                'break_points_saved_pct': stats.get('statistics', {}).get('break_points_saved_percentage'),
            }
            
            print(f"  ✓ Stats loaded: {summary['matches_played']} matches, {summary['matches_won']} wins")
            
            return summary
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return None
    
    def sync_recent_games(self, player_name: str, n_games: int = 10) -> List[Dict]:
        """
        Sync recent games for a player.
        
        Returns list of game summaries.
        """
        player_info = self.sync_player(player_name)
        if not player_info:
            return []
        
        print(f"\n[SYNC] Getting recent games for {player_name}...")
        
        try:
            games_data = self.api.get_games(
                player_id=player_info['api_id'],
                season=datetime.now().year
            )
            
            if not games_data.get('response'):
                print(f"  ❌ No games found")
                return []
            
            games = []
            for game in games_data['response'][:n_games]:
                # Get detailed stats
                game_stats = self.api.get_game_statistics(game['id'])
                
                games.append({
                    'date': game.get('date'),
                    'tournament': game.get('league', {}).get('name'),
                    'surface': game.get('league', {}).get('surface'),
                    'player1': game.get('players', {}).get('home', {}).get('name'),
                    'player2': game.get('players', {}).get('away', {}).get('name'),
                    'score': game.get('scores'),
                    'winner': game.get('winner', {}).get('name'),
                    'stats': game_stats.get('response', [])
                })
            
            print(f"  ✓ Loaded {len(games)} games")
            return games
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return []
    
    def get_player_profile_for_mc(self, player_name: str) -> Dict:
        """
        Get player profile formatted for Monte Carlo simulation.
        
        Combines API stats with local historical data.
        """
        # Sync latest data
        player_info = self.sync_player(player_name)
        if not player_info:
            return None
        
        # Get API stats
        api_stats = self.sync_player_stats(player_name)
        
        # Get local historical data
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                AVG(ms.aces) as avg_aces,
                AVG(ms.double_faults) as avg_df,
                AVG(ms.service_games_won * 1.0 / NULLIF(ms.service_games_played, 0)) as serve_hold_rate,
                AVG(ms.break_points_saved * 1.0 / NULLIF(ms.break_points_faced, 0)) as bp_save_rate,
                AVG(ms.total_games_won) as avg_games_won,
                COUNT(*) as n_matches,
                -- Variance
                AVG(ms.aces * ms.aces) - AVG(ms.aces) * AVG(ms.aces) as var_aces,
                AVG(ms.total_games_won * ms.total_games_won) - AVG(ms.total_games_won) * AVG(ms.total_games_won) as var_games
            FROM players p
            JOIN match_stats ms ON p.player_id = ms.player_id
            WHERE p.player_name LIKE ?
        """, (f"%{player_name}%",))
        
        local_stats = cursor.fetchone()
        
        import math
        
        profile = {
            'player_name': player_info['name'],
            'api_id': player_info['api_id'],
            'rank': player_info.get('rank'),
            
            # From API (current season)
            'season_matches': api_stats.get('matches_played', 0) if api_stats else 0,
            'season_win_rate': (api_stats.get('matches_won', 0) / max(api_stats.get('matches_played', 1), 1)) if api_stats else 0,
            
            # From local DB (historical)
            'historical_matches': local_stats['n_matches'] if local_stats else 0,
            'avg_aces': local_stats['avg_aces'] if local_stats else 0,
            'std_aces': math.sqrt(local_stats['var_aces']) if local_stats and local_stats['var_aces'] else 0,
            'avg_df': local_stats['avg_df'] if local_stats else 0,
            'serve_hold_rate': local_stats['serve_hold_rate'] if local_stats else 0.65,
            'bp_save_rate': local_stats['bp_save_rate'] if local_stats else 0.60,
            'avg_games_won': local_stats['avg_games_won'] if local_stats else 0,
            'std_games_won': math.sqrt(local_stats['var_games']) if local_stats and local_stats['var_games'] else 0,
            
            # Confidence (based on data availability)
            'confidence': min(1.0, (local_stats['n_matches'] if local_stats else 0) / 20)
        }
        
        return profile


# ============================================================================
# SECTION 4: CLI INTERFACE
# ============================================================================

def main():
    """CLI for API-Sports tennis connector"""
    import argparse
    
    parser = argparse.ArgumentParser(description='API-Sports Tennis Connector')
    parser.add_argument('--search', help='Search for a player')
    parser.add_argument('--stats', help='Get player statistics')
    parser.add_argument('--games', help='Get player recent games')
    parser.add_argument('--profile', help='Get MC simulation profile')
    parser.add_argument('--h2h', nargs=2, help='Head-to-head between two players')
    parser.add_argument('--rankings', choices=['atp', 'wta'], help='Get rankings')
    parser.add_argument('--test', action='store_true', help='Test API connection')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("API-SPORTS TENNIS CONNECTOR")
    print("=" * 60)
    
    try:
        client = APISportsTennisClient()
        sync = TennisAPISync()
        
        if args.test:
            print("\n[TEST] Testing API connection...")
            data = client.get_rankings('atp')
            if data.get('response'):
                print(f"  ✓ API connected! Found {len(data['response'])} rankings")
                print(f"  Top 3 ATP:")
                for p in data['response'][:3]:
                    print(f"    #{p.get('position')}: {p.get('player', {}).get('name')}")
            else:
                print(f"  ❌ API error: {data.get('errors')}")
        
        if args.search:
            print(f"\n[SEARCH] {args.search}")
            players = client.search_player(args.search)
            for p in players[:5]:
                print(f"  • {p.get('name')} (ID: {p.get('id')}) - {p.get('country', {}).get('name')}")
        
        if args.stats:
            stats = sync.sync_player_stats(args.stats)
            if stats:
                print(f"\n{stats['player']} - {stats['season']} Season:")
                print(f"  Matches: {stats['matches_played']} ({stats['matches_won']} wins)")
                if stats.get('aces_total'):
                    print(f"  Aces: {stats['aces_total']}")
                if stats.get('first_serve_pct'):
                    print(f"  1st Serve %: {stats['first_serve_pct']}%")
        
        if args.games:
            games = sync.sync_recent_games(args.games, n_games=5)
            print(f"\nRecent games for {args.games}:")
            for g in games:
                print(f"  {g['date'][:10]} | {g['tournament'][:25]:25} | {g['player1']} vs {g['player2']}")
        
        if args.profile:
            profile = sync.get_player_profile_for_mc(args.profile)
            if profile:
                print(f"\n{'='*50}")
                print(f"MC PROFILE: {profile['player_name']}")
                print(f"{'='*50}")
                print(f"  Rank: #{profile.get('rank', 'N/A')}")
                print(f"  Historical matches: {profile['historical_matches']}")
                print(f"  Avg Aces: {profile['avg_aces']:.1f} ± {profile['std_aces']:.1f}")
                print(f"  Avg DF: {profile['avg_df']:.1f}")
                print(f"  Serve Hold: {profile['serve_hold_rate']:.1%}")
                print(f"  BP Save: {profile['bp_save_rate']:.1%}")
                print(f"  Avg Games Won: {profile['avg_games_won']:.1f} ± {profile['std_games_won']:.1f}")
                print(f"  Confidence: {profile['confidence']:.1%}")
        
        if args.h2h:
            p1_info = sync.sync_player(args.h2h[0])
            p2_info = sync.sync_player(args.h2h[1])
            
            if p1_info and p2_info:
                h2h = client.get_head_to_head(p1_info['api_id'], p2_info['api_id'])
                games = h2h.get('response', [])
                
                p1_wins = sum(1 for g in games if g.get('winner', {}).get('id') == p1_info['api_id'])
                p2_wins = len(games) - p1_wins
                
                print(f"\n{'='*50}")
                print(f"HEAD-TO-HEAD: {p1_info['name']} vs {p2_info['name']}")
                print(f"{'='*50}")
                print(f"  Total matches: {len(games)}")
                print(f"  {p1_info['name']}: {p1_wins} wins")
                print(f"  {p2_info['name']}: {p2_wins} wins")
        
        if args.rankings:
            data = client.get_rankings(args.rankings)
            print(f"\n{args.rankings.upper()} Rankings (Top 20):")
            for p in data.get('response', [])[:20]:
                print(f"  #{p.get('position'):3} {p.get('player', {}).get('name'):25} {p.get('points')} pts")
        
        sync.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
