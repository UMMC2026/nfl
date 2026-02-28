"""
SOCCER PLAYER STATS — SQLite Database

Like Tennis, stores player stats in SQLite for easy updates and queries.
Replaces the hardcoded KNOWN_PLAYERS dict approach.

Usage:
    from soccer.data.soccer_stats_db import SoccerStatsDB
    
    db = SoccerStatsDB()
    stats = db.get_player("Bernardo Silva")
    db.update_player("Bernardo Silva", {"shots": 2.5, "games_played": 22})
"""

import sqlite3
import json
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass

# Database path
DB_PATH = Path(__file__).parent / "soccer_stats.db"


@dataclass
class PlayerStats:
    """Player statistics container - matches existing format."""
    name: str
    team: str
    position: str
    league: str
    games_played: int
    shots: float = 0.0
    shots_on_target: float = 0.0
    goals: float = 0.0
    assists: float = 0.0
    xg: float = 0.0
    xa: float = 0.0
    passes: float = 0.0
    passes_completed: float = 0.0
    key_passes: float = 0.0
    crosses: float = 0.0
    dribbles: float = 0.0
    tackles: float = 0.0
    interceptions: float = 0.0
    clearances: float = 0.0
    blocks: float = 0.0
    saves: float = 0.0
    clean_sheet_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for edge generation."""
        return {
            "name": self.name,
            "team": self.team,
            "position": self.position,
            "league": self.league,
            "games_played": self.games_played,
            "shots": {"avg": self.shots, "std": self.shots * 0.4},
            "shots_on_target": {"avg": self.shots_on_target, "std": self.shots_on_target * 0.5},
            "goals": {"avg": self.goals, "std": self.goals * 0.8},
            "assists": {"avg": self.assists, "std": self.assists * 0.9},
            "passes": {"avg": self.passes, "std": self.passes * 0.15},
            "passes_completed": {"avg": self.passes_completed, "std": self.passes_completed * 0.15},
            "tackles": {"avg": self.tackles, "std": self.tackles * 0.5},
            "interceptions": {"avg": self.interceptions, "std": self.interceptions * 0.6},
            "clearances": {"avg": self.clearances, "std": self.clearances * 0.5},
            "saves": {"avg": self.saves, "std": self.saves * 0.4},
        }


class SoccerStatsDB:
    """SQLite database for soccer player stats."""
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                name_key TEXT UNIQUE NOT NULL,
                team TEXT,
                position TEXT,
                league TEXT DEFAULT 'premier_league',
                games_played INTEGER DEFAULT 0,
                shots REAL DEFAULT 0.0,
                shots_on_target REAL DEFAULT 0.0,
                goals REAL DEFAULT 0.0,
                assists REAL DEFAULT 0.0,
                xg REAL DEFAULT 0.0,
                xa REAL DEFAULT 0.0,
                passes REAL DEFAULT 0.0,
                passes_completed REAL DEFAULT 0.0,
                key_passes REAL DEFAULT 0.0,
                crosses REAL DEFAULT 0.0,
                dribbles REAL DEFAULT 0.0,
                tackles REAL DEFAULT 0.0,
                interceptions REAL DEFAULT 0.0,
                clearances REAL DEFAULT 0.0,
                blocks REAL DEFAULT 0.0,
                saves REAL DEFAULT 0.0,
                clean_sheet_rate REAL DEFAULT 0.0,
                updated_at TEXT,
                source TEXT DEFAULT 'manual'
            )
        """)
        
        # Index for fast lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_key ON players(name_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_team ON players(team)")
        
        conn.commit()
        conn.close()
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for lookup (lowercase, no accents)."""
        import unicodedata
        normalized = unicodedata.normalize('NFD', name.lower().strip())
        return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    def get_player(self, name: str) -> Optional[PlayerStats]:
        """Get player stats by name."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        name_key = self._normalize_name(name)
        
        # Try exact match first
        cursor.execute("SELECT * FROM players WHERE name_key = ?", (name_key,))
        row = cursor.fetchone()
        
        # Try partial match if not found
        if not row:
            cursor.execute(
                "SELECT * FROM players WHERE name_key LIKE ? OR name LIKE ?",
                (f"%{name_key}%", f"%{name}%")
            )
            row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return PlayerStats(
                name=row['name'],
                team=row['team'] or '',
                position=row['position'] or '',
                league=row['league'] or 'premier_league',
                games_played=row['games_played'] or 0,
                shots=row['shots'] or 0.0,
                shots_on_target=row['shots_on_target'] or 0.0,
                goals=row['goals'] or 0.0,
                assists=row['assists'] or 0.0,
                xg=row['xg'] or 0.0,
                xa=row['xa'] or 0.0,
                passes=row['passes'] or 0.0,
                passes_completed=row['passes_completed'] or 0.0,
                key_passes=row['key_passes'] or 0.0,
                crosses=row['crosses'] or 0.0,
                dribbles=row['dribbles'] or 0.0,
                tackles=row['tackles'] or 0.0,
                interceptions=row['interceptions'] or 0.0,
                clearances=row['clearances'] or 0.0,
                blocks=row['blocks'] or 0.0,
                saves=row['saves'] or 0.0,
                clean_sheet_rate=row['clean_sheet_rate'] or 0.0,
            )
        return None
    
    def update_player(self, name: str, stats: Dict[str, Any], source: str = "manual") -> bool:
        """Insert or update player stats."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        name_key = self._normalize_name(name)
        now = datetime.now().isoformat()
        
        # Check if exists
        cursor.execute("SELECT id FROM players WHERE name_key = ?", (name_key,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            updates = []
            values = []
            for key, val in stats.items():
                if key not in ('name', 'name_key'):
                    updates.append(f"{key} = ?")
                    values.append(val)
            
            updates.append("updated_at = ?")
            values.append(now)
            updates.append("source = ?")
            values.append(source)
            values.append(name_key)
            
            cursor.execute(
                f"UPDATE players SET {', '.join(updates)} WHERE name_key = ?",
                values
            )
        else:
            # Insert new
            stats['name'] = name
            stats['name_key'] = name_key
            stats['updated_at'] = now
            stats['source'] = source
            
            columns = list(stats.keys())
            placeholders = ['?' for _ in columns]
            values = [stats[c] for c in columns]
            
            cursor.execute(
                f"INSERT INTO players ({', '.join(columns)}) VALUES ({', '.join(placeholders)})",
                values
            )
        
        conn.commit()
        conn.close()
        return True
    
    def get_all_players(self) -> Dict[str, PlayerStats]:
        """Get all players as dict (compatible with KNOWN_PLAYERS format)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM players")
        rows = cursor.fetchall()
        conn.close()
        
        players = {}
        for row in rows:
            name_key = row['name_key']
            players[name_key] = PlayerStats(
                name=row['name'],
                team=row['team'] or '',
                position=row['position'] or '',
                league=row['league'] or 'premier_league',
                games_played=row['games_played'] or 0,
                shots=row['shots'] or 0.0,
                shots_on_target=row['shots_on_target'] or 0.0,
                goals=row['goals'] or 0.0,
                assists=row['assists'] or 0.0,
                xg=row['xg'] or 0.0,
                xa=row['xa'] or 0.0,
                passes=row['passes'] or 0.0,
                passes_completed=row['passes_completed'] or 0.0,
                key_passes=row['key_passes'] or 0.0,
                crosses=row['crosses'] or 0.0,
                dribbles=row['dribbles'] or 0.0,
                tackles=row['tackles'] or 0.0,
                interceptions=row['interceptions'] or 0.0,
                clearances=row['clearances'] or 0.0,
                blocks=row['blocks'] or 0.0,
                saves=row['saves'] or 0.0,
                clean_sheet_rate=row['clean_sheet_rate'] or 0.0,
            )
        
        return players
    
    def count(self) -> int:
        """Count total players in database."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM players")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def search(self, query: str, limit: int = 10) -> List[PlayerStats]:
        """Search for players by name."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        q = f"%{query.lower()}%"
        cursor.execute(
            "SELECT * FROM players WHERE name_key LIKE ? OR name LIKE ? LIMIT ?",
            (q, q, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [
            PlayerStats(
                name=row['name'],
                team=row['team'] or '',
                position=row['position'] or '',
                league=row['league'] or 'premier_league',
                games_played=row['games_played'] or 0,
                shots=row['shots'] or 0.0,
                shots_on_target=row['shots_on_target'] or 0.0,
                goals=row['goals'] or 0.0,
                assists=row['assists'] or 0.0,
                xg=row['xg'] or 0.0,
                xa=row['xa'] or 0.0,
                passes=row['passes'] or 0.0,
                passes_completed=row['passes_completed'] or 0.0,
                key_passes=row['key_passes'] or 0.0,
                crosses=row['crosses'] or 0.0,
                dribbles=row['dribbles'] or 0.0,
                tackles=row['tackles'] or 0.0,
                interceptions=row['interceptions'] or 0.0,
                clearances=row['clearances'] or 0.0,
                blocks=row['blocks'] or 0.0,
                saves=row['saves'] or 0.0,
                clean_sheet_rate=row['clean_sheet_rate'] or 0.0,
            )
            for row in rows
        ]
    
    def import_from_dict(self, players_dict: Dict[str, Any]) -> int:
        """Import players from KNOWN_PLAYERS dict format."""
        count = 0
        for name_key, player in players_dict.items():
            if hasattr(player, '__dict__'):
                # It's a PlayerStats dataclass
                stats = {
                    'team': player.team,
                    'position': player.position,
                    'league': player.league,
                    'games_played': player.games_played,
                    'shots': player.shots,
                    'shots_on_target': player.shots_on_target,
                    'goals': player.goals,
                    'assists': player.assists,
                    'xg': player.xg,
                    'xa': player.xa,
                    'passes': player.passes,
                    'passes_completed': player.passes_completed,
                    'key_passes': player.key_passes,
                    'crosses': player.crosses,
                    'dribbles': player.dribbles,
                    'tackles': player.tackles,
                    'interceptions': player.interceptions,
                    'clearances': player.clearances,
                    'blocks': player.blocks,
                    'saves': player.saves,
                    'clean_sheet_rate': player.clean_sheet_rate,
                }
                self.update_player(player.name, stats, source="import")
                count += 1
        return count


def import_existing_database():
    """Import all players from the existing KNOWN_PLAYERS dict."""
    from soccer.data.player_database import KNOWN_PLAYERS
    
    db = SoccerStatsDB()
    print(f"📥 Importing {len(KNOWN_PLAYERS)} players from KNOWN_PLAYERS...")
    
    count = db.import_from_dict(KNOWN_PLAYERS)
    
    print(f"✅ Imported {count} players to {db.db_path}")
    print(f"   Database now has {db.count()} players")
    return count


# Compatibility layer - load from SQLite into KNOWN_PLAYERS format
def load_known_players() -> Dict[str, PlayerStats]:
    """Load all players from SQLite (drop-in replacement for KNOWN_PLAYERS)."""
    db = SoccerStatsDB()
    if db.count() == 0:
        # First run - import from existing dict
        import_existing_database()
    return db.get_all_players()


if __name__ == "__main__":
    import sys
    
    if "--import" in sys.argv:
        import_existing_database()
    elif "--count" in sys.argv:
        db = SoccerStatsDB()
        print(f"Players in database: {db.count()}")
    elif "--search" in sys.argv and len(sys.argv) > 2:
        db = SoccerStatsDB()
        query = sys.argv[sys.argv.index("--search") + 1]
        results = db.search(query)
        for p in results:
            print(f"  {p.name} ({p.team}) - {p.games_played} GP, {p.shots} shots/gm")
    else:
        print("Usage:")
        print("  --import    Import from KNOWN_PLAYERS dict")
        print("  --count     Show player count")
        print("  --search <name>  Search for player")
