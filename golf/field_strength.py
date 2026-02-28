"""
GOLF FIELD STRENGTH METRIC — Phase 5B Enhancement
==================================================

Calculates field quality for golf tournaments and applies adjustments:
- Weak field (low OWGR avg): Boost confidence (+2-4%)
- Strong field (high OWGR avg): Reduce confidence (-2-4%)
- Elite field (Majors, Signature): Maximum penalty consideration

Field Strength = Average OWGR of top 30 players in field

Usage:
    from golf.field_strength import get_field_strength_adjustment
    
    adj, info = get_field_strength_adjustment("Scottie Scheffler", "The Masters")
    # Returns: (-0.02, info_dict) for elite field

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

GOLF_DIR = Path(__file__).parent
FIELD_STRENGTH_PATH = GOLF_DIR / "data" / "field_strength.json"
PLAYER_OWGR_PATH = GOLF_DIR / "data" / "player_owgr.json"


class FieldTier(Enum):
    ELITE = "elite"       # Top 50 OWGR avg (Majors, Signature Events)
    STRONG = "strong"     # 50-100 OWGR avg
    AVERAGE = "average"   # 100-150 OWGR avg  
    WEAK = "weak"         # 150+ OWGR avg (Korn Ferry, minor events)


@dataclass
class FieldStrength:
    """Tournament field strength data."""
    tournament: str
    field_tier: FieldTier
    avg_owgr: float
    top_30_owgr: float
    field_size: int
    top_10_players: List[str] = field(default_factory=list)
    last_updated: Optional[str] = None


@dataclass
class PlayerFieldPosition:
    """Player's position relative to field."""
    player: str
    player_owgr: int
    field_avg_owgr: float
    relative_position: str  # "above", "at", "below" field average
    advantage_score: float  # -1.0 to +1.0


# =============================================================================
# FIELD STRENGTH THRESHOLDS
# =============================================================================

FIELD_TIER_THRESHOLDS = {
    "ELITE": 50,      # Avg OWGR < 50 = elite field
    "STRONG": 100,    # 50-100 = strong
    "AVERAGE": 150,   # 100-150 = average
    "WEAK": 300,      # 150+ = weak
}

# Known tournament field classifications (manual overrides)
TOURNAMENT_FIELD_OVERRIDES: Dict[str, FieldTier] = {
    # Majors - always elite
    "masters": FieldTier.ELITE,
    "the masters": FieldTier.ELITE,
    "pga championship": FieldTier.ELITE,
    "us open": FieldTier.ELITE,
    "u.s. open": FieldTier.ELITE,
    "open championship": FieldTier.ELITE,
    "the open": FieldTier.ELITE,
    "british open": FieldTier.ELITE,
    
    # PGA Tour Signature Events - elite
    "the players": FieldTier.ELITE,
    "players championship": FieldTier.ELITE,
    "arnold palmer invitational": FieldTier.ELITE,
    "genesis invitational": FieldTier.ELITE,
    "memorial tournament": FieldTier.ELITE,
    "wm phoenix open": FieldTier.ELITE,
    "rbc heritage": FieldTier.STRONG,  # Signature but weaker field historically
    
    # Strong regular events
    "tour championship": FieldTier.ELITE,  # Top 30 only
    "fedex st jude championship": FieldTier.ELITE,
    "bmw championship": FieldTier.ELITE,
    
    # Korn Ferry Tour - weak
    "korn ferry": FieldTier.WEAK,
    
    # DP World Tour - average to strong
    "dp world tour": FieldTier.AVERAGE,
    "european tour": FieldTier.AVERAGE,
}

# Adjustment values by field tier and player OWGR
# Elite players (OWGR < 30) get boosted in weak fields
# Worse players get penalized in strong fields
FIELD_ADJUSTMENTS = {
    FieldTier.ELITE: {
        "elite_player": -0.02,    # Even elite players face competition
        "top_player": -0.01,      # Top 50 gets slight penalty
        "average_player": -0.03,  # Below 50 gets bigger penalty
        "weak_player": -0.05,     # Below 100 heavily penalized
    },
    FieldTier.STRONG: {
        "elite_player": 0.01,
        "top_player": 0.0,
        "average_player": -0.02,
        "weak_player": -0.03,
    },
    FieldTier.AVERAGE: {
        "elite_player": 0.02,
        "top_player": 0.01,
        "average_player": 0.0,
        "weak_player": -0.01,
    },
    FieldTier.WEAK: {
        "elite_player": 0.04,     # Elite players dominate weak fields
        "top_player": 0.03,
        "average_player": 0.01,
        "weak_player": 0.0,
    },
}


def normalize_tournament_name(name: str) -> str:
    """Normalize tournament name for matching."""
    return name.lower().strip().replace("-", " ").replace("'", "")


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.lower().strip().replace("-", " ").replace("'", "")


def get_player_owgr_tier(owgr: int) -> str:
    """Classify player by OWGR."""
    if owgr <= 30:
        return "elite_player"
    elif owgr <= 50:
        return "top_player"
    elif owgr <= 100:
        return "average_player"
    else:
        return "weak_player"


def load_player_owgr_data() -> Dict[str, int]:
    """Load player OWGR rankings."""
    if PLAYER_OWGR_PATH.exists():
        try:
            with open(PLAYER_OWGR_PATH, encoding="utf-8") as f:
                data = json.load(f)
                return {k: v for k, v in data.items() if not k.startswith("_")}
        except Exception as e:
            print(f"[FIELD_STRENGTH] Warning: Could not load OWGR data: {e}")
    return {}


def save_player_owgr_data(data: Dict[str, int]) -> None:
    """Save player OWGR rankings."""
    PLAYER_OWGR_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "_metadata": {
            "last_updated": datetime.now().isoformat(),
            "description": "Official World Golf Ranking positions"
        }
    }
    output.update(data)
    
    with open(PLAYER_OWGR_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


def load_field_strength_data() -> Dict[str, FieldStrength]:
    """Load tournament field strength data."""
    if FIELD_STRENGTH_PATH.exists():
        try:
            with open(FIELD_STRENGTH_PATH, encoding="utf-8") as f:
                data = json.load(f)
                result = {}
                for tourney, info in data.items():
                    if tourney.startswith("_"):
                        continue
                    result[tourney] = FieldStrength(
                        tournament=tourney,
                        field_tier=FieldTier(info.get("field_tier", "average")),
                        avg_owgr=info.get("avg_owgr", 100.0),
                        top_30_owgr=info.get("top_30_owgr", 50.0),
                        field_size=info.get("field_size", 156),
                        top_10_players=info.get("top_10_players", []),
                        last_updated=info.get("last_updated"),
                    )
                return result
        except Exception as e:
            print(f"[FIELD_STRENGTH] Warning: Could not load field strength data: {e}")
    return {}


def save_field_strength_data(data: Dict[str, FieldStrength]) -> None:
    """Save field strength data."""
    FIELD_STRENGTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "_metadata": {
            "last_updated": datetime.now().isoformat(),
            "description": "Tournament field strength metrics"
        }
    }
    
    for tourney, strength in data.items():
        output[tourney] = {
            "field_tier": strength.field_tier.value,
            "avg_owgr": strength.avg_owgr,
            "top_30_owgr": strength.top_30_owgr,
            "field_size": strength.field_size,
            "top_10_players": strength.top_10_players,
            "last_updated": strength.last_updated,
        }
    
    with open(FIELD_STRENGTH_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


def get_field_tier(tournament: str) -> FieldTier:
    """
    Get field tier for a tournament.
    
    Checks manual overrides first, then stored data, then defaults.
    """
    normalized = normalize_tournament_name(tournament)
    
    # Check manual overrides
    for key, tier in TOURNAMENT_FIELD_OVERRIDES.items():
        if key in normalized:
            return tier
    
    # Check stored data
    stored = load_field_strength_data()
    if normalized in stored:
        return stored[normalized].field_tier
    
    # Default to average
    return FieldTier.AVERAGE


def get_player_owgr(player_name: str) -> int:
    """
    Get player's OWGR ranking.
    
    Returns 999 if not found.
    """
    normalized = normalize_player_name(player_name)
    data = load_player_owgr_data()
    
    for db_player, owgr in data.items():
        if normalize_player_name(db_player) == normalized:
            return owgr
    
    # Check for partial matches
    for db_player, owgr in data.items():
        if normalized in normalize_player_name(db_player):
            return owgr
        if normalize_player_name(db_player) in normalized:
            return owgr
    
    return 999  # Unknown player


def get_field_strength_adjustment(
    player_name: str,
    tournament: str,
    player_owgr: Optional[int] = None,
) -> Tuple[float, Dict]:
    """
    Get confidence adjustment based on field strength and player quality.
    
    Args:
        player_name: Player's full name
        tournament: Tournament name
        player_owgr: Player's OWGR (optional, will be looked up if not provided)
    
    Returns:
        Tuple of (adjustment, info_dict)
        adjustment: -0.05 to +0.04 (percentage points)
    """
    field_tier = get_field_tier(tournament)
    
    if player_owgr is None:
        player_owgr = get_player_owgr(player_name)
    
    player_tier = get_player_owgr_tier(player_owgr)
    adjustment = FIELD_ADJUSTMENTS[field_tier].get(player_tier, 0.0)
    
    info = {
        "player": player_name,
        "tournament": tournament,
        "field_tier": field_tier.value,
        "player_owgr": player_owgr,
        "player_tier": player_tier,
        "adjustment": adjustment,
        "adjustment_applied": abs(adjustment) > 0.005,
    }
    
    return adjustment, info


def apply_field_strength_adjustment(
    raw_probability: float,
    player_name: str,
    tournament: str,
    player_owgr: Optional[int] = None,
) -> Tuple[float, Dict]:
    """
    Apply field strength adjustment to probability.
    
    Args:
        raw_probability: Original probability
        player_name: Player name
        tournament: Tournament name
        player_owgr: Optional OWGR override
    
    Returns:
        Tuple of (adjusted_probability, adjustment_info)
    """
    adjustment, info = get_field_strength_adjustment(
        player_name, tournament, player_owgr
    )
    
    adjusted_prob = raw_probability + adjustment
    adjusted_prob = max(0.40, min(0.85, adjusted_prob))  # Clamp
    
    info["original_probability"] = raw_probability
    info["adjusted_probability"] = adjusted_prob
    
    return adjusted_prob, info


# =============================================================================
# DATA INGESTION (from DataGolf or PGA Tour API)
# =============================================================================

def update_owgr_rankings(rankings: List[Dict]) -> None:
    """
    Update OWGR rankings from external data.
    
    Args:
        rankings: List of dicts with 'player' and 'rank' keys
    """
    data = {}
    for entry in rankings:
        player = entry.get("player", "")
        rank = entry.get("rank", 999)
        if player:
            data[normalize_player_name(player)] = rank
    
    save_player_owgr_data(data)
    print(f"[FIELD_STRENGTH] Updated OWGR for {len(data)} players")


def update_tournament_field(
    tournament: str,
    player_owgrs: Dict[str, int],
) -> None:
    """
    Update field strength for a specific tournament.
    
    Args:
        tournament: Tournament name
        player_owgrs: Dict mapping player names to their OWGR
    """
    owgr_values = list(player_owgrs.values())
    
    if not owgr_values:
        return
    
    avg_owgr = sum(owgr_values) / len(owgr_values)
    sorted_owgrs = sorted(owgr_values)
    top_30_owgr = sum(sorted_owgrs[:30]) / min(30, len(sorted_owgrs))
    
    # Determine tier
    if top_30_owgr < FIELD_TIER_THRESHOLDS["ELITE"]:
        tier = FieldTier.ELITE
    elif top_30_owgr < FIELD_TIER_THRESHOLDS["STRONG"]:
        tier = FieldTier.STRONG
    elif top_30_owgr < FIELD_TIER_THRESHOLDS["AVERAGE"]:
        tier = FieldTier.AVERAGE
    else:
        tier = FieldTier.WEAK
    
    # Get top 10 players
    sorted_players = sorted(player_owgrs.items(), key=lambda x: x[1])
    top_10 = [p[0] for p in sorted_players[:10]]
    
    data = load_field_strength_data()
    normalized = normalize_tournament_name(tournament)
    
    data[normalized] = FieldStrength(
        tournament=normalized,
        field_tier=tier,
        avg_owgr=avg_owgr,
        top_30_owgr=top_30_owgr,
        field_size=len(player_owgrs),
        top_10_players=top_10,
        last_updated=datetime.now().isoformat(),
    )
    
    save_field_strength_data(data)
    print(f"[FIELD_STRENGTH] Updated {tournament}: {tier.value} (top30 avg: {top_30_owgr:.1f})")


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Golf Field Strength")
    parser.add_argument("--check", nargs=2, metavar=("PLAYER", "TOURNAMENT"),
                       help="Check player's field strength adjustment")
    parser.add_argument("--tournament", type=str,
                       help="Get field tier for a tournament")
    parser.add_argument("--list-majors", action="store_true",
                       help="List major tournaments and their tiers")
    
    args = parser.parse_args()
    
    if args.check:
        player, tournament = args.check
        adj, info = get_field_strength_adjustment(player, tournament)
        print(f"\n=== Field Strength Check: {player} @ {tournament} ===")
        print(f"  Field Tier: {info['field_tier']}")
        print(f"  Player OWGR: {info['player_owgr']}")
        print(f"  Player Tier: {info['player_tier']}")
        print(f"  Adjustment: {adj:+.1%}")
    
    elif args.tournament:
        tier = get_field_tier(args.tournament)
        print(f"\n{args.tournament}: {tier.value}")
    
    elif args.list_majors:
        print("\n=== Tournament Field Classifications ===")
        for tourney, tier in sorted(TOURNAMENT_FIELD_OVERRIDES.items()):
            emoji = "🏆" if tier == FieldTier.ELITE else "⭐" if tier == FieldTier.STRONG else "➖"
            print(f"  {emoji} {tourney.title()}: {tier.value}")
    
    else:
        parser.print_help()
