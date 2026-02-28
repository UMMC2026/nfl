"""
NBA STATS CACHE SYSTEM
Downloads player stats from NBA API and saves to CSV for fast retrieval.

Usage:
    python nba_stats_cache.py --status              # Check cache status
    python nba_stats_cache.py --player "Cam Thomas" # Get/update player
    python nba_stats_cache.py --from-json FILE.json # Update all players from slate
    python nba_stats_cache.py --export              # Export master CSV

Benefits:
    - No repeated API calls (saves time)
    - Works offline after initial download
    - Easy to view/edit in Excel
    - Persists between sessions
"""

import os
import csv
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

CACHE_DIR = Path("cache/nba_stats")
PLAYER_GAMELOGS_DIR = CACHE_DIR / "gamelogs"
PLAYER_IDS_FILE = CACHE_DIR / "player_ids.csv"
METADATA_FILE = CACHE_DIR / "metadata.json"
MASTER_STATS_FILE = CACHE_DIR / "all_player_stats.csv"

# How old data can be before refresh (in hours)
CACHE_TTL_HOURS = 12

# Rate limiting (NBA API is sensitive)
API_DELAY_SECONDS = 0.6

# ═══════════════════════════════════════════════════════════════════
# GAMELOG CSV COLUMNS
# ═══════════════════════════════════════════════════════════════════

GAMELOG_COLUMNS = [
    'player_name',
    'game_date',
    'opponent',
    'home_away',
    'result',
    'minutes',
    'points',
    'rebounds',
    'assists',
    'steals',
    'blocks',
    'turnovers',
    'fg_made',
    'fg_attempted',
    'fg3_made',
    'fg3_attempted',
    'ft_made',
    'ft_attempted',
    'plus_minus',
    'pra'
]

# ═══════════════════════════════════════════════════════════════════
# CACHE MANAGER
# ═══════════════════════════════════════════════════════════════════

class NBAStatsCache:
    """Manages NBA stats caching to CSV files"""
    
    def __init__(self):
        self._setup_directories()
        self.metadata = self._load_metadata()
        self._player_ids = self._load_player_ids()
    
    def _setup_directories(self):
        """Create cache directories if they don't exist"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        PLAYER_GAMELOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    def _load_metadata(self) -> Dict:
        """Load cache metadata (last update times, etc.)"""
        if METADATA_FILE.exists():
            with open(METADATA_FILE, encoding='utf-8') as f:
                return json.load(f)
        return {'players': {}}
    
    def _save_metadata(self):
        """Save cache metadata"""
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    def _load_player_ids(self) -> Dict[str, int]:
        """Load player ID cache from CSV"""
        if not PLAYER_IDS_FILE.exists():
            return {}
        
        ids = {}
        with open(PLAYER_IDS_FILE, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ids[row['player_name']] = int(row['player_id'])
        return ids
    
    def _save_player_id(self, player_name: str, player_id: int):
        """Save a player ID to CSV cache"""
        self._player_ids[player_name] = player_id
        
        # Check if file exists to write header
        file_exists = PLAYER_IDS_FILE.exists()
        
        with open(PLAYER_IDS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['player_name', 'player_id'])
            writer.writerow([player_name, player_id])
    
    def _is_cache_fresh(self, player_name: str) -> bool:
        """Check if player's cached data is still fresh"""
        player_info = self.metadata.get('players', {}).get(player_name, {})
        last_updated = player_info.get('last_updated')
        
        if not last_updated:
            return False
        
        last_update_dt = datetime.fromisoformat(last_updated)
        age_hours = (datetime.now() - last_update_dt).total_seconds() / 3600
        
        return age_hours < CACHE_TTL_HOURS
    
    def get_player_id(self, player_name: str) -> Optional[int]:
        """Get player ID, fetching from API if needed"""
        
        # Check cache first
        if player_name in self._player_ids:
            return self._player_ids[player_name]
        
        # Fetch from API
        try:
            from nba_api.stats.static import players
            
            all_players = players.get_players()
            
            # Try exact match first
            for p in all_players:
                if p['full_name'].lower() == player_name.lower():
                    self._save_player_id(player_name, p['id'])
                    return p['id']
            
            # Try partial match
            for p in all_players:
                if player_name.lower() in p['full_name'].lower():
                    self._save_player_id(player_name, p['id'])
                    return p['id']
            
            return None
            
        except Exception as e:
            print(f"   ⚠️  Could not find player ID for {player_name}: {e}")
            return None
    
    def fetch_gamelog(self, player_name: str, num_games: int = 10, force: bool = False) -> List[Dict]:
        """
        Fetch player game log, using cache if available.
        
        Args:
            player_name: Player's full name
            num_games: Number of recent games to fetch
            force: Force refresh even if cache is fresh
        
        Returns:
            List of game dicts with stats
        """
        
        # Check cache first (unless force refresh)
        if not force and self._is_cache_fresh(player_name):
            cached = self._load_gamelog_csv(player_name)
            if cached and len(cached) >= num_games:
                return cached[:num_games]
        
        # Fetch from API
        player_id = self.get_player_id(player_name)
        if not player_id:
            print(f"   ⚠️  Player not found: {player_name}")
            return []
        
        try:
            from nba_api.stats.endpoints import playergamelog
            
            time.sleep(API_DELAY_SECONDS)  # Rate limiting
            
            log = playergamelog.PlayerGameLog(
                player_id=player_id,
                season='2025-26',
                season_type_all_star='Regular Season'
            )
            
            df = log.get_data_frames()[0]
            
            if df.empty:
                print(f"   ⚠️  No games found for {player_name}")
                return []
            
            # Convert to list of dicts
            games = []
            for _, row in df.head(num_games).iterrows():
                matchup = str(row.get('MATCHUP', ''))
                game = {
                    'player_name': player_name,
                    'game_date': row.get('GAME_DATE', ''),
                    'opponent': matchup.split()[-1] if matchup else '',
                    'home_away': 'HOME' if 'vs.' in matchup else 'AWAY',
                    'result': row.get('WL', ''),
                    'minutes': int(row.get('MIN', 0)) if row.get('MIN') else 0,
                    'points': int(row.get('PTS', 0)),
                    'rebounds': int(row.get('REB', 0)),
                    'assists': int(row.get('AST', 0)),
                    'steals': int(row.get('STL', 0)),
                    'blocks': int(row.get('BLK', 0)),
                    'turnovers': int(row.get('TOV', 0)),
                    'fg_made': int(row.get('FGM', 0)),
                    'fg_attempted': int(row.get('FGA', 0)),
                    'fg3_made': int(row.get('FG3M', 0)),
                    'fg3_attempted': int(row.get('FG3A', 0)),
                    'ft_made': int(row.get('FTM', 0)),
                    'ft_attempted': int(row.get('FTA', 0)),
                    'plus_minus': int(row.get('PLUS_MINUS', 0)) if row.get('PLUS_MINUS') else 0,
                }
                game['pra'] = game['points'] + game['rebounds'] + game['assists']
                games.append(game)
            
            # Save to CSV cache
            self._save_gamelog_csv(player_name, games)
            
            # Update metadata
            self.metadata.setdefault('players', {})[player_name] = {
                'last_updated': datetime.now().isoformat(),
                'games_cached': len(games),
                'player_id': player_id
            }
            self._save_metadata()
            
            print(f"   ✅ Cached {len(games)} games for {player_name}")
            return games
            
        except Exception as e:
            print(f"   ❌ Error fetching {player_name}: {e}")
            
            # Try to return cached data even if stale
            cached = self._load_gamelog_csv(player_name)
            if cached:
                print(f"   ℹ️  Using stale cache ({len(cached)} games)")
                return cached[:num_games]
            
            return []
    
    def _save_gamelog_csv(self, player_name: str, games: List[Dict]):
        """Save player's game log to CSV"""
        safe_name = self._safe_filename(player_name)
        filepath = PLAYER_GAMELOGS_DIR / f"{safe_name}.csv"
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=GAMELOG_COLUMNS)
            writer.writeheader()
            writer.writerows(games)
    
    def _load_gamelog_csv(self, player_name: str) -> List[Dict]:
        """Load player's game log from CSV"""
        safe_name = self._safe_filename(player_name)
        filepath = PLAYER_GAMELOGS_DIR / f"{safe_name}.csv"
        
        if not filepath.exists():
            return []
        
        games = []
        with open(filepath, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                for key in ['minutes', 'points', 'rebounds', 'assists', 'steals',
                           'blocks', 'turnovers', 'fg_made', 'fg_attempted',
                           'fg3_made', 'fg3_attempted', 'ft_made', 'ft_attempted',
                           'plus_minus', 'pra']:
                    if key in row and row[key]:
                        try:
                            row[key] = int(row[key])
                        except:
                            row[key] = 0
                games.append(row)
        
        return games
    
    def _safe_filename(self, player_name: str) -> str:
        """Convert player name to safe filename"""
        return player_name.replace(' ', '_').replace("'", '').replace('"', '').replace('ë', 'e')
    
    def get_player_averages(self, player_name: str, num_games: int = 10) -> Dict:
        """
        Get player's averages from cached data.
        
        Returns dict with stat averages.
        """
        games = self.fetch_gamelog(player_name, num_games)
        
        if not games:
            return {}
        
        n = len(games)
        
        def safe_int(val):
            try:
                return int(val)
            except:
                return 0
        
        averages = {
            'player_name': player_name,
            'games': n,
            'points_avg': sum(safe_int(g.get('points', 0)) for g in games) / n,
            'rebounds_avg': sum(safe_int(g.get('rebounds', 0)) for g in games) / n,
            'assists_avg': sum(safe_int(g.get('assists', 0)) for g in games) / n,
            'steals_avg': sum(safe_int(g.get('steals', 0)) for g in games) / n,
            'blocks_avg': sum(safe_int(g.get('blocks', 0)) for g in games) / n,
            'turnovers_avg': sum(safe_int(g.get('turnovers', 0)) for g in games) / n,
            'fg3_made_avg': sum(safe_int(g.get('fg3_made', 0)) for g in games) / n,
            'minutes_avg': sum(safe_int(g.get('minutes', 0)) for g in games) / n,
            'pra_avg': sum(safe_int(g.get('pra', 0)) for g in games) / n,
        }
        
        # Calculate shooting percentages
        fg_made = sum(safe_int(g.get('fg_made', 0)) for g in games)
        fg_attempted = sum(safe_int(g.get('fg_attempted', 0)) for g in games)
        fg3_made = sum(safe_int(g.get('fg3_made', 0)) for g in games)
        fg3_attempted = sum(safe_int(g.get('fg3_attempted', 0)) for g in games)
        ft_made = sum(safe_int(g.get('ft_made', 0)) for g in games)
        ft_attempted = sum(safe_int(g.get('ft_attempted', 0)) for g in games)
        
        averages['fg_pct'] = round((fg_made / fg_attempted * 100), 1) if fg_attempted > 0 else 0
        averages['fg3_pct'] = round((fg3_made / fg3_attempted * 100), 1) if fg3_attempted > 0 else 0
        averages['ft_pct'] = round((ft_made / ft_attempted * 100), 1) if ft_attempted > 0 else 0
        
        return averages
    
    def get_stat_series(self, player_name: str, stat: str, num_games: int = 10) -> List[int]:
        """
        Get list of a specific stat over recent games.
        
        Args:
            player_name: Player name
            stat: Stat name (points, rebounds, assists, 3pm, pra, etc.)
            num_games: Number of games to fetch
        
        Returns:
            List of stat values (most recent first)
        """
        games = self.fetch_gamelog(player_name, num_games)
        
        # Map stat names to CSV columns
        stat_map = {
            'points': 'points', 'pts': 'points',
            'rebounds': 'rebounds', 'reb': 'rebounds',
            'assists': 'assists', 'ast': 'assists',
            'steals': 'steals', 'stl': 'steals',
            'blocks': 'blocks', 'blk': 'blocks',
            'turnovers': 'turnovers', 'tov': 'turnovers',
            '3pm': 'fg3_made', 'fg3m': 'fg3_made', 'threes': 'fg3_made',
            'pra': 'pra', 'pts+reb+ast': 'pra',
            'minutes': 'minutes', 'min': 'minutes',
        }
        
        stat_key = stat_map.get(stat.lower(), stat.lower())
        
        def safe_int(val):
            try:
                return int(val)
            except:
                return 0
        
        return [safe_int(g.get(stat_key, 0)) for g in games]
    
    def bulk_update(self, player_names: List[str], force: bool = False):
        """Update cache for multiple players"""
        print(f"\n📥 Updating cache for {len(player_names)} players...")
        print()
        
        updated = 0
        skipped = 0
        errors = 0
        
        for player in player_names:
            if not force and self._is_cache_fresh(player):
                print(f"   ⏭️  {player} (cache fresh)")
                skipped += 1
                continue
            
            games = self.fetch_gamelog(player, num_games=15, force=force)
            
            if games:
                updated += 1
            else:
                errors += 1
        
        print()
        print(f"✅ Updated: {updated} | ⏭️  Skipped: {skipped} | ❌ Errors: {errors}")
        
        return {'updated': updated, 'skipped': skipped, 'errors': errors}
    
    def export_master_csv(self, output_file: str = None):
        """Export all cached player stats to a single master CSV"""
        
        if output_file is None:
            output_file = MASTER_STATS_FILE
        
        all_stats = []
        
        # Collect all gamelogs
        for filepath in PLAYER_GAMELOGS_DIR.glob("*.csv"):
            player_name = filepath.stem.replace('_', ' ')
            games = self._load_gamelog_csv(player_name)
            
            if games:
                avgs = self.get_player_averages(player_name, len(games))
                avgs['last_updated'] = self.metadata.get('players', {}).get(
                    player_name, {}
                ).get('last_updated', '')
                all_stats.append(avgs)
        
        if not all_stats:
            print("No cached data to export")
            return
        
        # Sort by points average
        all_stats.sort(key=lambda x: x.get('points_avg', 0), reverse=True)
        
        # Write master CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = list(all_stats[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_stats)
        
        print(f"✅ Exported {len(all_stats)} players to {output_file}")
        return output_file
    
    def get_cache_status(self) -> Dict:
        """Get cache status summary"""
        
        cached_players = list(PLAYER_GAMELOGS_DIR.glob("*.csv"))
        
        fresh = 0
        stale = 0
        
        for filepath in cached_players:
            player_name = filepath.stem.replace('_', ' ')
            if self._is_cache_fresh(player_name):
                fresh += 1
            else:
                stale += 1
        
        return {
            'total_players': len(cached_players),
            'fresh': fresh,
            'stale': stale,
            'cache_dir': str(CACHE_DIR),
            'ttl_hours': CACHE_TTL_HOURS
        }


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS (for easy importing)
# ═══════════════════════════════════════════════════════════════════

# Global cache instance
_cache = None

def get_cache() -> NBAStatsCache:
    """Get the global cache instance"""
    global _cache
    if _cache is None:
        _cache = NBAStatsCache()
    return _cache

def get_player_stats(player_name: str, num_games: int = 10) -> Dict:
    """
    Quick function to get player stats from cache.
    
    Usage:
        from nba_stats_cache import get_player_stats
        stats = get_player_stats("Cam Thomas")
        print(f"PPG: {stats['points_avg']:.1f}")
    """
    return get_cache().get_player_averages(player_name, num_games)

def get_stat_series(player_name: str, stat: str, num_games: int = 10) -> List[int]:
    """
    Quick function to get stat series from cache.
    
    Usage:
        from nba_stats_cache import get_stat_series
        points = get_stat_series("Cam Thomas", "points")
        print(f"Last 10 games: {points}")
    """
    return get_cache().get_stat_series(player_name, stat, num_games)

def update_player(player_name: str, force: bool = False):
    """
    Update cache for a single player.
    
    Usage:
        from nba_stats_cache import update_player
        update_player("Cam Thomas")
    """
    get_cache().fetch_gamelog(player_name, num_games=15, force=force)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='NBA Stats Cache Manager')
    parser.add_argument('--player', type=str, help='Get/update specific player')
    parser.add_argument('--players', type=str, help='Comma-separated list of players')
    parser.add_argument('--refresh', action='store_true', help='Force refresh all data')
    parser.add_argument('--status', action='store_true', help='Show cache status')
    parser.add_argument('--export', action='store_true', help='Export all to master CSV')
    parser.add_argument('--from-json', type=str, help='Update players from JSON file')
    
    args = parser.parse_args()
    
    cache = get_cache()
    
    print("=" * 80)
    print("🏀 NBA STATS CACHE MANAGER")
    print("=" * 80)
    print()
    
    if args.status:
        status = cache.get_cache_status()
        print(f"📁 Cache directory: {status['cache_dir']}")
        print(f"👥 Total players cached: {status['total_players']}")
        print(f"✅ Fresh (< {status['ttl_hours']}h): {status['fresh']}")
        print(f"⚠️  Stale: {status['stale']}")
    
    elif args.export:
        cache.export_master_csv()
    
    elif args.player:
        print(f"Fetching stats for: {args.player}")
        stats = cache.get_player_averages(args.player, 10)
        if stats:
            print()
            print(f"📊 {args.player} (Last {stats['games']} games):")
            print(f"   PPG: {stats['points_avg']:.1f}")
            print(f"   RPG: {stats['rebounds_avg']:.1f}")
            print(f"   APG: {stats['assists_avg']:.1f}")
            print(f"   3PM: {stats['fg3_made_avg']:.1f}")
            print(f"   PRA: {stats['pra_avg']:.1f}")
            print(f"   FG%: {stats['fg_pct']:.1f}%")
            print(f"   3P%: {stats['fg3_pct']:.1f}%")
            print(f"   MIN: {stats['minutes_avg']:.1f}")
            
            # Show last 5 games
            series = cache.get_stat_series(args.player, 'points', 5)
            print(f"\n   Last 5 games (PTS): {series}")
        else:
            print(f"❌ Could not fetch stats for {args.player}")
    
    elif args.players:
        player_list = [p.strip() for p in args.players.split(',')]
        cache.bulk_update(player_list, force=args.refresh)
        cache.export_master_csv()
    
    elif args.from_json:
        # Extract players from JSON file
        print(f"📂 Loading players from: {args.from_json}")
        
        with open(args.from_json, encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', []))
        else:
            picks = data
        
        players = list(set(p.get('player', '') for p in picks if p.get('player')))
        print(f"   Found {len(players)} unique players")
        print()
        
        cache.bulk_update(players, force=args.refresh)
        cache.export_master_csv()
    
    else:
        # Show help
        print("Usage examples:")
        print()
        print("  # Check cache status")
        print("  python nba_stats_cache.py --status")
        print()
        print("  # Get single player stats")
        print('  python nba_stats_cache.py --player "Cam Thomas"')
        print()
        print("  # Update multiple players")
        print('  python nba_stats_cache.py --players "Cam Thomas,Stephen Curry"')
        print()
        print("  # Update all players from JSON slate")
        print("  python nba_stats_cache.py --from-json outputs/FILE.json")
        print()
        print("  # Force refresh all data")
        print("  python nba_stats_cache.py --from-json outputs/FILE.json --refresh")
        print()
        print("  # Export to master CSV")
        print("  python nba_stats_cache.py --export")
    
    print()
    print("=" * 80)
