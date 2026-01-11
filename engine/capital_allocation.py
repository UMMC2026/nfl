"""
Capital Allocation Engine

PURPOSE:
Controlled exposure based on policy, not guesses.
Probabilities inform sizing; rules control risk.

PRINCIPLES:
* Capital is allocated by POLICY, not confidence
* Tier decides eligibility, Kelly nudges (doesn't dictate)
* Hard bounds prevent ruin, floors prevent over-filtering
* Daily caps prevent aggregate overexposure
* Correlation limits prevent silent concentration risk
* Must not run if bias detected, ANALYSIS mode, or gates failed

USAGE:
    from engine.capital_allocation import allocate_capital
    
    allocated = allocate_capital(
        picks=validated_picks,
        bankroll=100.0,
        mode="BROADCAST",
        bias_detected=False
    )

ENFORCEMENT:
* Blocked if pipeline_mode != "BROADCAST"
* Blocked if bias_detected == True
* Blocked if regression tests failed
"""

from typing import List, Dict, Any, Tuple
from collections import defaultdict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# GLOBAL RISK BUDGET (POLICY LAYER)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Bankroll
DEFAULT_BANKROLL = 100.0        # Units (not dollars)

# Risk limits (percentage of bankroll)
MAX_DAILY_RISK = 0.08           # 8% of bankroll per day
MAX_SINGLE_BET = 0.025          # 2.5% cap per pick
MIN_SINGLE_BET = 0.005          # 0.5% floor

# Tier-based base allocation (percentage of bankroll)
TIER_BASE_UNITS = {
    "SLAM": 0.020,              # 2.0% base
    "STRONG": 0.012,            # 1.2% base
    "LEAN": 0.006,              # 0.6% base
    "NO PLAY": 0.0,             # Zero allocation
}

# Kelly fraction (conservative)
KELLY_FRACTION = 0.25           # 25% of full Kelly (never use full Kelly)

# Correlation limits
MAX_PLAYER_EXPOSURE = 1         # Max 1 pick per player (already enforced in primaries)
MAX_TEAM_EXPOSURE_PCT = 0.30    # Max 30% of daily capital on single team


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FRACTIONAL KELLY MODIFIER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def fractional_kelly(prob: float, odds_decimal: float, fraction: float = KELLY_FRACTION) -> float:
    """
    Calculate fractional Kelly criterion for bet sizing.
    
    Kelly formula: k = (b*p - q) / b
    where:
        b = decimal odds - 1 (net odds)
        p = probability of winning
        q = 1 - p (probability of losing)
    
    We NEVER use full Kelly. Conservative fraction (0.25) applied.
    
    Args:
        prob: Probability of hit (0-1)
        odds_decimal: Decimal odds (e.g., 1.91 for -110)
        fraction: Kelly fraction to use (default 0.25)
    
    Returns:
        Fractional Kelly percentage (0-1), or 0 if negative edge
    
    Notes:
        * Kelly is ADVISORY, not authoritative
        * Negative Kelly → 0 allocation (no bet)
        * Used as adjustment to tier base, not standalone sizing
    """
    if prob <= 0 or prob >= 1:
        return 0.0
    
    if odds_decimal <= 1:
        return 0.0
    
    b = odds_decimal - 1  # Net odds
    q = 1 - prob
    
    # Full Kelly
    k = (b * prob - q) / b
    
    # Apply conservative fraction
    fractional_k = max(0.0, k * fraction)
    
    return fractional_k


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# POSITION SIZE CALCULATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def compute_position_size(pick: Dict[str, Any], bankroll: float) -> Tuple[float, Dict[str, Any]]:
    """
    Calculate position size for a single pick.
    
    Process:
    1. Get tier base allocation
    2. Calculate Kelly adjustment
    3. Apply hard bounds (MIN/MAX)
    4. Convert to units
    
    Args:
        pick: Pick dictionary with tier, probability, odds
        bankroll: Current bankroll in units
    
    Returns:
        Tuple of (units, allocation_context_dict)
        
    Allocation context includes:
        * tier: Confidence tier
        * probability: Final probability
        * odds_decimal: Decimal odds
        * base_pct: Tier base percentage
        * kelly_pct: Kelly adjustment percentage
        * raw_pct: Base + Kelly before bounds
        * final_pct: After MIN/MAX bounds
        * units: Final allocation in units
        * capped: Whether MAX_SINGLE_BET was applied
        * floored: Whether MIN_SINGLE_BET was applied
    """
    tier = pick.get("confidence_tier", "NO PLAY")
    prob = pick.get("probability", 0.0)
    
    # Default odds if not provided (assume -110 / 1.91)
    odds_decimal = pick.get("odds_decimal", 1.91)
    
    # NO PLAY → zero allocation
    if tier not in TIER_BASE_UNITS or tier == "NO PLAY":
        return 0.0, {
            "tier": tier,
            "probability": prob,
            "odds_decimal": odds_decimal,
            "base_pct": 0.0,
            "kelly_pct": 0.0,
            "raw_pct": 0.0,
            "final_pct": 0.0,
            "units": 0.0,
            "capped": False,
            "floored": False,
            "reason": "NO PLAY tier"
        }
    
    # Tier base allocation
    base_pct = TIER_BASE_UNITS[tier]
    
    # Kelly adjustment
    kelly_pct = fractional_kelly(prob, odds_decimal, KELLY_FRACTION)
    
    # Combined sizing
    raw_pct = base_pct + kelly_pct
    
    # Apply hard bounds
    capped = raw_pct > MAX_SINGLE_BET
    floored = raw_pct < MIN_SINGLE_BET
    
    final_pct = raw_pct
    if capped:
        final_pct = MAX_SINGLE_BET
    elif floored:
        final_pct = MIN_SINGLE_BET
    
    # Convert to units
    units = round(final_pct * bankroll, 2)
    
    # Allocation context
    context = {
        "tier": tier,
        "probability": prob,
        "odds_decimal": odds_decimal,
        "base_pct": round(base_pct, 4),
        "kelly_pct": round(kelly_pct, 4),
        "raw_pct": round(raw_pct, 4),
        "final_pct": round(final_pct, 4),
        "units": units,
        "capped": capped,
        "floored": floored,
    }
    
    return units, context


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CORRELATION SAFETY (PORTFOLIO CONTROL)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def enforce_correlation_limits(picks: List[Dict[str, Any]], bankroll: float) -> List[Dict[str, Any]]:
    """
    Enforce correlation limits to prevent silent concentration risk.
    
    Limits:
    * Max 1 pick per player (should already be enforced by primaries)
    * Max 30% of daily capital on single team
    
    Args:
        picks: List of picks with units allocated
        bankroll: Current bankroll
    
    Returns:
        Picks list with correlation violations zeroed out
    
    Notes:
        * Player correlation already enforced in resolve_primaries
        * Team correlation enforced here as safety net
        * Violations logged in allocation_note field
    """
    # Track player exposure (safety check)
    player_exposure = defaultdict(list)
    
    # Track team exposure
    team_exposure = defaultdict(float)
    
    # First pass: track exposures
    for p in picks:
        player = p.get("player_name", "Unknown")
        team = p.get("team", "Unknown")
        units = p.get("units", 0.0)
        
        player_exposure[player].append(p)
        team_exposure[team] += units
    
    # Second pass: enforce limits
    for p in picks:
        player = p.get("player_name", "Unknown")
        team = p.get("team", "Unknown")
        units = p.get("units", 0.0)
        
        # Check player correlation (should already be enforced)
        if len(player_exposure[player]) > MAX_PLAYER_EXPOSURE:
            p["units"] = 0.0
            p["allocation_note"] = f"Dropped: Multiple picks on {player} (correlation)"
            continue
        
        # Check team correlation
        team_pct = team_exposure[team] / bankroll
        if team_pct > MAX_TEAM_EXPOSURE_PCT:
            p["units"] = 0.0
            p["allocation_note"] = f"Dropped: Team {team} exceeds {MAX_TEAM_EXPOSURE_PCT:.0%} cap ({team_pct:.1%})"
            continue
    
    return picks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DAILY EXPOSURE GOVERNOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def enforce_daily_cap(picks: List[Dict[str, Any]], bankroll: float) -> List[Dict[str, Any]]:
    """
    Enforce daily risk cap to prevent aggregate overexposure.
    
    Hard limit: MAX_DAILY_RISK (8%) of bankroll per day
    
    Args:
        picks: List of picks with units allocated
        bankroll: Current bankroll
    
    Returns:
        Picks list with violations zeroed out
    
    Notes:
        * Processes picks in order (first come, first served)
        * Once daily cap hit, all remaining picks dropped
        * No exceptions, no "just this once"
    """
    max_daily_units = bankroll * MAX_DAILY_RISK
    allocated = 0.0
    
    for p in picks:
        units = p.get("units", 0.0)
        
        if allocated + units > max_daily_units:
            # Daily cap exceeded
            p["units"] = 0.0
            p["allocation_note"] = f"Dropped: Daily risk cap ({MAX_DAILY_RISK:.0%}) exceeded"
        else:
            # Within cap
            allocated += units
    
    return picks


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CAPITAL ALLOCATION PIPELINE (MASTER FUNCTION)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def allocate_capital(
    picks: List[Dict[str, Any]],
    bankroll: float = DEFAULT_BANKROLL,
    mode: str = "ANALYSIS",
    bias_detected: bool = False
) -> List[Dict[str, Any]]:
    """
    Complete capital allocation pipeline.
    
    Process:
    1. Validate preconditions (mode, bias)
    2. Compute position sizes
    3. Enforce correlation limits
    4. Enforce daily cap
    5. Filter zero allocations
    
    Args:
        picks: List of validated picks (post-regression tests)
        bankroll: Current bankroll in units
        mode: Pipeline mode ("ANALYSIS" or "BROADCAST")
        bias_detected: Whether bias report flagged bias
    
    Returns:
        List of picks with capital allocated (units > 0 only)
    
    Raises:
        ValueError: If capital allocation blocked (bias, ANALYSIS mode, etc.)
    
    Notes:
        * Blocked if mode != "BROADCAST"
        * Blocked if bias_detected == True
        * Every pick includes capital_allocation audit trail
        * Only picks with units > 0 returned
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HARD STOPS (FAIL FAST)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    if mode != "BROADCAST":
        raise ValueError(
            "🚫 CAPITAL ALLOCATION BLOCKED\n"
            f"   Mode: {mode}\n"
            "   Capital allocation only allowed in BROADCAST mode\n"
            "   Run in BROADCAST mode with --mode broadcast"
        )
    
    if bias_detected:
        raise ValueError(
            "🚫 CAPITAL ALLOCATION BLOCKED\n"
            "   Bias detected in bias attribution report\n"
            "   Capital allocation disabled on biased runs\n"
            "   Fix bias before allocating capital"
        )
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 1: COMPUTE POSITION SIZES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    for p in picks:
        units, context = compute_position_size(p, bankroll)
        p["units"] = units
        p["capital_allocation"] = context
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 2: ENFORCE CORRELATION LIMITS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    picks = enforce_correlation_limits(picks, bankroll)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 3: ENFORCE DAILY CAP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    picks = enforce_daily_cap(picks, bankroll)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 4: FILTER ZERO ALLOCATIONS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    allocated = [p for p in picks if p.get("units", 0.0) > 0]
    
    return allocated


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ALLOCATION SUMMARY (REPORTING)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def summarize_allocation(picks: List[Dict[str, Any]], bankroll: float) -> Dict[str, Any]:
    """
    Generate allocation summary for reporting.
    
    Args:
        picks: List of allocated picks
        bankroll: Current bankroll
    
    Returns:
        Summary dict with:
            * total_picks: Number of picks allocated
            * total_units: Total units allocated
            * total_pct: Percentage of bankroll allocated
            * daily_cap_utilization: Percentage of daily cap used
            * tier_breakdown: Units by tier
            * avg_units_per_pick: Average allocation
    """
    total_picks = len(picks)
    total_units = sum(p.get("units", 0.0) for p in picks)
    total_pct = total_units / bankroll if bankroll > 0 else 0.0
    
    max_daily_units = bankroll * MAX_DAILY_RISK
    cap_utilization = total_units / max_daily_units if max_daily_units > 0 else 0.0
    
    # Tier breakdown
    tier_breakdown = defaultdict(float)
    for p in picks:
        tier = p.get("confidence_tier", "UNKNOWN")
        units = p.get("units", 0.0)
        tier_breakdown[tier] += units
    
    avg_units = total_units / total_picks if total_picks > 0 else 0.0
    
    return {
        "total_picks": total_picks,
        "total_units": round(total_units, 2),
        "total_pct": round(total_pct, 4),
        "daily_cap_pct": MAX_DAILY_RISK,
        "daily_cap_utilization": round(cap_utilization, 4),
        "tier_breakdown": dict(tier_breakdown),
        "avg_units_per_pick": round(avg_units, 2),
        "bankroll": bankroll,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

__all__ = [
    "allocate_capital",
    "summarize_allocation",
    "fractional_kelly",
    "compute_position_size",
    "enforce_correlation_limits",
    "enforce_daily_cap",
    # Constants
    "DEFAULT_BANKROLL",
    "MAX_DAILY_RISK",
    "MAX_SINGLE_BET",
    "MIN_SINGLE_BET",
    "TIER_BASE_UNITS",
    "KELLY_FRACTION",
]
