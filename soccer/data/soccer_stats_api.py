"""soccer/data/soccer_stats_api.py

Soccer Player Stats Data Layer
==============================
Manual-input stats for Monte Carlo simulations.

NO SCRAPING - Stats are provided by user via:
- JSON input files
- Interactive prompts
- CSV imports

Stats needed for soccer props:
- Tackles (L5, L10, season)
- Clearances
- Shots / Shots on Target
- Goals / Assists
- Goalie Saves
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import json
from datetime import datetime


@dataclass
class SoccerPlayerStats:
    """Player statistics for Monte Carlo modeling."""
    
    player: str
    team: str
    position: str = "Unknown"  # Goalkeeper, Defender, Midfielder, Attacker
    
    # Tackles (L5, L10, season averages + std)
    tackles_l5: float = 0.0
    tackles_l10: float = 0.0
    tackles_season: float = 0.0
    tackles_std: float = 0.5
    
    # Clearances
    clearances_l5: float = 0.0
    clearances_l10: float = 0.0
    clearances_season: float = 0.0
    clearances_std: float = 0.8
    
    # Shots
    shots_l5: float = 0.0
    shots_l10: float = 0.0
    shots_season: float = 0.0
    shots_std: float = 0.8
    
    # Shots on Target
    sot_l5: float = 0.0
    sot_l10: float = 0.0
    sot_season: float = 0.0
    sot_std: float = 0.5
    
    # Goals
    goals_l5: float = 0.0
    goals_l10: float = 0.0
    goals_season: float = 0.0
    goals_std: float = 0.3
    
    # Assists
    assists_l5: float = 0.0
    assists_l10: float = 0.0
    assists_season: float = 0.0
    assists_std: float = 0.25
    
    # Shots Assisted (key passes leading to shots)
    shots_assisted_l5: float = 0.0
    shots_assisted_l10: float = 0.0
    shots_assisted_season: float = 0.0
    shots_assisted_std: float = 0.5
    
    # Goalie Saves (for GK only)
    saves_l5: float = 0.0
    saves_l10: float = 0.0
    saves_season: float = 0.0
    saves_std: float = 1.2
    
    # Metadata
    matches_played: int = 0
    league: str = ""
    last_updated: str = ""


class SoccerStatsStore:
    """
    Manual stats storage for soccer players.
    
    No API scraping - all data comes from:
    1. User-provided JSON files
    2. Interactive CLI input
    3. CSV imports
    """
    
    def __init__(self):
        self.cache_dir = Path(__file__).parent / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "player_stats_cache.json"
        self._cache: Dict[str, SoccerPlayerStats] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached stats from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file) as f:
                    data = json.load(f)
                for key, vals in data.items():
                    self._cache[key] = SoccerPlayerStats(**vals)
            except Exception:
                self._cache = {}
    
    def _save_cache(self):
        """Persist cache to disk."""
        data = {}
        for key, stats in self._cache.items():
            data[key] = {
                "player": stats.player,
                "team": stats.team,
                "position": stats.position,
                "tackles_l5": stats.tackles_l5,
                "tackles_l10": stats.tackles_l10,
                "tackles_season": stats.tackles_season,
                "tackles_std": stats.tackles_std,
                "clearances_l5": stats.clearances_l5,
                "clearances_l10": stats.clearances_l10,
                "clearances_season": stats.clearances_season,
                "clearances_std": stats.clearances_std,
                "shots_l5": stats.shots_l5,
                "shots_l10": stats.shots_l10,
                "shots_season": stats.shots_season,
                "shots_std": stats.shots_std,
                "sot_l5": stats.sot_l5,
                "sot_l10": stats.sot_l10,
                "sot_season": stats.sot_season,
                "sot_std": stats.sot_std,
                "goals_l5": stats.goals_l5,
                "goals_l10": stats.goals_l10,
                "goals_season": stats.goals_season,
                "goals_std": stats.goals_std,
                "assists_l5": stats.assists_l5,
                "assists_l10": stats.assists_l10,
                "assists_season": stats.assists_season,
                "assists_std": stats.assists_std,
                "shots_assisted_l5": stats.shots_assisted_l5,
                "shots_assisted_l10": stats.shots_assisted_l10,
                "shots_assisted_season": stats.shots_assisted_season,
                "shots_assisted_std": stats.shots_assisted_std,
                "saves_l5": stats.saves_l5,
                "saves_l10": stats.saves_l10,
                "saves_season": stats.saves_season,
                "saves_std": stats.saves_std,
                "matches_played": stats.matches_played,
                "league": stats.league,
                "last_updated": stats.last_updated,
            }
        with open(self.cache_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def _normalize_key(self, player: str, team: str) -> str:
        """Create consistent lookup key."""
        return f"{player.lower().strip()}|{team.lower().strip()}"
    
    def get_player_stats(self, player: str, team: str) -> Optional[SoccerPlayerStats]:
        """Retrieve cached stats for a player."""
        key = self._normalize_key(player, team)
        return self._cache.get(key)
    
    def set_player_stats(self, stats: SoccerPlayerStats):
        """Store/update player stats in cache."""
        key = self._normalize_key(stats.player, stats.team)
        stats.last_updated = datetime.utcnow().isoformat()
        self._cache[key] = stats
        self._save_cache()
    
    def bulk_import_json(self, filepath: str) -> int:
        """
        Import player stats from a JSON file.
        
        Expected format:
        {
            "players": [
                {
                    "player": "Yassine Benzia",
                    "team": "Fayha",
                    "position": "Midfielder",
                    "tackles_l5": 2.4,
                    "tackles_l10": 2.1,
                    ...
                }
            ]
        }
        
        Returns:
            Number of players imported
        """
        with open(filepath) as f:
            data = json.load(f)
        
        count = 0
        for p in data.get("players", []):
            stats = SoccerPlayerStats(
                player=p.get("player", ""),
                team=p.get("team", ""),
                position=p.get("position", "Unknown"),
                tackles_l5=float(p.get("tackles_l5", 0)),
                tackles_l10=float(p.get("tackles_l10", 0)),
                tackles_season=float(p.get("tackles_season", 0)),
                tackles_std=float(p.get("tackles_std", 0.5)),
                clearances_l5=float(p.get("clearances_l5", 0)),
                clearances_l10=float(p.get("clearances_l10", 0)),
                clearances_season=float(p.get("clearances_season", 0)),
                clearances_std=float(p.get("clearances_std", 0.8)),
                shots_l5=float(p.get("shots_l5", 0)),
                shots_l10=float(p.get("shots_l10", 0)),
                shots_season=float(p.get("shots_season", 0)),
                shots_std=float(p.get("shots_std", 0.8)),
                sot_l5=float(p.get("sot_l5", 0)),
                sot_l10=float(p.get("sot_l10", 0)),
                sot_season=float(p.get("sot_season", 0)),
                sot_std=float(p.get("sot_std", 0.5)),
                goals_l5=float(p.get("goals_l5", 0)),
                goals_l10=float(p.get("goals_l10", 0)),
                goals_season=float(p.get("goals_season", 0)),
                goals_std=float(p.get("goals_std", 0.3)),
                assists_l5=float(p.get("assists_l5", 0)),
                assists_l10=float(p.get("assists_l10", 0)),
                assists_season=float(p.get("assists_season", 0)),
                assists_std=float(p.get("assists_std", 0.25)),
                shots_assisted_l5=float(p.get("shots_assisted_l5", 0)),
                shots_assisted_l10=float(p.get("shots_assisted_l10", 0)),
                shots_assisted_season=float(p.get("shots_assisted_season", 0)),
                shots_assisted_std=float(p.get("shots_assisted_std", 0.5)),
                saves_l5=float(p.get("saves_l5", 0)),
                saves_l10=float(p.get("saves_l10", 0)),
                saves_season=float(p.get("saves_season", 0)),
                saves_std=float(p.get("saves_std", 1.2)),
                matches_played=int(p.get("matches_played", 0)),
                league=p.get("league", ""),
            )
            self.set_player_stats(stats)
            count += 1
        
        return count
    
    def list_cached_players(self) -> List[str]:
        """Return list of cached player names."""
        return [s.player for s in self._cache.values()]
    
    def interactive_input(self, player: str, team: str, position: str, stat_type: str) -> SoccerPlayerStats:
        """
        Interactively prompt user for player stats.
        
        Args:
            player: Player name
            team: Team name
            position: Position (Goalkeeper, Defender, etc.)
            stat_type: Which stat to focus on (tackles, shots, saves, etc.)
        
        Returns:
            SoccerPlayerStats populated with user input
        """
        existing = self.get_player_stats(player, team)
        if existing:
            stats = existing
        else:
            stats = SoccerPlayerStats(player=player, team=team, position=position)
        
        print(f"\n--- Enter stats for {player} ({team}) ---")
        print(f"Stat focus: {stat_type}")
        print("Enter values or press Enter to keep defaults.\n")
        
        def get_float(prompt: str, default: float) -> float:
            val = input(f"{prompt} [{default}]: ").strip()
            if not val:
                return default
            try:
                return float(val)
            except ValueError:
                return default
        
        if stat_type in ("tackles",):
            stats.tackles_l5 = get_float("Tackles L5 avg", stats.tackles_l5)
            stats.tackles_l10 = get_float("Tackles L10 avg", stats.tackles_l10)
            stats.tackles_std = get_float("Tackles std dev", stats.tackles_std)
        
        elif stat_type in ("clearances",):
            stats.clearances_l5 = get_float("Clearances L5 avg", stats.clearances_l5)
            stats.clearances_l10 = get_float("Clearances L10 avg", stats.clearances_l10)
            stats.clearances_std = get_float("Clearances std dev", stats.clearances_std)
        
        elif stat_type in ("shots",):
            stats.shots_l5 = get_float("Shots L5 avg", stats.shots_l5)
            stats.shots_l10 = get_float("Shots L10 avg", stats.shots_l10)
            stats.shots_std = get_float("Shots std dev", stats.shots_std)
        
        elif stat_type in ("shots_on_target", "sot"):
            stats.sot_l5 = get_float("SOT L5 avg", stats.sot_l5)
            stats.sot_l10 = get_float("SOT L10 avg", stats.sot_l10)
            stats.sot_std = get_float("SOT std dev", stats.sot_std)
        
        elif stat_type in ("goals",):
            stats.goals_l5 = get_float("Goals L5 avg", stats.goals_l5)
            stats.goals_l10 = get_float("Goals L10 avg", stats.goals_l10)
            stats.goals_std = get_float("Goals std dev", stats.goals_std)
        
        elif stat_type in ("goalie_saves", "saves"):
            stats.saves_l5 = get_float("Saves L5 avg", stats.saves_l5)
            stats.saves_l10 = get_float("Saves L10 avg", stats.saves_l10)
            stats.saves_std = get_float("Saves std dev", stats.saves_std)
        
        elif stat_type in ("shots_assisted",):
            stats.shots_assisted_l5 = get_float("Shots Assisted L5 avg", stats.shots_assisted_l5)
            stats.shots_assisted_l10 = get_float("Shots Assisted L10 avg", stats.shots_assisted_l10)
            stats.shots_assisted_std = get_float("Shots Assisted std dev", stats.shots_assisted_std)
        
        stats.matches_played = int(get_float("Matches played (sample size)", stats.matches_played))
        
        self.set_player_stats(stats)
        return stats


# Singleton instance
_store: Optional[SoccerStatsStore] = None


def get_soccer_stats_store() -> SoccerStatsStore:
    """Get singleton stats store."""
    global _store
    if _store is None:
        _store = SoccerStatsStore()
    return _store
