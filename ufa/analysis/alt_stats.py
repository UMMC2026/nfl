"""
Alternative Stats Modeling Layer (Phase B)

Models alt-stats separately from core props:
- Volume-derived (pass attempts, targets, receptions)
- Early-sequence (first N minutes / attempts)
- Event/binary (longest plays, dunks, etc.)

All results are routed through governance layer (stat_class caps, regime gates, shrinkage).

Supports: NFL + NBA
Architecture: Sport-agnostic, context-driven
Safety: Zero regression to core picks (separate code path)
"""

from math import exp
from typing import Optional, Dict, Any
from dataclasses import dataclass


# ============================================================================
# UTILITY
# ============================================================================

def logistic(x: float) -> float:
    """Logistic function for probability scaling."""
    if x > 100:  # Prevent overflow
        return 1.0
    if x < -100:
        return 0.0
    return 1.0 / (1.0 + exp(-x))


# ============================================================================
# CONTEXT DATACLASSES (SPORT-AGNOSTIC)
# ============================================================================

@dataclass
class VolumeMicroContext:
    """Context for volume-derived stats."""
    minutes: float                # Projected minutes
    attempts_per_min: float       # Average attempts per minute
    usage: float                  # Usage rate (0-1)
    pace: float                   # Pace multiplier (1.0 = league avg)
    opp_adjustment: float         # Opponent defensive factor


@dataclass
class SequenceEarlyContext:
    """Context for early-sequence stats (live only)."""
    full_game_projection: float   # Full-game expected value
    early_share: float            # % of game stats come early (0.18-0.30)
    starter_prob: float           # Probability starts (0-1)
    opp_opening_factor: float     # Opening script tendency


@dataclass
class EventBinaryContext:
    """Context for event/binary stats."""
    event_rate: float             # Rate per attempt/minute
    opportunities: float          # Expected attempts/plays


# ============================================================================
# VOLUME-DERIVED MICRO STATS (68% CAP)
# ============================================================================

def model_volume_micro(line: float, ctx: VolumeMicroContext) -> Dict[str, Any]:
    """
    Model volume-derived stats (pass attempts, targets, receptions, FG attempts).
    
    Formula:
        E[X] = minutes × attempts_per_min × usage × pace × opp_adjustment
    
    Args:
        line: The prop line (e.g., 34.5 pass attempts)
        ctx: VolumeMicroContext with all inputs
    
    Returns:
        Dict with expected, raw_p_hit, notes
    """
    expected = (
        ctx.minutes
        * ctx.attempts_per_min
        * ctx.usage
        * ctx.pace
        * ctx.opp_adjustment
    )
    
    # Normalize by sqrt(expected) for variance scaling
    std_dev = max(1.0, expected ** 0.5)
    z_score = (expected - line) / std_dev
    raw_p_hit = logistic(z_score)
    
    return {
        "expected": round(expected, 2),
        "raw_p_hit": raw_p_hit,
        "notes": [
            "Volume-derived",
            f"E[X]={expected:.1f}",
            f"Pace={ctx.pace:.2f}x"
        ]
    }


# ============================================================================
# EARLY-SEQUENCE STATS (65% CAP, EARLY-LIVE ONLY)
# ============================================================================

def model_sequence_early(line: float, ctx: SequenceEarlyContext) -> Dict[str, Any]:
    """
    Model early-sequence stats (first 3 min points, first 10 pass attempts, etc.).
    
    Formula:
        E[EarlyX] = FullGameProjection × EarlyShare × StarterProb × OppOpeningFactor
    
    Key insight:
    - Early_share ≈ 0.18-0.30 depending on stat
    - Starter_prob gates: bench players ≈ 0 confidence
    - Opp opening factor accounts for script tendency
    
    Args:
        line: The prop line
        ctx: SequenceEarlyContext
    
    Returns:
        Dict with expected, raw_p_hit, notes
    """
    expected = (
        ctx.full_game_projection
        * ctx.early_share
        * ctx.starter_prob
        * ctx.opp_opening_factor
    )
    
    # Lower std dev for early stats (more predictable window)
    std_dev = max(0.8, expected ** 0.5)
    z_score = (expected - line) / std_dev
    raw_p_hit = logistic(z_score)
    
    return {
        "expected": round(expected, 2),
        "raw_p_hit": raw_p_hit,
        "notes": [
            "Early-sequence",
            "Starter-weighted" if ctx.starter_prob == 1.0 else "Bench-risk",
            f"E[X]={expected:.1f}"
        ]
    }


# ============================================================================
# EVENT / BINARY STATS (55% CAP, RESTRICTED)
# ============================================================================

def model_event_binary(line: float, ctx: EventBinaryContext) -> Dict[str, Any]:
    """
    Model event/binary stats (longest rush, dunks, turnovers, etc.).
    
    Formula:
        P(at least one) = 1 - (1 - event_rate) ^ opportunities
        E[count] = event_rate × opportunities
    
    Key: Binary events don't scale linearly. Rarity is the edge.
    
    Args:
        line: The prop line (e.g., "longest rush > 23 yards")
        ctx: EventBinaryContext
    
    Returns:
        Dict with expected, raw_p_hit, notes
    """
    # Expected count
    expected = ctx.event_rate * ctx.opportunities
    
    # Probability of at least one event
    p_at_least_one = 1.0 - (1.0 - ctx.event_rate) ** max(1.0, ctx.opportunities)
    raw_p_hit = p_at_least_one
    
    return {
        "expected": round(expected, 2),
        "raw_p_hit": raw_p_hit,
        "notes": [
            "Binary/event-based",
            f"Rate={ctx.event_rate:.2%}",
            f"Opps={ctx.opportunities:.0f}"
        ]
    }


# ============================================================================
# ROUTER (STAT CLASS → MODEL)
# ============================================================================

def model_alt_stat(
    line: float,
    stat_class: str,
    ctx: Any,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Route alt-stat to appropriate model based on stat_class.
    
    Args:
        line: Prop line
        stat_class: One of {volume_micro, sequence_early, event_binary}
        ctx: Context object (type varies by stat_class)
        debug: If True, include debug info
    
    Returns:
        Dict with expected, raw_p_hit, notes
    """
    if stat_class == "volume_micro":
        return model_volume_micro(line, ctx)
    
    elif stat_class == "sequence_early":
        return model_sequence_early(line, ctx)
    
    elif stat_class == "event_binary":
        return model_event_binary(line, ctx)
    
    else:
        raise ValueError(f"Unknown stat_class: {stat_class}. "
                        f"Must be one of: volume_micro, sequence_early, event_binary")


# ============================================================================
# CONTEXT BUILDERS (SPORT-SPECIFIC)
# ============================================================================

def build_nba_volume_context(
    player: str,
    minutes: float,
    usage_rate: float,
    attempts_per_min: float,
    pace_mult: float = 1.0,
    opp_def_rating: float = 100.0,
    league_avg_def: float = 100.0
) -> VolumeMicroContext:
    """
    Build NBA volume context for guards/wings/bigs.
    
    Args:
        player: Player name (informational)
        minutes: Projected minutes
        usage_rate: Season usage % (0.25 = 25%)
        attempts_per_min: Player's typical attempts/min
        pace_mult: Game pace multiplier vs league avg
        opp_def_rating: Opponent defensive rating
        league_avg_def: League average defensive rating
    
    Returns:
        VolumeMicroContext
    """
    opp_adj = league_avg_def / max(opp_def_rating, 80.0)  # Avoid division by zero
    
    return VolumeMicroContext(
        minutes=minutes,
        attempts_per_min=attempts_per_min,
        usage=usage_rate,
        pace=pace_mult,
        opp_adjustment=opp_adj
    )


def build_nfl_volume_context(
    player: str,
    snap_count: int,
    snaps_per_attempt: float,
    team_pace: float = 1.0,
    opp_pass_def: float = 1.0
) -> VolumeMicroContext:
    """
    Build NFL volume context for QBs, RBs, WRs.
    
    Args:
        player: Player name
        snap_count: Expected snaps
        snaps_per_attempt: QB snaps per pass attempt, etc.
        team_pace: Pace multiplier
        opp_pass_def: Opponent adjustment
    
    Returns:
        VolumeMicroContext
    """
    return VolumeMicroContext(
        minutes=snap_count / 60.0,  # Normalize to "time units"
        attempts_per_min=1.0 / snaps_per_attempt,
        usage=0.5,  # NFL context is different; adjust per sport
        pace=team_pace,
        opp_adjustment=opp_pass_def
    )


def build_early_context(
    full_game_proj: float,
    early_share: float = 0.25,
    is_starter: bool = True,
    opp_script_factor: float = 1.0
) -> SequenceEarlyContext:
    """
    Build early-sequence context (NBA or NFL).
    
    Args:
        full_game_proj: Full-game projection
        early_share: Fraction of game expected in early window (0.18-0.30)
        is_starter: Whether player starts
        opp_script_factor: Script tendency (1.0 = neutral, 0.8 = run-heavy, etc.)
    
    Returns:
        SequenceEarlyContext
    """
    return SequenceEarlyContext(
        full_game_projection=full_game_proj,
        early_share=early_share,
        starter_prob=1.0 if is_starter else 0.0,
        opp_opening_factor=opp_script_factor
    )


def build_event_context(
    event_rate: float,
    opportunities: float
) -> EventBinaryContext:
    """
    Build event-binary context.
    
    Args:
        event_rate: Rate per opportunity (e.g., 0.15 = 15% per rush)
        opportunities: Expected opportunities
    
    Returns:
        EventBinaryContext
    """
    return EventBinaryContext(
        event_rate=event_rate,
        opportunities=opportunities
    )


# ============================================================================
# TEST / EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Lamar Jackson pass attempts
    lamar_ctx = build_nfl_volume_context(
        player="Lamar Jackson",
        snap_count=65,
        snaps_per_attempt=1.9,  # ~34 attempts on 65 snaps
        team_pace=1.05,
        opp_pass_def=0.95
    )
    
    result = model_alt_stat(line=34.5, stat_class="volume_micro", ctx=lamar_ctx)
    print(f"Lamar Jackson Pass Attempts O 34.5:")
    print(f"  Expected: {result['expected']}")
    print(f"  P(hit): {result['raw_p_hit']:.3f}")
    print(f"  Notes: {result['notes']}")
    print()
    
    # Example: Early-game points
    early_ctx = build_early_context(
        full_game_proj=26.0,
        early_share=0.22,
        is_starter=True,
        opp_script_factor=1.0
    )
    
    result = model_alt_stat(line=5.5, stat_class="sequence_early", ctx=early_ctx)
    print(f"Player Points (First 3 Min) O 5.5:")
    print(f"  Expected: {result['expected']}")
    print(f"  P(hit): {result['raw_p_hit']:.3f}")
    print(f"  Notes: {result['notes']}")
