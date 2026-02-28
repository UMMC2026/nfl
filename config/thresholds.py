"""
THRESHOLDS.PY — Single Source of Truth for Tier Boundaries

GOVERNANCE: This file is the CANONICAL definition of tier thresholds.
All other modules (tiers.py, validate_output.py, render gates) MUST import from here.

DO NOT define tier thresholds anywhere else.
"""
from typing import Optional, Dict, Tuple, Union

import json
import os
from pathlib import Path

# =============================================================================
# TIER THRESHOLDS (Probability → Tier Assignment)
# =============================================================================
# SOP v2.4 CANONICAL THRESHOLDS - DO NOT MODIFY WITHOUT SOP UPDATE

TIERS: Dict[str, float] = {
    "SLAM": 0.80,      # ≥80% confidence (SOP v2.4)
    "STRONG": 0.65,    # ≥65% confidence (SOP v2.4)
    "LEAN": 0.55,      # ≥55% confidence (SOP v2.4)
    "SPEC": 0.50,      # ≥50% confidence (research only)
    "AVOID": 0.0,      # <50% (no edge)
}

# Sport-specific overrides (stricter or relaxed)
# AI ENGINEER REVIEW 2026-02-05: Tightened thresholds based on calibration analysis
# PHASE 5B UPDATE 2026-02-05: Added tournament-tier specific overrides
SPORT_TIER_OVERRIDES = {
    "CBB": {
        "SLAM": None,      # DISABLED for CBB — too volatile
        "STRONG": 0.70,    # Stricter: 70% vs 65%
        "LEAN": 0.60,      # Stricter: 60% vs 55%
    },
    "TENNIS": {
        # Base tennis thresholds (used for ATP 250/500 and Challengers)
        "SLAM": 0.82,      # Slightly higher due to variance
        "STRONG": 0.68,
        "LEAN": 0.58,
    },
    # PHASE 5B: Tennis tournament tier overrides
    "TENNIS_GRAND_SLAM": {
        # Grand Slams (Australian, French, Wimbledon, US Open)
        # Elite fields, more predictable, best-of-5 format (men)
        "SLAM": 0.80,      # ENABLED at 80% — elite field, predictable
        "STRONG": 0.66,    # Slightly relaxed
        "LEAN": 0.56,      # Slightly relaxed
    },
    "TENNIS_MASTERS": {
        # ATP Masters 1000 events (Miami, Monte Carlo, etc.)
        # Strong fields, top-32 seeds, more stable
        "SLAM": 0.80,      # ENABLED at 80% — quality field
        "STRONG": 0.67,
        "LEAN": 0.57,
    },
    "TENNIS_CHALLENGER": {
        # Challenger events — thin data, volatile
        "SLAM": None,      # DISABLED — too volatile
        "STRONG": 0.72,    # Stricter: require 72%
        "LEAN": 0.62,      # Stricter: require 62%
    },
    "NFL": {
        # AI ENGINEER FIX P3-A: NFL SLAM tightened from 0.80 to 0.85
        # Reason: Wide confidence intervals on game-level projections
        # Weather + injury variance requires stricter threshold
        "SLAM": 0.85,      # TIGHTENED: 85% vs 80% base (was too loose)
        "STRONG": 0.67,    # Slightly stricter: 67% vs 65%
        "LEAN": 0.57,      # Slightly stricter: 57% vs 55%
        # Weather penalty: Additional -5% when wind > 15mph (applied in nfl pipeline)
        # B2B penalty: Additional -3% for short rest (applied in nfl pipeline)
    },
    "NHL": {
        "SLAM": None,      # DISABLED for NHL — goalie variance too high
        "STRONG": 0.64,    # Stricter: 64% vs 65%
        "LEAN": 0.58,      # Stricter: 58% vs 55%
    },
    "GOLF": {
        # Base golf thresholds (used for web.com, Korn Ferry)
        "SLAM": None,      # DISABLED for Golf — tournament variance too high
        "STRONG": 0.65,    # Standard: 65%
        "LEAN": 0.55,      # Standard: 55%
    },
    # PHASE 5B: Golf tournament tier overrides
    "GOLF_MAJOR": {
        # The 4 Majors (Masters, PGA Championship, US Open, The Open)
        # Elite field (top 50 OWGR), most predictable
        "SLAM": 0.85,      # ENABLED at 85% — elite field, high bar
        "STRONG": 0.67,    # Slightly stricter
        "LEAN": 0.57,      # Slightly stricter
    },
    "GOLF_PGA_TOUR": {
        # Regular PGA Tour events (Players, signature events, etc.)
        # Quality field, reasonable predictability
        "SLAM": 0.85,      # ENABLED at 85% — requires high confidence
        "STRONG": 0.66,
        "LEAN": 0.56,
    },
    "GOLF_KORN_FERRY": {
        # Korn Ferry Tour (developmental, thin data)
        "SLAM": None,      # DISABLED — too volatile
        "STRONG": 0.70,    # Stricter
        "LEAN": 0.60,      # Stricter
    },
    "SOCCER": {
        # AI ENGINEER ADD: Soccer-specific thresholds
        "SLAM": 0.82,      # High threshold due to low-scoring variance
        "STRONG": 0.66,    # Slightly stricter
        "LEAN": 0.56,      # Slightly stricter
    },
}

# =============================================================================
# OPTIONAL THRESHOLD OVERRIDES (Runtime)
# =============================================================================
# Auto-calibration and ops workflows can write a JSON overrides file rather than
# mutating this canonical module. This keeps the SOP defaults intact while
# allowing controlled, reversible tuning.

_OVERRIDES_CACHE: Dict[str, object] = {
    "mtime": None,
    "data": {},
}


def _get_overrides_path() -> Path:
    # Allow ops to redirect via env var.
    env = (os.getenv("UFA_THRESHOLD_OVERRIDES_PATH") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "threshold_overrides.json"


def _load_threshold_overrides() -> Dict[str, Dict[str, Optional[float]]]:
    """Load threshold overrides from JSON.

    Supported formats:
      1) {"overrides": {"NBA": {"STRONG": 0.66, "LEAN": 0.56}}}
      2) {"NBA": {"STRONG": 0.66, "LEAN": 0.56}}

    Values may be floats in [0, 1] or percent-like numbers (e.g., 66 => 0.66).
    """
    path = _get_overrides_path()
    try:
        if not path.exists():
            _OVERRIDES_CACHE["mtime"] = None
            _OVERRIDES_CACHE["data"] = {}
            return {}
        mtime = path.stat().st_mtime
        if _OVERRIDES_CACHE.get("mtime") == mtime and isinstance(_OVERRIDES_CACHE.get("data"), dict):
            return _OVERRIDES_CACHE["data"]  # type: ignore[return-value]

        raw = json.loads(path.read_text(encoding="utf-8"))
        mapping = raw.get("overrides") if isinstance(raw, dict) and "overrides" in raw else raw
        if not isinstance(mapping, dict):
            _OVERRIDES_CACHE["mtime"] = mtime
            _OVERRIDES_CACHE["data"] = {}
            return {}

        overrides: Dict[str, Dict[str, Optional[float]]] = {}
        for sport, tiers in mapping.items():
            if not isinstance(sport, str) or not isinstance(tiers, dict):
                continue
            s = sport.strip().upper()
            overrides.setdefault(s, {})
            for tier, val in tiers.items():
                if not isinstance(tier, str):
                    continue
                t = tier.strip().upper()
                if val is None:
                    overrides[s][t] = None
                    continue
                try:
                    f = float(val)
                except Exception:
                    continue
                if f > 1.0:
                    f = f / 100.0
                if 0.0 <= f <= 1.0:
                    overrides[s][t] = round(f, 4)

        _OVERRIDES_CACHE["mtime"] = mtime
        _OVERRIDES_CACHE["data"] = overrides
        return overrides
    except Exception:
        # Never hard-fail threshold helpers.
        return {}

# =============================================================================
# CONFIDENCE CAPS BY STAT CLASS
# =============================================================================

CONFIDENCE_CAPS = {
    "core": 0.75,              # Base SLAM ceiling (unlocks to 0.80 with usage gate)
    "volume_micro": 0.68,      # Alt-stats: attempts, completions
    "sequence_early": 0.65,    # Early-sequence: first X minutes
    "event_binary": 0.55,      # Binary events: longest rush, dunks
}

# Usage/minutes requirements for unlocking CORE stat high confidence (80%)
CORE_UNLOCK_THRESHOLDS = {
    "usage_rate_min": 25.0,    # Must have ≥25% usage rate
    "minutes_min": 30.0,       # Must play ≥30 minutes projected
}

# =============================================================================
# VALIDATION CAPS (Hard limits for edge probability)
# =============================================================================

VALIDATION_CAPS = {
    "core_max": 0.70,          # Core stats max (before usage unlock)
    "alt_max": 0.65,           # Alt stats max
    "td_max": 0.55,            # Touchdown/binary max
}

# =============================================================================
# CONFIDENCE COMPRESSION (SOP Rule C1)
# =============================================================================
# When projection is far from line, cap confidence to prevent false SLAMs

COMPRESSION_THRESHOLD_STDDEV = 2.5      # If |projection - line| > 2.5σ, compress
COMPRESSED_MAX_CONFIDENCE = 0.65        # Cap at 65% for outlier projections

# =============================================================================
# KELLY CRITERION SIZING (SOP Rule)
# =============================================================================

KELLY_FRACTION = 0.25  # Fractional Kelly for safety (25% of full Kelly)

# Maximum bet size by tier (in units)
MAX_BET_BY_TIER = {
    "SLAM": 2.0,
    "STRONG": 1.5,
    "LEAN": 1.0,
    "SPEC": 0.5,
    "AVOID": 0.0,
    "NO_PLAY": 0.0,
}

# Standard vig assumption for odds calculation (-110 implies 52.4%)
STANDARD_IMPLIED_PROB = 0.524

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tier_threshold(tier: str, sport: Optional[str] = None) -> float:
    """
    Get threshold for a tier, with sport-specific overrides.
    
    Args:
        tier: SLAM, STRONG, LEAN, AVOID
        sport: Optional sport code (NBA, NFL, CBB, TENNIS)
    
    Returns:
        Probability threshold (0.0 - 1.0)
    
    Raises:
        ValueError: If tier is disabled for sport (e.g., CBB SLAM)
    """
    sport_u = sport.upper() if sport else None
    tier_u = tier.upper()

    # 1) Canonical sport overrides
    if sport_u and sport_u in SPORT_TIER_OVERRIDES:
        override = SPORT_TIER_OVERRIDES[sport_u].get(tier_u)
        if override is None and tier_u in SPORT_TIER_OVERRIDES[sport_u]:
            raise ValueError(f"{tier} tier is DISABLED for {sport}")
        if override is not None:
            base = float(override)
        else:
            base = float(TIERS.get(tier_u, 0.0))
    else:
        base = float(TIERS.get(tier_u, 0.0))

    # 2) Runtime overrides (GLOBAL then sport-specific)
    overrides = _load_threshold_overrides()
    for key in ("GLOBAL", sport_u):
        if not key:
            continue
        if key in overrides and tier_u in overrides[key]:
            val = overrides[key][tier_u]
            if val is None:
                raise ValueError(f"{tier} tier is DISABLED for {key}")
            return float(val)

    return base


def get_all_thresholds(sport: Optional[str] = None) -> Dict[str, Optional[float]]:
    """Get all tier thresholds for a sport."""
    sport_u = sport.upper() if sport else None
    result: Dict[str, Optional[float]] = dict(TIERS)

    # Canonical sport overrides
    if sport_u and sport_u in SPORT_TIER_OVERRIDES:
        for tier, val in SPORT_TIER_OVERRIDES[sport_u].items():
            result[tier] = None if val is None else float(val)

    # Runtime overrides: apply GLOBAL first, then sport-specific.
    overrides = _load_threshold_overrides()
    for key in ("GLOBAL", sport_u):
        if not key:
            continue
        block = overrides.get(key)
        if not isinstance(block, dict):
            continue
        for tier, val in block.items():
            result[tier] = val

    return result


def implied_tier(probability: float, sport: Optional[str] = None) -> str:
    """
    Determine tier from probability.
    
    Args:
        probability: 0.0 - 1.0
        sport: Optional sport code
    
    Returns:
        Tier string (SLAM, STRONG, LEAN, AVOID)
    """
    thresholds = get_all_thresholds(sport)
    
    # Check in order: SLAM → STRONG → LEAN → AVOID
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


def validate_tier_consistency(probability: float, declared_tier: str, sport: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate that declared tier matches probability.
    
    Returns:
        (is_valid, error_message)
    """
    expected = implied_tier(probability, sport)
    
    if expected != declared_tier:
        return False, f"Tier mismatch: prob={probability:.3f} implies {expected}, declared {declared_tier}"
    
    return True, ""


# =============================================================================
# CONFIDENCE COMPRESSION (SOP Rule C1)
# =============================================================================

def apply_confidence_compression(
    confidence: float,
    projection: float,
    line: float,
    std_dev: float
) -> Tuple[float, bool, str]:
    """
    Apply confidence compression when projection is far from line.
    
    SOP Rule C1: If |projection - line| > 2.5 × std_dev → confidence ≤ 65%
    
    Args:
        confidence: Raw confidence (0.0 - 1.0)
        projection: Model projection
        line: Market line
        std_dev: Standard deviation of projection
    
    Returns:
        (adjusted_confidence, was_compressed, reason)
    """
    if std_dev <= 0:
        return confidence, False, ""
    
    distance = abs(projection - line)
    distance_in_std = distance / std_dev
    
    if distance_in_std > COMPRESSION_THRESHOLD_STDDEV:
        if confidence > COMPRESSED_MAX_CONFIDENCE:
            reason = f"Compressed from {confidence:.1%} to {COMPRESSED_MAX_CONFIDENCE:.1%}: projection {projection:.1f} is {distance_in_std:.1f}σ from line {line}"
            return COMPRESSED_MAX_CONFIDENCE, True, reason
    
    return confidence, False, ""


# =============================================================================
# KELLY CRITERION BET SIZING
# =============================================================================

def compute_kelly_bet_size(
    confidence: float,
    tier: str,
    implied_prob: float = None
) -> Dict[str, float]:
    """
    Calculate Kelly criterion bet size.
    
    Kelly = (bp - q) / b
    where b = payout ratio, p = win prob, q = lose prob
    
    Args:
        confidence: Win probability (0.0 - 1.0)
        tier: SLAM, STRONG, LEAN, etc.
        implied_prob: Market implied probability (default 0.524 for -110)
    
    Returns:
        {
            "kelly_full": full Kelly fraction,
            "kelly_adjusted": fractional Kelly (25%),
            "recommended_units": capped by tier,
            "max_units_for_tier": tier maximum,
            "edge_percent": edge over market
        }
    """
    implied = implied_prob or STANDARD_IMPLIED_PROB
    
    # At -110, payout is 0.909 for a 1 unit stake
    payout_ratio = 0.909  # Decimal odds - 1
    
    p = confidence
    q = 1 - confidence
    b = payout_ratio
    
    # Kelly formula
    kelly_full = ((b * p) - q) / b if b > 0 else 0
    kelly_full = max(0, kelly_full)
    
    # Apply fractional Kelly
    kelly_adjusted = kelly_full * KELLY_FRACTION
    
    # Cap by tier maximum
    max_bet = MAX_BET_BY_TIER.get(tier.upper(), 0)
    recommended_units = min(kelly_adjusted, max_bet)
    recommended_units = round(recommended_units, 2)
    
    # Edge calculation
    edge_percent = (confidence - implied) * 100
    
    return {
        "kelly_full": round(kelly_full, 4),
        "kelly_adjusted": round(kelly_adjusted, 4),
        "recommended_units": recommended_units,
        "max_units_for_tier": max_bet,
        "edge_percent": round(edge_percent, 2),
    }


# =============================================================================
# CORRELATED EDGE CHECK
# =============================================================================

def check_correlated_not_tiered(
    tier: str,
    has_correlated_lines: bool
) -> Tuple[bool, str]:
    """
    SOP Rule B2: Correlated alternatives must NOT be tiered.
    
    Args:
        tier: Declared tier (SLAM, STRONG, LEAN, etc.)
        has_correlated_lines: Whether edge has correlated alternatives
    
    Returns:
        (is_valid, error_message)
    """
    actionable_tiers = {"SLAM", "STRONG", "LEAN"}
    
    if has_correlated_lines and tier.upper() in actionable_tiers:
        return False, f"Edge has correlated lines but is tiered as {tier} — should be CORRELATED_ALTERNATIVE"
    
    return True, ""
