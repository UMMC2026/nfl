"""
ON-DEMAND TENNIS DATA FETCHER
Fetches player match data from APIs when not found in local database.
Saves to CSV backup automatically.

Available APIs (free tiers):
1. API-Tennis.com - Free tier (100 requests/day)
2. RapidAPI Tennis Live Data - Free tier available
3. Flashscore (scraping fallback)

Usage:
    python tennis/scripts/fetch_player_on_demand.py --player "Fangran Tian"
    python tennis/scripts/fetch_player_on_demand.py --player "Tereza Martincova" --save

SOP v2.1 Compliant - Dynamic Data Layer
"""

import argparse
import json
import csv
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3
import os

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use environment variables directly

# ============================================================================
# PATHS
# ============================================================================

TENNIS_DIR = Path(__file__).parent.parent
DATA_DIR = TENNIS_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "api_cache"
DB_PATH = DATA_DIR / "tennis_stats.db"

# Ensure directories exist
CACHE_DIR.mkdir(exist_ok=True, parents=True)
RAW_DIR.mkdir(exist_ok=True, parents=True)

# ============================================================================
# API CONFIGURATIONS
# ============================================================================

# API-Tennis.com (free tier: 100 requests/day)
# Sign up at: https://www.api-tennis.com/
API_TENNIS_KEY = os.environ.get("API_TENNIS_KEY", "")
API_TENNIS_BASE = "https://api.api-tennis.com/tennis/"

# RapidAPI Tennis (various providers)
# Sign up at: https://rapidapi.com/search/tennis
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "tennis-live-data.p.rapidapi.com"

# Free alternative: Tennis Abstract GitHub (already using)
SACKMANN_BASE = "https://raw.githubusercontent.com/JeffSackmann"


# ============================================================================
# API CLIENTS
# ============================================================================

class TennisAPIClient:
    """Base class for tennis API clients"""
    
    def __init__(self):
        self.cache_file = CACHE_DIR / "api_responses.json"
        self._load_cache()
    
    def _load_cache(self):
        """Load cached responses"""
        if self.cache_file.exists():
            self.cache = json.loads(self.cache_file.read_text(encoding='utf-8'))
        else:
            self.cache = {}
    
    def _save_cache(self):
        """Save cache to disk"""
        self.cache_file.write_text(json.dumps(self.cache, indent=2), encoding='utf-8')
    
    def search_player(self, name: str) -> Optional[Dict]:
        """Search for player - override in subclass"""
        raise NotImplementedError
    
    def get_player_matches(self, player_id: str, limit: int = 50) -> List[Dict]:
        """Get player matches - override in subclass"""
        raise NotImplementedError


class APITennisClient(TennisAPIClient):
    """
    Client for API-Tennis.com
    Free tier: 100 requests/day
    
    To use:
    1. Sign up at https://www.api-tennis.com/
    2. Set API_TENNIS_KEY environment variable
    """
    
    def __init__(self):
        super().__init__()
        self.api_key = API_TENNIS_KEY
        self.base_url = API_TENNIS_BASE
    
    def _request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Make API request"""
        if not self.api_key:
            print("⚠️ API_TENNIS_KEY not set. Sign up at https://www.api-tennis.com/")
            return None
        
        params = params or {}
        params['APIkey'] = self.api_key
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.base_url}?{query}"
        
        # Check cache
        cache_key = f"api_tennis_{endpoint}_{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache[cache_key] = data
                self._save_cache()
                return data
        except Exception as e:
            print(f"API Error: {e}")
            return None
    
    def search_player(self, name: str) -> Optional[Dict]:
        """Search for player by name"""
        return self._request("", {"method": "get_players", "player_name": name})
    
    def get_player_matches(self, player_key: str, limit: int = 50) -> List[Dict]:
        """Get player's recent matches"""
        result = self._request("", {
            "method": "get_games", 
            "player_key": player_key,
            "n": str(limit)
        })
        if result and 'result' in result:
            return result['result']
        return []


class RapidAPITennisClient(TennisAPIClient):
    """
    Client for RapidAPI Tennis Live Data
    
    To use:
    1. Sign up at https://rapidapi.com/sportcontentapi/api/tennis-live-data
    2. Set RAPIDAPI_KEY environment variable
    """
    
    def __init__(self):
        super().__init__()
        self.api_key = RAPIDAPI_KEY
        self.host = RAPIDAPI_HOST
    
    def _request(self, endpoint: str) -> Optional[Dict]:
        """Make API request"""
        if not self.api_key:
            print("⚠️ RAPIDAPI_KEY not set. Sign up at https://rapidapi.com/")
            return None
        
        url = f"https://{self.host}/{endpoint}"
        
        # Check cache
        cache_key = f"rapidapi_{endpoint}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            req = urllib.request.Request(url, headers={
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": self.host
            })
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache[cache_key] = data
                self._save_cache()
                return data
        except Exception as e:
            print(f"API Error: {e}")
            return None
    
    def search_player(self, name: str) -> Optional[Dict]:
        """Search for player"""
        # RapidAPI Tennis Live Data uses different endpoints
        return self._request(f"players/search/{name.replace(' ', '%20')}")
    
    def get_player_matches(self, player_id: str, limit: int = 50) -> List[Dict]:
        """Get player matches"""
        result = self._request(f"players/{player_id}/matches")
        if result and 'results' in result:
            return result['results'][:limit]
        return []


# ============================================================================
# ON-DEMAND FETCHER
# ============================================================================

class OnDemandTennisFetcher:
    """
    Fetches tennis player data on-demand from available APIs.
    Saves to CSV backup and imports to database.
    """
    
    def __init__(self):
        self.clients = []
        
        # Initialize available clients
        if API_TENNIS_KEY:
            self.clients.append(('API-Tennis', APITennisClient()))
        if RAPIDAPI_KEY:
            self.clients.append(('RapidAPI', RapidAPITennisClient()))
        
        # CSV backup file
        self.backup_csv = RAW_DIR / "on_demand_matches.csv"
        self._init_csv()
    
    def _init_csv(self):
        """Initialize CSV backup file with headers"""
        if not self.backup_csv.exists():
            with open(self.backup_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'fetch_date', 'source', 'player_name', 'opponent_name',
                    'tournament', 'surface', 'match_date', 'round',
                    'score', 'winner', 'aces', 'double_faults',
                    'first_serve_pct', 'break_points_saved', 'break_points_faced'
                ])
    
    def check_local_db(self, player_name: str) -> bool:
        """Check if player has data in local database"""
        if not DB_PATH.exists():
            return False
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        # Check if player exists and has match stats
        cur.execute("""
            SELECT COUNT(*) FROM match_stats ms
            JOIN players p ON ms.player_id = p.player_id
            WHERE p.player_name LIKE ?
        """, (f"%{player_name}%",))
        
        count = cur.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def fetch_player(self, player_name: str, force: bool = False) -> Dict:
        """
        Fetch player data from APIs if not in local database.
        
        Args:
            player_name: Player to search for
            force: Fetch even if player exists locally
        
        Returns:
            Dict with player info and matches
        """
        result = {
            'player_name': player_name,
            'found': False,
            'source': None,
            'matches': [],
            'local_exists': False
        }
        
        # Check local database first
        if self.check_local_db(player_name):
            result['local_exists'] = True
            if not force:
                print(f"✓ {player_name} exists in local database")
                return result
        
        if not self.clients:
            print("\n⚠️ No API keys configured!")
            print("\nTo enable on-demand fetching, set one of these environment variables:")
            print("  • API_TENNIS_KEY - Get from https://www.api-tennis.com/ (free: 100 req/day)")
            print("  • RAPIDAPI_KEY - Get from https://rapidapi.com/search/tennis")
            return result
        
        # Try each API client
        for name, client in self.clients:
            print(f"\n[{name}] Searching for {player_name}...")
            
            try:
                player_data = client.search_player(player_name)
                
                if player_data and 'result' in player_data:
                    players = player_data['result']
                    if players:
                        player = players[0]
                        player_key = player.get('player_key', player.get('id'))
                        
                        print(f"  Found: {player.get('player_name', player_name)}")
                        
                        # Get matches
                        matches = client.get_player_matches(player_key)
                        
                        if matches:
                            result['found'] = True
                            result['source'] = name
                            result['matches'] = matches
                            result['player_data'] = player
                            
                            print(f"  Retrieved {len(matches)} matches")
                            return result
            
            except Exception as e:
                print(f"  Error: {e}")
                continue
        
        print(f"\n✗ Could not find {player_name} in any API")
        return result
    
    def save_to_csv(self, result: Dict) -> Path:
        """Save fetched matches to CSV backup"""
        if not result['found'] or not result['matches']:
            return None
        
        player_name = result['player_name']
        source = result['source']
        fetch_date = datetime.now().strftime("%Y-%m-%d")
        
        rows_added = 0
        
        with open(self.backup_csv, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            for match in result['matches']:
                # Normalize match data (different APIs have different formats)
                row = [
                    fetch_date,
                    source,
                    player_name,
                    match.get('opponent', match.get('opponent_name', '')),
                    match.get('tournament', match.get('event_name', '')),
                    match.get('surface', ''),
                    match.get('date', match.get('match_date', '')),
                    match.get('round', ''),
                    match.get('score', match.get('result', '')),
                    match.get('winner', ''),
                    match.get('aces', ''),
                    match.get('double_faults', ''),
                    match.get('first_serve_pct', ''),
                    match.get('bp_saved', ''),
                    match.get('bp_faced', '')
                ]
                writer.writerow(row)
                rows_added += 1
        
        print(f"\n✓ Saved {rows_added} matches to {self.backup_csv.name}")
        return self.backup_csv
    
    def import_to_db(self, result: Dict) -> int:
        """Import fetched matches to SQLite database"""
        if not result['found'] or not result['matches']:
            return 0
        
        if not DB_PATH.exists():
            print("Database not found!")
            return 0
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        player_name = result['player_name']
        imported = 0
        
        # Ensure player exists
        cur.execute('INSERT OR IGNORE INTO players (player_name) VALUES (?)', (player_name,))
        cur.execute('SELECT player_id FROM players WHERE player_name = ?', (player_name,))
        player_id = cur.fetchone()[0]
        
        for match in result['matches']:
            try:
                # Extract match data
                opponent = match.get('opponent', match.get('opponent_name', 'Unknown'))
                tournament = match.get('tournament', match.get('event_name', 'Unknown'))
                surface = match.get('surface', 'Hard')
                match_date = match.get('date', match.get('match_date', ''))
                
                # Ensure opponent exists
                cur.execute('INSERT OR IGNORE INTO players (player_name) VALUES (?)', (opponent,))
                cur.execute('SELECT player_id FROM players WHERE player_name = ?', (opponent,))
                opp_row = cur.fetchone()
                opponent_id = opp_row[0] if opp_row else None
                
                # Determine winner
                won = match.get('winner', '').lower() == player_name.lower()
                winner_id = player_id if won else opponent_id
                
                # Insert match
                cur.execute('''
                    INSERT OR IGNORE INTO matches (
                        tournament_name, tournament_level, surface, match_date,
                        round, player1_id, player2_id, winner_id, score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tournament, 'On-Demand', surface, match_date,
                    match.get('round', ''), player_id, opponent_id, winner_id,
                    match.get('score', match.get('result', ''))
                ))
                
                if cur.rowcount > 0:
                    imported += 1
                
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        
        print(f"✓ Imported {imported} matches to database")
        return imported


# ============================================================================
# CLI
# ============================================================================

def show_api_setup_instructions():
    """Show instructions for setting up API keys"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           TENNIS API SETUP INSTRUCTIONS                          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  OPTION 1: API-Tennis.com (Recommended)                          ║
║  ─────────────────────────────────────                           ║
║  • Free tier: 100 requests/day                                   ║
║  • Covers: ATP, WTA, ITF, Challengers                            ║
║  • Sign up: https://www.api-tennis.com/                          ║
║                                                                  ║
║  Setup:                                                          ║
║    $env:API_TENNIS_KEY = "your_key_here"                         ║
║    # Or add to .env file:                                        ║
║    API_TENNIS_KEY=your_key_here                                  ║
║                                                                  ║
║  ────────────────────────────────────────────────────────────    ║
║                                                                  ║
║  OPTION 2: RapidAPI Tennis                                       ║
║  ─────────────────────────────                                   ║
║  • Various free tiers available                                  ║
║  • Sign up: https://rapidapi.com/search/tennis                   ║
║                                                                  ║
║  Setup:                                                          ║
║    $env:RAPIDAPI_KEY = "your_key_here"                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


def main():
    parser = argparse.ArgumentParser(description="On-Demand Tennis Data Fetcher")
    parser.add_argument('--player', '-p', help='Player name to fetch')
    parser.add_argument('--save', '-s', action='store_true', help='Save to CSV backup')
    parser.add_argument('--import-db', '-i', action='store_true', help='Import to database')
    parser.add_argument('--force', '-f', action='store_true', help='Force fetch even if exists locally')
    parser.add_argument('--setup', action='store_true', help='Show API setup instructions')
    parser.add_argument('--status', action='store_true', help='Show API status')
    
    args = parser.parse_args()
    
    if args.setup:
        show_api_setup_instructions()
        return
    
    fetcher = OnDemandTennisFetcher()
    
    if args.status:
        print("\n" + "="*60)
        print("ON-DEMAND FETCHER STATUS")
        print("="*60)
        
        print(f"\nAPI Keys Configured:")
        print(f"  • API_TENNIS_KEY: {'✓ Set' if API_TENNIS_KEY else '✗ Not set'}")
        print(f"  • RAPIDAPI_KEY:   {'✓ Set' if RAPIDAPI_KEY else '✗ Not set'}")
        
        print(f"\nBackup CSV: {fetcher.backup_csv}")
        if fetcher.backup_csv.exists():
            lines = len(fetcher.backup_csv.read_text().splitlines()) - 1
            print(f"  → {lines} matches saved")
        
        print(f"\nCache: {CACHE_DIR}")
        cache_files = list(CACHE_DIR.glob("*.json"))
        print(f"  → {len(cache_files)} cached responses")
        
        if not API_TENNIS_KEY and not RAPIDAPI_KEY:
            print("\n⚠️ No API keys configured! Run with --setup for instructions.")
        
        print("="*60)
        return
    
    if not args.player:
        parser.print_help()
        print("\nExamples:")
        print("  python fetch_player_on_demand.py --player 'Fangran Tian' --save")
        print("  python fetch_player_on_demand.py --player 'Tereza Martincova' --save --import-db")
        print("  python fetch_player_on_demand.py --setup")
        return
    
    # Fetch player
    result = fetcher.fetch_player(args.player, force=args.force)
    
    if result['found']:
        if args.save:
            fetcher.save_to_csv(result)
        
        if args.import_db:
            fetcher.import_to_db(result)
        
        if not args.save and not args.import_db:
            print("\nTip: Use --save to backup to CSV or --import-db to add to database")
    
    elif result['local_exists']:
        print(f"\n{args.player} already has data locally. Use --force to re-fetch.")


if __name__ == "__main__":
    main()
