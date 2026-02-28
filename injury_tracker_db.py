"""
INJURY TRACKER DATABASE
Real-time injury status tracking to avoid trap lines.

Usage:
    from injury_tracker_db import injuries
    
    # Check if player is injured
    status = injuries.get_player_status("Tyler Herro")
    # → {'status': 'OUT', 'injury': 'ankle', 'return_date': None}
    
    # Get all injured players for a slate
    injured = injuries.check_slate("outputs/SLATE.json")
    # → List of injured players to AVOID

Benefits:
    - Avoid betting on injured/limited players
    - Flag GTD (game-time decisions)
    - Track minute restrictions
    - Historical injury impact
"""

import sqlite3
import json
import time
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
from contextlib import contextmanager

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

DB_PATH = Path("cache/injury_tracker.db")
CACHE_TTL_HOURS = 4  # Injuries change frequently

# Try to import NBA API
try:
    from nba_api.stats.endpoints import playerindex
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════════
# INJURY STATUS LEVELS
# ═══════════════════════════════════════════════════════════════════

INJURY_LEVELS = {
    'OUT': {'severity': 5, 'action': 'SKIP', 'emoji': '🚫'},
    'DOUBTFUL': {'severity': 4, 'action': 'SKIP', 'emoji': '⛔'},
    'QUESTIONABLE': {'severity': 3, 'action': 'CAUTION', 'emoji': '⚠️'},
    'PROBABLE': {'severity': 2, 'action': 'MONITOR', 'emoji': '👀'},
    'GTD': {'severity': 3, 'action': 'CAUTION', 'emoji': '⏳'},  # Game-time decision
    'DAY-TO-DAY': {'severity': 2, 'action': 'MONITOR', 'emoji': '📅'},
    'ACTIVE': {'severity': 0, 'action': 'OK', 'emoji': '✅'},
    'UNKNOWN': {'severity': 1, 'action': 'CHECK', 'emoji': '❓'},
}

# ═══════════════════════════════════════════════════════════════════
# HARDCODED INJURY REPORT (Updated Jan 30, 2026)
# In production, this would be scraped from NBA.com or FantasyLabs
# ═══════════════════════════════════════════════════════════════════

CURRENT_INJURIES = {
    # Format: 'Player Name': {'status': 'OUT/QUESTIONABLE/etc', 'injury': 'description', 'team': 'XXX'}
    
    # HIGH PROFILE OUT
    'Tyler Herro': {'status': 'OUT', 'injury': 'groin strain', 'team': 'MIA'},
    'Anthony Davis': {'status': 'OUT', 'injury': 'abdominal strain', 'team': 'LAL'},
    'Kyrie Irving': {'status': 'OUT', 'injury': 'back spasms', 'team': 'DAL'},
    'Tyrese Haliburton': {'status': 'OUT', 'injury': 'hamstring', 'team': 'IND'},
    'Dejounte Murray': {'status': 'OUT', 'injury': 'hand fracture', 'team': 'NOP'},
    'Fred VanVleet': {'status': 'OUT', 'injury': 'knee', 'team': 'HOU'},
    'Kristaps Porzingis': {'status': 'OUT', 'injury': 'ankle', 'team': 'BOS'},
    'Paolo Banchero': {'status': 'OUT', 'injury': 'oblique tear', 'team': 'ORL'},
    'Kawhi Leonard': {'status': 'OUT', 'injury': 'knee inflammation', 'team': 'LAC'},
    'Jimmy Butler': {'status': 'OUT', 'injury': 'ankle', 'team': 'MIA'},
    
    # QUESTIONABLE / GTD
    'Luka Doncic': {'status': 'QUESTIONABLE', 'injury': 'calf strain', 'team': 'DAL'},
    'Ja Morant': {'status': 'QUESTIONABLE', 'injury': 'shoulder', 'team': 'MEM'},
    'Zion Williamson': {'status': 'GTD', 'injury': 'hamstring tightness', 'team': 'NOP'},
    'Joel Embiid': {'status': 'GTD', 'injury': 'knee management', 'team': 'PHI'},
    'Damian Lillard': {'status': 'QUESTIONABLE', 'injury': 'calf', 'team': 'MIL'},
    'Karl-Anthony Towns': {'status': 'QUESTIONABLE', 'injury': 'knee soreness', 'team': 'NYK'},
    
    # PROBABLE / DAY-TO-DAY
    'LeBron James': {'status': 'PROBABLE', 'injury': 'foot soreness', 'team': 'LAL'},
    'Kevin Durant': {'status': 'DAY-TO-DAY', 'injury': 'calf tightness', 'team': 'PHX'},
    'Giannis Antetokounmpo': {'status': 'PROBABLE', 'injury': 'back tightness', 'team': 'MIL'},
    
    # RETURNING FROM INJURY (minute restrictions likely)
    'Chet Holmgren': {'status': 'ACTIVE', 'injury': 'returning from hip', 'team': 'OKC', 'minutes_restriction': True},
    'Scoot Henderson': {'status': 'ACTIVE', 'injury': 'returning from ankle', 'team': 'POR', 'minutes_restriction': True},
}

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class InjuryTrackerDB:
    """SQLite database for tracking player injuries"""
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._load_current_injuries()
    
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
            # Current injury status
            conn.execute('''
                CREATE TABLE IF NOT EXISTS injuries (
                    player_name TEXT PRIMARY KEY,
                    team TEXT,
                    status TEXT,
                    injury TEXT,
                    minutes_restriction BOOLEAN DEFAULT FALSE,
                    games_missed INTEGER DEFAULT 0,
                    last_updated TIMESTAMP,
                    source TEXT DEFAULT 'manual'
                )
            ''')
            
            # Injury history (for tracking patterns)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS injury_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT,
                    team TEXT,
                    status TEXT,
                    injury TEXT,
                    reported_date DATE,
                    resolved_date DATE,
                    games_missed INTEGER,
                    first_game_back_stats TEXT
                )
            ''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON injuries(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_team ON injuries(team)')
    
    def _load_current_injuries(self):
        """Load hardcoded injuries into database"""
        with self._get_conn() as conn:
            for player, info in CURRENT_INJURIES.items():
                conn.execute('''
                    INSERT OR REPLACE INTO injuries 
                    (player_name, team, status, injury, minutes_restriction, last_updated, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    player,
                    info.get('team'),
                    info.get('status'),
                    info.get('injury'),
                    info.get('minutes_restriction', False),
                    datetime.now().isoformat(),
                    'hardcoded_jan30'
                ))
    
    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_player_status(self, player_name: str) -> Optional[Dict]:
        """
        Get injury status for a player.
        
        Returns:
            Dict with status, injury, action, emoji or None if healthy
        """
        with self._get_conn() as conn:
            row = conn.execute(
                'SELECT * FROM injuries WHERE player_name = ?',
                (player_name,)
            ).fetchone()
            
            if row:
                status = row['status']
                level = INJURY_LEVELS.get(status, INJURY_LEVELS['UNKNOWN'])
                
                return {
                    'player_name': player_name,
                    'team': row['team'],
                    'status': status,
                    'injury': row['injury'],
                    'minutes_restriction': row['minutes_restriction'],
                    'action': level['action'],
                    'emoji': level['emoji'],
                    'severity': level['severity']
                }
        
        return None  # Player is healthy
    
    def is_injured(self, player_name: str) -> bool:
        """Quick check if player has any injury status"""
        status = self.get_player_status(player_name)
        return status is not None and status['status'] not in ('ACTIVE', 'PROBABLE')
    
    def should_skip(self, player_name: str) -> bool:
        """Check if player should be skipped (OUT/DOUBTFUL)"""
        status = self.get_player_status(player_name)
        if not status:
            return False
        return status['action'] == 'SKIP'
    
    def needs_caution(self, player_name: str) -> bool:
        """Check if player needs caution (QUESTIONABLE/GTD)"""
        status = self.get_player_status(player_name)
        if not status:
            return False
        return status['action'] == 'CAUTION'
    
    def get_all_injuries(self, status_filter: str = None) -> List[Dict]:
        """Get all players with injuries"""
        query = 'SELECT * FROM injuries'
        params = []
        
        if status_filter:
            query += ' WHERE status = ?'
            params.append(status_filter)
        
        query += ' ORDER BY status, player_name'
        
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row) -> Dict:
        """Convert database row to dict with action info"""
        status = row['status']
        level = INJURY_LEVELS.get(status, INJURY_LEVELS['UNKNOWN'])
        
        return {
            'player_name': row['player_name'],
            'team': row['team'],
            'status': status,
            'injury': row['injury'],
            'minutes_restriction': row['minutes_restriction'],
            'action': level['action'],
            'emoji': level['emoji']
        }
    
    def get_team_injuries(self, team: str) -> List[Dict]:
        """Get all injuries for a team"""
        with self._get_conn() as conn:
            rows = conn.execute(
                'SELECT * FROM injuries WHERE team = ? ORDER BY status',
                (team.upper(),)
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]
    
    # ═══════════════════════════════════════════════════════════════
    # SLATE VALIDATION
    # ═══════════════════════════════════════════════════════════════
    
    def check_slate(self, json_file: str) -> Dict:
        """
        Check all players in a slate for injuries.
        
        Returns:
            Dict with skip (OUT/DOUBTFUL), caution (QUESTIONABLE/GTD), monitor (PROBABLE)
        """
        with open(json_file, encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', []))
        else:
            picks = data
        
        players = set(p.get('player', p.get('player_name')) for p in picks if p.get('player') or p.get('player_name'))
        
        results = {
            'skip': [],      # OUT, DOUBTFUL - don't bet
            'caution': [],   # QUESTIONABLE, GTD - bet carefully
            'monitor': [],   # PROBABLE, DAY-TO-DAY - likely playing
            'restricted': [] # Active but minutes restriction
        }
        
        for player in players:
            status = self.get_player_status(player)
            
            if status:
                entry = {
                    'player': player,
                    'team': status['team'],
                    'status': status['status'],
                    'injury': status['injury'],
                    'emoji': status['emoji']
                }
                
                if status['action'] == 'SKIP':
                    results['skip'].append(entry)
                elif status['action'] == 'CAUTION':
                    results['caution'].append(entry)
                elif status['action'] == 'MONITOR':
                    results['monitor'].append(entry)
                
                if status.get('minutes_restriction'):
                    results['restricted'].append(entry)
        
        return results
    
    def get_injury_warning(self, player_name: str) -> Optional[str]:
        """
        Get formatted injury warning for narratives.
        
        Returns:
            Warning string or None if healthy
        """
        status = self.get_player_status(player_name)
        
        if not status:
            return None
        
        emoji = status['emoji']
        injury = status['injury']
        action = status['action']
        
        if action == 'SKIP':
            return f"{emoji} **{status['status']}** ({injury}) - DO NOT BET"
        elif action == 'CAUTION':
            return f"{emoji} **{status['status']}** ({injury}) - Risky, may not play"
        elif action == 'MONITOR':
            return f"{emoji} {status['status']} ({injury}) - Likely playing but monitor"
        elif status.get('minutes_restriction'):
            return f"⚠️ Minutes restriction likely (returning from {injury})"
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # MANUAL UPDATES
    # ═══════════════════════════════════════════════════════════════
    
    def update_injury(self, player_name: str, status: str, injury: str = None, 
                      team: str = None, minutes_restriction: bool = False):
        """Manually update injury status"""
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO injuries 
                (player_name, team, status, injury, minutes_restriction, last_updated, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_name,
                team,
                status.upper(),
                injury,
                minutes_restriction,
                datetime.now().isoformat(),
                'manual'
            ))
    
    def clear_injury(self, player_name: str):
        """Remove player from injury list (they're healthy)"""
        with self._get_conn() as conn:
            conn.execute('DELETE FROM injuries WHERE player_name = ?', (player_name,))
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict:
        """Get injury database statistics"""
        with self._get_conn() as conn:
            total = conn.execute('SELECT COUNT(*) FROM injuries').fetchone()[0]
            
            by_status = {}
            for row in conn.execute('SELECT status, COUNT(*) as cnt FROM injuries GROUP BY status').fetchall():
                by_status[row['status']] = row['cnt']
            
            return {
                'total_injuries': total,
                'by_status': by_status,
                'db_path': str(self.db_path)
            }
    
    def print_report(self):
        """Print formatted injury report"""
        print("=" * 70)
        print("🏥 NBA INJURY REPORT")
        print("=" * 70)
        print()
        
        # OUT players
        out_players = self.get_all_injuries('OUT')
        if out_players:
            print("🚫 OUT (Do Not Bet):")
            for p in out_players:
                print(f"   {p['player_name']} ({p['team']}) - {p['injury']}")
            print()
        
        # DOUBTFUL
        doubtful = self.get_all_injuries('DOUBTFUL')
        if doubtful:
            print("⛔ DOUBTFUL (Skip):")
            for p in doubtful:
                print(f"   {p['player_name']} ({p['team']}) - {p['injury']}")
            print()
        
        # QUESTIONABLE/GTD
        questionable = self.get_all_injuries('QUESTIONABLE') + self.get_all_injuries('GTD')
        if questionable:
            print("⚠️ QUESTIONABLE/GTD (Caution):")
            for p in questionable:
                print(f"   {p['player_name']} ({p['team']}) - {p['injury']}")
            print()
        
        # PROBABLE
        probable = self.get_all_injuries('PROBABLE') + self.get_all_injuries('DAY-TO-DAY')
        if probable:
            print("👀 PROBABLE/DAY-TO-DAY (Monitor):")
            for p in probable:
                print(f"   {p['player_name']} ({p['team']}) - {p['injury']}")
            print()


# ═══════════════════════════════════════════════════════════════════
# SINGLETON + CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

injuries = InjuryTrackerDB()

def get_player_status(player_name: str) -> Optional[Dict]:
    return injuries.get_player_status(player_name)

def is_injured(player_name: str) -> bool:
    return injuries.is_injured(player_name)

def should_skip(player_name: str) -> bool:
    return injuries.should_skip(player_name)

def check_slate(json_file: str) -> Dict:
    return injuries.check_slate(json_file)

def get_injury_warning(player_name: str) -> Optional[str]:
    return injuries.get_injury_warning(player_name)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='NBA Injury Tracker')
    parser.add_argument('--report', action='store_true', help='Show full injury report')
    parser.add_argument('--player', type=str, help='Check specific player')
    parser.add_argument('--team', type=str, help='Show team injuries')
    parser.add_argument('--check', type=str, help='Check slate for injuries')
    parser.add_argument('--stats', action='store_true', help='Show database stats')
    
    args = parser.parse_args()
    
    db = InjuryTrackerDB()
    
    if args.report:
        db.print_report()
    
    elif args.player:
        status = db.get_player_status(args.player)
        if status:
            print(f"{status['emoji']} {args.player}: {status['status']}")
            print(f"   Injury: {status['injury']}")
            print(f"   Action: {status['action']}")
            warning = db.get_injury_warning(args.player)
            if warning:
                print(f"   Warning: {warning}")
        else:
            print(f"✅ {args.player}: HEALTHY (no injury reported)")
    
    elif args.team:
        injuries_list = db.get_team_injuries(args.team)
        print(f"🏀 {args.team} Injuries ({len(injuries_list)})")
        print("-" * 50)
        for p in injuries_list:
            print(f"   {p['emoji']} {p['player_name']}: {p['status']} ({p['injury']})")
    
    elif args.check:
        results = db.check_slate(args.check)
        
        print("=" * 70)
        print("🏥 SLATE INJURY CHECK")
        print("=" * 70)
        print()
        
        if results['skip']:
            print(f"🚫 SKIP THESE ({len(results['skip'])}):")
            for p in results['skip']:
                print(f"   {p['emoji']} {p['player']} ({p['team']}) - {p['status']}: {p['injury']}")
            print()
        
        if results['caution']:
            print(f"⚠️ USE CAUTION ({len(results['caution'])}):")
            for p in results['caution']:
                print(f"   {p['emoji']} {p['player']} ({p['team']}) - {p['status']}: {p['injury']}")
            print()
        
        if results['monitor']:
            print(f"👀 MONITOR ({len(results['monitor'])}):")
            for p in results['monitor']:
                print(f"   {p['emoji']} {p['player']} ({p['team']}) - {p['status']}: {p['injury']}")
            print()
        
        if not results['skip'] and not results['caution'] and not results['monitor']:
            print("✅ No injury concerns found in this slate!")
    
    elif args.stats:
        stats = db.get_stats()
        print(f"📊 Injury Database Stats")
        print(f"   Total: {stats['total_injuries']}")
        for status, count in stats['by_status'].items():
            print(f"   {status}: {count}")
    
    else:
        db.print_report()
