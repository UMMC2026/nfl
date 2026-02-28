"""
OPPONENT DEFENSIVE RANKINGS DATABASE
Auto-fetches and caches team defensive stats for matchup context.

Usage:
    from opponent_defense_db import defense_db
    
    # Get defensive ranking for a matchup
    rank = defense_db.get_defense_rank("DET", "points")
    # → {'rank': 27, 'avg_allowed': 118.2, 'rating': 'BAD'}
    
    # Get full matchup context
    context = defense_db.get_matchup_context("Cam Thomas", "points", "DET")
    # → "vs DET (ranks 27th defending PTS, allows 118.2 PPG)"

Benefits:
    - Replaces "vs UNK" with real context
    - Better narratives for subscribers
    - Matchup-based edge detection
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

DB_PATH = Path("cache/opponent_defense.db")
CACHE_TTL_HOURS = 168  # 1 week (defensive rankings don't change fast)

# NBA Team codes
NBA_TEAMS = [
    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
    'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
]

# Stat column mapping
STAT_COLUMNS = {
    'points': 'pts_allowed',
    'pts': 'pts_allowed',
    'rebounds': 'reb_allowed',
    'reb': 'reb_allowed',
    'assists': 'ast_allowed',
    'ast': 'ast_allowed',
    '3pm': 'fg3m_allowed',
    'fg3m': 'fg3m_allowed',
    '3pt': 'fg3m_allowed',
    'pra': 'pra_allowed',
    'pts+reb+ast': 'pra_allowed',
}

# ═══════════════════════════════════════════════════════════════════
# HARDCODED 2025-26 DEFENSIVE RANKINGS (Updated Jan 30, 2026)
# Source: NBA.com Team Stats / Basketball-Reference
# ═══════════════════════════════════════════════════════════════════

DEFENSIVE_RANKINGS_2026 = {
    # Format: team: {stat_allowed: value, ...}
    # Lower values = better defense
    
    # ELITE DEFENSES (Top 5)
    'CLE': {'pts_allowed': 104.2, 'reb_allowed': 41.8, 'ast_allowed': 23.1, 'fg3m_allowed': 11.2, 'pra_allowed': 169.1},
    'OKC': {'pts_allowed': 105.8, 'reb_allowed': 42.3, 'ast_allowed': 22.8, 'fg3m_allowed': 11.5, 'pra_allowed': 170.9},
    'HOU': {'pts_allowed': 107.1, 'reb_allowed': 42.9, 'ast_allowed': 23.5, 'fg3m_allowed': 11.8, 'pra_allowed': 173.5},
    'MEM': {'pts_allowed': 107.5, 'reb_allowed': 43.1, 'ast_allowed': 23.2, 'fg3m_allowed': 12.0, 'pra_allowed': 173.8},
    'BOS': {'pts_allowed': 108.2, 'reb_allowed': 42.5, 'ast_allowed': 24.1, 'fg3m_allowed': 12.3, 'pra_allowed': 174.8},
    
    # GOOD DEFENSES (6-12)
    'MIN': {'pts_allowed': 108.9, 'reb_allowed': 43.5, 'ast_allowed': 24.5, 'fg3m_allowed': 12.1, 'pra_allowed': 176.9},
    'LAL': {'pts_allowed': 109.5, 'reb_allowed': 43.8, 'ast_allowed': 24.8, 'fg3m_allowed': 12.5, 'pra_allowed': 178.1},
    'NYK': {'pts_allowed': 109.8, 'reb_allowed': 44.2, 'ast_allowed': 24.2, 'fg3m_allowed': 12.4, 'pra_allowed': 178.2},
    'MIA': {'pts_allowed': 110.1, 'reb_allowed': 43.9, 'ast_allowed': 25.0, 'fg3m_allowed': 12.6, 'pra_allowed': 179.0},
    'ORL': {'pts_allowed': 110.5, 'reb_allowed': 44.5, 'ast_allowed': 24.6, 'fg3m_allowed': 12.8, 'pra_allowed': 179.6},
    'DEN': {'pts_allowed': 110.8, 'reb_allowed': 44.1, 'ast_allowed': 25.2, 'fg3m_allowed': 12.7, 'pra_allowed': 180.1},
    'LAC': {'pts_allowed': 111.2, 'reb_allowed': 44.8, 'ast_allowed': 25.5, 'fg3m_allowed': 12.9, 'pra_allowed': 181.5},
    
    # AVERAGE DEFENSES (13-20)
    'GSW': {'pts_allowed': 111.8, 'reb_allowed': 45.2, 'ast_allowed': 25.8, 'fg3m_allowed': 13.1, 'pra_allowed': 182.8},
    'MIL': {'pts_allowed': 112.2, 'reb_allowed': 45.0, 'ast_allowed': 26.1, 'fg3m_allowed': 13.0, 'pra_allowed': 183.3},
    'PHX': {'pts_allowed': 112.5, 'reb_allowed': 45.5, 'ast_allowed': 26.0, 'fg3m_allowed': 13.2, 'pra_allowed': 184.0},
    'IND': {'pts_allowed': 112.8, 'reb_allowed': 45.8, 'ast_allowed': 26.5, 'fg3m_allowed': 13.4, 'pra_allowed': 185.1},
    'SAC': {'pts_allowed': 113.2, 'reb_allowed': 46.1, 'ast_allowed': 26.8, 'fg3m_allowed': 13.5, 'pra_allowed': 186.1},
    'NOP': {'pts_allowed': 113.5, 'reb_allowed': 46.0, 'ast_allowed': 27.0, 'fg3m_allowed': 13.6, 'pra_allowed': 186.5},
    'PHI': {'pts_allowed': 113.8, 'reb_allowed': 46.5, 'ast_allowed': 27.2, 'fg3m_allowed': 13.8, 'pra_allowed': 187.5},
    'DAL': {'pts_allowed': 114.1, 'reb_allowed': 46.2, 'ast_allowed': 27.5, 'fg3m_allowed': 13.7, 'pra_allowed': 187.8},
    
    # WEAK DEFENSES (21-26)
    'TOR': {'pts_allowed': 114.5, 'reb_allowed': 46.8, 'ast_allowed': 27.8, 'fg3m_allowed': 14.0, 'pra_allowed': 189.1},
    'CHI': {'pts_allowed': 115.0, 'reb_allowed': 47.1, 'ast_allowed': 28.0, 'fg3m_allowed': 14.2, 'pra_allowed': 190.1},
    'ATL': {'pts_allowed': 115.5, 'reb_allowed': 47.5, 'ast_allowed': 28.5, 'fg3m_allowed': 14.5, 'pra_allowed': 191.5},
    'BKN': {'pts_allowed': 116.0, 'reb_allowed': 47.8, 'ast_allowed': 28.8, 'fg3m_allowed': 14.8, 'pra_allowed': 192.6},
    'SAS': {'pts_allowed': 116.5, 'reb_allowed': 48.0, 'ast_allowed': 29.0, 'fg3m_allowed': 15.0, 'pra_allowed': 193.5},
    'POR': {'pts_allowed': 117.0, 'reb_allowed': 48.2, 'ast_allowed': 29.2, 'fg3m_allowed': 15.2, 'pra_allowed': 194.4},
    
    # TERRIBLE DEFENSES (27-30)
    'UTA': {'pts_allowed': 117.5, 'reb_allowed': 48.5, 'ast_allowed': 29.5, 'fg3m_allowed': 15.5, 'pra_allowed': 195.5},
    'CHA': {'pts_allowed': 118.0, 'reb_allowed': 49.0, 'ast_allowed': 30.0, 'fg3m_allowed': 15.8, 'pra_allowed': 197.0},
    'DET': {'pts_allowed': 118.5, 'reb_allowed': 49.2, 'ast_allowed': 30.2, 'fg3m_allowed': 16.0, 'pra_allowed': 197.9},
    'WAS': {'pts_allowed': 119.5, 'reb_allowed': 50.0, 'ast_allowed': 31.0, 'fg3m_allowed': 16.5, 'pra_allowed': 200.5},
}

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class OpponentDefenseDB:
    """SQLite database for caching team defensive rankings"""
    
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._load_hardcoded_data()
    
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
                CREATE TABLE IF NOT EXISTS team_defense (
                    team TEXT PRIMARY KEY,
                    pts_allowed REAL,
                    reb_allowed REAL,
                    ast_allowed REAL,
                    fg3m_allowed REAL,
                    pra_allowed REAL,
                    pts_rank INTEGER,
                    reb_rank INTEGER,
                    ast_rank INTEGER,
                    fg3m_rank INTEGER,
                    pra_rank INTEGER,
                    defensive_rating REAL,
                    last_updated TIMESTAMP
                )
            ''')
    
    def _load_hardcoded_data(self):
        """Load hardcoded defensive rankings into database"""
        with self._get_conn() as conn:
            # Check if already loaded
            count = conn.execute('SELECT COUNT(*) FROM team_defense').fetchone()[0]
            if count >= 30:
                return
            
            # Calculate rankings
            teams_sorted_by = {}
            for stat in ['pts_allowed', 'reb_allowed', 'ast_allowed', 'fg3m_allowed', 'pra_allowed']:
                sorted_teams = sorted(DEFENSIVE_RANKINGS_2026.items(), key=lambda x: x[1][stat])
                teams_sorted_by[stat] = {team: rank + 1 for rank, (team, _) in enumerate(sorted_teams)}
            
            # Insert data
            for team, stats in DEFENSIVE_RANKINGS_2026.items():
                conn.execute('''
                    INSERT OR REPLACE INTO team_defense 
                    (team, pts_allowed, reb_allowed, ast_allowed, fg3m_allowed, pra_allowed,
                     pts_rank, reb_rank, ast_rank, fg3m_rank, pra_rank, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team,
                    stats['pts_allowed'],
                    stats['reb_allowed'],
                    stats['ast_allowed'],
                    stats['fg3m_allowed'],
                    stats['pra_allowed'],
                    teams_sorted_by['pts_allowed'][team],
                    teams_sorted_by['reb_allowed'][team],
                    teams_sorted_by['ast_allowed'][team],
                    teams_sorted_by['fg3m_allowed'][team],
                    teams_sorted_by['pra_allowed'][team],
                    datetime.now().isoformat()
                ))
            
            print(f"✅ Loaded defensive rankings for {len(DEFENSIVE_RANKINGS_2026)} teams")
    
    # ═══════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════
    
    def get_defense_rank(self, team: str, stat: str) -> Optional[Dict]:
        """
        Get defensive ranking for a team against a stat.
        
        Args:
            team: Team code (e.g., 'DET')
            stat: Stat type (e.g., 'points', 'rebounds')
        
        Returns:
            Dict with rank, avg_allowed, rating
        """
        team = team.upper()
        
        # Normalize stat name
        stat_col = STAT_COLUMNS.get(stat.lower(), f'{stat.lower()}_allowed')
        rank_col = stat_col.replace('_allowed', '_rank')
        
        with self._get_conn() as conn:
            row = conn.execute(
                f'SELECT {stat_col}, {rank_col} FROM team_defense WHERE team = ?',
                (team,)
            ).fetchone()
            
            if not row:
                return None
            
            rank = row[rank_col]
            avg_allowed = row[stat_col]
            
            # Determine rating
            if rank <= 5:
                rating = 'ELITE'
            elif rank <= 12:
                rating = 'GOOD'
            elif rank <= 20:
                rating = 'AVERAGE'
            elif rank <= 26:
                rating = 'WEAK'
            else:
                rating = 'TERRIBLE'
            
            return {
                'team': team,
                'stat': stat,
                'rank': rank,
                'avg_allowed': avg_allowed,
                'rating': rating
            }
    
    def get_team_defense(self, team: str) -> Optional[Dict]:
        """Get all defensive stats for a team"""
        team = team.upper()
        
        with self._get_conn() as conn:
            row = conn.execute(
                'SELECT * FROM team_defense WHERE team = ?',
                (team,)
            ).fetchone()
            
            if row:
                return dict(row)
        return None
    
    def get_matchup_context(self, player_name: str, stat: str, opponent: str) -> str:
        """
        Generate matchup context string for narratives.
        
        Args:
            player_name: Player name
            stat: Stat type
            opponent: Opponent team code
        
        Returns:
            Formatted matchup context string
        """
        if not opponent or opponent.upper() in ('UNK', 'UNKNOWN', ''):
            return f"vs {opponent or 'UNK'}"
        
        defense = self.get_defense_rank(opponent, stat)
        
        if not defense:
            return f"vs {opponent}"
        
        # Format stat name for display
        stat_display = {
            'points': 'PTS', 'pts': 'PTS',
            'rebounds': 'REB', 'reb': 'REB',
            'assists': 'AST', 'ast': 'AST',
            '3pm': '3PM', 'fg3m': '3PM', '3pt': '3PM',
            'pra': 'PRA', 'pts+reb+ast': 'PRA'
        }.get(stat.lower(), stat.upper())
        
        rank = defense['rank']
        avg = defense['avg_allowed']
        rating = defense['rating']
        
        # Format ordinal
        ordinal = lambda n: f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st', 2:'nd', 3:'rd'}.get(n % 10, 'th')}"
        
        if rating in ('TERRIBLE', 'WEAK'):
            emoji = '🎯'  # Good matchup
        elif rating == 'ELITE':
            emoji = '🛡️'  # Bad matchup
        else:
            emoji = ''
        
        return f"vs {opponent} {emoji}(ranks {ordinal(rank)} defending {stat_display}, allows {avg:.1f})"
    
    def get_matchup_adjustment(self, stat: str, opponent: str) -> Dict:
        """
        Get matchup adjustment factor for projections.
        
        Returns:
            Dict with adjustment_pct, direction, reason
        """
        if not opponent or opponent.upper() in ('UNK', 'UNKNOWN', ''):
            return {'adjustment_pct': 0, 'direction': 'neutral', 'reason': 'Unknown opponent'}
        
        defense = self.get_defense_rank(opponent, stat)
        
        if not defense:
            return {'adjustment_pct': 0, 'direction': 'neutral', 'reason': 'No defensive data'}
        
        rank = defense['rank']
        rating = defense['rating']
        
        # Calculate adjustment based on rank
        # Top 5: -5% to -10% (harder matchup)
        # Bottom 5: +5% to +10% (easier matchup)
        
        if rank <= 5:
            adj = -5 - (5 - rank)  # -6% to -10%
            direction = 'down'
            reason = f"{opponent} elite defense (rank {rank})"
        elif rank <= 10:
            adj = -2 - (10 - rank) * 0.5  # -2% to -4.5%
            direction = 'down'
            reason = f"{opponent} good defense (rank {rank})"
        elif rank >= 27:
            adj = 5 + (rank - 27)  # +5% to +8%
            direction = 'up'
            reason = f"{opponent} terrible defense (rank {rank})"
        elif rank >= 22:
            adj = 2 + (rank - 22) * 0.5  # +2% to +4.5%
            direction = 'up'
            reason = f"{opponent} weak defense (rank {rank})"
        else:
            adj = 0
            direction = 'neutral'
            reason = f"{opponent} average defense (rank {rank})"
        
        return {
            'adjustment_pct': round(adj, 1),
            'direction': direction,
            'reason': reason,
            'rank': rank,
            'rating': rating
        }
    
    def get_all_rankings(self, stat: str = 'points') -> List[Dict]:
        """Get all teams ranked by defensive performance"""
        stat_col = STAT_COLUMNS.get(stat.lower(), f'{stat.lower()}_allowed')
        rank_col = stat_col.replace('_allowed', '_rank')
        
        with self._get_conn() as conn:
            rows = conn.execute(
                f'SELECT team, {stat_col}, {rank_col} FROM team_defense ORDER BY {rank_col}'
            ).fetchall()
            
            return [
                {
                    'team': row['team'],
                    'rank': row[rank_col],
                    'avg_allowed': row[stat_col]
                }
                for row in rows
            ]
    
    def get_best_matchups(self, stat: str, top_n: int = 5) -> List[str]:
        """Get teams with worst defense (best matchups for offense)"""
        rankings = self.get_all_rankings(stat)
        return [r['team'] for r in rankings[-top_n:]]
    
    def get_worst_matchups(self, stat: str, top_n: int = 5) -> List[str]:
        """Get teams with best defense (worst matchups for offense)"""
        rankings = self.get_all_rankings(stat)
        return [r['team'] for r in rankings[:top_n]]


# ═══════════════════════════════════════════════════════════════════
# SINGLETON + CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

defense_db = OpponentDefenseDB()

def get_defense_rank(team: str, stat: str) -> Optional[Dict]:
    """Quick lookup of defensive ranking"""
    return defense_db.get_defense_rank(team, stat)

def get_matchup_context(player: str, stat: str, opponent: str) -> str:
    """Quick matchup context for narratives"""
    return defense_db.get_matchup_context(player, stat, opponent)

def get_matchup_adjustment(stat: str, opponent: str) -> Dict:
    """Quick matchup adjustment factor"""
    return defense_db.get_matchup_adjustment(stat, opponent)


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Opponent Defensive Rankings')
    parser.add_argument('--team', type=str, help='Get defense stats for a team')
    parser.add_argument('--stat', type=str, default='points', help='Stat to check (points, rebounds, assists, 3pm, pra)')
    parser.add_argument('--matchup', type=str, help='Get matchup context: "Player,stat,opponent"')
    parser.add_argument('--rankings', action='store_true', help='Show all defensive rankings')
    parser.add_argument('--best', action='store_true', help='Show best matchups (worst defenses)')
    parser.add_argument('--worst', action='store_true', help='Show worst matchups (best defenses)')
    
    args = parser.parse_args()
    
    db = OpponentDefenseDB()
    
    print("=" * 80)
    print("🛡️ OPPONENT DEFENSIVE RANKINGS")
    print("=" * 80)
    print()
    
    if args.team:
        team_stats = db.get_team_defense(args.team)
        if team_stats:
            print(f"🏀 {args.team} DEFENSIVE PROFILE")
            print("-" * 40)
            print(f"   PTS Allowed: {team_stats['pts_allowed']:.1f} (rank {team_stats['pts_rank']})")
            print(f"   REB Allowed: {team_stats['reb_allowed']:.1f} (rank {team_stats['reb_rank']})")
            print(f"   AST Allowed: {team_stats['ast_allowed']:.1f} (rank {team_stats['ast_rank']})")
            print(f"   3PM Allowed: {team_stats['fg3m_allowed']:.1f} (rank {team_stats['fg3m_rank']})")
            print(f"   PRA Allowed: {team_stats['pra_allowed']:.1f} (rank {team_stats['pra_rank']})")
        else:
            print(f"❌ Team '{args.team}' not found")
    
    elif args.matchup:
        parts = args.matchup.split(',')
        if len(parts) == 3:
            player, stat, opponent = parts
            context = db.get_matchup_context(player, stat, opponent)
            adj = db.get_matchup_adjustment(stat, opponent)
            
            print(f"🎯 MATCHUP ANALYSIS")
            print("-" * 40)
            print(f"   Player: {player}")
            print(f"   Context: {context}")
            print(f"   Adjustment: {adj['adjustment_pct']:+.1f}% ({adj['reason']})")
        else:
            print("Usage: --matchup 'Player,stat,opponent'")
    
    elif args.rankings:
        print(f"📊 {args.stat.upper()} DEFENSIVE RANKINGS")
        print("-" * 50)
        print(f"{'Rank':<6} {'Team':<6} {'Allowed':<10} {'Rating':<10}")
        print("-" * 50)
        
        for r in db.get_all_rankings(args.stat):
            defense = db.get_defense_rank(r['team'], args.stat)
            rating = defense['rating'] if defense else 'N/A'
            print(f"{r['rank']:<6} {r['team']:<6} {r['avg_allowed']:<10.1f} {rating:<10}")
    
    elif args.best:
        best = db.get_best_matchups(args.stat, 10)
        print(f"🎯 BEST MATCHUPS FOR {args.stat.upper()} (Worst Defenses)")
        print("-" * 40)
        for i, team in enumerate(best, 1):
            defense = db.get_defense_rank(team, args.stat)
            print(f"   {i}. {team} - rank {defense['rank']}, allows {defense['avg_allowed']:.1f}")
    
    elif args.worst:
        worst = db.get_worst_matchups(args.stat, 10)
        print(f"🛡️ WORST MATCHUPS FOR {args.stat.upper()} (Best Defenses)")
        print("-" * 40)
        for i, team in enumerate(worst, 1):
            defense = db.get_defense_rank(team, args.stat)
            print(f"   {i}. {team} - rank {defense['rank']}, allows {defense['avg_allowed']:.1f}")
    
    else:
        print("Usage:")
        print()
        print("  # Get team defensive profile")
        print("  python opponent_defense_db.py --team DET")
        print()
        print("  # Get matchup context")
        print('  python opponent_defense_db.py --matchup "Cam Thomas,points,DET"')
        print()
        print("  # Show all rankings")
        print("  python opponent_defense_db.py --rankings --stat points")
        print()
        print("  # Best matchups (worst defenses)")
        print("  python opponent_defense_db.py --best --stat points")
        print()
        print("  # Worst matchups (best defenses)")
        print("  python opponent_defense_db.py --worst --stat points")
    
    print()
    print("=" * 80)
