"""
CALIBRATION FIXER — Confidence Compression to Reduce Calibration Error
======================================================================

Problem: System has 28% calibration error. When predicting 73% confidence,
actual hit rate is only 43.5%.

Solution: Apply sigmoid compression to pull extreme confidences toward 50%.

Usage:
    from config.calibration_fixer import apply_calibration_fix, CalibrationConfig
    
    # Apply fix to a confidence value
    fixed_conf = apply_calibration_fix(0.75)  # Returns ~0.62
    
    # With player config integration
    result = apply_calibration_fix(0.75, player_name="Victor Wembanyama", stat="PTS")
"""

import math
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

# Integration with player configs
try:
    from config.player_configs import get_player_config_manager, PlayerConfigManager
    HAS_PLAYER_CONFIGS = True
except ImportError:
    HAS_PLAYER_CONFIGS = False


@dataclass
class CalibrationResult:
    """Result of calibration fix."""
    raw_probability: float
    adjusted_probability: float
    sigmoid_compressed: float
    archetype_cap: Optional[float]
    details: list
    
    @property
    def total_adjustment(self) -> float:
        return self.adjusted_probability - self.raw_probability


@dataclass
class CalibrationConfig:
    """Configuration for calibration fixes."""
    
    # Sigmoid compression parameters
    compression_strength: float = 0.35   # How much to compress (0.35 = moderate)
    center_point: float = 0.50           # Center of compression (50%)
    
    # Archetype-based caps (from assessment)
    archetype_caps: Dict[str, float] = None
    
    # Sample size scaling
    min_games_for_full_confidence: int = 10
    low_sample_penalty: float = 0.90     # Multiply by this if < min_games
    
    # Direction bias (from calibration data)
    under_boost: float = 1.03            # UNDERs historically +3%
    over_penalty: float = 0.94           # OVERs historically -6%
    
    def __post_init__(self):
        if self.archetype_caps is None:
            self.archetype_caps = {
                "BENCH_MICROWAVE": 0.55,    # Max 55% for bench scorers
                "CONNECTOR_STARTER": 0.70,   # Max 70% for role players
                "PRIMARY_USAGE_SCORER": 0.80, # Full confidence for stars
                "SECONDARY_CREATOR": 0.72,   # Max 72% for secondary options
            }


# Default configuration
DEFAULT_CONFIG = CalibrationConfig()


def sigmoid_compress(confidence: float, strength: float = 0.35, center: float = 0.50) -> float:
    """
    Apply sigmoid compression to pull confidence toward center.
    
    This reduces overconfidence by compressing extreme values.
    
    Args:
        confidence: Raw confidence (0.0 - 1.0)
        strength: Compression strength (0.0 = none, 1.0 = heavy)
        center: Center point of compression
    
    Returns:
        Compressed confidence (0.0 - 1.0)
    
    Example:
        0.80 → ~0.68 (pulled toward 0.50)
        0.60 → ~0.58 (slight adjustment)
        0.50 → 0.50 (unchanged)
    """
    if strength <= 0:
        return confidence
    
    # Distance from center
    distance = confidence - center
    
    # Compress using smooth function
    # New value = center + distance * (1 - strength * |distance|^0.5)
    compression_factor = 1 - strength * (abs(distance) ** 0.5)
    compression_factor = max(0.3, compression_factor)  # Floor at 30% of original distance
    
    compressed = center + distance * compression_factor
    
    # Ensure valid range
    return max(0.0, min(1.0, compressed))


def apply_archetype_cap(confidence: float, archetype: str, caps: Dict[str, float] = None) -> Tuple[float, bool, str]:
    """
    Apply archetype-based confidence cap.
    
    Args:
        confidence: Current confidence
        archetype: Player archetype (BENCH_MICROWAVE, etc.)
        caps: Optional cap dictionary (uses default if None)
    
    Returns:
        (capped_confidence, was_capped, reason)
    """
    caps = caps or DEFAULT_CONFIG.archetype_caps
    
    if not archetype:
        return confidence, False, ""
    
    archetype_upper = archetype.upper()
    cap = caps.get(archetype_upper)
    
    if cap is not None and confidence > cap:
        reason = f"Archetype cap ({archetype}): {confidence:.1%} → {cap:.1%}"
        return cap, True, reason
    
    return confidence, False, ""


def apply_sample_size_scaling(confidence: float, sample_n: int, config: CalibrationConfig = None) -> Tuple[float, bool, str]:
    """
    Reduce confidence for small sample sizes.
    
    Args:
        confidence: Current confidence
        sample_n: Number of games in sample
        config: Calibration config
    
    Returns:
        (adjusted_confidence, was_adjusted, reason)
    """
    config = config or DEFAULT_CONFIG
    
    if sample_n >= config.min_games_for_full_confidence:
        return confidence, False, ""
    
    if sample_n <= 0:
        # No data = pull toward 50%
        adjusted = 0.50 + (confidence - 0.50) * 0.5
        return adjusted, True, f"No sample data: {confidence:.1%} → {adjusted:.1%}"
    
    # Linear scaling from 0 to min_games
    scale_factor = sample_n / config.min_games_for_full_confidence
    scale_factor = max(0.5, scale_factor)  # Floor at 50% confidence retention
    
    # Compress toward 50%
    distance_from_center = confidence - 0.50
    adjusted = 0.50 + distance_from_center * scale_factor
    
    if abs(adjusted - confidence) > 0.001:
        reason = f"Small sample ({sample_n} games): {confidence:.1%} → {adjusted:.1%}"
        return adjusted, True, reason
    
    return confidence, False, ""


def apply_direction_bias(confidence: float, direction: str, config: CalibrationConfig = None) -> Tuple[float, bool, str]:
    """
    Apply direction-based bias from calibration data.
    
    Historical data shows UNDERs hit more often than predicted,
    OVERs hit less often.
    
    Args:
        confidence: Current confidence
        direction: "higher"/"over" or "lower"/"under"
        config: Calibration config
    
    Returns:
        (adjusted_confidence, was_adjusted, reason)
    """
    config = config or DEFAULT_CONFIG
    
    direction_lower = direction.lower() if direction else ""
    
    if direction_lower in ("lower", "under"):
        adjusted = confidence * config.under_boost
        adjusted = min(adjusted, 0.85)  # Cap boost
        if adjusted != confidence:
            return adjusted, True, f"UNDER boost: {confidence:.1%} → {adjusted:.1%}"
    
    elif direction_lower in ("higher", "over"):
        adjusted = confidence * config.over_penalty
        if adjusted != confidence:
            return adjusted, True, f"OVER penalty: {confidence:.1%} → {adjusted:.1%}"
    
    return confidence, False, ""


def apply_calibration_fix(
    raw_probability: float,
    direction: str = None,
    archetype: str = None,
    sample_n: int = None,
    player_name: str = None,
    stat: str = None,
    config: CalibrationConfig = None,
    verbose: bool = False
) -> 'CalibrationResult':
    """
    Apply full calibration fix pipeline.
    
    Order of operations:
    1. Player config lookup (if available)
    2. Sigmoid compression (reduces overconfidence)
    3. Archetype/Player cap (role-based limits)
    4. Sample size scaling (penalize small samples)
    5. Direction bias (UNDER/OVER historical adjustment)
    
    Args:
        raw_probability: Raw confidence (0.0 - 1.0)
        direction: "higher"/"lower" for direction bias
        archetype: Player archetype for cap (overridden by player_name if found)
        sample_n: Sample size for scaling
        player_name: Player name to look up in player_configs
        stat: Stat type (PTS, REB, AST, etc.) for player-specific overrides
        config: CalibrationConfig (uses default if None)
        verbose: Print adjustments
    
    Returns:
        CalibrationResult with adjusted probability and details
    """
    config = config or DEFAULT_CONFIG
    
    # Initialize result
    current = raw_probability
    details = []
    archetype_cap = None
    variance_multiplier = 1.0
    player_direction_bias = {"OVER": 0.0, "UNDER": 0.0}
    
    # 1. Player config lookup
    if HAS_PLAYER_CONFIGS and player_name:
        try:
            manager = get_player_config_manager()
            player_config = manager.get_config(player_name)
            
            if player_config:
                # Get stat-specific config
                effective = player_config.get_effective_config(stat or "PTS")
                
                # Override archetype from player config
                archetype = player_config.archetype.value.upper()
                
                # Get player-specific caps and penalties
                player_cap = effective.get("confidence_cap")
                if player_cap:
                    archetype_cap = player_cap / 100.0  # Convert to 0-1
                
                variance_multiplier = effective.get("variance_penalty_multiplier", 1.0)
                player_direction_bias = effective.get("direction_bias", {"OVER": 0.0, "UNDER": 0.0})
                
                details.append(f"Player config: {player_config.player_name} ({archetype})")
                
                if verbose:
                    print(f"  [PLAYER CONFIG] {player_config.player_name}: archetype={archetype}, cap={player_cap}, var_pen={variance_multiplier}")
        except Exception as e:
            if verbose:
                print(f"  [PLAYER CONFIG] Error: {e}")
    
    # Record raw probability for result
    sigmoid_compressed = current
    
    # 2. Sigmoid compression (modified by variance multiplier)
    effective_strength = config.compression_strength * variance_multiplier
    compressed = sigmoid_compress(current, effective_strength, config.center_point)
    if abs(compressed - current) > 0.001:
        details.append(f"Sigmoid compression: {current:.1%} → {compressed:.1%}")
        if verbose:
            print(f"  [CALIBRATION] Sigmoid: {current:.1%} → {compressed:.1%}")
        sigmoid_compressed = compressed
        current = compressed
    
    # 3. Archetype/Player cap
    applied_cap = None
    if archetype_cap:
        # Use player-specific cap
        if current > archetype_cap:
            details.append(f"Player cap ({archetype}): {current:.1%} → {archetype_cap:.1%}")
            if verbose:
                print(f"  [CALIBRATION] Player cap: {current:.1%} → {archetype_cap:.1%}")
            applied_cap = archetype_cap
            current = archetype_cap
    elif archetype:
        # Use archetype cap from config
        capped, was_capped, reason = apply_archetype_cap(current, archetype, config.archetype_caps)
        if was_capped:
            details.append(reason)
            if verbose:
                print(f"  [CALIBRATION] {reason}")
            applied_cap = capped
            current = capped
    
    # 4. Sample size scaling
    if sample_n is not None:
        scaled, was_scaled, reason = apply_sample_size_scaling(current, sample_n, config)
        if was_scaled:
            details.append(reason)
            if verbose:
                print(f"  [CALIBRATION] {reason}")
            current = scaled
    
    # 5. Direction bias (combine player-specific and global)
    if direction:
        direction_lower = direction.lower()
        
        # Player-specific direction bias first
        if direction_lower in ("lower", "under") and player_direction_bias.get("UNDER", 0) != 0:
            bias = player_direction_bias["UNDER"]
            adjusted = current + bias  # Bias is additive for player configs
            adjusted = min(max(adjusted, 0.0), 0.90)
            if abs(adjusted - current) > 0.001:
                details.append(f"Player UNDER bias: {current:.1%} → {adjusted:.1%}")
                if verbose:
                    print(f"  [CALIBRATION] Player UNDER bias: {current:.1%} → {adjusted:.1%}")
                current = adjusted
        elif direction_lower in ("higher", "over") and player_direction_bias.get("OVER", 0) != 0:
            bias = player_direction_bias["OVER"]
            adjusted = current + bias
            adjusted = min(max(adjusted, 0.0), 0.90)
            if abs(adjusted - current) > 0.001:
                details.append(f"Player OVER bias: {current:.1%} → {adjusted:.1%}")
                if verbose:
                    print(f"  [CALIBRATION] Player OVER bias: {current:.1%} → {adjusted:.1%}")
                current = adjusted
        
        # Global direction bias
        biased, was_biased, reason = apply_direction_bias(current, direction, config)
        if was_biased:
            details.append(reason)
            if verbose:
                print(f"  [CALIBRATION] {reason}")
            current = biased
    
    return CalibrationResult(
        raw_probability=raw_probability,
        adjusted_probability=round(current, 4),
        sigmoid_compressed=sigmoid_compressed,
        archetype_cap=applied_cap,
        details=details
    )


def get_calibrated_confidence(
    confidence: float,
    direction: str = None,
    archetype: str = None,
    sample_n: int = None,
    player_name: str = None,
    stat: str = None
) -> float:
    """
    Simple helper to get calibrated confidence value.
    
    Usage:
        calibrated = get_calibrated_confidence(0.75, direction="higher", archetype="BENCH_MICROWAVE")
        calibrated = get_calibrated_confidence(0.75, player_name="Victor Wembanyama", stat="PTS")
    """
    result = apply_calibration_fix(
        confidence, 
        direction=direction, 
        archetype=archetype, 
        sample_n=sample_n,
        player_name=player_name,
        stat=stat
    )
    return result.adjusted_probability


# =============================================================================
# CALIBRATION ANALYSIS
# =============================================================================

def estimate_calibration_improvement(confidences: list, hit_rates: list) -> Dict[str, float]:
    """
    Estimate calibration improvement from fix.
    
    Args:
        confidences: List of predicted confidences
        hit_rates: List of actual hit rates (0 or 1)
    
    Returns:
        {
            "original_error": original calibration error,
            "projected_error": projected error after fix,
            "improvement": percentage improvement
        }
    """
    if not confidences or not hit_rates or len(confidences) != len(hit_rates):
        return {"original_error": 0, "projected_error": 0, "improvement": 0}
    
    # Original calibration error
    original_predicted = sum(confidences) / len(confidences)
    actual_rate = sum(hit_rates) / len(hit_rates)
    original_error = abs(original_predicted - actual_rate)
    
    # Apply fix to each confidence
    fixed_confidences = [get_calibrated_confidence(c) for c in confidences]
    fixed_predicted = sum(fixed_confidences) / len(fixed_confidences)
    projected_error = abs(fixed_predicted - actual_rate)
    
    improvement = (original_error - projected_error) / original_error * 100 if original_error > 0 else 0
    
    return {
        "original_error": round(original_error * 100, 1),
        "projected_error": round(projected_error * 100, 1),
        "improvement": round(improvement, 1),
    }


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def calibration_fix_for_pick(pick: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply calibration fix to a pick dictionary.
    
    Expects pick to have: probability (or confidence), direction, archetype, sample_n
    Returns updated pick with calibrated_probability field.
    """
    confidence = pick.get("probability", pick.get("confidence", 50)) / 100
    direction = pick.get("direction", "")
    archetype = pick.get("archetype", pick.get("role", ""))
    sample_n = pick.get("sample_n", pick.get("games", 10))
    
    result = apply_calibration_fix(confidence, direction, archetype, sample_n)
    
    pick["calibrated_probability"] = round(result["final"] * 100, 1)
    pick["calibration_adjustments"] = result["adjustments"]
    pick["calibration_delta"] = round(result["total_adjustment"] * 100, 1)
    
    return pick


if __name__ == "__main__":
    # Test calibration fix
    print("=" * 60)
    print("CALIBRATION FIX TEST")
    print("=" * 60)
    
    test_cases = [
        {"raw_probability": 0.80, "direction": "higher", "archetype": "PRIMARY_USAGE_SCORER", "sample_n": 15},
        {"raw_probability": 0.75, "direction": "higher", "archetype": "BENCH_MICROWAVE", "sample_n": 8},
        {"raw_probability": 0.68, "direction": "lower", "archetype": "CONNECTOR_STARTER", "sample_n": 12},
        {"raw_probability": 0.60, "direction": "higher", "archetype": None, "sample_n": 3},
    ]
    
    for case in test_cases:
        print(f"\nInput: {case}")
        result = apply_calibration_fix(**case)
        print(f"Result: {result.raw_probability:.1%} → {result.adjusted_probability:.1%}")
        print(f"Details: {result.details}")
