"""
CBB Edge Gates — Enhanced with All Controls
---------------------------------------------
Hard blocks specific to college basketball.
These gates are STRICTER than NBA to respect CBB chaos.

Gate Categories:
1. Base gates (minutes, composite, blowout, variance, sample)
2. Tournament gates (March restrictions)
3. State gates (unders-only mode, daily exposure)
4. Prior gates (public fade, conference strength)
5. Regime gates (season regime adjustments)
"""

import json
import yaml
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass

from .edge_generator import CBBEdge


# Config paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
MODELS_DIR = Path(__file__).parent.parent / "models"


@dataclass
class GateResult:
    """Result of a gate check."""
    passed: bool
    gate_name: str
    reason: Optional[str] = None
    adjustment: Optional[float] = None  # Probability adjustment if any


def load_config(name: str) -> dict:
    """Load YAML or JSON config file."""
    yaml_path = CONFIG_DIR / f"{name}.yaml"
    json_path = CONFIG_DIR / f"{name}.json"
    
    if yaml_path.exists():
        with open(yaml_path) as f:
            return yaml.safe_load(f)
    elif json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return {}


def load_model_prior(name: str) -> dict:
    """Load model prior file."""
    yaml_path = MODELS_DIR / f"{name}.yaml"
    json_path = MODELS_DIR / f"{name}.json"
    
    if yaml_path.exists():
        with open(yaml_path) as f:
            return yaml.safe_load(f)
    elif json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return {}


def apply_cbb_edge_gates(
    edge: 'CBBEdge',
    player_features: Any,
    game_context: Any,
    is_tournament: bool = False,
    regime: str = "MID_SEASON",
    public_bet_pct: Optional[float] = None
) -> 'CBBEdge':
    """
    Apply all CBB-specific edge gates.
    
    Gates (in order):
    1. State gates (unders-only, exposure limits)
    2. Tournament gates (March restrictions)
    3. Minutes threshold gate
    4. Composite stat ban gate
    5. Blowout protection gate
    6. Variance penalty gate
    7. Sample size gate
    8. Public fade gate
    9. Conference strength gate
    10. Regime adjustment gate
    
    Any gate failure blocks the edge.
    """
    from sports.cbb.config import CBB_EDGE_GATES, BLOCKED_STATS
    
    # --- HARD BLOCK: Missing spread/game context --- 
    # If spread or game context is missing, block
    spread = getattr(game_context, 'spread', None)
    if spread is None:
        edge.is_blocked = True
        edge.block_reason = "MISSING_SPREAD_OR_CONTEXT (spread missing)"
        return edge
    # --- HARD BLOCK: Line sanity check ---
    # Block if line is negative/zero or >2.5x recent average (L10)
    recent_avg = getattr(player_features, 'avg_points_l10', None)
    if edge.line is None or edge.line <= 0:
        edge.is_blocked = True
        edge.block_reason = f"INVALID_LINE (line={edge.line})"
        return edge
    if recent_avg is not None and recent_avg > 0 and edge.line > 2.5 * recent_avg:
        edge.is_blocked = True
        edge.block_reason = f"LINE_TOO_HIGH (line={edge.line}, avg_l10={recent_avg})"
        return edge

        # Already blocked upstream
        if edge.is_blocked:
            return edge

        # Track all gate results for transparency
        gate_results = []

        # === STATE GATES ===
        # Gate 1: Unders-only mode
        result = _gate_unders_only_mode(edge)
        gate_results.append(result)
        if not result.passed:
            edge.is_blocked = True
            edge.block_reason = result.reason
            return edge

        # Gate 2: Daily exposure check
        result = _gate_daily_exposure(edge)
        gate_results.append(result)
        if not result.passed:
            edge.is_blocked = True
            edge.block_reason = result.reason
            return edge

        # === TOURNAMENT GATES ===
        if is_tournament:
            result = _gate_tournament_mode(edge)
            gate_results.append(result)
            if not result.passed:
                edge.is_blocked = True
                edge.block_reason = result.reason
                return edge
            # Apply tournament probability cap
            if result.adjustment is not None:
                edge.probability = min(edge.probability, result.adjustment)

        # === BASE GATES ===
        # Gate 3: Minutes threshold (no unders on low-minute players)
        if edge.direction == "lower" and CBB_EDGE_GATES.block_under_low_minutes:
            if player_features.avg_minutes_l10 < CBB_EDGE_GATES.min_minutes_avg:
                edge.is_blocked = True
                edge.block_reason = f"UNDER_LOW_MINUTES ({player_features.avg_minutes_l10:.1f} mpg)"
                return edge

        # --- HARD BLOCK: Missing recent averages (L3/L5/L10) ---
        # If all recent averages are missing or zero, block the edge
        l3 = getattr(player_features, 'avg_points_l3', None)
        l5 = getattr(player_features, 'avg_points_l5', None)
        l10 = getattr(player_features, 'avg_points_l10', None)
        # If all are None or zero, block
        if (l3 is None or l3 == 0) and (l5 is None or l5 == 0) and (l10 is None or l10 == 0):
            edge.is_blocked = True
            edge.block_reason = "MISSING_RECENT_AVG (L3/L5/L10 all missing or zero)"
            return edge

        # Gate 4: Composite stat ban
        if edge.stat in BLOCKED_STATS and not CBB_EDGE_GATES.allow_composite_stats:
            edge.is_blocked = True
            edge.block_reason = f"COMPOSITE_STAT_BLOCKED ({edge.stat})"
            return edge

        # Gate 5: Blowout protection (no overs in blowout games)
        if edge.direction == "higher":
            if game_context.blowout_probability > CBB_EDGE_GATES.max_blowout_probability:
                edge.is_blocked = True
                edge.block_reason = f"BLOWOUT_RISK ({game_context.blowout_probability:.1%})"
                return edge

        # Gate 6: Variance penalty
        variance_threshold = get_stat_mean(player_features, edge.stat) * CBB_EDGE_GATES.variance_penalty_factor
        if get_stat_std(player_features, edge.stat) > variance_threshold:
            if edge.probability > CBB_EDGE_GATES.variance_confidence_cap:
                edge.probability = CBB_EDGE_GATES.variance_confidence_cap
                edge.tier = "LEAN"  # Downgrade tier

        # Gate 7: Sample size
        if player_features.games_played < CBB_EDGE_GATES.min_games_played:
            edge.is_blocked = True
            edge.block_reason = f"INSUFFICIENT_SAMPLE ({player_features.games_played} games)"
            return edge

        # === PRIOR GATES ===
        # Gate 8: Public fade
        if public_bet_pct is not None:
            result = _gate_public_fade(edge, public_bet_pct)
            gate_results.append(result)
            if not result.passed:
                edge.is_blocked = True
                edge.block_reason = result.reason
                return edge

        # Gate 9: Conference strength
        result = _gate_conference_strength(edge)
        gate_results.append(result)
        if not result.passed:
            edge.is_blocked = True
            edge.block_reason = result.reason
            return edge

        # Gate 10: Regime adjustment
        result = _gate_regime_adjustment(edge, regime)
        gate_results.append(result)
        if not result.passed:
            edge.is_blocked = True
            edge.block_reason = result.reason
            return edge

        return edge
    
    # Apply probability cap
    prob_cap = march.get("probability_cap", 0.65)
    
    return GateResult(
        passed=True,
        gate_name="TOURNAMENT_MODE",
        adjustment=prob_cap
    )


def _gate_public_fade(edge: CBBEdge, public_pct: float) -> GateResult:
    """Apply public betting fade logic."""
    config = load_model_prior("public_fade")
    thresholds = config.get("THRESHOLDS", {})
    actions = config.get("ACTIONS", {})
    
    # Check if edge direction aligns with public
    # (Simplified: assume public_pct is % on the direction we're betting)
    
    hard_block_threshold = thresholds.get("HARD_BLOCK_AT", 75)
    fade_soft_threshold = thresholds.get("FADE_SOFT_AT", 65)
    
    if public_pct >= hard_block_threshold:
        return GateResult(
            passed=False,
            gate_name="PUBLIC_FADE",
            reason=f"PUBLIC_HERD ({public_pct:.0f}% on this side)"
        )
    
    if public_pct >= fade_soft_threshold:
        soft_action = actions.get("FADE_SOFT", {})
        adjustment = 1.0 - soft_action.get("confidence_penalty", 0.05)
        return GateResult(
            passed=True,
            gate_name="PUBLIC_FADE",
            reason=f"Public fade soft ({public_pct:.0f}%)",
            adjustment=adjustment
        )
    
    return GateResult(passed=True, gate_name="PUBLIC_FADE")


def _gate_season_regime(edge: CBBEdge, regime: str) -> GateResult:
    """Apply season regime adjustments."""
    config = load_config("season_regimes")
    regime_config = config.get(regime, config.get("MID_SEASON", {}))
    
    confidence_mult = regime_config.get("confidence_multiplier", 1.0)
    max_cap = regime_config.get("max_confidence_cap", 0.70)
    
    # Calculate adjusted cap
    adjusted_cap = min(edge.probability * confidence_mult, max_cap)
    
    return GateResult(
        passed=True,
        gate_name="SEASON_REGIME",
        reason=f"Regime {regime}",
        adjustment=adjusted_cap
    )


def _recalculate_tier(edge: CBBEdge) -> CBBEdge:
    """Recalculate tier based on final probability."""
    thresholds = load_config("thresholds")
    tier_config = thresholds.get("TIER_THRESHOLDS", {})
    
    strong_thresh = tier_config.get("STRONG", 0.70)
    lean_thresh = tier_config.get("LEAN", 0.60)
    
    if edge.probability >= strong_thresh:
        edge.tier = "STRONG"
    elif edge.probability >= lean_thresh:
        edge.tier = "LEAN"
    else:
        edge.is_blocked = True
        edge.block_reason = f"BELOW_LEAN_THRESHOLD ({edge.probability:.1%})"
    
    return edge


def get_stat_mean(player_features: Any, stat: str) -> float:
    """Get player's mean for a stat from features."""
    stat_map = {
        "points": "avg_points_l10",
        "rebounds": "avg_rebounds_l10",
        "assists": "avg_assists_l10",
    }
    attr = stat_map.get(stat, "avg_points_l10")
    return getattr(player_features, attr, 10.0)


def get_stat_std(player_features: Any, stat: str) -> float:
    """
    Get player's standard deviation for a stat.
    
    Note: This is a simplification. In production, compute actual std from game logs.
    """
    return getattr(player_features, "minutes_std_l10", 5.0)


def validate_edge_gates(edges: list) -> dict:
    """
    Validate edge gates were applied correctly.
    
    Returns summary of blocked vs passed edges.
    """
    total = len(edges)
    blocked = sum(1 for e in edges if e.is_blocked)
    passed = total - blocked
    
    block_reasons = {}
    for e in edges:
        if e.is_blocked and e.block_reason:
            reason = e.block_reason.split(" ")[0]
            block_reasons[reason] = block_reasons.get(reason, 0) + 1
    
    return {
        "total": total,
        "blocked": blocked,
        "passed": passed,
        "block_rate": blocked / total if total > 0 else 0,
        "block_reasons": block_reasons,
    }


# === ADDITIONAL GATE UTILITIES ===

def detect_season_regime() -> str:
    """
    Auto-detect current season regime based on date.
    
    Returns one of: EARLY_SEASON, MID_SEASON, LATE_SEASON, 
    CONFERENCE_TOURNAMENT, NCAA_TOURNAMENT
    """
    from datetime import date
    
    today = date.today()
    month, day = today.month, today.day
    
    # November early games
    if month == 11 and day <= 20:
        return "EARLY_SEASON"
    
    # Conference tournaments (early March)
    if month == 3 and day <= 14:
        return "CONFERENCE_TOURNAMENT"
    
    # March Madness (mid-March through early April)
    if (month == 3 and day >= 15) or (month == 4 and day <= 10):
        return "NCAA_TOURNAMENT"
    
    # Late season (February)
    if month == 2:
        return "LATE_SEASON"
    
    # Mid season (default)
    return "MID_SEASON"


def is_tournament_game(game_context: Any) -> bool:
    """Check if game is a tournament game."""
    # Check game context for tournament indicators
    tournament_indicators = [
        "NCAA",
        "March Madness",
        "Tournament",
        "Conference Tournament",
        "NIT"
    ]
    
    venue = getattr(game_context, "venue", "")
    event = getattr(game_context, "event_name", "")
    
    for indicator in tournament_indicators:
        if indicator.lower() in venue.lower() or indicator.lower() in event.lower():
            return True
    
    # Check regime
    regime = detect_season_regime()
    return regime in ["CONFERENCE_TOURNAMENT", "NCAA_TOURNAMENT"]
