"""
HOME/AWAY SPLITS DATABASE
Player performance splits by location for better projections.

Usage:
    from home_away_splits_db import splits_db
    
    # Get splits for a player
    splits = splits_db.get_player_splits("Stephen Curry")
    # → {'home_ppg': 28.3, 'away_ppg': 24.1, 'home_boost': 17.4%}
    
    # Get location adjustment
    adj = splits_db.get_location_adjustment("Stephen Curry", "points", is_home=False)
    # → {'adjustment': -4.2, 'pct_diff': -14.8%}

Benefits:
    - More accurate projections by location
    - Some players are 30% better at home
    - Better variance estimation
"""

import sqlite3
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from contextlib import contextmanager

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

DB_PATH = Path("cache/home_away_splits.db")
CACHE_TTL_HOURS = 168  # 1 week

# NBA API imports (optional)
try:
    from nba_api.stats.static import players as nba_players
    from nba_api.stats.endpoints import playergamelog
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class HomeAwaySplitsDB:
    """SQLite database for caching home/away performance splits"""
    
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
            conn.execute('''
                CREATE TABLE IF NOT EXISTS player_splits (
                    player_name TEXT PRIMARY KEY,
                    player_id INTEGER,
                    team TEXT,
                    
                    -- Home stats
                    home_games INTEGER,
                    home_pts_avg REAL,
                    home_pts_std REAL,
                    home_reb_avg REAL,
                    home_ast_avg REAL,
                    home_fg3m_avg REAL,
                    home_pra_avg REAL,
                    
                    -- Away stats
                    away_games INTEGER,
                    away_pts_avg REAL,
                    away_pts_std REAL,
                    away_reb_avg REAL,
                    away_ast_avg REAL,
                    away_fg3m_avg REAL,
                    away_pra_avg REAL,
                    
                    -- Calculated differences
                    pts_home_diff REAL,  -- Home PPG - Away PPG
                    pts_home_pct REAL,   -- (Home - Away) / Away * 100
                    
                    last_updated TIMESTAMP
                )
            ''')
    
    # ═══════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ═══════════════════════════════════════════════════════════════
    
    def update_player(self, player_name: str, force: bool = False) -> bool:
        """
        Update home/away splits for a player from NBA API.
        
        Returns:
            True if updated, False if failed or skipped
        """
        if not NBA_API_AVAILABLE:
            print(f"   ⚠️  NBA API not available for {player_name}")
            return False
        
        # Check cache freshness
        if not force:
            with self._get_conn() as conn:
                row = conn.execute(
                    'SELECT last_updated FROM player_splits WHERE player_name = ?',
                    (player_name,)
                ).fetchone()
                
                if row and row['last_updated']:
                    last_update = datetime.fromisoformat(row['last_updated'])
                    if datetime.now() - last_update < timedelta(hours=CACHE_TTL_HOURS):
                        return False  # Cache fresh
        
        # Get player ID
        all_players = nba_players.get_players()
        player_id = None
        
        for p in all_players:
            if p['full_name'].lower() == player_name.lower():
                player_id = p['id']
                break
        
        if not player_id:
            # Try partial match
            name_parts = player_name.lower().split()
            for p in all_players:
                if all(part in p['full_name'].lower() for part in name_parts):
                    player_id = p['id']
                    break
        
        if not player_id:
            print(f"   ❌ Player not found: {player_name}")
            return False
        
        try:
            time.sleep(0.6)  # Rate limiting
            
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
            
            # Parse matchup to determine home/away
            def is_home_game(matchup):
                return 'vs.' in matchup
            
            df['is_home'] = df['MATCHUP'].apply(is_home_game)
            
            # Calculate home stats
            home_games = df[df['is_home']]
            away_games = df[~df['is_home']]
            
            # Extract team from matchup
            team = df.iloc[0]['MATCHUP'].split()[0] if not df.empty else None
            
            splits = {
                'player_name': player_name,
                'player_id': player_id,
                'team': team,
                
                # Home stats
                'home_games': len(home_games),
                'home_pts_avg': home_games['PTS'].mean() if len(home_games) > 0 else 0,
                'home_pts_std': home_games['PTS'].std() if len(home_games) > 0 else 0,
                'home_reb_avg': home_games['REB'].mean() if len(home_games) > 0 else 0,
                'home_ast_avg': home_games['AST'].mean() if len(home_games) > 0 else 0,
                'home_fg3m_avg': home_games['FG3M'].mean() if len(home_games) > 0 else 0,
                'home_pra_avg': (home_games['PTS'] + home_games['REB'] + home_games['AST']).mean() if len(home_games) > 0 else 0,
                
                # Away stats
                'away_games': len(away_games),
                'away_pts_avg': away_games['PTS'].mean() if len(away_games) > 0 else 0,
                'away_pts_std': away_games['PTS'].std() if len(away_games) > 0 else 0,
                'away_reb_avg': away_games['REB'].mean() if len(away_games) > 0 else 0,
                'away_ast_avg': away_games['AST'].mean() if len(away_games) > 0 else 0,
                'away_fg3m_avg': away_games['FG3M'].mean() if len(away_games) > 0 else 0,
                'away_pra_avg': (away_games['PTS'] + away_games['REB'] + away_games['AST']).mean() if len(away_games) > 0 else 0,
            }
            
            # Calculate differences
            if splits['away_pts_avg'] > 0:
                splits['pts_home_diff'] = splits['home_pts_avg'] - splits['away_pts_avg']
                splits['pts_home_pct'] = (splits['pts_home_diff'] / splits['away_pts_avg']) * 100
            else:
                splits['pts_home_diff'] = 0
                splits['pts_home_pct'] = 0
            
            # Save to database
            self._save_splits(splits)
            
            print(f"   ✅ {player_name}: Home {splits['home_pts_avg']:.1f} / Away {splits['away_pts_avg']:.1f} PPG ({splits['pts_home_pct']:+.1f}%)")
            return True
            
        except Exception as e:
            print(f"   ❌ Error fetching {player_name}: {e}")
            return False
    
    def _save_splits(self, splits: Dict):
        """Save player splits to database"""
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO player_splits 
                (player_name, player_id, team,
                 home_games, home_pts_avg, home_pts_std, home_reb_avg, home_ast_avg, home_fg3m_avg, home_pra_avg,
                 away_games, away_pts_avg, away_pts_std, away_reb_avg, away_ast_avg, away_fg3m_avg, away_pra_avg,
                 pts_home_diff, pts_home_pct, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                splits['player_name'],
                splits['player_id'],
                splits['team'],
                splits['home_games'],
                splits['home_pts_avg'],
                splits['home_pts_std'],
                splits['home_reb_avg'],
                splits['home_ast_avg'],
                splits['home_fg3m_avg'],
                splits['home_pra_avg'],
                splits['away_games'],
                splits['away_pts_avg'],
                splits['away_pts_std'],
                splits['away_reb_avg'],
                splits['away_ast_avg'],
                splits['away_fg3m_avg'],
                splits['away_pra_avg'],
                splits['pts_home_diff'],
                splits['pts_home_pct'],
                datetime.now().isoformat()
            ))
    
    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_player_splits(self, player_name: str) -> Optional[Dict]:
        """Get all splits for a player"""
        with self._get_conn() as conn:
            row = conn.execute(
                'SELECT * FROM player_splits WHERE player_name = ?',
                (player_name,)
            ).fetchone()
            
            if row:
                return dict(row)
        return None
    
    def get_location_adjustment(self, player_name: str, stat: str, is_home: bool) -> Dict:
        """
        Get adjustment factor for a specific location.
        
        Args:
            player_name: Player name
            stat: Stat type (points, rebounds, etc.)
            is_home: Whether game is at home
        
        Returns:
            Dict with adjustment, pct_diff, reason
        """
        splits = self.get_player_splits(player_name)
        
        if not splits:
            return {
                'adjustment': 0,
                'pct_diff': 0,
                'reason': 'No split data available',
                'is_home': is_home
            }
        
        # Map stat to column
        stat_map = {
            'points': ('home_pts_avg', 'away_pts_avg'),
            'pts': ('home_pts_avg', 'away_pts_avg'),
            'rebounds': ('home_reb_avg', 'away_reb_avg'),
            'reb': ('home_reb_avg', 'away_reb_avg'),
            'assists': ('home_ast_avg', 'away_ast_avg'),
            'ast': ('home_ast_avg', 'away_ast_avg'),
            '3pm': ('home_fg3m_avg', 'away_fg3m_avg'),
            'fg3m': ('home_fg3m_avg', 'away_fg3m_avg'),
            'pra': ('home_pra_avg', 'away_pra_avg'),
        }
        
        cols = stat_map.get(stat.lower())
        if not cols:
            return {
                'adjustment': 0,
                'pct_diff': 0,
                'reason': f'Unknown stat: {stat}',
                'is_home': is_home
            }
        
        home_col, away_col = cols
        home_avg = splits.get(home_col, 0) or 0
        away_avg = splits.get(away_col, 0) or 0
        
        # Overall average
        overall_avg = (home_avg * splits.get('home_games', 0) + away_avg * splits.get('away_games', 0)) / max(1, splits.get('home_games', 0) + splits.get('away_games', 0))
        
        # Calculate adjustment from overall average
        if is_home:
            adjustment = home_avg - overall_avg
            location_avg = home_avg
            location = 'HOME'
        else:
            adjustment = away_avg - overall_avg
            location_avg = away_avg
            location = 'AWAY'
        
        pct_diff = (adjustment / overall_avg * 100) if overall_avg > 0 else 0
        
        return {
            'adjustment': round(adjustment, 1),
            'pct_diff': round(pct_diff, 1),
            'location_avg': round(location_avg, 1),
            'overall_avg': round(overall_avg, 1),
            'home_avg': round(home_avg, 1),
            'away_avg': round(away_avg, 1),
            'is_home': is_home,
            'location': location,
            'reason': f"{location} game: {location_avg:.1f} vs overall {overall_avg:.1f}"
        }
    
    def get_biggest_home_court_advantages(self, stat: str = 'points', min_games: int = 5) -> List[Dict]:
        """Get players with biggest home court advantage"""
        stat_map = {
            'points': 'pts_home_pct',
            'pts': 'pts_home_pct',
        }
        
        col = stat_map.get(stat.lower(), 'pts_home_pct')
        
        with self._get_conn() as conn:
            rows = conn.execute(f'''
                SELECT player_name, team, home_pts_avg, away_pts_avg, {col} as home_pct,
                       home_games, away_games
                FROM player_splits
                WHERE home_games >= ? AND away_games >= ?
                ORDER BY {col} DESC
                LIMIT 20
            ''', (min_games, min_games)).fetchall()
            
            return [dict(row) for row in rows]
    
    def update_from_json(self, json_file: str, force: bool = False) -> Dict:
        """Update splits for all players in a slate"""
        import json as json_module
        
        with open(json_file, encoding='utf-8') as f:
            data = json_module.load(f)
        
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', []))
        else:
            picks = data
        
        players = list(set(p.get('player', p.get('player_name')) for p in picks if p.get('player') or p.get('player_name')))
        
        print(f"📊 Updating splits for {len(players)} players")
        print("-" * 60)
        
        results = {'updated': 0, 'skipped': 0, 'failed': 0}
        
        for player in sorted(players):
            if self.update_player(player, force):
                results['updated'] += 1
            else:
                with self._get_conn() as conn:
                    row = conn.execute(
                        'SELECT player_name FROM player_splits WHERE player_name = ?',
                        (player,)
                    ).fetchone()
                    
                    if row:
                        results['skipped'] += 1
                    else:
                        results['failed'] += 1
        
        print("-" * 60)
        print(f"✅ Updated: {results['updated']}, ⏭️ Skipped: {results['skipped']}, ❌ Failed: {results['failed']}")
        
        return results
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self._get_conn() as conn:
            total = conn.execute('SELECT COUNT(*) FROM player_splits').fetchone()[0]
            
            return {
                'total_players': total,
                'db_path': str(self.db_path)
            }


# ═══════════════════════════════════════════════════════════════════
# SINGLETON + CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

splits_db = HomeAwaySplitsDB()

def get_player_splits(player_name: str) -> Optional[Dict]:
    """Quick lookup of player splits"""
    return splits_db.get_player_splits(player_name)

def get_location_adjustment(player_name: str, stat: str, is_home: bool) -> Dict:
    """Quick location adjustment"""
    return splits_db.get_location_adjustment(player_name, stat, is_home)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Home/Away Splits Database')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--player', type=str, help='Get/update splits for a player')
    parser.add_argument('--adjust', type=str, help='Get adjustment: "Player,stat,home|away"')
    parser.add_argument('--from-json', type=str, help='Update all players from JSON file')
    parser.add_argument('--biggest', action='store_true', help='Show biggest home court advantages')
    parser.add_argument('--force', action='store_true', help='Force update')
    
    args = parser.parse_args()
    
    db = HomeAwaySplitsDB()
    
    print("=" * 80)
    print("🏠 HOME/AWAY SPLITS DATABASE")
    print("=" * 80)
    print()
    
    if args.stats:
        stats = db.get_stats()
        print(f"📁 Database: {stats['db_path']}")
        print(f"👥 Total players: {stats['total_players']}")
    
    elif args.player:
        print(f"🔍 Looking up: {args.player}")
        print("-" * 40)
        
        db.update_player(args.player, force=args.force)
        
        splits = db.get_player_splits(args.player)
        if splits:
            print(f"\n📊 {args.player} SPLITS")
            print(f"   HOME: {splits['home_pts_avg']:.1f} PPG ({splits['home_games']} games)")
            print(f"   AWAY: {splits['away_pts_avg']:.1f} PPG ({splits['away_games']} games)")
            print(f"   DIFF: {splits['pts_home_diff']:+.1f} ({splits['pts_home_pct']:+.1f}%)")
        else:
            print(f"   ❌ No data available")
    
    elif args.adjust:
        parts = args.adjust.split(',')
        if len(parts) == 3:
            player, stat, location = parts
            is_home = location.lower() in ('home', 'h', 'true', '1')
            adj = db.get_location_adjustment(player, stat, is_home)
            
            print(f"🎯 LOCATION ADJUSTMENT")
            print("-" * 40)
            print(f"   Player: {player}")
            print(f"   Location: {adj['location']}")
            print(f"   {stat.upper()} avg at {adj['location']}: {adj['location_avg']:.1f}")
            print(f"   Overall avg: {adj['overall_avg']:.1f}")
            print(f"   Adjustment: {adj['adjustment']:+.1f} ({adj['pct_diff']:+.1f}%)")
        else:
            print('Usage: --adjust "Player,stat,home|away"')
    
    elif args.from_json:
        db.update_from_json(args.from_json, force=args.force)
    
    elif args.biggest:
        print("📊 BIGGEST HOME COURT ADVANTAGES (Points)")
        print("-" * 60)
        print(f"{'Player':<25} {'Team':<6} {'Home':<8} {'Away':<8} {'Diff':<8}")
        print("-" * 60)
        
        for p in db.get_biggest_home_court_advantages('points', 3):
            print(f"{p['player_name']:<25} {p['team'] or 'N/A':<6} {p['home_pts_avg']:.1f}    {p['away_pts_avg']:.1f}    {p['home_pct']:+.1f}%")
    
    else:
        print("Usage:")
        print()
        print("  # Show database stats")
        print("  python home_away_splits_db.py --stats")
        print()
        print("  # Get/update player splits")
        print('  python home_away_splits_db.py --player "Stephen Curry"')
        print()
        print("  # Get location adjustment")
        print('  python home_away_splits_db.py --adjust "Stephen Curry,points,away"')
        print()
        print("  # Update all players from slate")
        print("  python home_away_splits_db.py --from-json outputs/FILE.json")
        print()
        print("  # Show biggest home court advantages")
        print("  python home_away_splits_db.py --biggest")
    
    print()
    print("=" * 80)
