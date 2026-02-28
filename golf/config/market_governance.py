"""
Golf Market Governance
======================
Explicit market whitelist and blacklist for Phase 1 Golf.

TRUTH PRINCIPLE:
The system refuses to model markets where data is insufficient.
This is NOT a limitation — it's intellectual honesty.

PHASE 1 (Current State):
- No ShotLink round-level data
- No hole-by-hole distributions
- Limited to tournament-level + head-to-head markets

PHASE 2 (Future - Requires ShotLink):
- Round strokes
- Birdies per round
- Fairways hit
- Pars
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class MarketStatus(Enum):
    """Market availability status."""
    ENABLED = "enabled"           # Full modeling allowed
    RESEARCH_ONLY = "research"    # Calculate but don't bet
    DISABLED = "disabled"         # Don't even calculate
    REQUIRES_DATA = "requires_data"  # Blocked until ShotLink


@dataclass
class MarketConfig:
    """Configuration for a single market type."""
    name: str
    status: MarketStatus
    reason: str
    max_confidence: float = 0.75  # Cap for OVERCONFIDENT protection
    min_sample_size: int = 10
    requires_shotlink: bool = False
    model_type: str = "gaussian"  # gaussian, poisson, elo, beta


# =============================================================================
# GOLF MARKET WHITELIST — PHASE 1 (NO SHOTLINK)
# =============================================================================

GOLF_MARKETS: Dict[str, MarketConfig] = {
    # =========================================================================
    # ENABLED MARKETS (Full modeling, betting allowed)
    # =========================================================================
    
    "head_to_head": MarketConfig(
        name="Head-to-Head Matchup",
        status=MarketStatus.ENABLED,
        reason="Relative skill comparison, no absolute stat needed",
        max_confidence=0.72,
        min_sample_size=5,
        model_type="elo",
    ),
    
    "matchup": MarketConfig(
        name="Matchup (G-market)",
        status=MarketStatus.ENABLED,
        reason="Two-player comparison using SG differentials",
        max_confidence=0.72,
        min_sample_size=5,
        model_type="elo",
    ),
    
    "cut_made": MarketConfig(
        name="Make/Miss Cut",
        status=MarketStatus.ENABLED,
        reason="Binary outcome with historical base rates",
        max_confidence=0.78,
        min_sample_size=8,
        model_type="beta",
    ),
    
    "top_20": MarketConfig(
        name="Top 20 Finish",
        status=MarketStatus.ENABLED,
        reason="Broad placement band, reducible to skill tier",
        max_confidence=0.70,
        min_sample_size=10,
        model_type="beta",
    ),
    
    "top_10": MarketConfig(
        name="Top 10 Finish",
        status=MarketStatus.ENABLED,
        reason="Placement band with reasonable historical data",
        max_confidence=0.68,
        min_sample_size=10,
        model_type="beta",
    ),
    
    "top_5": MarketConfig(
        name="Top 5 Finish",
        status=MarketStatus.ENABLED,
        reason="Elite placement, requires strong skill signal",
        max_confidence=0.65,
        min_sample_size=12,
        model_type="beta",
    ),
    
    # =========================================================================
    # RESEARCH ONLY (Calculate for learning, don't bet)
    # =========================================================================
    
    "finishing_position": MarketConfig(
        name="Finishing Position (Exact)",
        status=MarketStatus.RESEARCH_ONLY,
        reason="High variance, field-dependent, weak edge signal",
        max_confidence=0.60,
        min_sample_size=15,
        model_type="gaussian",
    ),
    
    "tournament_winner": MarketConfig(
        name="Tournament Winner",
        status=MarketStatus.RESEARCH_ONLY,
        reason="Extreme variance, only for tracking accuracy",
        max_confidence=0.55,
        min_sample_size=20,
        model_type="beta",
    ),
    
    # =========================================================================
    # UI-DERIVED STATS (from Underdog screenshot) — ENABLED
    # Schema: golf/config/ingest_schema_v1.py
    # =========================================================================
    
    "round_strokes": MarketConfig(
        name="Round Strokes",
        status=MarketStatus.ENABLED,
        reason="UI-derived. Model uses line inference + course adjustment.",
        max_confidence=0.62,  # Conservative cap
        requires_shotlink=False,
        model_type="gaussian",
        min_sample_size=5,
    ),
    
    "birdies_or_better": MarketConfig(
        name="Birdies or Better",
        status=MarketStatus.ENABLED,
        reason="UI-derived. Poisson model from historical averages.",
        max_confidence=0.62,  # CONSERVATIVE - birdies cluster
        requires_shotlink=False,
        model_type="poisson",
        min_sample_size=5,
    ),
    
    # Alias for backwards compatibility
    "birdies": MarketConfig(
        name="Birdies Per Round",
        status=MarketStatus.ENABLED,
        reason="Alias for birdies_or_better",
        max_confidence=0.62,
        requires_shotlink=False,
        model_type="poisson",
    ),
    
    "pars": MarketConfig(
        name="Pars Per Round",
        status=MarketStatus.REQUIRES_DATA,
        reason="Dependent on birdie/bogey split, no round data",
        max_confidence=0.60,
        requires_shotlink=True,
        model_type="poisson",
    ),
    
    "bogeys": MarketConfig(
        name="Bogeys Per Round",
        status=MarketStatus.REQUIRES_DATA,
        reason="Course-dependent, no round-level variance data",
        max_confidence=0.62,
        requires_shotlink=True,
        model_type="poisson",
    ),
    
    "fairways_hit": MarketConfig(
        name="Fairways Hit",
        status=MarketStatus.RESEARCH_ONLY,
        reason="UI-derived but high variance. Track for calibration.",
        max_confidence=0.58,
        requires_shotlink=False,
        model_type="poisson",
        min_sample_size=8,
    ),
    
    "greens_in_regulation": MarketConfig(
        name="Greens in Regulation",
        status=MarketStatus.RESEARCH_ONLY,
        reason="UI-derived but high variance. Track for calibration.",
        max_confidence=0.58,
        requires_shotlink=False,
        model_type="poisson",
        min_sample_size=8,
    ),
    
    "eagles": MarketConfig(
        name="Eagles Per Round",
        status=MarketStatus.DISABLED,
        reason="Extremely rare event, insufficient data for modeling",
        max_confidence=0.55,
        requires_shotlink=True,
        model_type="poisson",
    ),
    
    "putts": MarketConfig(
        name="Putts Per Round",
        status=MarketStatus.DISABLED,
        reason="No putting distribution data",
        max_confidence=0.58,
        requires_shotlink=True,
        model_type="poisson",
    ),
}


# =============================================================================
# MARKET ALIASES (Normalize different naming conventions)
# =============================================================================

MARKET_ALIASES: Dict[str, str] = {
    # Round strokes variants (UI: "Round Strokes")
    "strokes": "round_strokes",
    "round_score": "round_strokes",
    "score": "round_strokes",
    "total_strokes": "round_strokes",
    
    # Birdies variants (UI: "Birdies or Better")
    "birdies_per_round": "birdies_or_better",
    "birdie": "birdies_or_better",
    "birdies": "birdies_or_better",
    
    # Made cut (UI: "Made Cuts")
    "made_cut": "cut_made",
    "make_cut": "cut_made",
    "miss_cut": "cut_made",
    "made_cuts": "cut_made",
    
    # GIR (UI: "Greens in Regulation")
    "gir": "greens_in_regulation",
    "greens": "greens_in_regulation",
    
    # Fairways (UI: "Fairways Hit")
    "fairways": "fairways_hit",
    "fir": "fairways_hit",
    
    # Matchup variants
    "h2h": "head_to_head",
    "versus": "head_to_head",
    "vs": "head_to_head",
    "g": "matchup",  # Underdog's "G" markets
    "birdies_or_better_matchup": "matchup",  # G-markets
    
    # Placement variants
    "top20": "top_20",
    "top10": "top_10",
    "top5": "top_5",
    
    # Finishing position (UI: "Tourney Finishing Position")
    "finish": "finishing_position",
    "placement": "finishing_position",
    "position": "finishing_position",
    "tourney_finishing_position": "finishing_position",
}


def normalize_market(market: str) -> str:
    """Normalize market name to canonical form."""
    market_lower = market.lower().strip().replace(" ", "_").replace("-", "_")
    return MARKET_ALIASES.get(market_lower, market_lower)


def get_market_config(market: str) -> Optional[MarketConfig]:
    """Get configuration for a market type."""
    normalized = normalize_market(market)
    return GOLF_MARKETS.get(normalized)


def is_market_enabled(market: str) -> bool:
    """Check if market is enabled for betting."""
    config = get_market_config(market)
    if config is None:
        return False
    return config.status == MarketStatus.ENABLED


def is_market_allowed(market: str) -> bool:
    """Check if market is allowed for calculation (enabled or research)."""
    config = get_market_config(market)
    if config is None:
        return False
    return config.status in [MarketStatus.ENABLED, MarketStatus.RESEARCH_ONLY]


def get_market_max_confidence(market: str) -> float:
    """Get maximum confidence cap for a market (OVERCONFIDENT protection)."""
    config = get_market_config(market)
    if config is None:
        return 0.60  # Conservative default
    return config.max_confidence


def get_disabled_reason(market: str) -> str:
    """Get reason why market is disabled."""
    config = get_market_config(market)
    if config is None:
        return "Unknown market type"
    return config.reason


def validate_market_for_edge(
    market: str, 
    probability: float
) -> Tuple[bool, str, str]:
    """
    Validate if an edge can be generated for this market.
    
    Returns:
        Tuple of (is_valid, pick_state, reason)
    """
    config = get_market_config(market)
    
    # Unknown market
    if config is None:
        return False, "REJECTED", f"Unknown market type: {market}"
    
    # Disabled markets
    if config.status == MarketStatus.DISABLED:
        return False, "REJECTED", f"[MARKET DISABLED] {market}: {config.reason}"
    
    # Requires ShotLink
    if config.status == MarketStatus.REQUIRES_DATA:
        return False, "REJECTED", f"[REQUIRES SHOTLINK] {market}: {config.reason}"
    
    # Research only
    if config.status == MarketStatus.RESEARCH_ONLY:
        return True, "VETTED", f"[RESEARCH ONLY] {market}: Tracking for calibration"
    
    # Overconfident check
    if probability > config.max_confidence:
        return False, "REJECTED", f"[OVERCONFIDENT] {market}: {probability:.1%} exceeds {config.max_confidence:.0%} cap"
    
    # Passed all checks
    return True, "OPTIMIZABLE", ""


def get_enabled_markets() -> List[str]:
    """Get list of all enabled markets."""
    return [
        name for name, config in GOLF_MARKETS.items() 
        if config.status == MarketStatus.ENABLED
    ]


def get_disabled_markets() -> List[str]:
    """Get list of all disabled markets."""
    return [
        name for name, config in GOLF_MARKETS.items() 
        if config.status in [MarketStatus.DISABLED, MarketStatus.REQUIRES_DATA]
    ]


def print_market_status():
    """Print formatted market status table."""
    print("=" * 70)
    print("GOLF MARKET GOVERNANCE — PHASE 1 (NO SHOTLINK)")
    print("=" * 70)
    
    print("\n✅ ENABLED (Betting Allowed):")
    for name, config in GOLF_MARKETS.items():
        if config.status == MarketStatus.ENABLED:
            print(f"   • {config.name:<25} (max: {config.max_confidence:.0%})")
    
    print("\n📊 RESEARCH ONLY (Track, Don't Bet):")
    for name, config in GOLF_MARKETS.items():
        if config.status == MarketStatus.RESEARCH_ONLY:
            print(f"   • {config.name:<25} — {config.reason}")
    
    print("\n❌ DISABLED (Requires ShotLink):")
    for name, config in GOLF_MARKETS.items():
        if config.status in [MarketStatus.DISABLED, MarketStatus.REQUIRES_DATA]:
            print(f"   • {config.name:<25} — {config.reason}")
    
    print("\n" + "=" * 70)


# =============================================================================
# GOLF-SPECIFIC CONFIDENCE GOVERNORS
# =============================================================================

def get_golf_confidence_cap(market: str, direction: str) -> float:
    """
    Get confidence cap with direction-specific adjustments.
    
    Golf UNDERS are more dangerous due to clustering effects.
    """
    config = get_market_config(market)
    base_cap = config.max_confidence if config else 0.60
    
    # UNDER/LOWER gets stricter cap for high-variance stats
    if direction.lower() in ["lower", "under"]:
        if market in ["birdies", "pars", "bogeys"]:
            return min(base_cap, 0.62)  # STRICT cap for count stats
        elif market in ["round_strokes"]:
            return min(base_cap, 0.65)  # Moderate cap for strokes
    
    return base_cap


# =============================================================================
# DEMO / TEST
# =============================================================================

if __name__ == "__main__":
    print_market_status()
    
    print("\n\nValidation Tests:")
    tests = [
        ("head_to_head", 0.68),
        ("birdies", 0.65),
        ("round_strokes", 0.70),
        ("fairways_hit", 0.55),
        ("top_20", 0.72),
        ("finishing_position", 0.58),
    ]
    
    for market, prob in tests:
        valid, state, reason = validate_market_for_edge(market, prob)
        status = "✓" if valid else "✗"
        print(f"   {status} {market} @ {prob:.0%} → {state} {reason}")
