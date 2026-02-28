"""
TENNIS CSV IMPORTER
Import historical data from Tennis Abstract, ATP, and other free sources

Supported formats:
1. Tennis Abstract match-level data
2. ATP official stats exports
3. Custom CSV format (for manual entry)

SOP v2.1 Compliant - Data Layer
"""

import csv
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


# ============================================================================
# SECTION 1: CSV FORMAT DEFINITIONS
# ============================================================================

# Tennis Abstract format (Jeff Sackmann's GitHub data)
# https://github.com/JeffSackmann/tennis_atp / tennis_wta
TENNIS_ABSTRACT_COLUMNS = {
    'tourney_id': 'tournament_id',
    'tourney_name': 'tournament_name',
    'surface': 'surface',
    'tourney_level': 'tournament_level',
    'tourney_date': 'match_date',
    'match_num': 'match_num',
    'winner_name': 'winner_name',
    'winner_hand': 'winner_hand',
    'winner_ht': 'winner_height',
    'winner_ioc': 'winner_country',
    'winner_age': 'winner_age',
    'loser_name': 'loser_name',
    'loser_hand': 'loser_hand',
    'loser_ht': 'loser_height',
    'loser_ioc': 'loser_country',
    'loser_age': 'loser_age',
    'score': 'score',
    'best_of': 'best_of',
    'round': 'round',
    'minutes': 'duration_minutes',
    # Stats columns
    'w_ace': 'winner_aces',
    'w_df': 'winner_df',
    'w_svpt': 'winner_serve_points',
    'w_1stIn': 'winner_first_in',
    'w_1stWon': 'winner_first_won',
    'w_2ndWon': 'winner_second_won',
    'w_SvGms': 'winner_service_games',
    'w_bpSaved': 'winner_bp_saved',
    'w_bpFaced': 'winner_bp_faced',
    'l_ace': 'loser_aces',
    'l_df': 'loser_df',
    'l_svpt': 'loser_serve_points',
    'l_1stIn': 'loser_first_in',
    'l_1stWon': 'loser_first_won',
    'l_2ndWon': 'loser_second_won',
    'l_SvGms': 'loser_service_games',
    'l_bpSaved': 'loser_bp_saved',
    'l_bpFaced': 'loser_bp_faced',
}

# Tournament level mappings
TOURNEY_LEVEL_MAP = {
    'G': 'Grand Slam',
    'M': 'Masters 1000',
    'A': 'ATP 500',
    'B': 'ATP 250',
    'F': 'Tour Finals',
    'D': 'Davis Cup',
    'C': 'Challenger',
}

# Round mappings
ROUND_MAP = {
    'F': 'Final',
    'SF': 'Semifinal',
    'QF': 'Quarterfinal',
    'R16': 'Round of 16',
    'R32': 'Round of 32',
    'R64': 'Round of 64',
    'R128': 'Round of 128',
    'RR': 'Round Robin',
    'BR': 'Bronze Medal',
}


# ============================================================================
# SECTION 2: DATABASE SCHEMA (Matches tennis_data_infrastructure.py)
# ============================================================================

TENNIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT UNIQUE NOT NULL,
    country TEXT,
    hand TEXT,
    height_cm INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_name TEXT NOT NULL,
    tournament_level TEXT,
    surface TEXT NOT NULL,
    match_date DATE NOT NULL,
    round TEXT,
    player1_id INTEGER REFERENCES players(player_id),
    player2_id INTEGER REFERENCES players(player_id),
    winner_id INTEGER REFERENCES players(player_id),
    score TEXT,
    sets_p1 INTEGER,
    sets_p2 INTEGER,
    games_p1 INTEGER,
    games_p2 INTEGER,
    match_duration_minutes INTEGER,
    best_of INTEGER DEFAULT 3,
    source_file TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS match_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER REFERENCES matches(match_id),
    player_id INTEGER REFERENCES players(player_id),
    aces INTEGER DEFAULT 0,
    double_faults INTEGER DEFAULT 0,
    first_serve_in INTEGER,
    first_serve_won INTEGER,
    second_serve_won INTEGER,
    serve_points INTEGER,
    service_games_played INTEGER,
    service_games_won INTEGER,
    break_points_faced INTEGER DEFAULT 0,
    break_points_saved INTEGER DEFAULT 0,
    break_points_opportunities INTEGER DEFAULT 0,
    break_points_converted INTEGER DEFAULT 0,
    total_games_won INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_surface ON matches(surface);
CREATE INDEX IF NOT EXISTS idx_matches_player1 ON matches(player1_id);
CREATE INDEX IF NOT EXISTS idx_matches_player2 ON matches(player2_id);
CREATE INDEX IF NOT EXISTS idx_match_stats_player ON match_stats(player_id);
"""


# ============================================================================
# SECTION 3: CSV IMPORTER CLASS
# ============================================================================

class TennisCSVImporter:
    """
    Import tennis data from various CSV formats.
    
    Primary source: Tennis Abstract (Jeff Sackmann)
    - ATP: https://github.com/JeffSackmann/tennis_atp
    - WTA: https://github.com/JeffSackmann/tennis_wta
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to tennis/data folder
            base_path = Path(__file__).parent
            db_path = base_path / "tennis_stats.db"
        
        self.db_path = str(db_path)
        self.conn = None
        self._init_db()
        
        # Stats tracking
        self.import_stats = {
            'matches_imported': 0,
            'matches_skipped': 0,
            'players_added': 0,
            'errors': []
        }
    
    def _init_db(self):
        """Initialize SQLite database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(TENNIS_SCHEMA)
        self.conn.commit()
        print(f"✓ Database initialized: {self.db_path}")
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    # ----- Player Management -----
    
    def _get_or_create_player(
        self, 
        name: str, 
        country: str = None, 
        hand: str = None,
        height: int = None
    ) -> int:
        """Get player_id or create new player"""
        cursor = self.conn.cursor()
        
        # Normalize name
        name = name.strip().title()
        
        # Check if exists
        cursor.execute("SELECT player_id FROM players WHERE player_name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row['player_id']
        
        # Create new
        cursor.execute(
            "INSERT INTO players (player_name, country, hand, height_cm) VALUES (?, ?, ?, ?)",
            (name, country, hand, height)
        )
        self.conn.commit()
        self.import_stats['players_added'] += 1
        return cursor.lastrowid
    
    # ----- Score Parsing -----
    
    def _parse_score(self, score: str) -> Tuple[int, int, int, int]:
        """
        Parse tennis score string.
        
        Input: "6-4 3-6 7-6(5)"
        Output: (sets_p1, sets_p2, games_p1, games_p2)
        """
        if not score:
            return (0, 0, 0, 0)
        
        sets_p1, sets_p2 = 0, 0
        games_p1, games_p2 = 0, 0
        
        # Split into sets
        sets = score.replace('RET', '').replace('W/O', '').strip().split()
        
        for s in sets:
            # Parse set score like "6-4" or "7-6(5)"
            match = re.match(r'(\d+)-(\d+)(\(\d+\))?', s)
            if match:
                g1 = int(match.group(1))
                g2 = int(match.group(2))
                games_p1 += g1
                games_p2 += g2
                
                if g1 > g2:
                    sets_p1 += 1
                elif g2 > g1:
                    sets_p2 += 1
        
        return (sets_p1, sets_p2, games_p1, games_p2)
    
    # ----- Tennis Abstract Import -----
    
    def import_tennis_abstract(
        self, 
        csv_path: str,
        year_filter: int = None,
        surface_filter: str = None,
        min_tourney_level: str = None
    ) -> Dict:
        """
        Import from Tennis Abstract CSV format.
        
        Download from:
        - ATP: https://github.com/JeffSackmann/tennis_atp/blob/master/atp_matches_2024.csv
        - WTA: https://github.com/JeffSackmann/tennis_wta/blob/master/wta_matches_2024.csv
        
        Args:
            csv_path: Path to CSV file
            year_filter: Only import matches from this year
            surface_filter: Only import 'Hard', 'Clay', or 'Grass'
            min_tourney_level: Minimum level ('G'=Slams, 'M'=Masters, etc.)
        """
        print(f"\n{'='*60}")
        print(f"IMPORTING: {csv_path}")
        print(f"{'='*60}")
        
        # Reset stats
        self.import_stats = {
            'matches_imported': 0,
            'matches_skipped': 0,
            'players_added': 0,
            'errors': []
        }
        
        # Level hierarchy for filtering
        level_order = ['G', 'M', 'A', 'B', 'F', 'D', 'C']
        min_level_idx = level_order.index(min_tourney_level) if min_tourney_level else len(level_order)
        
        source_file = Path(csv_path).name
        
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Apply filters
                    if year_filter:
                        match_date = row.get('tourney_date', '')
                        if match_date and not match_date.startswith(str(year_filter)):
                            continue
                    
                    if surface_filter:
                        if row.get('surface', '').lower() != surface_filter.lower():
                            continue
                    
                    if min_tourney_level:
                        level = row.get('tourney_level', 'C')
                        if level not in level_order:
                            continue
                        if level_order.index(level) > min_level_idx:
                            continue
                    
                    # Skip if no stats (incomplete record)
                    if not row.get('w_ace') or row.get('w_ace') == '':
                        self.import_stats['matches_skipped'] += 1
                        continue
                    
                    self._import_tennis_abstract_row(row, source_file)
                    
                except Exception as e:
                    self.import_stats['errors'].append(f"Row error: {e}")
                    continue
        
        self.conn.commit()
        
        # Print summary
        print(f"\n{'='*60}")
        print("IMPORT COMPLETE")
        print(f"{'='*60}")
        print(f"  Matches imported: {self.import_stats['matches_imported']}")
        print(f"  Matches skipped:  {self.import_stats['matches_skipped']}")
        print(f"  Players added:    {self.import_stats['players_added']}")
        if self.import_stats['errors']:
            print(f"  Errors: {len(self.import_stats['errors'])}")
        
        return self.import_stats
    
    def _import_tennis_abstract_row(self, row: Dict, source_file: str):
        """Import single row from Tennis Abstract format"""
        cursor = self.conn.cursor()
        
        # Get/create players
        winner_id = self._get_or_create_player(
            row.get('winner_name', 'Unknown'),
            row.get('winner_ioc'),
            row.get('winner_hand'),
            int(row.get('winner_ht')) if row.get('winner_ht') else None
        )
        
        loser_id = self._get_or_create_player(
            row.get('loser_name', 'Unknown'),
            row.get('loser_ioc'),
            row.get('loser_hand'),
            int(row.get('loser_ht')) if row.get('loser_ht') else None
        )
        
        # Parse score
        score = row.get('score', '')
        sets_w, sets_l, games_w, games_l = self._parse_score(score)
        
        # Parse date
        date_str = row.get('tourney_date', '')
        if len(date_str) == 8:  # Format: YYYYMMDD
            match_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        else:
            match_date = date_str
        
        # Map tournament level
        tourney_level = TOURNEY_LEVEL_MAP.get(
            row.get('tourney_level', ''), 
            row.get('tourney_level', 'Unknown')
        )
        
        # Insert match
        cursor.execute("""
            INSERT INTO matches (
                tournament_name, tournament_level, surface, match_date, round,
                player1_id, player2_id, winner_id, score,
                sets_p1, sets_p2, games_p1, games_p2,
                match_duration_minutes, best_of, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get('tourney_name'),
            tourney_level,
            row.get('surface', 'Hard').title(),
            match_date,
            ROUND_MAP.get(row.get('round', ''), row.get('round')),
            winner_id,  # Winner is player1
            loser_id,   # Loser is player2
            winner_id,
            score,
            sets_w,
            sets_l,
            games_w,
            games_l,
            int(row.get('minutes')) if row.get('minutes') else None,
            int(row.get('best_of', 3)),
            source_file
        ))
        
        match_id = cursor.lastrowid
        
        # Insert winner stats
        self._insert_player_stats(cursor, match_id, winner_id, {
            'aces': row.get('w_ace'),
            'double_faults': row.get('w_df'),
            'serve_points': row.get('w_svpt'),
            'first_serve_in': row.get('w_1stIn'),
            'first_serve_won': row.get('w_1stWon'),
            'second_serve_won': row.get('w_2ndWon'),
            'service_games': row.get('w_SvGms'),
            'bp_saved': row.get('w_bpSaved'),
            'bp_faced': row.get('w_bpFaced'),
            'games_won': games_w
        })
        
        # Insert loser stats
        self._insert_player_stats(cursor, match_id, loser_id, {
            'aces': row.get('l_ace'),
            'double_faults': row.get('l_df'),
            'serve_points': row.get('l_svpt'),
            'first_serve_in': row.get('l_1stIn'),
            'first_serve_won': row.get('l_1stWon'),
            'second_serve_won': row.get('l_2ndWon'),
            'service_games': row.get('l_SvGms'),
            'bp_saved': row.get('l_bpSaved'),
            'bp_faced': row.get('l_bpFaced'),
            'games_won': games_l
        })
        
        self.import_stats['matches_imported'] += 1
    
    def _insert_player_stats(self, cursor, match_id: int, player_id: int, stats: Dict):
        """Insert player match statistics"""
        
        def safe_int(val):
            if val is None or val == '':
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None
        
        svc_games = safe_int(stats.get('service_games'))
        bp_faced = safe_int(stats.get('bp_faced')) or 0
        bp_saved = safe_int(stats.get('bp_saved')) or 0
        
        cursor.execute("""
            INSERT OR REPLACE INTO match_stats (
                match_id, player_id,
                aces, double_faults,
                first_serve_in, first_serve_won, second_serve_won,
                serve_points, service_games_played, service_games_won,
                break_points_faced, break_points_saved,
                break_points_opportunities, break_points_converted,
                total_games_won
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match_id,
            player_id,
            safe_int(stats.get('aces')),
            safe_int(stats.get('double_faults')),
            safe_int(stats.get('first_serve_in')),
            safe_int(stats.get('first_serve_won')),
            safe_int(stats.get('second_serve_won')),
            safe_int(stats.get('serve_points')),
            svc_games,
            svc_games - (bp_faced - bp_saved) if svc_games else None,  # Estimate games won
            bp_faced,
            bp_saved,
            0,  # BP opportunities (need opponent data)
            0,  # BP converted (need opponent data)
            safe_int(stats.get('games_won'))
        ))
    
    # ----- Custom CSV Import -----
    
    def import_custom_csv(self, csv_path: str) -> Dict:
        """
        Import from custom/manual CSV format.
        
        Required columns:
        - player1, player2, winner
        - match_date, tournament, surface
        - score (optional)
        - p1_aces, p1_df, p1_games, p2_aces, p2_df, p2_games (optional)
        """
        print(f"\n{'='*60}")
        print(f"IMPORTING CUSTOM CSV: {csv_path}")
        print(f"{'='*60}")
        
        self.import_stats = {
            'matches_imported': 0,
            'matches_skipped': 0,
            'players_added': 0,
            'errors': []
        }
        
        source_file = Path(csv_path).name
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    self._import_custom_row(row, source_file)
                except Exception as e:
                    self.import_stats['errors'].append(f"Row error: {e}")
                    continue
        
        self.conn.commit()
        
        print(f"\n  Matches imported: {self.import_stats['matches_imported']}")
        print(f"  Players added:    {self.import_stats['players_added']}")
        
        return self.import_stats
    
    def _import_custom_row(self, row: Dict, source_file: str):
        """Import single row from custom format"""
        cursor = self.conn.cursor()
        
        # Get/create players
        p1_id = self._get_or_create_player(row['player1'])
        p2_id = self._get_or_create_player(row['player2'])
        
        winner_name = row.get('winner', row['player1'])
        winner_id = p1_id if winner_name == row['player1'] else p2_id
        
        # Parse score if present
        score = row.get('score', '')
        sets_p1, sets_p2, games_p1, games_p2 = self._parse_score(score)
        
        # Insert match
        cursor.execute("""
            INSERT INTO matches (
                tournament_name, tournament_level, surface, match_date, round,
                player1_id, player2_id, winner_id, score,
                sets_p1, sets_p2, games_p1, games_p2,
                best_of, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get('tournament', 'Unknown'),
            row.get('level', 'Unknown'),
            row.get('surface', 'Hard'),
            row.get('match_date'),
            row.get('round', 'Unknown'),
            p1_id,
            p2_id,
            winner_id,
            score,
            sets_p1,
            sets_p2,
            games_p1 or row.get('p1_games'),
            games_p2 or row.get('p2_games'),
            int(row.get('best_of', 3)),
            source_file
        ))
        
        match_id = cursor.lastrowid
        
        # Insert stats if available
        if row.get('p1_aces'):
            self._insert_player_stats(cursor, match_id, p1_id, {
                'aces': row.get('p1_aces'),
                'double_faults': row.get('p1_df'),
                'games_won': games_p1 or row.get('p1_games')
            })
        
        if row.get('p2_aces'):
            self._insert_player_stats(cursor, match_id, p2_id, {
                'aces': row.get('p2_aces'),
                'double_faults': row.get('p2_df'),
                'games_won': games_p2 or row.get('p2_games')
            })
        
        self.import_stats['matches_imported'] += 1
    
    # ----- Query Methods -----
    
    def get_player_stats(self, player_name: str, n_matches: int = 10) -> Dict:
        """Get recent stats for a player"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                p.player_name,
                m.surface,
                m.match_date,
                m.tournament_name,
                ms.aces,
                ms.double_faults,
                ms.service_games_played,
                ms.break_points_faced,
                ms.break_points_saved,
                ms.total_games_won,
                CASE WHEN m.winner_id = p.player_id THEN 1 ELSE 0 END as won
            FROM players p
            JOIN match_stats ms ON p.player_id = ms.player_id
            JOIN matches m ON ms.match_id = m.match_id
            WHERE p.player_name LIKE ?
            ORDER BY m.match_date DESC
            LIMIT ?
        """, (f"%{player_name}%", n_matches))
        
        rows = cursor.fetchall()
        
        if not rows:
            return None
        
        return {
            'player': rows[0]['player_name'],
            'matches': n_matches,
            'records': [dict(row) for row in rows]
        }
    
    def get_head_to_head(self, player1: str, player2: str) -> Dict:
        """Get head-to-head record between two players"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.*,
                p1.player_name as p1_name,
                p2.player_name as p2_name,
                pw.player_name as winner_name
            FROM matches m
            JOIN players p1 ON m.player1_id = p1.player_id
            JOIN players p2 ON m.player2_id = p2.player_id
            JOIN players pw ON m.winner_id = pw.player_id
            WHERE (p1.player_name LIKE ? AND p2.player_name LIKE ?)
               OR (p1.player_name LIKE ? AND p2.player_name LIKE ?)
            ORDER BY m.match_date DESC
        """, (f"%{player1}%", f"%{player2}%", f"%{player2}%", f"%{player1}%"))
        
        rows = cursor.fetchall()
        
        if not rows:
            return {'matches': 0, 'p1_wins': 0, 'p2_wins': 0}
        
        p1_wins = sum(1 for r in rows if player1.lower() in r['winner_name'].lower())
        p2_wins = len(rows) - p1_wins
        
        return {
            'matches': len(rows),
            'p1_wins': p1_wins,
            'p2_wins': p2_wins,
            'history': [dict(row) for row in rows]
        }
    
    def get_surface_stats(self, player_name: str) -> Dict:
        """Get player stats broken down by surface"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                m.surface,
                COUNT(*) as matches,
                SUM(CASE WHEN m.winner_id = p.player_id THEN 1 ELSE 0 END) as wins,
                AVG(ms.aces) as avg_aces,
                AVG(ms.double_faults) as avg_df,
                AVG(ms.total_games_won) as avg_games
            FROM players p
            JOIN match_stats ms ON p.player_id = ms.player_id
            JOIN matches m ON ms.match_id = m.match_id
            WHERE p.player_name LIKE ?
            GROUP BY m.surface
        """, (f"%{player_name}%",))
        
        rows = cursor.fetchall()
        
        return {
            surface: {
                'matches': row['matches'],
                'wins': row['wins'],
                'win_rate': row['wins'] / row['matches'] if row['matches'] > 0 else 0,
                'avg_aces': row['avg_aces'],
                'avg_df': row['avg_df'],
                'avg_games': row['avg_games']
            }
            for row in rows
            for surface in [row['surface']]
        }


# ============================================================================
# SECTION 4: CLI INTERFACE
# ============================================================================

def download_instructions():
    """Print instructions for downloading Tennis Abstract data"""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║           HOW TO DOWNLOAD TENNIS ABSTRACT DATA                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  1. Go to GitHub:                                                    ║
║     ATP:  https://github.com/JeffSackmann/tennis_atp                 ║
║     WTA:  https://github.com/JeffSackmann/tennis_wta                 ║
║                                                                      ║
║  2. Download match files:                                            ║
║     - atp_matches_2024.csv (or any year)                            ║
║     - atp_matches_2025.csv                                          ║
║     - wta_matches_2024.csv                                          ║
║                                                                      ║
║  3. Place files in: tennis/data/raw/                                 ║
║                                                                      ║
║  4. Run importer:                                                    ║
║     python tennis_csv_importer.py --import atp_matches_2024.csv     ║
║                                                                      ║
║  Data includes:                                                      ║
║     ✓ All ATP/WTA matches                                           ║
║     ✓ Aces, DFs, serve %, break points                              ║
║     ✓ Surface, tournament level                                      ║
║     ✓ Score and duration                                            ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def main():
    """CLI interface for tennis CSV importer"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Tennis CSV Importer')
    parser.add_argument('--import', dest='import_file', help='CSV file to import')
    parser.add_argument('--format', choices=['tennis_abstract', 'custom'], 
                       default='tennis_abstract', help='CSV format')
    parser.add_argument('--year', type=int, help='Filter by year')
    parser.add_argument('--surface', help='Filter by surface (Hard/Clay/Grass)')
    parser.add_argument('--level', help='Min tournament level (G/M/A/B)')
    parser.add_argument('--db', default='tennis_stats.db', help='Database path')
    parser.add_argument('--player', help='Query player stats')
    parser.add_argument('--h2h', nargs=2, help='Head-to-head query')
    parser.add_argument('--instructions', action='store_true', 
                       help='Show download instructions')
    
    args = parser.parse_args()
    
    if args.instructions:
        download_instructions()
        return
    
    # Initialize importer
    importer = TennisCSVImporter(args.db)
    
    # Import file
    if args.import_file:
        if args.format == 'tennis_abstract':
            importer.import_tennis_abstract(
                args.import_file,
                year_filter=args.year,
                surface_filter=args.surface,
                min_tourney_level=args.level
            )
        else:
            importer.import_custom_csv(args.import_file)
    
    # Query player
    if args.player:
        stats = importer.get_player_stats(args.player)
        if stats:
            print(f"\n{stats['player']} - Last {stats['matches']} matches:")
            for r in stats['records']:
                won = "W" if r['won'] else "L"
                print(f"  {r['match_date']} | {r['tournament_name'][:20]:20} | "
                      f"{r['surface']:5} | {won} | "
                      f"Aces:{r['aces'] or 0:2} DF:{r['double_faults'] or 0:2}")
        else:
            print(f"No data found for {args.player}")
    
    # Query H2H
    if args.h2h:
        h2h = importer.get_head_to_head(args.h2h[0], args.h2h[1])
        print(f"\nHead-to-Head: {args.h2h[0]} vs {args.h2h[1]}")
        print(f"  Total matches: {h2h['matches']}")
        print(f"  {args.h2h[0]}: {h2h['p1_wins']} wins")
        print(f"  {args.h2h[1]}: {h2h['p2_wins']} wins")
    
    # If no action specified, show help
    if not any([args.import_file, args.player, args.h2h]):
        download_instructions()
        print("\nUsage examples:")
        print("  python tennis_csv_importer.py --import atp_matches_2024.csv")
        print("  python tennis_csv_importer.py --player 'Djokovic' --db tennis_stats.db")
        print("  python tennis_csv_importer.py --h2h 'Djokovic' 'Alcaraz'")
    
    importer.close()


if __name__ == "__main__":
    main()
