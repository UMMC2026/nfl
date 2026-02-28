"""
GOLF TOURNAMENT TIER CLASSIFICATION — Phase 5B Enhancement
============================================================

Classifies golf tournaments into tiers for threshold adjustment:
- MAJOR: The 4 Majors (Masters, PGA Championship, US Open, The Open)
- PGA_TOUR: Regular PGA Tour events (signature events, regular events)
- KORN_FERRY: Developmental tour (thin data, volatile)
- DP_WORLD: European Tour (DP World Tour)
- LIV: LIV Golf (limited data)

Usage:
    from golf.tournament_tier import get_tournament_tier, get_golf_thresholds
    
    tier = get_tournament_tier("WM Phoenix Open")
    thresholds = get_golf_thresholds(tier)

Created: 2026-02-05
Phase: 5B Week 1
"""

from __future__ import annotations

import os
import sys
import re
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum

# Add project root to path for standalone execution
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class GolfTournamentTier(Enum):
    """Golf tournament classification tiers."""
    MAJOR = "major"
    PGA_SIGNATURE = "pga_signature"
    PGA_TOUR = "pga_tour"
    KORN_FERRY = "korn_ferry"
    DP_WORLD = "dp_world"
    LIV = "liv"
    UNKNOWN = "unknown"


# =============================================================================
# TOURNAMENT CLASSIFICATIONS
# =============================================================================

MAJORS = {
    # The 4 Majors
    "masters",
    "the masters",
    "masters tournament",
    "pga championship",
    "us open",
    "u.s. open",
    "the open",
    "the open championship",
    "british open",
}

PGA_SIGNATURE_EVENTS = {
    # 8 Signature Events (2024+ format) — elevated purse, elite field
    "the sentry",
    "sentry tournament of champions",
    "at&t pebble beach pro-am",
    "pebble beach",
    "the genesis invitational",
    "genesis invitational",
    "arnold palmer invitational",
    "bay hill",
    "rbc heritage",
    "wells fargo championship",
    "memorial tournament",
    "the memorial",
    "travelers championship",
    "fedex st. jude championship",
    
    # The Players Championship (often called "5th Major")
    "the players",
    "the players championship",
    "tpc sawgrass",
}

PGA_TOUR_REGULAR = {
    # Regular PGA Tour events (partial list, common ones)
    "wm phoenix open",
    "phoenix open",
    "waste management phoenix open",
    "farmers insurance open",
    "torrey pines",
    "sony open",
    "american express",
    "la quinta",
    "at&t byron nelson",
    "charles schwab challenge",
    "colonial",
    "rocket mortgage classic",
    "john deere classic",
    "3m open",
    "wyndham championship",
    "barracuda championship",
    "fortinet championship",
    "sanderson farms championship",
    "shriners hospitals",
    "cj cup",
    "zozo championship",
    "rsa championship",
    "houston open",
    "texas open",
    "cognizant classic",
    "mexico open",
    "puerto rico open",
}

KORN_FERRY_KEYWORDS = {
    "korn ferry",
    "korn ferry tour",
    "kft",
    "web.com",
    "nationwide tour",
}

LIV_KEYWORDS = {
    "liv golf",
    "liv",
}

DP_WORLD_KEYWORDS = {
    "dp world",
    "european tour",
    "rolex series",
    "bmw pga",
    "scottish open",
    "irish open",
    "italian open",
    "spanish open",
    "french open golf",
    "alfred dunhill",
    "nedbank",
    "dp world tour",
}


# =============================================================================
# TIER CLASSIFICATION FUNCTIONS
# =============================================================================

def normalize_tournament_name(name: str) -> str:
    """Normalize tournament name for matching."""
    name = name.lower().strip()
    # Remove year suffixes
    name = re.sub(r'\s*20\d{2}\s*', ' ', name)
    # Remove round indicators
    name = re.sub(r'\s*r[1-4]\s*', ' ', name)
    return name.strip()


def get_tournament_tier(tournament_name: str) -> GolfTournamentTier:
    """
    Classify a golf tournament into a tier.
    
    Args:
        tournament_name: Name of the tournament (e.g., "WM Phoenix Open R1")
    
    Returns:
        GolfTournamentTier enum value
    """
    normalized = normalize_tournament_name(tournament_name)
    
    # Check Majors first (highest priority)
    for major in MAJORS:
        if major in normalized or normalized in major:
            return GolfTournamentTier.MAJOR
    
    # Check Signature Events
    for sig in PGA_SIGNATURE_EVENTS:
        if sig in normalized or normalized in sig:
            return GolfTournamentTier.PGA_SIGNATURE
    
    # Check Korn Ferry
    for kf in KORN_FERRY_KEYWORDS:
        if kf in normalized:
            return GolfTournamentTier.KORN_FERRY
    
    # Check LIV
    for liv in LIV_KEYWORDS:
        if liv in normalized:
            return GolfTournamentTier.LIV
    
    # Check DP World Tour
    for dp in DP_WORLD_KEYWORDS:
        if dp in normalized:
            return GolfTournamentTier.DP_WORLD
    
    # Check regular PGA Tour events
    for pga in PGA_TOUR_REGULAR:
        if pga in normalized or normalized in pga:
            return GolfTournamentTier.PGA_TOUR
    
    # Default to PGA Tour (assume most events are PGA Tour)
    # This is safer than UNKNOWN since most props are PGA Tour
    return GolfTournamentTier.PGA_TOUR


def get_tier_sport_key(tier: GolfTournamentTier) -> str:
    """
    Get the sport key for thresholds.py lookup.
    
    Maps GolfTournamentTier to SPORT_TIER_OVERRIDES key.
    """
    mapping = {
        GolfTournamentTier.MAJOR: "GOLF_MAJOR",
        GolfTournamentTier.PGA_SIGNATURE: "GOLF_PGA_TOUR",  # Signature = high-quality PGA
        GolfTournamentTier.PGA_TOUR: "GOLF_PGA_TOUR",
        GolfTournamentTier.KORN_FERRY: "GOLF_KORN_FERRY",
        GolfTournamentTier.DP_WORLD: "GOLF_PGA_TOUR",      # Similar quality to PGA
        GolfTournamentTier.LIV: "GOLF",                    # Use base (limited data)
        GolfTournamentTier.UNKNOWN: "GOLF",
    }
    return mapping.get(tier, "GOLF")


def get_golf_thresholds(tier: GolfTournamentTier) -> Dict[str, Optional[float]]:
    """
    Get tier thresholds for a tournament tier.
    
    Args:
        tier: GolfTournamentTier enum value
    
    Returns:
        Dict with SLAM, STRONG, LEAN thresholds
    """
    from config.thresholds import SPORT_TIER_OVERRIDES, TIERS
    
    sport_key = get_tier_sport_key(tier)
    
    if sport_key in SPORT_TIER_OVERRIDES:
        overrides = SPORT_TIER_OVERRIDES[sport_key]
        return {
            "SLAM": overrides.get("SLAM"),
            "STRONG": overrides.get("STRONG", TIERS["STRONG"]),
            "LEAN": overrides.get("LEAN", TIERS["LEAN"]),
        }
    
    # Fallback to base TIERS
    return {
        "SLAM": TIERS["SLAM"],
        "STRONG": TIERS["STRONG"],
        "LEAN": TIERS["LEAN"],
    }


def implied_tier_for_golf(
    probability: float,
    tournament_name: str,
) -> str:
    """
    Determine tier from probability using tournament-specific thresholds.
    
    Args:
        probability: 0.0 - 1.0
        tournament_name: Name of the tournament
    
    Returns:
        Tier string (SLAM, STRONG, LEAN, AVOID)
    """
    tier = get_tournament_tier(tournament_name)
    thresholds = get_golf_thresholds(tier)
    
    slam_thresh = thresholds.get("SLAM")
    strong_thresh = thresholds.get("STRONG")
    lean_thresh = thresholds.get("LEAN")
    
    if slam_thresh is not None and probability >= slam_thresh:
        return "SLAM"
    if strong_thresh is not None and probability >= strong_thresh:
        return "STRONG"
    if lean_thresh is not None and probability >= lean_thresh:
        return "LEAN"
    return "AVOID"


# =============================================================================
# FIELD STRENGTH ESTIMATION
# =============================================================================

# Average OWGR by tournament tier (approximate)
TIER_FIELD_STRENGTH = {
    GolfTournamentTier.MAJOR: 25,           # Top 25 OWGR avg
    GolfTournamentTier.PGA_SIGNATURE: 40,   # Top 40 OWGR avg
    GolfTournamentTier.PGA_TOUR: 75,        # Top 75 OWGR avg
    GolfTournamentTier.DP_WORLD: 100,       # Top 100 OWGR avg
    GolfTournamentTier.LIV: 60,             # Mixed (some elite, some not)
    GolfTournamentTier.KORN_FERRY: 250,     # Developmental
    GolfTournamentTier.UNKNOWN: 100,
}


def get_estimated_field_strength(tournament_name: str) -> int:
    """
    Estimate field strength (average OWGR) for a tournament.
    
    Lower number = stronger field.
    """
    tier = get_tournament_tier(tournament_name)
    return TIER_FIELD_STRENGTH.get(tier, 100)


def field_strength_confidence_adjustment(
    base_probability: float,
    tournament_name: str,
) -> float:
    """
    Adjust confidence based on field strength.
    
    Stronger field = more predictable outcomes = slight confidence boost.
    Weaker field = more variance = slight confidence penalty.
    
    Args:
        base_probability: Raw probability (0.0 - 1.0)
        tournament_name: Name of the tournament
    
    Returns:
        Adjusted probability
    """
    field_strength = get_estimated_field_strength(tournament_name)
    
    # Adjustment scale:
    # OWGR avg 25 (majors) → +3% boost
    # OWGR avg 75 (regular PGA) → no adjustment
    # OWGR avg 250 (Korn Ferry) → -5% penalty
    
    if field_strength <= 30:
        adjustment = 0.03  # Elite field boost
    elif field_strength <= 50:
        adjustment = 0.02  # Signature event boost
    elif field_strength <= 100:
        adjustment = 0.00  # No adjustment
    elif field_strength <= 200:
        adjustment = -0.02  # Slight penalty
    else:
        adjustment = -0.05  # Developmental tour penalty
    
    # Apply adjustment but don't exceed bounds
    adjusted = base_probability + adjustment
    return max(0.50, min(0.95, adjusted))


# =============================================================================
# TIER INFO FOR REPORTING
# =============================================================================

@dataclass
class GolfTournamentInfo:
    """Information about a golf tournament."""
    name: str
    tier: GolfTournamentTier
    tier_display: str
    slam_enabled: bool
    slam_threshold: Optional[float]
    strong_threshold: float
    lean_threshold: float
    estimated_field_owgr: int


def get_tournament_info(tournament_name: str) -> GolfTournamentInfo:
    """Get full information about a tournament."""
    tier = get_tournament_tier(tournament_name)
    thresholds = get_golf_thresholds(tier)
    
    tier_display_map = {
        GolfTournamentTier.MAJOR: "🏆 Major Championship",
        GolfTournamentTier.PGA_SIGNATURE: "⭐ PGA Signature Event",
        GolfTournamentTier.PGA_TOUR: "PGA Tour",
        GolfTournamentTier.DP_WORLD: "DP World Tour",
        GolfTournamentTier.LIV: "⚠️ LIV Golf",
        GolfTournamentTier.KORN_FERRY: "⚠️ Korn Ferry Tour",
        GolfTournamentTier.UNKNOWN: "Unknown",
    }
    
    return GolfTournamentInfo(
        name=tournament_name,
        tier=tier,
        tier_display=tier_display_map.get(tier, "Unknown"),
        slam_enabled=thresholds.get("SLAM") is not None,
        slam_threshold=thresholds.get("SLAM"),
        strong_threshold=thresholds.get("STRONG", 0.65),
        lean_threshold=thresholds.get("LEAN", 0.55),
        estimated_field_owgr=get_estimated_field_strength(tournament_name),
    )


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Test tournament tier classification."""
    test_tournaments = [
        "The Masters 2026",
        "PGA Championship",
        "US Open",
        "The Open Championship",
        "WM Phoenix Open R1",
        "The Players Championship",
        "Genesis Invitational",
        "Arnold Palmer Invitational",
        "Korn Ferry Tour Event",
        "LIV Golf Adelaide",
        "DP World Tour Championship",
        "Random Tournament",
    ]
    
    print("\n" + "=" * 70)
    print("GOLF TOURNAMENT TIER CLASSIFICATION")
    print("=" * 70)
    
    for name in test_tournaments:
        info = get_tournament_info(name)
        slam_str = f"SLAM ≥{info.slam_threshold:.0%}" if info.slam_enabled else "SLAM disabled"
        print(f"\n  {name}")
        print(f"    Tier: {info.tier_display} | Field OWGR ~{info.estimated_field_owgr}")
        print(f"    {slam_str} | STRONG ≥{info.strong_threshold:.0%} | LEAN ≥{info.lean_threshold:.0%}")
    
    print("\n" + "=" * 70)
    print("✅ Classification complete")


if __name__ == "__main__":
    main()
