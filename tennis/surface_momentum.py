"""
TENNIS SURFACE MOMENTUM TRACKING — Phase 5B Enhancement
=========================================================

Tracks player performance on specific surfaces and applies adjustments:
- Strong surface specialist: +3-5% confidence boost
- Weak on surface: -3-5% confidence penalty
- Clay specialists on clay get biggest boost (Nadal effect)

Data Sources:
- ATP/WTA match history by surface
- Last 10-20 matches on each surface
- Win rate, games won percentage, break point conversion

Usage:
    from tennis.surface_momentum import get_surface_adjustment, get_player_surface_stats
    
    adjustment = get_surface_adjustment("Rafael Nadal", "CLAY")
    # Returns: +0.05 (5% boost)

Created: 2026-02-05
Phase: 5B Week 3-4
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

TENNIS_DIR = Path(__file__).parent
SURFACE_STATS_PATH = TENNIS_DIR / "data" / "surface_stats.json"


class Surface(Enum):
    HARD = "hard"
    CLAY = "clay"
    GRASS = "grass"
    INDOOR = "indoor"  # Treated as hard for most purposes


@dataclass
class SurfaceStats:
    """Player stats on a specific surface."""
    player: str
    surface: str
    matches_played: int = 0
    matches_won: int = 0
    sets_played: int = 0
    sets_won: int = 0
    games_played: int = 0
    games_won: int = 0
    last_updated: Optional[str] = None
    
    @property
    def win_rate(self) -> float:
        if self.matches_played == 0:
            return 0.5
        return self.matches_won / self.matches_played
    
    @property
    def set_win_rate(self) -> float:
        if self.sets_played == 0:
            return 0.5
        return self.sets_won / self.sets_played
    
    @property
    def game_win_rate(self) -> float:
        if self.games_played == 0:
            return 0.5
        return self.games_won / self.games_played


@dataclass  
class SurfaceMomentum:
    """Player's recent form on a surface."""
    player: str
    surface: str
    last_5_results: List[str] = field(default_factory=list)  # ["W", "L", "W", "W", "L"]
    recent_win_rate: float = 0.5
    momentum_score: float = 0.0  # -1.0 to +1.0
    adjustment: float = 0.0  # Confidence adjustment to apply


# =============================================================================
# SURFACE SPECIALIST THRESHOLDS
# =============================================================================

# Win rate thresholds for surface specialist classification
SURFACE_SPECIALIST_THRESHOLDS = {
    "DOMINANT": 0.75,    # 75%+ win rate = dominant specialist (+5%)
    "STRONG": 0.65,      # 65-74% = strong on surface (+3%)
    "AVERAGE": 0.50,     # 50-64% = average (no adjustment)
    "WEAK": 0.40,        # 40-49% = weak on surface (-3%)
    "STRUGGLE": 0.30,    # <40% = struggles on surface (-5%)
}

# Adjustment values by specialist level
SURFACE_ADJUSTMENTS = {
    "DOMINANT": 0.05,    # +5% confidence
    "STRONG": 0.03,      # +3% confidence
    "AVERAGE": 0.0,      # No adjustment
    "WEAK": -0.03,       # -3% confidence
    "STRUGGLE": -0.05,   # -5% confidence
}

# Known surface specialists (manual overrides for elite players)
# Format: {"player_name": {"clay": adjustment, "hard": adjustment, "grass": adjustment}}
KNOWN_SPECIALISTS: Dict[str, Dict[str, float]] = {
    # Clay Court Specialists
    "rafael nadal": {"clay": 0.08, "hard": 0.0, "grass": -0.02},
    "carlos alcaraz": {"clay": 0.04, "hard": 0.03, "grass": 0.02},
    "casper ruud": {"clay": 0.05, "hard": -0.02, "grass": -0.03},
    "stefanos tsitsipas": {"clay": 0.04, "hard": 0.0, "grass": -0.02},
    
    # Hard Court Specialists  
    "novak djokovic": {"clay": 0.03, "hard": 0.04, "grass": 0.03},
    "daniil medvedev": {"clay": -0.03, "hard": 0.05, "grass": -0.02},
    "jannik sinner": {"clay": 0.02, "hard": 0.04, "grass": 0.02},
    
    # Grass Court Specialists
    "jack draper": {"clay": -0.02, "hard": 0.02, "grass": 0.05},
    
    # WTA Specialists
    "iga swiatek": {"clay": 0.07, "hard": 0.03, "grass": 0.0},
    "aryna sabalenka": {"clay": 0.02, "hard": 0.04, "grass": 0.0},
}


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.lower().strip().replace("-", " ").replace("'", "")


def normalize_surface(surface: str) -> str:
    """Normalize surface name."""
    s = surface.lower().strip()
    if s in ("hard", "hardcourt", "hard court", "outdoor hard"):
        return "hard"
    if s in ("clay", "red clay", "terre battue"):
        return "clay"
    if s in ("grass", "lawn"):
        return "grass"
    if s in ("indoor", "indoor hard", "carpet"):
        return "hard"  # Treat indoor as hard
    return "hard"  # Default


def load_surface_stats() -> Dict[str, Dict[str, SurfaceStats]]:
    """Load surface stats database."""
    if SURFACE_STATS_PATH.exists():
        try:
            with open(SURFACE_STATS_PATH, encoding="utf-8") as f:
                data = json.load(f)
                # Convert to SurfaceStats objects
                result = {}
                for player, surfaces in data.items():
                    if player.startswith("_"):
                        continue
                    result[player] = {}
                    for surf, stats in surfaces.items():
                        result[player][surf] = SurfaceStats(
                            player=player,
                            surface=surf,
                            matches_played=stats.get("matches_played", 0),
                            matches_won=stats.get("matches_won", 0),
                            sets_played=stats.get("sets_played", 0),
                            sets_won=stats.get("sets_won", 0),
                            games_played=stats.get("games_played", 0),
                            games_won=stats.get("games_won", 0),
                            last_updated=stats.get("last_updated"),
                        )
                return result
        except Exception as e:
            print(f"[SURFACE_MOMENTUM] Warning: Could not load surface stats: {e}")
    return {}


def save_surface_stats(data: Dict[str, Dict[str, SurfaceStats]]) -> None:
    """Save surface stats to database."""
    SURFACE_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable format
    output = {
        "_metadata": {
            "last_updated": datetime.now().isoformat(),
            "description": "Tennis player surface performance stats"
        }
    }
    
    for player, surfaces in data.items():
        output[player] = {}
        for surf, stats in surfaces.items():
            output[player][surf] = {
                "matches_played": stats.matches_played,
                "matches_won": stats.matches_won,
                "sets_played": stats.sets_played,
                "sets_won": stats.sets_won,
                "games_played": stats.games_played,
                "games_won": stats.games_won,
                "last_updated": stats.last_updated,
            }
    
    with open(SURFACE_STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


def get_specialist_level(win_rate: float) -> str:
    """Determine specialist level from win rate."""
    if win_rate >= SURFACE_SPECIALIST_THRESHOLDS["DOMINANT"]:
        return "DOMINANT"
    elif win_rate >= SURFACE_SPECIALIST_THRESHOLDS["STRONG"]:
        return "STRONG"
    elif win_rate >= SURFACE_SPECIALIST_THRESHOLDS["AVERAGE"]:
        return "AVERAGE"
    elif win_rate >= SURFACE_SPECIALIST_THRESHOLDS["WEAK"]:
        return "WEAK"
    else:
        return "STRUGGLE"


def get_player_surface_stats(player_name: str, surface: str) -> Optional[SurfaceStats]:
    """
    Get a player's stats on a specific surface.
    
    Args:
        player_name: Player's full name
        surface: Surface type (hard, clay, grass)
    
    Returns:
        SurfaceStats if available, None otherwise
    """
    normalized_player = normalize_player_name(player_name)
    normalized_surface = normalize_surface(surface)
    
    db = load_surface_stats()
    
    for db_player, surfaces in db.items():
        if normalize_player_name(db_player) == normalized_player:
            if normalized_surface in surfaces:
                return surfaces[normalized_surface]
    
    return None


def get_surface_adjustment(player_name: str, surface: str) -> Tuple[float, Dict]:
    """
    Get confidence adjustment based on player's surface performance.
    
    Args:
        player_name: Player's full name
        surface: Surface type (hard, clay, grass)
    
    Returns:
        Tuple of (adjustment, info_dict)
        adjustment: -0.05 to +0.08 (percentage points)
    """
    normalized_player = normalize_player_name(player_name)
    normalized_surface = normalize_surface(surface)
    
    info = {
        "player": player_name,
        "surface": normalized_surface,
        "adjustment": 0.0,
        "source": "default",
        "specialist_level": "AVERAGE",
    }
    
    # Check known specialists first (manual overrides)
    if normalized_player in KNOWN_SPECIALISTS:
        specialist_adj = KNOWN_SPECIALISTS[normalized_player].get(normalized_surface, 0.0)
        if specialist_adj != 0.0:
            info["adjustment"] = specialist_adj
            info["source"] = "known_specialist"
            info["specialist_level"] = "DOMINANT" if specialist_adj > 0.04 else "STRONG" if specialist_adj > 0 else "WEAK"
            return specialist_adj, info
    
    # Check stats database
    stats = get_player_surface_stats(player_name, surface)
    
    if stats and stats.matches_played >= 10:
        # Enough data to calculate
        win_rate = stats.win_rate
        level = get_specialist_level(win_rate)
        adjustment = SURFACE_ADJUSTMENTS[level]
        
        info["adjustment"] = adjustment
        info["source"] = "stats_database"
        info["specialist_level"] = level
        info["win_rate"] = round(win_rate, 3)
        info["matches_played"] = stats.matches_played
        
        return adjustment, info
    
    # Not enough data - no adjustment
    info["source"] = "insufficient_data"
    return 0.0, info


def apply_surface_momentum(
    raw_probability: float,
    player_a: str,
    player_b: str,
    surface: str,
) -> Tuple[float, Dict]:
    """
    Apply surface momentum adjustments to probability.
    
    For Total Games markets, we adjust based on BOTH players' surface form.
    
    Args:
        raw_probability: Original probability
        player_a: First player
        player_b: Second player  
        surface: Surface type
    
    Returns:
        Tuple of (adjusted_probability, adjustment_info)
    """
    adj_a, info_a = get_surface_adjustment(player_a, surface)
    adj_b, info_b = get_surface_adjustment(player_b, surface)
    
    # Net adjustment: if one player is strong and other weak, market moves
    # For OVER/UNDER games, surface specialists tend to extend matches
    # A dominant player shortens matches (fewer games)
    
    # Simple approach: average the magnitudes
    net_adj = (adj_a + adj_b) / 2
    
    adjusted_prob = raw_probability + net_adj
    adjusted_prob = max(0.40, min(0.85, adjusted_prob))  # Clamp
    
    info = {
        "player_a": {
            "name": player_a,
            "adjustment": adj_a,
            "level": info_a.get("specialist_level"),
        },
        "player_b": {
            "name": player_b,
            "adjustment": adj_b,
            "level": info_b.get("specialist_level"),
        },
        "surface": surface,
        "net_adjustment": net_adj,
        "adjustment_applied": abs(net_adj) > 0.01,
    }
    
    return adjusted_prob, info


# =============================================================================
# DATA INGESTION (from Sackmann data or ATP API)
# =============================================================================

def ingest_from_match_history(matches: List[Dict]) -> None:
    """
    Ingest surface stats from match history.
    
    Args:
        matches: List of match dicts with keys:
            - winner_name, loser_name
            - surface
            - winner_games, loser_games (optional)
            - winner_sets, loser_sets (optional)
    """
    db = load_surface_stats()
    
    for match in matches:
        winner = match.get("winner_name", "")
        loser = match.get("loser_name", "")
        surface = normalize_surface(match.get("surface", "hard"))
        
        for player, won in [(winner, True), (loser, False)]:
            if not player:
                continue
                
            normalized = normalize_player_name(player)
            
            if normalized not in db:
                db[normalized] = {}
            if surface not in db[normalized]:
                db[normalized][surface] = SurfaceStats(player=normalized, surface=surface)
            
            stats = db[normalized][surface]
            stats.matches_played += 1
            if won:
                stats.matches_won += 1
            
            # Update sets/games if available
            if "winner_sets" in match and "loser_sets" in match:
                w_sets = match.get("winner_sets", 0) or 0
                l_sets = match.get("loser_sets", 0) or 0
                if won:
                    stats.sets_won += w_sets
                    stats.sets_played += w_sets + l_sets
                else:
                    stats.sets_won += l_sets
                    stats.sets_played += w_sets + l_sets
            
            stats.last_updated = datetime.now().isoformat()
    
    save_surface_stats(db)
    print(f"[SURFACE_MOMENTUM] Ingested {len(matches)} matches")


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tennis Surface Momentum")
    parser.add_argument("--check", nargs=2, metavar=("PLAYER", "SURFACE"),
                       help="Check player's surface adjustment")
    parser.add_argument("--list-specialists", action="store_true",
                       help="List known surface specialists")
    
    args = parser.parse_args()
    
    if args.check:
        player, surface = args.check
        adj, info = get_surface_adjustment(player, surface)
        print(f"\n=== Surface Check: {player} on {surface} ===")
        print(f"  Adjustment: {adj:+.1%}")
        print(f"  Specialist Level: {info.get('specialist_level')}")
        print(f"  Source: {info.get('source')}")
        if 'win_rate' in info:
            print(f"  Win Rate: {info['win_rate']:.1%}")
            print(f"  Matches Played: {info['matches_played']}")
    
    elif args.list_specialists:
        print("\n=== Known Surface Specialists ===")
        for player, adjustments in sorted(KNOWN_SPECIALISTS.items()):
            print(f"\n  {player.title()}:")
            for surf, adj in adjustments.items():
                emoji = "🔥" if adj > 0.04 else "✅" if adj > 0 else "⚠️" if adj < 0 else "➖"
                print(f"    {emoji} {surf}: {adj:+.0%}")
    
    else:
        parser.print_help()
