"""
FUOOM PLAYER STATS CACHE (SQLite Version)
Fast, indexed player stats with data quality validation.

Usage:
    from player_stats_db import PlayerStatsDB
    
    db = PlayerStatsDB()
    db.update_player("Cam Thomas")
    stats = db.get_player("Cam Thomas")
    
    # Bulk update from slate
    db.update_from_json("outputs/SLATE.json")

Benefits:
    - Instant lookups (indexed by player name)
    - Data quality validation (detect μ=8.7 bugs)
    - Team mapping source of truth
    - Freshness tracking
    - Sample size verification
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
from contextlib import contextmanager

# ═══════════════════════════════════════════════════════════════════
# NBA API IMPORT (Optional)
# ═══════════════════════════════════════════════════════════════════

try:
    from nba_api.stats.static import players as nba_players
    from nba_api.stats.endpoints import playergamelog
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    print("⚠️  nba_api not installed. Run: pip install nba_api")

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

DB_PATH = Path("cache/player_stats.db")
CACHE_TTL_HOURS = 12
API_DELAY = 0.6  # Rate limiting

# Team code mappings
TEAM_ABBREVIATIONS = {
    'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
    'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
    'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
    'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
    'Los Angeles Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
    'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
    'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
    'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
    'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
    'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
}

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class PlayerStatsDB:
    """SQLite database for caching player stats with fast indexed lookups"""
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema"""
        with self._get_conn() as conn:
            # Main player stats table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_name TEXT PRIMARY KEY,
                    player_id INTEGER,
                    team TEXT,
                    position TEXT,
                    
                    -- Last update
                    last_updated TIMESTAMP,
                    games_available INTEGER,
                    
                    -- L10 Averages
                    points_L10 REAL,
                    rebounds_L10 REAL,
                    assists_L10 REAL,
                    steals_L10 REAL,
                    blocks_L10 REAL,
                    turnovers_L10 REAL,
                    fg3_made_L10 REAL,
                    pra_L10 REAL,
                    
                    -- L10 Standard Deviations
                    points_L10_std REAL,
                    rebounds_L10_std REAL,
                    assists_L10_std REAL,
                    fg3_made_L10_std REAL,
                    pra_L10_std REAL,
                    
                    -- L10 Min/Max (for range validation)
                    points_L10_min REAL,
                    points_L10_max REAL,
                    
                    -- Season averages
                    points_season REAL,
                    rebounds_season REAL,
                    assists_season REAL,
                    
                    -- Raw game logs (JSON)
                    last_10_games TEXT,
                    
                    -- Metadata
                    data_source TEXT DEFAULT 'NBA_API'
                )
            ''')
            
            # Player ID lookup table (for faster API calls)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS player_ids (
                    player_name TEXT PRIMARY KEY,
                    player_id INTEGER,
                    team TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # Create indexes
            conn.execute('CREATE INDEX IF NOT EXISTS idx_team ON player_stats(team)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_updated ON player_stats(last_updated)')
    
    # ═══════════════════════════════════════════════════════════════
    # PLAYER LOOKUP
    # ═══════════════════════════════════════════════════════════════
    
    def _get_player_id(self, player_name: str) -> Optional[int]:
        """Get NBA API player ID, using cache or API lookup"""
        # Check cache first
        with self._get_conn() as conn:
            row = conn.execute(
                'SELECT player_id FROM player_ids WHERE player_name = ?',
                (player_name,)
            ).fetchone()
            
            if row and row['player_id']:
                return row['player_id']
        
        # Not in cache, look up via API
        if not NBA_API_AVAILABLE:
            return None
        
        all_players = nba_players.get_players()
        
        # Try exact match
        for p in all_players:
            if p['full_name'].lower() == player_name.lower():
                self._cache_player_id(player_name, p['id'])
                return p['id']
        
        # Try partial match
        name_parts = player_name.lower().split()
        for p in all_players:
            if all(part in p['full_name'].lower() for part in name_parts):
                self._cache_player_id(player_name, p['id'])
                return p['id']
        
        return None
    
    def _cache_player_id(self, player_name: str, player_id: int):
        """Cache player ID for faster future lookups"""
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO player_ids (player_name, player_id)
                VALUES (?, ?)
            ''', (player_name, player_id))
    
    # ═══════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ═══════════════════════════════════════════════════════════════
    
    def update_player(self, player_name: str, force: bool = False) -> bool:
        """
        Update player stats from NBA API.
        
        Args:
            player_name: Player full name
            force: Force update even if cache is fresh
        
        Returns:
            True if updated, False if skipped or failed
        """
        if not NBA_API_AVAILABLE:
            print(f"   ⚠️  NBA API not available for {player_name}")
            return False
        
        # Check if cache is fresh
        if not force:
            with self._get_conn() as conn:
                row = conn.execute(
                    'SELECT last_updated FROM player_stats WHERE player_name = ?',
                    (player_name,)
                ).fetchone()
                
                if row and row['last_updated']:
                    last_update = datetime.fromisoformat(row['last_updated'])
                    if datetime.now() - last_update < timedelta(hours=CACHE_TTL_HOURS):
                        return False  # Cache is fresh
        
        # Get player ID
        player_id = self._get_player_id(player_name)
        if not player_id:
            print(f"   ❌ Player not found: {player_name}")
            return False
        
        try:
            # Rate limiting
            time.sleep(API_DELAY)
            
            # Fetch game log
            gamelog = playergamelog.PlayerGameLog(
                player_id=player_id,
                season='2025-26',
                season_type_all_star='Regular Season'
            )
            df = gamelog.get_data_frames()[0]
            
            if df.empty:
                # Try previous season
                gamelog = playergamelog.PlayerGameLog(
                    player_id=player_id,
                    season='2024-25',
                    season_type_all_star='Regular Season'
                )
                df = gamelog.get_data_frames()[0]
            
            if df.empty:
                print(f"   ⚠️  No games found for {player_name}")
                return False
            
            # Calculate stats from L10 games
            recent = df.head(10)
            
            stats = {
                'player_name': player_name,
                'player_id': player_id,
                'team': self._extract_team(df),
                'last_updated': datetime.now().isoformat(),
                'games_available': len(df),
                
                # L10 Averages
                'points_L10': recent['PTS'].mean(),
                'rebounds_L10': recent['REB'].mean(),
                'assists_L10': recent['AST'].mean(),
                'steals_L10': recent['STL'].mean(),
                'blocks_L10': recent['BLK'].mean(),
                'turnovers_L10': recent['TOV'].mean(),
                'fg3_made_L10': recent['FG3M'].mean(),
                'pra_L10': (recent['PTS'] + recent['REB'] + recent['AST']).mean(),
                
                # L10 Standard Deviations
                'points_L10_std': recent['PTS'].std(),
                'rebounds_L10_std': recent['REB'].std(),
                'assists_L10_std': recent['AST'].std(),
                'fg3_made_L10_std': recent['FG3M'].std(),
                'pra_L10_std': (recent['PTS'] + recent['REB'] + recent['AST']).std(),
                
                # L10 Min/Max
                'points_L10_min': recent['PTS'].min(),
                'points_L10_max': recent['PTS'].max(),
                
                # Season averages
                'points_season': df['PTS'].mean(),
                'rebounds_season': df['REB'].mean(),
                'assists_season': df['AST'].mean(),
                
                # Raw game logs
                'last_10_games': json.dumps(recent.to_dict('records'))
            }
            
            # Save to database
            self._save_player_stats(stats)
            
            print(f"   ✅ {player_name}: {stats['points_L10']:.1f} PPG ({len(recent)} games)")
            return True
            
        except Exception as e:
            print(f"   ❌ Error fetching {player_name}: {e}")
            return False
    
    def _extract_team(self, df) -> str:
        """Extract team abbreviation from matchup string"""
        if df.empty:
            return None
        
        matchup = df.iloc[0]['MATCHUP']
        # Matchup format: "BKN vs. NYK" or "BKN @ NYK"
        if ' vs. ' in matchup:
            return matchup.split(' vs. ')[0]
        elif ' @ ' in matchup:
            return matchup.split(' @ ')[0]
        return None
    
    def _save_player_stats(self, stats: Dict):
        """Save player stats to database"""
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO player_stats (
                    player_name, player_id, team, last_updated, games_available,
                    points_L10, rebounds_L10, assists_L10, steals_L10, blocks_L10, turnovers_L10, fg3_made_L10, pra_L10,
                    points_L10_std, rebounds_L10_std, assists_L10_std, fg3_made_L10_std, pra_L10_std,
                    points_L10_min, points_L10_max,
                    points_season, rebounds_season, assists_season,
                    last_10_games
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                stats['player_name'],
                stats['player_id'],
                stats['team'],
                stats['last_updated'],
                stats['games_available'],
                stats['points_L10'],
                stats['rebounds_L10'],
                stats['assists_L10'],
                stats['steals_L10'],
                stats['blocks_L10'],
                stats['turnovers_L10'],
                stats['fg3_made_L10'],
                stats['pra_L10'],
                stats['points_L10_std'],
                stats['rebounds_L10_std'],
                stats['assists_L10_std'],
                stats['fg3_made_L10_std'],
                stats['pra_L10_std'],
                stats['points_L10_min'],
                stats['points_L10_max'],
                stats['points_season'],
                stats['rebounds_season'],
                stats['assists_season'],
                stats['last_10_games']
            ))
    
    # ═══════════════════════════════════════════════════════════════
    # BATCH UPDATES
    # ═══════════════════════════════════════════════════════════════
    
    def update_from_json(self, json_file: str, force: bool = False) -> Dict:
        """
        Update stats for all players in a JSON slate file.
        
        Returns:
            Dict with counts: updated, skipped, failed
        """
        with open(json_file, encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', []))
        else:
            picks = data
        
        # Get unique player names
        players = list(set(p.get('player', p.get('player_name')) for p in picks if p.get('player') or p.get('player_name')))
        
        print(f"📊 Updating {len(players)} players from {Path(json_file).name}")
        print("-" * 60)
        
        results = {'updated': 0, 'skipped': 0, 'failed': 0}
        
        for player in sorted(players):
            if self.update_player(player, force):
                results['updated'] += 1
            else:
                # Check if it was skipped (fresh cache) or failed
                with self._get_conn() as conn:
                    row = conn.execute(
                        'SELECT player_name FROM player_stats WHERE player_name = ?',
                        (player,)
                    ).fetchone()
                    
                    if row:
                        results['skipped'] += 1
                    else:
                        results['failed'] += 1
        
        print("-" * 60)
        print(f"✅ Updated: {results['updated']}, ⏭️ Skipped: {results['skipped']}, ❌ Failed: {results['failed']}")
        
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_player(self, player_name: str) -> Optional[Dict]:
        """
        Get cached player stats.
        
        Returns:
            Dict with player stats or None if not found
        """
        with self._get_conn() as conn:
            row = conn.execute(
                'SELECT * FROM player_stats WHERE player_name = ?',
                (player_name,)
            ).fetchone()
            
            if row:
                return dict(row)
        return None
    
    def get_stat(self, player_name: str, stat: str) -> Optional[Dict]:
        """
        Get specific stat for a player.
        
        Args:
            player_name: Player name
            stat: Stat type (points, rebounds, assists, fg3_made, pra)
        
        Returns:
            Dict with mu, sigma, n
        """
        # Normalize stat name
        stat_map = {
            'pts': 'points', 'points': 'points',
            'reb': 'rebounds', 'rebounds': 'rebounds',
            'ast': 'assists', 'assists': 'assists',
            '3pm': 'fg3_made', '3pt': 'fg3_made', 'fg3m': 'fg3_made', 'fg3_made': 'fg3_made',
            'pra': 'pra', 'pts+reb+ast': 'pra'
        }
        
        stat_col = stat_map.get(stat.lower(), stat.lower())
        
        player = self.get_player(player_name)
        if not player:
            return None
        
        avg = player.get(f'{stat_col}_L10')
        std = player.get(f'{stat_col}_L10_std')
        
        if avg is None:
            return None
        
        return {
            'mu': avg,
            'sigma': std or 0,
            'n': min(10, player.get('games_available', 10)),
            'team': player.get('team')
        }
    
    def validate_projection(self, player_name: str, stat: str, projected_mu: float) -> Dict:
        """
        Validate a projection against cached data.
        
        Returns:
            Dict with is_valid, actual_avg, pct_diff, warning
        """
        actual = self.get_stat(player_name, stat)
        
        if not actual:
            return {
                'is_valid': None,
                'warning': 'NO_DATA',
                'message': f'No cached data for {player_name}'
            }
        
        actual_avg = actual['mu']
        pct_diff = (projected_mu - actual_avg) / actual_avg * 100 if actual_avg > 0 else 0
        
        # Flag if more than 40% off
        is_valid = abs(pct_diff) < 40
        
        result = {
            'is_valid': is_valid,
            'projected': projected_mu,
            'actual_avg': actual_avg,
            'pct_diff': round(pct_diff, 1)
        }
        
        if not is_valid:
            result['warning'] = 'SUSPICIOUS_PROJECTION'
            result['message'] = f'{player_name} {stat}: projected {projected_mu:.1f} but L10 avg is {actual_avg:.1f} ({pct_diff:+.1f}%)'
        
        return result
    
    def get_team_players(self, team: str) -> List[Dict]:
        """Get all cached players for a team"""
        with self._get_conn() as conn:
            rows = conn.execute(
                'SELECT * FROM player_stats WHERE team = ? ORDER BY points_L10 DESC',
                (team,)
            ).fetchall()
            return [dict(row) for row in rows]
    
    def find_stale_players(self, hours: int = 24) -> List[str]:
        """Find players whose cache is older than specified hours"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        with self._get_conn() as conn:
            rows = conn.execute(
                'SELECT player_name FROM player_stats WHERE last_updated < ?',
                (cutoff,)
            ).fetchall()
            return [row['player_name'] for row in rows]
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self._get_conn() as conn:
            total = conn.execute('SELECT COUNT(*) FROM player_stats').fetchone()[0]
            
            # Count fresh vs stale
            cutoff = (datetime.now() - timedelta(hours=CACHE_TTL_HOURS)).isoformat()
            fresh = conn.execute(
                'SELECT COUNT(*) FROM player_stats WHERE last_updated > ?',
                (cutoff,)
            ).fetchone()[0]
            
            teams = conn.execute('SELECT COUNT(DISTINCT team) FROM player_stats').fetchone()[0]
            
            return {
                'total_players': total,
                'fresh_cache': fresh,
                'stale_cache': total - fresh,
                'unique_teams': teams,
                'db_path': str(self.db_path)
            }
    
    def export_to_csv(self, output_file: str = None):
        """Export all player stats to CSV"""
        import csv
        
        if output_file is None:
            output_file = f"cache/player_stats_export_{date.today()}.csv"
        
        with self._get_conn() as conn:
            rows = conn.execute(
                'SELECT player_name, team, points_L10, rebounds_L10, assists_L10, fg3_made_L10, pra_L10, points_L10_std, games_available, last_updated FROM player_stats ORDER BY points_L10 DESC'
            ).fetchall()
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['player_name', 'team', 'PPG', 'RPG', 'APG', '3PM', 'PRA', 'PTS_STD', 'games', 'updated'])
                for row in rows:
                    writer.writerow([
                        row['player_name'],
                        row['team'],
                        round(row['points_L10'] or 0, 1),
                        round(row['rebounds_L10'] or 0, 1),
                        round(row['assists_L10'] or 0, 1),
                        round(row['fg3_made_L10'] or 0, 1),
                        round(row['pra_L10'] or 0, 1),
                        round(row['points_L10_std'] or 0, 1),
                        row['games_available'],
                        row['last_updated'][:10] if row['last_updated'] else ''
                    ])
        
        print(f"✅ Exported {len(rows)} players to {output_file}")
        return output_file
    
    def get_connection(self):
        """Get raw database connection for advanced queries"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


# ═══════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

_db = None

def get_db() -> PlayerStatsDB:
    """Get singleton database instance"""
    global _db
    if _db is None:
        _db = PlayerStatsDB()
    return _db

def get_player_stats(player_name: str) -> Optional[Dict]:
    """Quick lookup of player stats"""
    return get_db().get_player(player_name)

def get_stat(player_name: str, stat: str) -> Optional[Dict]:
    """Quick lookup of specific stat"""
    return get_db().get_stat(player_name, stat)

def validate_projection(player_name: str, stat: str, mu: float) -> Dict:
    """Quick validation of a projection"""
    return get_db().validate_projection(player_name, stat, mu)

def update_player(player_name: str, force: bool = False) -> bool:
    """Quick update of a player"""
    return get_db().update_player(player_name, force)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Player Stats Cache (SQLite)')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--player', type=str, help='Get/update single player')
    parser.add_argument('--from-json', type=str, help='Update all players from JSON file')
    parser.add_argument('--validate', type=str, help='Validate projection: "Player Name,stat,mu"')
    parser.add_argument('--team', type=str, help='Show all players for a team')
    parser.add_argument('--stale', action='store_true', help='Show players with stale cache')
    parser.add_argument('--export', action='store_true', help='Export to CSV')
    parser.add_argument('--force', action='store_true', help='Force update even if fresh')
    
    args = parser.parse_args()
    
    db = PlayerStatsDB()
    
    print("=" * 80)
    print("📊 FUOOM PLAYER STATS CACHE (SQLite)")
    print("=" * 80)
    print()
    
    if args.stats:
        stats = db.get_stats()
        print(f"📁 Database: {stats['db_path']}")
        print(f"👥 Total players: {stats['total_players']}")
        print(f"✅ Fresh cache: {stats['fresh_cache']}")
        print(f"⏳ Stale cache: {stats['stale_cache']}")
        print(f"🏀 Teams: {stats['unique_teams']}")
    
    elif args.player:
        print(f"🔍 Looking up: {args.player}")
        print("-" * 40)
        
        # Update if needed
        db.update_player(args.player, force=args.force)
        
        # Show stats
        player = db.get_player(args.player)
        if player:
            print(f"   Team: {player.get('team')}")
            print(f"   Games: {player.get('games_available')}")
            print(f"   PPG: {player.get('points_L10', 0):.1f} (σ={player.get('points_L10_std', 0):.1f})")
            print(f"   RPG: {player.get('rebounds_L10', 0):.1f}")
            print(f"   APG: {player.get('assists_L10', 0):.1f}")
            print(f"   3PM: {player.get('fg3_made_L10', 0):.1f}")
            print(f"   PRA: {player.get('pra_L10', 0):.1f}")
            print(f"   Updated: {player.get('last_updated', 'Never')[:19]}")
        else:
            print(f"   ❌ No data available")
    
    elif args.from_json:
        db.update_from_json(args.from_json, force=args.force)
    
    elif args.validate:
        parts = args.validate.split(',')
        if len(parts) != 3:
            print("Usage: --validate 'Player Name,stat,mu'")
        else:
            player, stat, mu = parts[0], parts[1], float(parts[2])
            result = db.validate_projection(player, stat, mu)
            
            if result.get('is_valid') is None:
                print(f"⚠️  {result['message']}")
            elif result['is_valid']:
                print(f"✅ Valid: projected {mu} vs actual {result['actual_avg']:.1f} ({result['pct_diff']:+.1f}%)")
            else:
                print(f"❌ SUSPICIOUS: {result['message']}")
    
    elif args.team:
        players = db.get_team_players(args.team)
        print(f"🏀 {args.team} Players ({len(players)})")
        print("-" * 60)
        for p in players[:15]:
            print(f"   {p['player_name']:<25} {p['points_L10']:.1f} PPG")
    
    elif args.stale:
        stale = db.find_stale_players(24)
        print(f"⏳ Stale Players ({len(stale)})")
        print("-" * 40)
        for name in stale[:20]:
            print(f"   {name}")
    
    elif args.export:
        db.export_to_csv()
    
    else:
        print("Usage examples:")
        print()
        print("  # Show database stats")
        print("  python player_stats_db.py --stats")
        print()
        print("  # Get/update single player")
        print('  python player_stats_db.py --player "Cam Thomas"')
        print()
        print("  # Update all players from slate")
        print("  python player_stats_db.py --from-json outputs/FILE.json")
        print()
        print("  # Validate a projection")
        print('  python player_stats_db.py --validate "Cam Thomas,points,8.7"')
        print()
        print("  # Show team players")
        print("  python player_stats_db.py --team BKN")
        print()
        print("  # Export to CSV")
        print("  python player_stats_db.py --export")
    
    print()
    print("=" * 80)
