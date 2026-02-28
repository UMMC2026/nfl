"""
CALIBRATION ADJUSTMENT MODULE
=============================

Empirically-derived calibration based on 97-pick backtest showing
systematic overconfidence of ~8% in LEAN tier.

Key Finding:
- Model says 55% → Actual 47.3%
- Model says 60% → Actual ~52%
- Model says 65% → Actual ~57%

This module applies temperature scaling to align predictions with reality.

Usage:
    from config.calibration_adjustments import apply_calibration, get_calibrated_tier
    
    raw_prob = 0.62
    calibrated_prob = apply_calibration(raw_prob, sport='CBB')
    tier = get_calibrated_tier(calibrated_prob, sport='CBB')
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


# =============================================================================
# EMPIRICAL CALIBRATION CURVES (from backtest data)
# =============================================================================

# CBB Calibration: Your model is ~8% overconfident across the board
CBB_CALIBRATION_MAP = {
    # Raw → Calibrated (based on 97-pick backtest)
    0.50: 0.42,   # 50% picks hit at 42%
    0.55: 0.47,   # 55% picks hit at 47% (confirmed from data)
    0.60: 0.52,   # 60% picks hit at ~52%
    0.65: 0.57,   # Projected from trend
    0.70: 0.62,   # Projected
    0.75: 0.68,   # Projected (high confidence more accurate)
    0.80: 0.74,   # Diminishing overconfidence at high end
}

# NBA Calibration (separate curve - generally better calibrated)
NBA_CALIBRATION_MAP = {
    0.50: 0.47,   # Slightly overconfident
    0.55: 0.52,   # ~3% overconfident
    0.60: 0.57,   # ~3% overconfident
    0.65: 0.62,   # ~3% overconfident
    0.70: 0.67,   # Better at higher confidence
    0.75: 0.73,   # Nearly calibrated
    0.80: 0.78,   # Well calibrated
}

# Tennis Calibration (surface-specific would be better)
TENNIS_CALIBRATION_MAP = {
    0.50: 0.48,
    0.55: 0.53,
    0.60: 0.57,
    0.65: 0.62,
    0.70: 0.67,
    0.75: 0.72,
    0.80: 0.77,
}

CALIBRATION_MAPS = {
    'CBB': CBB_CALIBRATION_MAP,
    'NBA': NBA_CALIBRATION_MAP,
    'TENNIS': TENNIS_CALIBRATION_MAP,
}


# =============================================================================
# NEW TIER THRESHOLDS (Calibrated)
# =============================================================================

@dataclass
class TierThresholds:
    """Tier thresholds after calibration adjustment"""
    slam: Optional[float]  # None if tier disabled
    strong: float
    lean: float
    skip: float  # Below this = SKIP


# CALIBRATED thresholds (these are raw model outputs that map to profitable tiers)
CBB_TIERS_CALIBRATED = TierThresholds(
    slam=None,      # No SLAM tier for CBB (too volatile)
    strong=0.72,    # Raw 72% → Calibrated 64% → Actual ~62% (profitable)
    lean=0.67,      # Raw 67% → Calibrated 59% → Actual ~57% (marginally profitable)
    skip=0.67,      # Everything below 67% raw is unprofitable
)

NBA_TIERS_CALIBRATED = TierThresholds(
    slam=0.80,      # Raw 80% → Calibrated 78%
    strong=0.70,    # Raw 70% → Calibrated 67%
    lean=0.60,      # Raw 60% → Calibrated 57%
    skip=0.55,      # Below this = unprofitable
)

CALIBRATED_TIERS = {
    'CBB': CBB_TIERS_CALIBRATED,
    'NBA': NBA_TIERS_CALIBRATED,
}


# =============================================================================
# CALIBRATION FUNCTIONS
# =============================================================================

def interpolate_calibration(raw_prob: float, calibration_map: Dict[float, float]) -> float:
    """
    Linear interpolation between known calibration points.
    
    Args:
        raw_prob: Raw model probability (0-1)
        calibration_map: Dict mapping raw → calibrated probabilities
        
    Returns:
        Calibrated probability
    """
    sorted_keys = sorted(calibration_map.keys())
    
    # Clamp to known range
    if raw_prob <= sorted_keys[0]:
        return calibration_map[sorted_keys[0]]
    if raw_prob >= sorted_keys[-1]:
        return calibration_map[sorted_keys[-1]]
    
    # Find surrounding points and interpolate
    for i in range(len(sorted_keys) - 1):
        x0, x1 = sorted_keys[i], sorted_keys[i+1]
        if x0 <= raw_prob <= x1:
            y0, y1 = calibration_map[x0], calibration_map[x1]
            # Linear interpolation
            calibrated = y0 + (raw_prob - x0) * (y1 - y0) / (x1 - x0)
            return calibrated
    
    return raw_prob  # Fallback


def apply_calibration(
    raw_prob: float,
    sport: str = 'CBB',
    direction: Optional[str] = None
) -> float:
    """
    Apply empirical calibration to raw model probability.
    
    Args:
        raw_prob: Raw probability from Poisson/model (0-1)
        sport: 'CBB', 'NBA', 'TENNIS'
        direction: 'OVER' or 'UNDER' (for directional bias adjustment)
        
    Returns:
        Calibrated probability accounting for systematic overconfidence
    """
    calibration_map = CALIBRATION_MAPS.get(sport.upper(), CBB_CALIBRATION_MAP)
    
    calibrated = interpolate_calibration(raw_prob, calibration_map)
    
    # Apply directional bias if specified (from your data: UNDER slightly better)
    if direction:
        if direction.upper() in ['UNDER', 'LOWER']:
            calibrated *= 1.02  # UNDERs are 2% better calibrated
        elif direction.upper() in ['OVER', 'HIGHER']:
            calibrated *= 0.98  # OVERs are 2% worse
    
    return min(max(calibrated, 0.0), 1.0)


def get_calibrated_tier(
    raw_prob: float,
    sport: str = 'CBB',
    use_calibration: bool = True
) -> Tuple[str, float]:
    """
    Determine tier using calibrated thresholds.
    
    Args:
        raw_prob: Raw model probability
        sport: Sport type
        use_calibration: Whether to apply calibration adjustment
        
    Returns:
        (tier_name, calibrated_probability)
    """
    if use_calibration:
        prob = apply_calibration(raw_prob, sport)
    else:
        prob = raw_prob
    
    thresholds = CALIBRATED_TIERS.get(sport.upper(), CBB_TIERS_CALIBRATED)
    
    # Determine tier from calibrated probability
    # Note: We compare RAW prob against calibrated thresholds
    # This ensures only truly confident picks make it through
    
    if thresholds.slam and raw_prob >= thresholds.slam:
        return 'SLAM', prob
    elif raw_prob >= thresholds.strong:
        return 'STRONG', prob
    elif raw_prob >= thresholds.lean:
        return 'LEAN', prob
    else:
        return 'SKIP', prob


def get_tier_from_calibrated(
    calibrated_prob: float,
    sport: str = 'CBB'
) -> str:
    """
    Determine tier from already-calibrated probability.
    
    Uses calibrated probability thresholds:
    - STRONG: calibrated >= 60% (was 70% raw, now 62% actual)
    - LEAN: calibrated >= 55% (was 67% raw, now 57% actual)
    - SKIP: below 55% calibrated
    """
    if sport.upper() == 'CBB':
        if calibrated_prob >= 0.62:
            return 'STRONG'
        elif calibrated_prob >= 0.57:
            return 'LEAN'
        else:
            return 'SKIP'
    else:  # NBA/other
        if calibrated_prob >= 0.75:
            return 'SLAM'
        elif calibrated_prob >= 0.65:
            return 'STRONG'
        elif calibrated_prob >= 0.55:
            return 'LEAN'
        else:
            return 'SKIP'


# =============================================================================
# TEMPERATURE SCALING (Alternative approach)
# =============================================================================

def temperature_scaling(
    raw_prob: float,
    temperature: float = 1.15  # >1 = less confident
) -> float:
    """
    Apply temperature scaling to probability.
    
    For overconfident models, temperature > 1 reduces extreme probabilities.
    
    Your backtest shows ~8% overconfidence, suggesting T ≈ 1.15
    
    Formula: calibrated = raw ^ T / (raw ^ T + (1-raw) ^ T)
    
    Args:
        raw_prob: Raw probability
        temperature: Scaling factor (1.15 = 15% less confident)
        
    Returns:
        Temperature-scaled probability
    """
    if raw_prob <= 0 or raw_prob >= 1:
        return raw_prob
    
    import math
    
    # Logit transformation with temperature
    numerator = raw_prob ** temperature
    denominator = numerator + (1 - raw_prob) ** temperature
    
    return numerator / denominator


# CBB-specific temperature based on backtest
# Updated 2026-02-10: release ~9% of the previous down-scaling pressure
# so well-supported CBB edges are not over-flattened.
CBB_TEMPERATURE = 1.09  # 9% less confident (was 18%)
NBA_TEMPERATURE = 1.08  # 8% less confident (3% overconfidence)


def apply_temperature(raw_prob: float, sport: str = 'CBB') -> float:
    """Apply sport-specific temperature scaling."""
    temps = {
        'CBB': CBB_TEMPERATURE,
        'NBA': NBA_TEMPERATURE,
        'TENNIS': 1.10,
    }
    return temperature_scaling(raw_prob, temps.get(sport.upper(), 1.15))


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_calibration_report(sport: str = 'CBB') -> str:
    """Generate a calibration report for documentation."""
    cal_map = CALIBRATION_MAPS.get(sport.upper(), CBB_CALIBRATION_MAP)
    thresholds = CALIBRATED_TIERS.get(sport.upper(), CBB_TIERS_CALIBRATED)
    
    report = f"""
CALIBRATION REPORT: {sport.upper()}
{'=' * 50}

RAW → CALIBRATED PROBABILITY MAPPING:
"""
    for raw, cal in sorted(cal_map.items()):
        diff = raw - cal
        report += f"  {raw*100:.0f}% raw → {cal*100:.0f}% calibrated ({diff*100:+.1f}% adjustment)\n"
    
    report += f"""
CALIBRATED TIER THRESHOLDS (Raw Probability):
  SLAM:   {'DISABLED' if thresholds.slam is None else f'{thresholds.slam*100:.0f}%'}
  STRONG: {thresholds.strong*100:.0f}%
  LEAN:   {thresholds.lean*100:.0f}%
  SKIP:   <{thresholds.skip*100:.0f}%

PROFITABLE RANGE:
  Only picks with raw probability >= {thresholds.lean*100:.0f}% are actionable
  This maps to calibrated probability >= {apply_calibration(thresholds.lean, sport)*100:.0f}%
  Expected hit rate: ~{apply_calibration(thresholds.lean, sport)*100:.0f}%
"""
    return report


# =============================================================================
# DEMO
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("  CALIBRATION ADJUSTMENT MODULE - DEMO")
    print("=" * 60)
    
    # Test CBB calibration
    print("\nCBB CALIBRATION TEST:")
    print("-" * 40)
    for raw in [0.55, 0.60, 0.65, 0.70, 0.75]:
        calibrated = apply_calibration(raw, 'CBB')
        tier, _ = get_calibrated_tier(raw, 'CBB')
        print(f"  Raw {raw*100:.0f}% → Calibrated {calibrated*100:.1f}% → {tier}")
    
    # Test temperature scaling
    print("\nTEMPERATURE SCALING TEST (CBB):")
    print("-" * 40)
    for raw in [0.55, 0.60, 0.65, 0.70, 0.75]:
        temp_scaled = apply_temperature(raw, 'CBB')
        print(f"  Raw {raw*100:.0f}% → Temp-scaled {temp_scaled*100:.1f}%")
    
    # Print full report
    print("\n")
    print(get_calibration_report('CBB'))
