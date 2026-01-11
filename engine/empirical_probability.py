"""
Phase 1B - Empirical Probability Mapping

Truth-preserving probability calculation from historical frequencies.
No distributional assumptions. No curve fitting. Direct observation.
"""
from typing import Optional


# Constants
MIN_SAMPLE_SIZE = 10        # Minimum games for valid probability
LOW_CONFIDENCE_CAP = 0.65   # Max probability when sample < MIN_SAMPLE_SIZE
MIN_MINUTES_THRESHOLD = 10  # Minimum minutes for game to count


def build_empirical_distribution(game_logs: list, stat: str) -> list[float]:
    """
    Extract sorted stat outcomes from game logs.
    
    Args:
        game_logs: List of game dicts with stat values
        stat: Stat name to extract
    
    Returns:
        Sorted list of stat values (minutes-qualified games only)
    """
    values = []
    
    for game in game_logs:
        # Minutes qualification
        minutes = game.get('minutes', game.get('min', 0))
        if minutes < MIN_MINUTES_THRESHOLD:
            continue
        
        # Stat extraction (handle multiple field names)
        stat_value = game.get(stat)
        if stat_value is None:
            # Try alternate field names
            stat_lower = stat.lower().replace('_', '').replace('+', '')
            for key in game:
                key_normalized = key.lower().replace('_', '').replace('+', '')
                if key_normalized == stat_lower:
                    stat_value = game[key]
                    break
        
        if stat_value is not None:
            try:
                values.append(float(stat_value))
            except (ValueError, TypeError):
                continue
    
    return sorted(values)


def empirical_prob_over(distribution: list[float], line: float) -> Optional[float]:
    """
    Calculate probability of exceeding line from empirical distribution.
    
    Args:
        distribution: Sorted list of historical stat values
        line: Target line to exceed
    
    Returns:
        P(stat > line) or None if insufficient data
    """
    if not distribution:
        return None
    
    exceed_count = sum(1 for value in distribution if value > line)
    return exceed_count / len(distribution)


def empirical_prob_under(distribution: list[float], line: float) -> Optional[float]:
    """
    Calculate probability of staying under line from empirical distribution.
    
    Args:
        distribution: Sorted list of historical stat values
        line: Target line to stay under
    
    Returns:
        P(stat < line) or None if insufficient data
    """
    if not distribution:
        return None
    
    # UNDER = strictly less than line
    # Pushes (stat == line) treated as UNDER for safety
    under_count = sum(1 for value in distribution if value < line)
    return under_count / len(distribution)


def empirical_prob_hit(distribution: list[float], line: float, direction: str) -> Optional[float]:
    """
    Calculate probability of hitting direction from empirical distribution.
    
    Args:
        distribution: Sorted list of historical stat values
        line: Target line
        direction: "higher"/"over" or "lower"/"under"
    
    Returns:
        P(hit) or None if insufficient data
    """
    if not distribution:
        return None
    
    direction_normalized = direction.lower()
    
    if direction_normalized in ("higher", "over", "o"):
        return empirical_prob_over(distribution, line)
    elif direction_normalized in ("lower", "under", "u"):
        return empirical_prob_under(distribution, line)
    else:
        raise ValueError(f"Invalid direction: {direction}")


def apply_small_sample_protection(probability: float, sample_size: int) -> tuple[float, bool]:
    """
    Cap probability when sample size is insufficient.
    
    Args:
        probability: Raw empirical probability
        sample_size: Number of games in distribution
    
    Returns:
        (protected_probability, was_capped)
    """
    if sample_size < MIN_SAMPLE_SIZE:
        capped = min(probability, LOW_CONFIDENCE_CAP)
        return capped, capped != probability
    
    return probability, False


def pace_blend_probability(
    empirical_p: float,
    pace_adjusted_mean: float,
    line: float,
    max_adjustment: float = 0.05
) -> float:
    """
    Blend empirical probability with pace-adjusted mean signal.
    
    Keeps probability grounded in empirical reality while allowing
    pace context to influence direction.
    
    Args:
        empirical_p: Base empirical probability
        pace_adjusted_mean: Mean after pace adjustment
        line: Target line
        max_adjustment: Maximum probability adjustment (default 0.05)
    
    Returns:
        Final blended probability
    """
    mean_delta = pace_adjusted_mean - line
    
    # Convert mean delta to probability adjustment (scaled)
    adjustment = max(-max_adjustment, min(max_adjustment, mean_delta / 10))
    
    # Apply and bound to [0.01, 0.99]
    final_p = empirical_p + adjustment
    return max(0.01, min(0.99, final_p))


def calculate_empirical_probability(
    game_logs: list,
    stat: str,
    line: float,
    direction: str,
    pace_adjusted_mean: Optional[float] = None
) -> dict:
    """
    Complete empirical probability calculation with logging.
    
    Args:
        game_logs: Historical game data
        stat: Stat name
        line: Target line
        direction: "higher" or "lower"
        pace_adjusted_mean: Optional pace-adjusted mean for blending
    
    Returns:
        Dict with probability and full audit trail
    """
    # Build distribution
    distribution = build_empirical_distribution(game_logs, stat)
    
    if not distribution:
        return {
            "probability": None,
            "method": "empirical",
            "error": "no_valid_games",
            "sample_size": 0
        }
    
    # Calculate empirical probability
    empirical_p = empirical_prob_hit(distribution, line, direction)
    
    if empirical_p is None:
        return {
            "probability": None,
            "method": "empirical",
            "error": "calculation_failed",
            "sample_size": len(distribution)
        }
    
    # Small sample protection
    protected_p, was_capped = apply_small_sample_protection(empirical_p, len(distribution))
    
    # Pace blending (if available)
    if pace_adjusted_mean is not None:
        final_p = pace_blend_probability(protected_p, pace_adjusted_mean, line)
    else:
        final_p = protected_p
    
    # Full audit trail
    return {
        "probability": final_p,
        "method": "empirical",
        "sample_size": len(distribution),
        "empirical_hit_rate": round(empirical_p, 4),
        "small_sample_capped": was_capped,
        "low_confidence": len(distribution) < MIN_SAMPLE_SIZE,
        "pace_blended": pace_adjusted_mean is not None,
        "pace_adjusted_mean": pace_adjusted_mean,
        "line": line,
        "direction": direction,
        "distribution_min": round(min(distribution), 2),
        "distribution_max": round(max(distribution), 2),
        "distribution_median": round(distribution[len(distribution)//2], 2)
    }
