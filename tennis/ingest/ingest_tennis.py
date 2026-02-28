"""
TENNIS INGEST — Data Collection Layer
=====================================
Loads player stats, Elo ratings, and match context.
No external scraping. Manual/permitted sources only.

Output: Structured data for downstream engines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

TENNIS_DIR = Path(__file__).parent.parent
CONFIG_DIR = TENNIS_DIR / "config"
DATA_DIR = TENNIS_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


@dataclass
class PlayerStats:
    name: str
    tour: str  # ATP | WTA
    ranking: Optional[int] = None
    elo_hard: float = 1500.0
    elo_clay: float = 1500.0
    elo_grass: float = 1500.0
    elo_indoor: float = 1500.0
    hold_pct_hard: float = 0.80
    hold_pct_clay: float = 0.78
    hold_pct_grass: float = 0.82
    hold_pct_indoor: float = 0.81
    break_pct: float = 0.22
    tiebreak_rate: float = 0.22
    straight_set_pct: float = 0.60
    aces_per_service_game: float = 0.5
    return_pts_won: float = 0.38
    ace_pct: float = 0.07           # Aces as % of serve points
    first_serve_pct: float = 0.62   # First serve in %
    return_rating: float = 100.0    # Return pressure rating
    surface_win_pct: Dict[str, float] = field(default_factory=dict)  # Win % by surface
    
    # NEW: Rolling window stats (L10 = last 10 matches)
    ace_pct_L10: Optional[float] = None
    first_serve_pct_L10: Optional[float] = None
    hold_pct_L10: Optional[float] = None
    win_pct_L10: Optional[float] = None
    straight_set_pct_L10: Optional[float] = None
    surface_form_L10: Dict[str, float] = field(default_factory=dict)  # Win % by surface L10
    matches_analyzed: int = 0       # Number of recent matches used
    stats_updated: Optional[str] = None  # ISO timestamp of last update
    elo_updated: Optional[str] = None    # ISO timestamp of last Elo update
    
    is_qualifier: bool = False
    retired_last_2: bool = False
    injury_return_days: Optional[int] = None
    matches_last_5_days: int = 0


@dataclass
class MatchContext:
    player_a: str
    player_b: str
    tournament: str
    surface: str
    best_of: int
    date: str
    round: Optional[str] = None


def load_global_config() -> Dict:
    """Load tennis_global.json config."""
    config_path = CONFIG_DIR / "tennis_global.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))
    return {}


def load_player_stats() -> Dict[str, PlayerStats]:
    """
    Load player statistics from data/player_stats.json.
    
    Returns dict keyed by player name (lowercase).
    """
    stats_file = DATA_DIR / "player_stats.json"
    if not stats_file.exists():
        return {}
    
    try:
        raw = json.loads(stats_file.read_text(encoding="utf-8"))
    except Exception:
        return {}
    
    players = {}
    for name, data in raw.items():
        # Support both old format and new nested Elo format
        elo_data = data.get("elo", {})
        surface_wins = data.get("surface_win_pct", {})
        
        # Detect tour from name or data
        tour = data.get("tour", "ATP")
        if any(n.lower() in name.lower() for n in ["rybakina", "osaka", "keys", "gracheva", "krueger", "cirstea"]):
            tour = "WTA"
        
        players[name.lower()] = PlayerStats(
            name=data.get("name", name),
            tour=tour,
            ranking=data.get("ranking", data.get("rank")),
            elo_hard=elo_data.get("HARD", data.get("elo_hard", 1500.0)),
            elo_clay=elo_data.get("CLAY", data.get("elo_clay", 1500.0)),
            elo_grass=elo_data.get("GRASS", data.get("elo_grass", 1500.0)),
            elo_indoor=elo_data.get("INDOOR", data.get("elo_indoor", 1500.0)),
            hold_pct_hard=data.get("hold_pct", data.get("hold_pct_hard", 0.80)),
            hold_pct_clay=data.get("hold_pct_clay", data.get("hold_pct", 0.78)),
            hold_pct_grass=data.get("hold_pct_grass", data.get("hold_pct", 0.82)),
            hold_pct_indoor=data.get("hold_pct_indoor", data.get("hold_pct", 0.81)),
            break_pct=data.get("break_pct", 0.22),
            tiebreak_rate=data.get("tiebreak_rate", 0.22),
            straight_set_pct=data.get("straight_set_pct", 0.60),
            aces_per_service_game=data.get("aces_per_service_game", 0.5),
            return_pts_won=data.get("return_pts_won", 0.38),
            ace_pct=data.get("ace_pct", 0.07),
            first_serve_pct=data.get("first_serve_pct", 0.62),
            return_rating=data.get("return_rating", 100.0),
            surface_win_pct=surface_wins if isinstance(surface_wins, dict) else {},
            
            # Rolling window stats
            ace_pct_L10=data.get("ace_pct_L10"),
            first_serve_pct_L10=data.get("first_serve_pct_L10"),
            hold_pct_L10=data.get("hold_pct_L10"),
            win_pct_L10=data.get("win_pct_L10"),
            straight_set_pct_L10=data.get("straight_set_pct_L10"),
            surface_form_L10=data.get("surface_form_L10", {}),
            matches_analyzed=data.get("matches_analyzed", 0),
            stats_updated=data.get("stats_updated"),
            elo_updated=data.get("elo_updated"),
            
            is_qualifier=data.get("is_qualifier", False),
            retired_last_2=data.get("retired_last_2", False),
            injury_return_days=data.get("injury_return_days"),
            matches_last_5_days=data.get("matches_last_5_days", 0),
        )
    
    return players


def get_player_elo(player: str, surface: str, stats: Dict[str, PlayerStats]) -> float:
    """Get player Elo for a specific surface."""
    p = stats.get(player.lower())
    if not p:
        return 1500.0
    
    elo_map = {
        "HARD": p.elo_hard,
        "CLAY": p.elo_clay,
        "GRASS": p.elo_grass,
        "INDOOR": p.elo_indoor,
    }
    return elo_map.get(surface.upper(), 1500.0)


def get_player_hold_pct(player: str, surface: str, stats: Dict[str, PlayerStats]) -> float:
    """Get player hold % for a specific surface."""
    p = stats.get(player.lower())
    if not p:
        return 0.80
    
    hold_map = {
        "HARD": p.hold_pct_hard,
        "CLAY": p.hold_pct_clay,
        "GRASS": p.hold_pct_grass,
        "INDOOR": p.hold_pct_indoor,
    }
    return hold_map.get(surface.upper(), 0.80)


def check_global_blocks(
    player_a: str,
    player_b: str,
    surface: Optional[str],
    stats: Dict[str, PlayerStats],
    config: Dict,
) -> List[str]:
    """
    Check global block rules.
    
    Returns list of block reasons (empty = passed).
    """
    blocks = config.get("global_blocks", {})
    reasons = []
    
    # Surface unknown
    if blocks.get("surface_unknown") and not surface:
        reasons.append("SURFACE_UNKNOWN")
    
    # Valid surface check
    valid_surfaces = config.get("valid_surfaces", [])
    if surface and surface.upper() not in valid_surfaces:
        reasons.append("INVALID_SURFACE")
    
    # Retirement in last 2
    if blocks.get("retirement_last_2"):
        for p in [player_a, player_b]:
            ps = stats.get(p.lower())
            if ps and ps.retired_last_2:
                reasons.append(f"RETIRED_LAST_2::{p}")
    
    # Injury return
    injury_days = blocks.get("injury_return_days", 14)
    for p in [player_a, player_b]:
        ps = stats.get(p.lower())
        if ps and ps.injury_return_days is not None:
            if ps.injury_return_days <= injury_days:
                reasons.append(f"INJURY_RETURN::{p}::{ps.injury_return_days}d")
    
    # Opponent unknown
    if blocks.get("opponent_unknown"):
        if not player_a or not player_b:
            reasons.append("OPPONENT_UNKNOWN")
    
    return reasons


def ingest_match_list(matches: List[Dict]) -> List[MatchContext]:
    """Convert raw match dicts to MatchContext objects."""
    contexts = []
    for m in matches:
        ctx = MatchContext(
            player_a=m.get("player_a", m.get("player_1", "")),
            player_b=m.get("player_b", m.get("player_2", "")),
            tournament=m.get("tournament", ""),
            surface=m.get("surface", ""),
            best_of=m.get("best_of", 3),
            date=m.get("date", datetime.now().strftime("%Y-%m-%d")),
            round=m.get("round"),
        )
        contexts.append(ctx)
    return contexts


def save_ingested_data(matches: List[MatchContext], filename: str = "ingested_matches.json"):
    """Save ingested match data."""
    output = DATA_DIR / filename
    data = [
        {
            "player_a": m.player_a,
            "player_b": m.player_b,
            "tournament": m.tournament,
            "surface": m.surface,
            "best_of": m.best_of,
            "date": m.date,
            "round": m.round,
        }
        for m in matches
    ]
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return output


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------

def main():
    print("Tennis Ingest — Loading data...")
    
    config = load_global_config()
    stats = load_player_stats()
    
    print(f"Config loaded: {len(config)} keys")
    print(f"Player stats loaded: {len(stats)} players")
    
    # Create empty player_stats.json if not exists
    stats_file = DATA_DIR / "player_stats.json"
    if not stats_file.exists():
        stats_file.write_text("{}", encoding="utf-8")
        print(f"Created empty: {stats_file}")
    
    print("Ingest complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
