"""
FUOOM PICK HISTORY DATABASE
Stores every pick ever made for calibration, backtesting, and learning.

Usage:
    from pick_history_db import PickHistoryDB
    
    db = PickHistoryDB()
    db.log_pick(pick_data)
    db.resolve_pick(pick_id, actual_value)
    calibration = db.get_calibration_report()

Benefits:
    - Track all picks forever
    - Automatic hit rate calculation (no 8000% bugs!)
    - Calibration analysis
    - Performance attribution
    - Backtesting ready
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from contextlib import contextmanager

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

DB_PATH = Path("cache/pick_history.db")

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class PickHistoryDB:
    """SQLite database for tracking all picks and results"""
    
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
            # Main picks table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS picks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    -- Slate info
                    slate_date DATE NOT NULL,
                    slate_name TEXT,
                    sport TEXT DEFAULT 'NBA',
                    
                    -- Pick details
                    player_name TEXT NOT NULL,
                    team TEXT,
                    opponent TEXT,
                    stat TEXT NOT NULL,
                    line REAL NOT NULL,
                    direction TEXT NOT NULL,
                    
                    -- Model output
                    mu REAL,
                    sigma REAL,
                    confidence REAL,
                    effective_confidence REAL,
                    edge REAL,
                    z_score REAL,
                    tier TEXT,
                    kelly_pct REAL,
                    
                    -- Archetype/specialist
                    archetype TEXT,
                    specialist TEXT,
                    
                    -- Result
                    actual_value REAL,
                    hit BOOLEAN,
                    margin REAL,  -- How much over/under the line
                    
                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    
                    -- Metadata (JSON)
                    metadata TEXT
                )
            ''')
            
            # Create indexes for fast queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_player ON picks(player_name)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_stat ON picks(stat)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_slate_date ON picks(slate_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tier ON picks(tier)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_resolved ON picks(resolved_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sport ON picks(sport)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_direction ON picks(direction)')
            
            # Unique constraint to prevent duplicates
            conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_pick 
                ON picks(slate_date, player_name, stat, line, direction)
            ''')
    
    # ═══════════════════════════════════════════════════════════════
    # LOGGING PICKS
    # ═══════════════════════════════════════════════════════════════
    
    def log_pick(self, pick: Dict, slate_date: date = None, slate_name: str = None) -> int:
        """
        Log a single pick to the database.
        
        Args:
            pick: Dict with pick data (player, stat, line, direction, mu, sigma, etc.)
            slate_date: Date of the slate (defaults to today)
            slate_name: Name of the slate
        
        Returns:
            Pick ID
        """
        if slate_date is None:
            slate_date = date.today()
        
        with self._get_conn() as conn:
            try:
                cursor = conn.execute('''
                    INSERT INTO picks (
                        slate_date, slate_name, sport,
                        player_name, team, opponent, stat, line, direction,
                        mu, sigma, confidence, effective_confidence, edge, z_score, tier, kelly_pct,
                        archetype, specialist, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(slate_date),
                    slate_name or pick.get('slate_name'),
                    pick.get('sport', 'NBA'),
                    pick.get('player', pick.get('player_name')),
                    pick.get('team'),
                    pick.get('opponent'),
                    pick.get('stat', pick.get('market')),
                    pick.get('line'),
                    pick.get('direction'),
                    pick.get('mu'),
                    pick.get('sigma'),
                    pick.get('confidence'),
                    pick.get('effective_confidence', pick.get('eff%')),
                    pick.get('edge'),
                    pick.get('z_score'),
                    pick.get('tier'),
                    pick.get('kelly_pct'),
                    pick.get('archetype'),
                    pick.get('specialist'),
                    json.dumps(pick.get('metadata', {}))
                ))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Duplicate pick, return existing ID
                cursor = conn.execute('''
                    SELECT id FROM picks 
                    WHERE slate_date = ? AND player_name = ? AND stat = ? AND line = ? AND direction = ?
                ''', (
                    str(slate_date),
                    pick.get('player', pick.get('player_name')),
                    pick.get('stat', pick.get('market')),
                    pick.get('line'),
                    pick.get('direction')
                ))
                row = cursor.fetchone()
                return row['id'] if row else None
    
    def log_picks_batch(self, picks: List[Dict], slate_date: date = None, slate_name: str = None) -> int:
        """
        Log multiple picks at once (faster than individual inserts).
        
        Returns:
            Number of picks logged
        """
        count = 0
        for pick in picks:
            try:
                self.log_pick(pick, slate_date, slate_name)
                count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to log pick: {pick.get('player')}: {e}")
        return count
    
    def log_from_json(self, json_file: str) -> int:
        """
        Log all picks from a RISK_FIRST JSON file.
        
        Returns:
            Number of picks logged
        """
        with open(json_file, encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', []))
            slate_name = data.get('slate_name', Path(json_file).stem)
        else:
            picks = data
            slate_name = Path(json_file).stem
        
        # Extract date from filename or use today
        import re
        match = re.search(r'(\d{8})', json_file)
        if match:
            date_str = match.group(1)
            slate_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        else:
            slate_date = date.today()
        
        return self.log_picks_batch(picks, slate_date, slate_name)
    
    # ═══════════════════════════════════════════════════════════════
    # RESOLVING PICKS
    # ═══════════════════════════════════════════════════════════════
    
    def resolve_pick(self, pick_id: int, actual_value: float) -> bool:
        """
        Resolve a pick with the actual result.
        
        Args:
            pick_id: Database ID of the pick
            actual_value: Actual stat value achieved
        
        Returns:
            Whether the pick hit
        """
        with self._get_conn() as conn:
            # Get pick details
            row = conn.execute(
                'SELECT line, direction FROM picks WHERE id = ?',
                (pick_id,)
            ).fetchone()
            
            if not row:
                return None
            
            line, direction = row['line'], row['direction']
            
            # Determine if hit
            if direction.lower() in ('higher', 'over', 'more'):
                hit = actual_value > line
            else:
                hit = actual_value < line
            
            margin = actual_value - line
            
            # Update pick
            conn.execute('''
                UPDATE picks 
                SET actual_value = ?, hit = ?, margin = ?, resolved_at = ?
                WHERE id = ?
            ''', (actual_value, hit, margin, datetime.now(), pick_id))
            
            return hit
    
    def resolve_by_player(self, player_name: str, stat: str, actual_value: float, 
                          slate_date: date = None) -> List[bool]:
        """
        Resolve all picks for a player/stat on a given date.
        
        Returns:
            List of hit results
        """
        if slate_date is None:
            slate_date = date.today()
        
        with self._get_conn() as conn:
            rows = conn.execute('''
                SELECT id, line, direction FROM picks 
                WHERE player_name = ? AND stat = ? AND slate_date = ? AND resolved_at IS NULL
            ''', (player_name, stat, str(slate_date))).fetchall()
            
            results = []
            for row in rows:
                if row['direction'].lower() in ('higher', 'over', 'more'):
                    hit = actual_value > row['line']
                else:
                    hit = actual_value < row['line']
                
                margin = actual_value - row['line']
                
                conn.execute('''
                    UPDATE picks 
                    SET actual_value = ?, hit = ?, margin = ?, resolved_at = ?
                    WHERE id = ?
                ''', (actual_value, hit, margin, datetime.now(), row['id']))
                
                results.append(hit)
            
            return results
    
    # ═══════════════════════════════════════════════════════════════
    # QUERIES & ANALYTICS
    # ═══════════════════════════════════════════════════════════════
    
    def get_hit_rate(self, player_name: str = None, stat: str = None, 
                     direction: str = None, tier: str = None) -> Dict:
        """
        Get hit rate with optional filters.
        
        Returns:
            Dict with total, hits, hit_rate
        """
        query = '''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN hit THEN 1 ELSE 0 END) as hits
            FROM picks
            WHERE resolved_at IS NOT NULL
        '''
        params = []
        
        if player_name:
            query += ' AND player_name = ?'
            params.append(player_name)
        if stat:
            query += ' AND stat = ?'
            params.append(stat)
        if direction:
            query += ' AND direction = ?'
            params.append(direction)
        if tier:
            query += ' AND tier = ?'
            params.append(tier)
        
        with self._get_conn() as conn:
            row = conn.execute(query, params).fetchone()
            
            total = row['total'] or 0
            hits = row['hits'] or 0
            hit_rate = (hits / total * 100) if total > 0 else 0
            
            return {
                'total': total,
                'hits': hits,
                'hit_rate': round(hit_rate, 1)
            }
    
    def get_calibration_report(self, sport: str = None) -> List[Dict]:
        """
        Get calibration data - predicted confidence vs actual hit rate.
        
        Returns:
            List of dicts with confidence bucket, predicted rate, actual rate, sample size
        """
        query = '''
            SELECT 
                ROUND(COALESCE(effective_confidence, confidence) / 5) * 5 as conf_bucket,
                AVG(COALESCE(effective_confidence, confidence)) as predicted_rate,
                AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) * 100 as actual_rate,
                COUNT(*) as sample_size
            FROM picks
            WHERE resolved_at IS NOT NULL
        '''
        params = []
        
        if sport:
            query += ' AND sport = ?'
            params.append(sport)
        
        query += ' GROUP BY conf_bucket ORDER BY conf_bucket'
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            
            return [
                {
                    'confidence_bucket': row['conf_bucket'],
                    'predicted_rate': round(row['predicted_rate'], 1),
                    'actual_rate': round(row['actual_rate'], 1),
                    'sample_size': row['sample_size'],
                    'delta': round(row['actual_rate'] - row['predicted_rate'], 1)
                }
                for row in rows
            ]
    
    def get_stat_performance(self) -> List[Dict]:
        """
        Get performance breakdown by stat type.
        
        Returns:
            List of dicts sorted by hit rate
        """
        query = '''
            SELECT 
                stat,
                COUNT(*) as total_picks,
                SUM(CASE WHEN hit THEN 1 ELSE 0 END) as hits,
                AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) * 100 as hit_rate,
                AVG(margin) as avg_margin
            FROM picks
            WHERE resolved_at IS NOT NULL
            GROUP BY stat
            ORDER BY hit_rate DESC
        '''
        
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            
            return [
                {
                    'stat': row['stat'],
                    'total_picks': row['total_picks'],
                    'hits': row['hits'],
                    'hit_rate': round(row['hit_rate'], 1),
                    'avg_margin': round(row['avg_margin'], 2) if row['avg_margin'] else 0
                }
                for row in rows
            ]
    
    def get_direction_performance(self) -> Dict:
        """
        Get performance breakdown by direction (higher/lower).
        
        Returns:
            Dict with higher and lower stats
        """
        query = '''
            SELECT 
                CASE 
                    WHEN direction IN ('higher', 'over', 'more') THEN 'HIGHER'
                    ELSE 'LOWER'
                END as dir,
                COUNT(*) as total,
                AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) * 100 as hit_rate
            FROM picks
            WHERE resolved_at IS NOT NULL
            GROUP BY dir
        '''
        
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            
            result = {}
            for row in rows:
                result[row['dir']] = {
                    'total': row['total'],
                    'hit_rate': round(row['hit_rate'], 1)
                }
            
            return result
    
    def get_tier_performance(self) -> List[Dict]:
        """
        Get performance breakdown by tier.
        
        Returns:
            List of dicts sorted by tier level
        """
        query = '''
            SELECT 
                tier,
                COUNT(*) as total_picks,
                SUM(CASE WHEN hit THEN 1 ELSE 0 END) as hits,
                AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) * 100 as hit_rate
            FROM picks
            WHERE resolved_at IS NOT NULL AND tier IS NOT NULL
            GROUP BY tier
            ORDER BY 
                CASE tier 
                    WHEN 'ELITE' THEN 1 
                    WHEN 'SLAM' THEN 2 
                    WHEN 'STRONG' THEN 3 
                    WHEN 'LEAN' THEN 4 
                    ELSE 5 
                END
        '''
        
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            
            return [
                {
                    'tier': row['tier'],
                    'total_picks': row['total_picks'],
                    'hits': row['hits'],
                    'hit_rate': round(row['hit_rate'], 1)
                }
                for row in rows
            ]
    
    def get_player_history(self, player_name: str, limit: int = 50) -> List[Dict]:
        """
        Get all picks for a specific player.
        
        Returns:
            List of pick dicts
        """
        query = '''
            SELECT * FROM picks 
            WHERE player_name = ?
            ORDER BY slate_date DESC, created_at DESC
            LIMIT ?
        '''
        
        with self._get_conn() as conn:
            rows = conn.execute(query, (player_name, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def get_unresolved_picks(self, slate_date: date = None) -> List[Dict]:
        """
        Get picks that haven't been resolved yet.
        
        Returns:
            List of pick dicts
        """
        query = 'SELECT * FROM picks WHERE resolved_at IS NULL'
        params = []
        
        if slate_date:
            query += ' AND slate_date = ?'
            params.append(str(slate_date))
        
        query += ' ORDER BY slate_date, player_name'
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    
    def get_daily_summary(self, slate_date: date = None) -> Dict:
        """
        Get summary stats for a specific day.
        
        Returns:
            Dict with daily stats
        """
        if slate_date is None:
            slate_date = date.today()
        
        query = '''
            SELECT 
                COUNT(*) as total_picks,
                SUM(CASE WHEN resolved_at IS NOT NULL THEN 1 ELSE 0 END) as resolved,
                SUM(CASE WHEN hit THEN 1 ELSE 0 END) as hits,
                AVG(CASE WHEN hit THEN 1.0 ELSE 0.0 END) * 100 as hit_rate
            FROM picks
            WHERE slate_date = ?
        '''
        
        with self._get_conn() as conn:
            row = conn.execute(query, (str(slate_date),)).fetchone()
            
            return {
                'date': str(slate_date),
                'total_picks': row['total_picks'] or 0,
                'resolved': row['resolved'] or 0,
                'pending': (row['total_picks'] or 0) - (row['resolved'] or 0),
                'hits': row['hits'] or 0,
                'hit_rate': round(row['hit_rate'], 1) if row['hit_rate'] else 0
            }
    
    def find_suspicious_projections(self, stats_cache_conn) -> List[Dict]:
        """
        Find picks where mu is suspiciously different from actual average.
        
        Args:
            stats_cache_conn: Connection to player stats cache DB
        
        Returns:
            List of suspicious picks
        """
        query = '''
            SELECT id, player_name, stat, mu, line, direction, slate_date
            FROM picks
            WHERE mu IS NOT NULL
            ORDER BY slate_date DESC
            LIMIT 1000
        '''
        
        suspicious = []
        
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            
            for row in rows:
                # Look up actual average from stats cache
                cache_row = stats_cache_conn.execute(
                    f"SELECT {row['stat']}_L10 as avg FROM player_stats WHERE player_name = ?",
                    (row['player_name'],)
                ).fetchone()
                
                if cache_row and cache_row['avg']:
                    actual_avg = cache_row['avg']
                    
                    # Flag if mu is more than 40% off actual average
                    if actual_avg > 0 and abs(row['mu'] - actual_avg) / actual_avg > 0.4:
                        suspicious.append({
                            'pick_id': row['id'],
                            'player_name': row['player_name'],
                            'stat': row['stat'],
                            'mu': row['mu'],
                            'actual_avg': actual_avg,
                            'pct_off': round((row['mu'] - actual_avg) / actual_avg * 100, 1)
                        })
        
        return suspicious
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        with self._get_conn() as conn:
            total = conn.execute('SELECT COUNT(*) FROM picks').fetchone()[0]
            resolved = conn.execute('SELECT COUNT(*) FROM picks WHERE resolved_at IS NOT NULL').fetchone()[0]
            
            unique_players = conn.execute('SELECT COUNT(DISTINCT player_name) FROM picks').fetchone()[0]
            unique_slates = conn.execute('SELECT COUNT(DISTINCT slate_date) FROM picks').fetchone()[0]
            
            return {
                'total_picks': total,
                'resolved_picks': resolved,
                'pending_picks': total - resolved,
                'unique_players': unique_players,
                'unique_slates': unique_slates,
                'db_path': str(self.db_path)
            }
    
    def export_to_csv(self, output_file: str = None):
        """Export all picks to CSV"""
        import csv
        
        if output_file is None:
            output_file = f"cache/pick_history_export_{date.today()}.csv"
        
        with self._get_conn() as conn:
            rows = conn.execute('SELECT * FROM picks ORDER BY slate_date, created_at').fetchall()
            
            if not rows:
                print("No picks to export")
                return
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(rows[0].keys())  # Header
                writer.writerows([tuple(row) for row in rows])
        
        print(f"✅ Exported {len(rows)} picks to {output_file}")
        return output_file


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Pick History Database Manager')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--log', type=str, help='Log picks from JSON file')
    parser.add_argument('--calibration', action='store_true', help='Show calibration report')
    parser.add_argument('--performance', action='store_true', help='Show stat performance')
    parser.add_argument('--player', type=str, help='Show player history')
    parser.add_argument('--unresolved', action='store_true', help='Show unresolved picks')
    parser.add_argument('--export', action='store_true', help='Export to CSV')
    
    args = parser.parse_args()
    
    db = PickHistoryDB()
    
    print("=" * 80)
    print("📊 FUOOM PICK HISTORY DATABASE")
    print("=" * 80)
    print()
    
    if args.stats:
        stats = db.get_stats()
        print(f"📁 Database: {stats['db_path']}")
        print(f"📋 Total picks: {stats['total_picks']}")
        print(f"✅ Resolved: {stats['resolved_picks']}")
        print(f"⏳ Pending: {stats['pending_picks']}")
        print(f"👥 Unique players: {stats['unique_players']}")
        print(f"📅 Unique slates: {stats['unique_slates']}")
    
    elif args.log:
        count = db.log_from_json(args.log)
        print(f"✅ Logged {count} picks from {args.log}")
    
    elif args.calibration:
        report = db.get_calibration_report()
        print("📊 CALIBRATION REPORT")
        print("-" * 60)
        print(f"{'Conf':<10} {'Predicted':<12} {'Actual':<12} {'Delta':<10} {'N':<8}")
        print("-" * 60)
        for row in report:
            print(f"{row['confidence_bucket']:<10} {row['predicted_rate']:<12.1f} {row['actual_rate']:<12.1f} {row['delta']:<10.1f} {row['sample_size']:<8}")
    
    elif args.performance:
        stats = db.get_stat_performance()
        print("📊 STAT PERFORMANCE")
        print("-" * 60)
        print(f"{'Stat':<15} {'Picks':<10} {'Hits':<10} {'Hit Rate':<12}")
        print("-" * 60)
        for row in stats:
            print(f"{row['stat']:<15} {row['total_picks']:<10} {row['hits']:<10} {row['hit_rate']:<12.1f}%")
    
    elif args.player:
        history = db.get_player_history(args.player, limit=20)
        print(f"📊 {args.player} PICK HISTORY")
        print("-" * 80)
        for pick in history:
            result = '✅' if pick['hit'] else '❌' if pick['hit'] is not None else '⏳'
            conf = pick['confidence'] or pick['effective_confidence'] or 0
            print(f"{result} {pick['slate_date']} | {pick['stat']} {pick['direction']} {pick['line']} | Conf: {conf:.0f}%")
    
    elif args.unresolved:
        picks = db.get_unresolved_picks()
        print(f"⏳ UNRESOLVED PICKS ({len(picks)})")
        print("-" * 80)
        for pick in picks[:20]:
            print(f"   {pick['slate_date']} | {pick['player_name']} {pick['stat']} {pick['direction']} {pick['line']}")
    
    elif args.export:
        db.export_to_csv()
    
    else:
        print("Usage examples:")
        print()
        print("  # Show database stats")
        print("  python pick_history_db.py --stats")
        print()
        print("  # Log picks from JSON")
        print("  python pick_history_db.py --log outputs/FILE.json")
        print()
        print("  # Show calibration report")
        print("  python pick_history_db.py --calibration")
        print()
        print("  # Show stat performance")
        print("  python pick_history_db.py --performance")
        print()
        print("  # Show player history")
        print('  python pick_history_db.py --player "Cam Thomas"')
        print()
        print("  # Export to CSV")
        print("  python pick_history_db.py --export")
    
    print()
    print("=" * 80)
