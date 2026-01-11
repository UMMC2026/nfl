import math
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass

# Optional alt-stats layer (Phase B)
try:
    from ufa.analysis.alt_stats import model_alt_stat
    ALT_STATS_AVAILABLE = True
except ImportError:
    ALT_STATS_AVAILABLE = False

# ============================================================================
# GOVERNANCE LAYER: STAT CLASSIFICATION & REGIME AWARENESS
# ============================================================================

# Canonical stat classification (NFL + NBA)
STAT_CLASS: Dict[str, str] = {
    # CORE (traditional props - no regime gate)
    "points": "core",
    "rebounds": "core",
    "assists": "core",
    "pass_yards": "core",
    "rush_yards": "core",
    "receiving_yards": "core",
    "pts+reb": "core",
    "pts+ast": "core",
    "pts+reb+ast": "core",
    "reb+ast": "core",
    
    # VOLUME-DERIVED (alt-stats - capped at 68%)
    "pass_attempts": "volume_micro",
    "rush_attempts": "volume_micro",
    "fg_attempted": "volume_micro",
    "three_pt_attempted": "volume_micro",
    "two_pt_attempted": "volume_micro",
    "receptions": "volume_micro",
    "targets": "volume_micro",
    "completions": "volume_micro",
    
    # EARLY-SEQUENCE (alt-stats - early-live only, capped at 65%)
    "points_first_3_minutes": "sequence_early",
    "assists_first_3_minutes": "sequence_early",
    "rebounds_first_3_minutes": "sequence_early",
    "completions_first_10_attempts": "sequence_early",
    "rush_yards_first_5_attempts": "sequence_early",
    "receiving_yards_first_2_receptions": "sequence_early",
    
    # EVENT / BINARY (alt-stats - restricted, capped at 55%)
    "longest_rush": "event_binary",
    "longest_reception": "event_binary",
    "dunks": "event_binary",
    "blocks_steals": "event_binary",
    "turnovers": "event_binary",
    "quarters_with_3_points": "event_binary",
}

# Regime-aware stat activation matrix
STAT_REGIME_ALLOWED = {
    "core": {"PREGAME", "EARLY_LIVE", "MID_LIVE", "BLOWOUT"},
    "volume_micro": {"PREGAME", "EARLY_LIVE", "MID_LIVE"},
    "sequence_early": {"EARLY_LIVE"},
    "event_binary": {"PREGAME", "EARLY_LIVE"},
}

# Confidence caps by stat class
# CORE stats can reach 80% ONLY if player meets usage/minutes thresholds
# Otherwise capped at 75% (baseline SLAM ceiling)
CONFIDENCE_CAPS = {
    "core": 0.75,           # Base SLAM ceiling (unlocks to 80% with usage gate)
    "volume_micro": 0.68,
    "sequence_early": 0.65,
    "event_binary": 0.55,
}

# Usage/minutes requirements for unlocking CORE stat high confidence (80%)
CORE_UNLOCK_THRESHOLDS = {
    "usage_rate_min": 25.0,    # Must have ≥25% usage rate
    "minutes_min": 30.0,       # Must play ≥30 minutes projected
}


@dataclass
class GameState:
    """Minimal game state for regime detection."""
    is_live: bool = False
    minutes_elapsed: Optional[float] = None
    plays_elapsed: Optional[int] = None
    score_diff: int = 0
    quarter: int = 0


def detect_regime(game: GameState = None) -> str:
    """
    Determine game regime (pregame, early-live, mid-game, blowout).
    Used to gate alt-stats and early-sequence bets.
    """
    if game is None:
        return "PREGAME"
    
    if not game.is_live:
        return "PREGAME"
    
    # NBA: early-live is first 3 minutes
    if game.minutes_elapsed is not None:
        if game.minutes_elapsed <= 3:
            return "EARLY_LIVE"
    
    # NFL: early-live is first 10 plays
    if game.plays_elapsed is not None:
        if game.plays_elapsed <= 10:
            return "EARLY_LIVE"
    
    # Blowout detection (15+ point margin)
    if abs(game.score_diff) >= 15:
        return "BLOWOUT"
    
    return "MID_LIVE"


def apply_confidence_governor(
    p_hit: float,
    stat_class: str,
    sample_size: int = 10,
    usage_rate: Optional[float] = None,
    minutes_projected: Optional[float] = None
) -> float:
    """
    Apply confidence cap and sample-size shrinkage.
    
    CORE stats unlock to 80% cap if player meets usage/minutes thresholds:
    - usage_rate >= 25%
    - minutes_projected >= 30
    
    Otherwise capped at default levels per stat class.
    
    Args:
        p_hit: Raw probability from model
        stat_class: One of {core, volume_micro, sequence_early, event_binary}
        sample_size: Number of historical data points
        usage_rate: Player usage rate (optional, for CORE unlock)
        minutes_projected: Projected minutes (optional, for CORE unlock)
    
    Returns:
        Governed probability (capped + shrunk)
    """
    cap = CONFIDENCE_CAPS.get(stat_class, 0.68)
    
    # CORE stat unlock: 80% cap if usage/minutes thresholds met
    if stat_class == "core":
        if (usage_rate is not None and 
            minutes_projected is not None and
            usage_rate >= CORE_UNLOCK_THRESHOLDS["usage_rate_min"] and
            minutes_projected >= CORE_UNLOCK_THRESHOLDS["minutes_min"]):
            cap = 0.80  # Unlock high confidence for volume CORE stats
    
    # Bayesian-style shrinkage: less data = more shrinkage toward 50%
    if sample_size < 10:
        p_hit *= 0.65
    elif sample_size < 20:
        p_hit *= 0.80
    elif sample_size < 30:
        p_hit *= 0.90
    # else: full confidence (sample_size >= 30)
    
    return min(p_hit, cap)


def correlation_penalty(stat_classes: List[str]) -> float:
    """
    Apply penalty to EV for same-class stacking (parlays).
    Prevents overstacking early-sequence or event stats.
    
    Args:
        stat_classes: List of stat classes in proposed entry
    
    Returns:
        Penalty multiplier (< 1.0 reduces EV)
    """
    penalty = 1.0
    
    # Penalize multiple early-sequence stats in same entry
    if stat_classes.count("sequence_early") > 1:
        penalty *= 0.85
    
    # Penalize multiple event/binary stats in same entry
    if stat_classes.count("event_binary") > 1:
        penalty *= 0.80
    
    return penalty


def _mean_std(xs: List[float]) -> Tuple[float, float]:
    n = len(xs)
    if n < 2:
        raise ValueError("Need at least 2 recent values to estimate sigma.")
    mu = sum(xs) / n
    var = sum((x - mu) ** 2 for x in xs) / (n - 1)
    sigma = math.sqrt(max(var, 1e-9))
    return mu, sigma

def _norm_cdf(x: float, mu: float, sigma: float) -> float:
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))

def prob_hit(line: float, direction: str, *, recent_values: Optional[List[float]]=None,
             mu: Optional[float]=None, sigma: Optional[float]=None,
             stat_name: Optional[str]=None, sample_size: Optional[int]=None,
             game: Optional[GameState]=None,
             usage_rate: Optional[float]=None,
             minutes_projected: Optional[float]=None) -> float:
    """
    Normal approximation MVP with optional governance layer.
    
    Args:
        line: Prop line (e.g., 24.5 points)
        direction: "higher" or "lower"
        recent_values: List of recent game values (for mu/sigma inference)
        mu: Mean (if recent_values not provided)
        sigma: Std dev (if recent_values not provided)
        stat_name: Name of stat (e.g., "points") - triggers classification lookup
        sample_size: Number of historical games (optional; inferred from recent_values)
        game: GameState object (optional; enables regime gating)
        usage_rate: Player usage rate (optional; unlocks CORE stat 80% cap)
        minutes_projected: Projected minutes (optional; unlocks CORE stat 80% cap)
    
    Returns:
        Governed probability (0.0 to 1.0), or None if stat suppressed by regime
    """
    if recent_values is not None:
        mu, sigma = _mean_std(recent_values)
        if sample_size is None:
            sample_size = len(recent_values)
    else:
        if mu is None or sigma is None:
            raise ValueError("Provide either recent_values OR (mu and sigma).")
        if sample_size is None:
            sample_size = 10  # Default assumption
        sigma = max(float(sigma), 1e-6)
    
    # Regime gating (suppress stat if not allowed)
    if stat_name is not None:
        stat_class = STAT_CLASS.get(stat_name, "core")
        regime = detect_regime(game)
        
        if regime not in STAT_REGIME_ALLOWED[stat_class]:
            return None  # Stat suppressed by regime
        
        # Apply confidence governor
        p_under_or_equal = _norm_cdf(float(line), float(mu), float(sigma))
        if direction == "lower":
            raw_p = float(p_under_or_equal)
        elif direction == "higher":
            raw_p = float(1.0 - p_under_or_equal)
        else:
            raise ValueError("direction must be 'higher' or 'lower'")
        
        # Apply cap + shrinkage (with usage/minutes for CORE unlock)
        return apply_confidence_governor(
            raw_p, stat_class, sample_size,
            usage_rate=usage_rate,
            minutes_projected=minutes_projected
        )
    
    # No regime gating: use original logic (backward compatible)
    p_under_or_equal = _norm_cdf(float(line), float(mu), float(sigma))
    if direction == "lower":
        return float(p_under_or_equal)
    if direction == "higher":
        return float(1.0 - p_under_or_equal)
    raise ValueError("direction must be 'higher' or 'lower'")


# ============================================================================
# PHASE B: ALT-STATS INTEGRATION POINT (OPTIONAL)
# ============================================================================
# To use alt-stats modeling (volume_micro, sequence_early, event_binary):
#
# 1. In daily_pipeline.py or your calling code:
#    - Build context object (alt_stats.VolumeMicroContext, etc.)
#    - Call: result = model_alt_stat(line, stat_class, ctx)
#    - Extract: raw_p, expected, notes = result["raw_p_hit"], result["expected"], result["notes"]
#
# 2. Apply governance:
#    p_governed = apply_confidence_governor(raw_p, stat_class, sample_size)
#
# 3. Proceed as normal (calibration, tiering, cheatsheet)
#
# Alt-stats flow through the same governance gates (caps, shrinkage, regime restrictions).
# No modifications to core logic needed.
#
# Example:
#    from ufa.analysis.alt_stats import build_nfl_volume_context, model_alt_stat
#
#    ctx = build_nfl_volume_context(
#        player="Lamar Jackson",
#        snap_count=65,
#        snaps_per_attempt=1.9,
#        team_pace=1.05
#    )
#    result = model_alt_stat(line=34.5, stat_class="volume_micro", ctx=ctx)
#    p_hit = apply_confidence_governor(result["raw_p_hit"], "volume_micro", sample_size=15)
#    # Continue with calibration...
# ============================================================================
