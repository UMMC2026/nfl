"""
TENNIS TOURNAMENT TIER CLASSIFICATION — Phase 5B Enhancement
=============================================================

Classifies tennis tournaments into tiers for threshold adjustment:
- GRAND_SLAM: Australian Open, French Open, Wimbledon, US Open
- MASTERS: ATP Masters 1000 events (9 tournaments)
- ATP_500: ATP 500 level events
- ATP_250: ATP 250 level events
- CHALLENGER: ATP Challenger Tour

Usage:
    from tennis.tournament_tier import get_tournament_tier, get_tennis_thresholds
    
    tier = get_tournament_tier("Australian Open")
    thresholds = get_tennis_thresholds(tier)

Created: 2026-02-05
Phase: 5B Week 1
"""

from __future__ import annotations

import os
import sys
import re
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path for standalone execution
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class TournamentTier(Enum):
    """Tennis tournament classification tiers."""
    GRAND_SLAM = "grand_slam"
    MASTERS = "masters"
    ATP_500 = "atp_500"
    ATP_250 = "atp_250"
    CHALLENGER = "challenger"
    WTA_1000 = "wta_1000"
    WTA_500 = "wta_500"
    WTA_250 = "wta_250"
    UNKNOWN = "unknown"


# =============================================================================
# TOURNAMENT CLASSIFICATIONS
# =============================================================================

GRAND_SLAMS = {
    "australian open",
    "french open",
    "roland garros",
    "wimbledon",
    "us open",
    "australian open 2026",
    "french open 2026",
    "wimbledon 2026",
    "us open 2026",
}

ATP_MASTERS_1000 = {
    # Hard Court
    "indian wells",
    "bnp paribas open",
    "miami open",
    "miami",
    "shanghai",
    "shanghai masters",
    "paris masters",
    "paris",
    "rolex paris masters",
    "canada masters",
    "canadian open",
    "rogers cup",
    "cincinnati",
    "western & southern open",
    "cincinnati masters",
    
    # Clay Court
    "monte carlo",
    "monte-carlo masters",
    "madrid open",
    "madrid",
    "italian open",
    "rome",
    "internazionali bnl d'italia",
}

ATP_500 = {
    "rotterdam",
    "rio open",
    "acapulco",
    "dubai",
    "barcelona",
    "queen's club",
    "halle",
    "hamburg",
    "washington",
    "citi open",
    "tokyo",
    "japan open",
    "vienna",
    "erste bank open",
    "basel",
    "swiss indoors",
}

WTA_1000 = {
    "indian wells",
    "miami open",
    "madrid open",
    "rome",
    "canadian open",
    "cincinnati",
    "wuhan",
    "beijing",
    "wta finals",
}

# Challenger keywords
CHALLENGER_KEYWORDS = {
    "challenger",
    "atp challenger",
    "itf",
    "futures",
    "$25k",
    "$15k",
    "$60k",
    "$80k",
    "$100k",
}


# =============================================================================
# TIER CLASSIFICATION FUNCTIONS
# =============================================================================

def normalize_tournament_name(name: str) -> str:
    """Normalize tournament name for matching."""
    # Convert to lowercase, remove extra whitespace
    name = name.lower().strip()
    # Remove year suffixes
    name = re.sub(r'\s*20\d{2}\s*', ' ', name)
    # Remove "atp" or "wta" prefixes if not part of classification
    name = re.sub(r'^(atp|wta)\s+', '', name)
    return name.strip()


def get_tournament_tier(tournament_name: str) -> TournamentTier:
    """
    Classify a tennis tournament into a tier.
    
    Args:
        tournament_name: Name of the tournament (e.g., "Australian Open 2026")
    
    Returns:
        TournamentTier enum value
    """
    normalized = normalize_tournament_name(tournament_name)
    
    # Check Grand Slams first (highest priority)
    for gs in GRAND_SLAMS:
        if gs in normalized or normalized in gs:
            return TournamentTier.GRAND_SLAM
    
    # Check Masters 1000
    for m in ATP_MASTERS_1000:
        if m in normalized or normalized in m:
            return TournamentTier.MASTERS
    
    # Check WTA 1000
    for w in WTA_1000:
        if w in normalized or normalized in w:
            return TournamentTier.WTA_1000
    
    # Check ATP 500
    for a5 in ATP_500:
        if a5 in normalized or normalized in a5:
            return TournamentTier.ATP_500
    
    # Check Challenger keywords
    for ck in CHALLENGER_KEYWORDS:
        if ck in normalized:
            return TournamentTier.CHALLENGER
    
    # Default to ATP 250 (most common)
    return TournamentTier.ATP_250


def get_tier_sport_key(tier: TournamentTier) -> str:
    """
    Get the sport key for thresholds.py lookup.
    
    Maps TournamentTier to SPORT_TIER_OVERRIDES key.
    """
    mapping = {
        TournamentTier.GRAND_SLAM: "TENNIS_GRAND_SLAM",
        TournamentTier.MASTERS: "TENNIS_MASTERS",
        TournamentTier.WTA_1000: "TENNIS_MASTERS",  # Same thresholds as ATP Masters
        TournamentTier.ATP_500: "TENNIS",           # Use base tennis thresholds
        TournamentTier.ATP_250: "TENNIS",           # Use base tennis thresholds
        TournamentTier.WTA_500: "TENNIS",
        TournamentTier.WTA_250: "TENNIS",
        TournamentTier.CHALLENGER: "TENNIS_CHALLENGER",
        TournamentTier.UNKNOWN: "TENNIS",
    }
    return mapping.get(tier, "TENNIS")


def get_tennis_thresholds(tier: TournamentTier) -> Dict[str, Optional[float]]:
    """
    Get tier thresholds for a tournament tier.
    
    Args:
        tier: TournamentTier enum value
    
    Returns:
        Dict with SLAM, STRONG, LEAN thresholds
    """
    # Import here to avoid circular imports
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


def implied_tier_for_tennis(
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
    thresholds = get_tennis_thresholds(tier)
    
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
# TIER INFO FOR REPORTING
# =============================================================================

@dataclass
class TournamentInfo:
    """Information about a tennis tournament."""
    name: str
    tier: TournamentTier
    tier_display: str
    slam_enabled: bool
    slam_threshold: Optional[float]
    strong_threshold: float
    lean_threshold: float


def get_tournament_info(tournament_name: str) -> TournamentInfo:
    """Get full information about a tournament."""
    tier = get_tournament_tier(tournament_name)
    thresholds = get_tennis_thresholds(tier)
    
    tier_display_map = {
        TournamentTier.GRAND_SLAM: "🏆 Grand Slam",
        TournamentTier.MASTERS: "⭐ Masters 1000",
        TournamentTier.WTA_1000: "⭐ WTA 1000",
        TournamentTier.ATP_500: "ATP 500",
        TournamentTier.ATP_250: "ATP 250",
        TournamentTier.WTA_500: "WTA 500",
        TournamentTier.WTA_250: "WTA 250",
        TournamentTier.CHALLENGER: "⚠️ Challenger",
        TournamentTier.UNKNOWN: "Unknown",
    }
    
    return TournamentInfo(
        name=tournament_name,
        tier=tier,
        tier_display=tier_display_map.get(tier, "Unknown"),
        slam_enabled=thresholds.get("SLAM") is not None,
        slam_threshold=thresholds.get("SLAM"),
        strong_threshold=thresholds.get("STRONG", 0.65),
        lean_threshold=thresholds.get("LEAN", 0.55),
    )


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Test tournament tier classification."""
    test_tournaments = [
        "Australian Open 2026",
        "French Open",
        "Wimbledon",
        "US Open",
        "Indian Wells",
        "Miami Open",
        "Monte Carlo Masters",
        "Rotterdam",
        "Barcelona Open",
        "ATP Challenger Tour",
        "Mubadala Citi DC Open",
        "Random Tournament",
    ]
    
    print("\n" + "=" * 70)
    print("TENNIS TOURNAMENT TIER CLASSIFICATION")
    print("=" * 70)
    
    for name in test_tournaments:
        info = get_tournament_info(name)
        slam_str = f"SLAM ≥{info.slam_threshold:.0%}" if info.slam_enabled else "SLAM disabled"
        print(f"\n  {name}")
        print(f"    Tier: {info.tier_display}")
        print(f"    {slam_str} | STRONG ≥{info.strong_threshold:.0%} | LEAN ≥{info.lean_threshold:.0%}")
    
    print("\n" + "=" * 70)
    print("✅ Classification complete")


if __name__ == "__main__":
    main()
