"""
EDGE DIAGNOSTICS MODULE
Provides σ-distance, penalty attribution, and confidence tier labeling.

Key Features:
1. σ-distance (z-score) calculation with human-readable interpretation
2. Penalty attribution tracing (stat tax, variance penalty, market inflation)
3. Confidence tier labeling (SLAM/STRONG/LEAN/NO PLAY)
4. Edge quality diagnostics

This module is consumed by:
- risk_first_analyzer.py (adds diagnostics to pick results)
- menu.py (renders diagnostics in FULL_REPORT)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIDENCE TIER DEFINITIONS (per .github/copilot-instructions.md)
# ═══════════════════════════════════════════════════════════════════════════════

TIER_THRESHOLDS = {
    "nba": {
        "SLAM": 80.0,      # ≥80%
        "STRONG": 65.0,    # ≥65%
        "LEAN": 55.0,      # ≥55%
        "NO_PLAY": 0.0     # <55%
    },
    "cbb": {
        # CBB uses stricter thresholds
        "STRONG": 70.0,    # ≥70% (no SLAM tier)
        "LEAN": 60.0,      # ≥60%
        "NO_PLAY": 0.0     # <60%
    },
    "nfl": {
        "SLAM": 80.0,
        "STRONG": 65.0,
        "LEAN": 55.0,
        "NO_PLAY": 0.0
    },
    "tennis": {
        "SLAM": 80.0,
        "STRONG": 65.0,
        "LEAN": 55.0,
        "NO_PLAY": 0.0
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# STAT-SPECIFIC PENALTY RATES
# ═══════════════════════════════════════════════════════════════════════════════

# Stat taxes: higher = more aggressive penalty (market is more efficient on these)
STAT_TAX_RATES = {
    # High variance / volatile stats get taxed harder
    "points": 0.12,        # 12% tax - most liquid market
    "pts": 0.12,
    "assists": 0.10,       # 10% tax - scheme dependent
    "ast": 0.10,
    "3pm": 0.08,           # 8% tax - highly volatile
    "3ptm": 0.08,
    "threes": 0.08,
    "steals": 0.06,        # 6% tax - rare event
    "stl": 0.06,
    "blocks": 0.06,        # 6% tax - rare event
    "blk": 0.06,
    
    # Lower variance stats get less penalty
    "rebounds": 0.05,      # 5% tax - more predictable
    "reb": 0.05,
    "turnovers": 0.04,     # 4% tax
    "tov": 0.04,
    
    # Combo stats get reduced penalty (diversification)
    "pra": 0.06,           # 6% tax - PTS+REB+AST
    "pts+reb+ast": 0.06,
    "pts+ast": 0.05,       # 5% tax
    "pts+reb": 0.05,
    "reb+ast": 0.04,       # 4% tax
}

DEFAULT_STAT_TAX = 0.08  # 8% default


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ZScoreDiagnostic:
    """σ-distance diagnostic with interpretation."""
    z_score: float                  # Raw z-score (line - μ) / σ
    z_direction: str                # "above" or "below" mean
    sigma_distance: float           # Absolute σ distance
    interpretation: str             # Human-readable interpretation
    edge_quality: str               # ELITE/STRONG/MODERATE/THIN
    
    def to_dict(self) -> dict:
        return {
            "z_score": round(self.z_score, 3),
            "z_direction": self.z_direction,
            "sigma_distance": round(self.sigma_distance, 3),
            "interpretation": self.interpretation,
            "edge_quality": self.edge_quality
        }


@dataclass
class PenaltyAttribution:
    """Breakdown of how raw probability was penalized to reach final."""
    raw_probability: float          # Before any penalties
    stat_tax_pct: float             # Stat-specific market tax
    variance_penalty_pct: float     # High-σ penalty
    market_inflation_pct: float     # Over-bias / line inflation penalty
    context_penalty_pct: float      # B2B, rest, injury, etc.
    total_penalty_pct: float        # Sum of all penalties
    final_probability: float        # After all penalties
    penalty_details: List[str] = field(default_factory=list)  # Explanations
    
    def to_dict(self) -> dict:
        return {
            "raw_probability": round(self.raw_probability, 2),
            "stat_tax_pct": round(self.stat_tax_pct, 2),
            "variance_penalty_pct": round(self.variance_penalty_pct, 2),
            "market_inflation_pct": round(self.market_inflation_pct, 2),
            "context_penalty_pct": round(self.context_penalty_pct, 2),
            "total_penalty_pct": round(self.total_penalty_pct, 2),
            "final_probability": round(self.final_probability, 2),
            "penalty_details": self.penalty_details
        }


@dataclass 
class TierLabel:
    """Confidence tier with label and thresholds."""
    tier: str                       # SLAM/STRONG/LEAN/NO_PLAY
    confidence: float               # Actual confidence value
    tier_floor: float               # Minimum for this tier
    tier_ceiling: Optional[float]   # Maximum for this tier (None = unbounded)
    sport: str                      # Sport context
    
    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "confidence": round(self.confidence, 2),
            "tier_floor": round(self.tier_floor, 2),
            "tier_ceiling": round(self.tier_ceiling, 2) if self.tier_ceiling else None,
            "sport": self.sport
        }


@dataclass
class EdgeDiagnostic:
    """Complete edge diagnostic bundle."""
    z_score_diagnostic: ZScoreDiagnostic
    penalty_attribution: PenaltyAttribution
    tier_label: TierLabel
    diagnostic_summary: str         # One-line summary for reports
    
    def to_dict(self) -> dict:
        return {
            "z_score": self.z_score_diagnostic.to_dict(),
            "penalties": self.penalty_attribution.to_dict(),
            "tier": self.tier_label.to_dict(),
            "summary": self.diagnostic_summary
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_z_score(
    line: float,
    mu: float,
    sigma: float,
    direction: str
) -> ZScoreDiagnostic:
    """
    Calculate z-score (σ-distance) with human-readable interpretation.
    
    z = (line − μ) / σ
    
    For OVER bets: negative z (line below mean) is favorable
    For UNDER bets: positive z (line above mean) is favorable
    
    Args:
        line: The prop line
        mu: Player's mean/average for the stat
        sigma: Standard deviation
        direction: "higher" (OVER) or "lower" (UNDER)
        
    Returns:
        ZScoreDiagnostic with z-score and interpretation
    """
    if sigma <= 0:
        sigma = 0.01  # Prevent division by zero
    
    # Raw z-score: how many σ is the line from the mean?
    z_raw = (line - mu) / sigma
    z_direction = "above" if z_raw > 0 else "below" if z_raw < 0 else "at"
    sigma_distance = abs(z_raw)
    
    # Interpret in context of bet direction
    is_over = direction.lower() == "higher"
    
    # For OVER: want line BELOW mean (negative z)
    # For UNDER: want line ABOVE mean (positive z)
    directional_z = -z_raw if is_over else z_raw
    
    # Edge quality based on directional z
    if directional_z >= 1.0:
        edge_quality = "ELITE"
    elif directional_z >= 0.5:
        edge_quality = "STRONG"
    elif directional_z >= 0.25:
        edge_quality = "MODERATE"
    elif directional_z >= 0.0:
        edge_quality = "THIN"
    else:
        edge_quality = "NEGATIVE"  # Line is unfavorable vs direction
    
    # Build interpretation string
    direction_word = "OVER" if is_over else "UNDER"
    if is_over:
        if z_raw < 0:
            interpretation = f"Line {line} is {sigma_distance:.2f}σ BELOW mean ({mu:.1f}) → favorable for {direction_word}"
        elif z_raw > 0:
            interpretation = f"Line {line} is {sigma_distance:.2f}σ ABOVE mean ({mu:.1f}) → unfavorable for {direction_word}"
        else:
            interpretation = f"Line {line} is AT mean ({mu:.1f}) → coin flip for {direction_word}"
    else:
        if z_raw > 0:
            interpretation = f"Line {line} is {sigma_distance:.2f}σ ABOVE mean ({mu:.1f}) → favorable for {direction_word}"
        elif z_raw < 0:
            interpretation = f"Line {line} is {sigma_distance:.2f}σ BELOW mean ({mu:.1f}) → unfavorable for {direction_word}"
        else:
            interpretation = f"Line {line} is AT mean ({mu:.1f}) → coin flip for {direction_word}"
    
    return ZScoreDiagnostic(
        z_score=z_raw,
        z_direction=z_direction,
        sigma_distance=sigma_distance,
        interpretation=interpretation,
        edge_quality=edge_quality
    )


def calculate_penalty_attribution(
    raw_probability: float,
    final_probability: float,
    stat: str,
    sigma: float,
    direction: str,
    context_flags: Optional[Dict] = None
) -> PenaltyAttribution:
    """
    Attribute the gap between raw and final probability to specific penalty sources.
    
    This reverse-engineers where the penalty came from based on:
    1. Stat type (points taxed harder than rebounds)
    2. Variance (high σ = more penalty)
    3. Market direction (OVER bias penalty)
    4. Context (B2B, rest, injuries)
    
    Args:
        raw_probability: The unadjusted probability (0-100 scale)
        final_probability: After all gates/penalties (0-100 scale)
        stat: Stat type (e.g., "points", "rebounds", "pra")
        sigma: Standard deviation (high = more variance penalty)
        direction: "higher" or "lower"
        context_flags: Optional dict with context penalty flags
        
    Returns:
        PenaltyAttribution with breakdown
    """
    stat_lower = stat.lower().strip()
    context_flags = context_flags or {}
    
    # Calculate total penalty applied
    total_penalty = raw_probability - final_probability
    
    # If no penalty, return zeroed attribution
    if total_penalty <= 0:
        return PenaltyAttribution(
            raw_probability=raw_probability,
            stat_tax_pct=0.0,
            variance_penalty_pct=0.0,
            market_inflation_pct=0.0,
            context_penalty_pct=0.0,
            total_penalty_pct=0.0,
            final_probability=final_probability,
            penalty_details=["No penalty applied"]
        )
    
    # Attribution heuristics (approximate backward engineering)
    # These weights should sum to ~1.0 for typical cases
    
    # 1. Stat tax
    stat_tax_rate = STAT_TAX_RATES.get(stat_lower, DEFAULT_STAT_TAX)
    stat_tax_pct = min(raw_probability * stat_tax_rate, total_penalty * 0.35)
    
    # 2. Variance penalty (based on σ)
    # σ > 8 = high variance, σ < 3 = low variance
    variance_multiplier = min(1.0, max(0.0, (sigma - 3.0) / 10.0))  # 0-1 scale
    variance_penalty_pct = min(total_penalty * 0.30 * variance_multiplier, total_penalty * 0.30)
    
    # 3. Market inflation penalty (OVER bias)
    is_over = direction.lower() == "higher"
    if is_over:
        market_inflation_pct = min(total_penalty * 0.25, total_penalty * 0.25)
    else:
        market_inflation_pct = 0.0
    
    # 4. Context penalty (residual - B2B, rest, injuries, etc.)
    attributed = stat_tax_pct + variance_penalty_pct + market_inflation_pct
    context_penalty_pct = max(0.0, total_penalty - attributed)
    
    # Build explanation details
    details = []
    if stat_tax_pct > 0:
        details.append(f"Stat Tax ({stat_lower}): −{stat_tax_pct:.1f}%")
    if variance_penalty_pct > 0:
        details.append(f"Variance Penalty (σ={sigma:.1f}): −{variance_penalty_pct:.1f}%")
    if market_inflation_pct > 0:
        details.append(f"Market Inflation (OVER bias): −{market_inflation_pct:.1f}%")
    if context_penalty_pct > 0:
        details.append(f"Context Adjustments: −{context_penalty_pct:.1f}%")
    
    return PenaltyAttribution(
        raw_probability=raw_probability,
        stat_tax_pct=stat_tax_pct,
        variance_penalty_pct=variance_penalty_pct,
        market_inflation_pct=market_inflation_pct,
        context_penalty_pct=context_penalty_pct,
        total_penalty_pct=total_penalty,
        final_probability=final_probability,
        penalty_details=details
    )


def get_tier_label(
    confidence: float,
    sport: str = "nba"
) -> TierLabel:
    """
    Get the confidence tier label based on sport-specific thresholds.
    
    Args:
        confidence: Effective confidence (0-100 scale)
        sport: Sport code (nba, cbb, nfl, tennis)
        
    Returns:
        TierLabel with tier name and boundaries
    """
    sport_lower = sport.lower().strip()
    thresholds = TIER_THRESHOLDS.get(sport_lower, TIER_THRESHOLDS["nba"])
    
    # Sort tiers by threshold descending
    sorted_tiers = sorted(
        [(name, thresh) for name, thresh in thresholds.items() if name != "NO_PLAY"],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Find matching tier
    tier = "NO_PLAY"
    tier_floor = 0.0
    tier_ceiling = None
    
    for i, (tier_name, threshold) in enumerate(sorted_tiers):
        if confidence >= threshold:
            tier = tier_name
            tier_floor = threshold
            # Ceiling is the next tier's floor (or None if top tier)
            if i > 0:
                tier_ceiling = sorted_tiers[i - 1][1]
            else:
                tier_ceiling = None
            break
    
    # Handle NO_PLAY case
    if tier == "NO_PLAY":
        tier_floor = 0.0
        tier_ceiling = sorted_tiers[-1][1] if sorted_tiers else 55.0
    
    return TierLabel(
        tier=tier,
        confidence=confidence,
        tier_floor=tier_floor,
        tier_ceiling=tier_ceiling,
        sport=sport_lower
    )


def generate_edge_diagnostic(
    line: float,
    mu: float,
    sigma: float,
    direction: str,
    raw_probability: float,
    final_probability: float,
    stat: str,
    sport: str = "nba",
    context_flags: Optional[Dict] = None
) -> EdgeDiagnostic:
    """
    Generate complete edge diagnostic bundle.
    
    This is the main entry point for the edge diagnostics system.
    
    Args:
        line: Prop line
        mu: Player's mean for stat
        sigma: Standard deviation
        direction: "higher" or "lower"
        raw_probability: Before penalties (0-100)
        final_probability: After penalties (0-100)
        stat: Stat type
        sport: Sport code
        context_flags: Optional context penalty flags
        
    Returns:
        EdgeDiagnostic with full breakdown
    """
    # Calculate each diagnostic component
    z_diag = calculate_z_score(line, mu, sigma, direction)
    penalty_attr = calculate_penalty_attribution(
        raw_probability, final_probability, stat, sigma, direction, context_flags
    )
    tier_label = get_tier_label(final_probability, sport)
    
    # Build summary line
    dir_word = "OVER" if direction.lower() == "higher" else "UNDER"
    summary = (
        f"z={z_diag.z_score:+.2f}σ | "
        f"Raw {raw_probability:.0f}% → Final {final_probability:.0f}% (−{penalty_attr.total_penalty_pct:.0f}%) | "
        f"Tier: {tier_label.tier}"
    )
    
    return EdgeDiagnostic(
        z_score_diagnostic=z_diag,
        penalty_attribution=penalty_attr,
        tier_label=tier_label,
        diagnostic_summary=summary
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FORMATTING FUNCTIONS (for report rendering)
# ═══════════════════════════════════════════════════════════════════════════════

def format_z_score_line(z_diag: ZScoreDiagnostic) -> str:
    """Format z-score for report display."""
    return f"z = {z_diag.z_score:+.2f}σ ({z_diag.interpretation})"


def format_penalty_breakdown(penalty: PenaltyAttribution) -> List[str]:
    """Format penalty breakdown as report lines."""
    lines = [
        f"Penalty Breakdown:",
    ]
    for detail in penalty.penalty_details:
        lines.append(f"  • {detail}")
    lines.append(f"  ─────────────────────")
    lines.append(f"  Total: −{penalty.total_penalty_pct:.1f}% ({penalty.raw_probability:.1f}% → {penalty.final_probability:.1f}%)")
    return lines


def format_tier_label(tier: TierLabel) -> str:
    """Format tier label for report display."""
    if tier.tier_ceiling:
        return f"[{tier.tier}] ({tier.tier_floor:.0f}%-{tier.tier_ceiling:.0f}%)"
    else:
        return f"[{tier.tier}] (≥{tier.tier_floor:.0f}%)"


def format_diagnostic_block(diag: EdgeDiagnostic, compact: bool = False) -> List[str]:
    """
    Format complete diagnostic as report block.
    
    Args:
        diag: EdgeDiagnostic object
        compact: If True, use single-line format
        
    Returns:
        List of formatted lines
    """
    if compact:
        return [diag.diagnostic_summary]
    
    lines = []
    
    # Z-score line
    lines.append(f"  │  σ-Distance:  {format_z_score_line(diag.z_score_diagnostic)}")
    
    # Penalty breakdown
    if diag.penalty_attribution.total_penalty_pct > 0:
        lines.append(f"  │  {format_penalty_breakdown(diag.penalty_attribution)[0]}")
        for detail in diag.penalty_attribution.penalty_details:
            lines.append(f"  │    • {detail}")
    
    # Tier label
    lines.append(f"  │  Tier:        {format_tier_label(diag.tier_label)}")
    
    return lines


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("EDGE DIAGNOSTICS TEST")
    print("=" * 70)
    
    # Test case: Brunson UNDER 28.5
    print("\n--- Test Case: Brunson Points UNDER 28.5 ---")
    diag = generate_edge_diagnostic(
        line=28.5,
        mu=22.1,
        sigma=12.18,
        direction="lower",
        raw_probability=68.4,
        final_probability=55.2,
        stat="points",
        sport="nba"
    )
    
    print(f"\nSummary: {diag.diagnostic_summary}")
    print("\nFull Breakdown:")
    for line in format_diagnostic_block(diag):
        print(line)
    
    # Test case: Bey Points OVER 15.5
    print("\n--- Test Case: Bey Points OVER 15.5 ---")
    diag2 = generate_edge_diagnostic(
        line=15.5,
        mu=21.4,
        sigma=9.28,
        direction="higher",
        raw_probability=47.6,
        final_probability=38.4,
        stat="points",
        sport="nba"
    )
    
    print(f"\nSummary: {diag2.diagnostic_summary}")
    print(f"\nZ-score interpretation: {diag2.z_score_diagnostic.interpretation}")
    
    # Test tier labeling
    print("\n--- Tier Labeling Tests ---")
    for conf in [85, 72, 58, 45]:
        tier = get_tier_label(conf, "nba")
        print(f"  {conf}% → {format_tier_label(tier)}")
    
    print("\n[Done]")
