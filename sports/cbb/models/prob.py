"""
CBB Probability Model

Mirrors NBA's ufa/analysis/prob.py with CBB-specific distinctions:

NBA vs CBB Key Differences:
---------------------------
| Aspect           | NBA                    | CBB                        |
|------------------|------------------------|----------------------------|
| Distribution     | Normal (Gaussian)      | Poisson (discrete counts)  |
| Max Probability  | 80% (SLAM w/ usage)    | 79% (no SLAM tier)         |
| Tiers            | SLAM/STRONG/LEAN/SKIP  | STRONG/LEAN/SKIP only      |
| Core Cap         | 75-80%                 | 75%                        |
| Min Games        | 10                     | 5                          |
| Min MPG          | 25                     | 20                         |
| Data Source      | nba_api                | ESPN CBB API               |

CBB uses Poisson because:
- Lower scoring environment (60-80 PPG team vs 100-120 NBA)
- Discrete count distributions fit better
- Higher variance in outcomes
- Smaller sample sizes (30-35 games vs 82)

GOVERNANCE: Tier thresholds imported from config/thresholds.py (single source of truth).
"""

import sys
import math
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config.thresholds import get_all_thresholds, CONFIDENCE_CAPS

# ============================================================================
# GOVERNANCE: CBB STAT CLASSIFICATION
# ============================================================================

CBB_STAT_CLASS: Dict[str, str] = {
    # CORE (traditional props)
    "points": "core",
    "rebounds": "core", 
    "assists": "core",
    "pts+reb": "core",
    "pts+ast": "core",
    "pts+reb+ast": "core",
    "pra": "core",
    "reb+ast": "core",
    
    # VOLUME-DERIVED (capped lower)
    "fg_attempted": "volume_micro",
    "three_pt_attempted": "volume_micro",
    "minutes": "volume_micro",
    
    # EVENT / BINARY (highly restricted)
    "3pm": "event_binary",
    "steals": "event_binary",
    "blocks": "event_binary",
    "turnovers": "event_binary",
    "dunks": "event_binary",
}

# CBB Confidence caps (stricter than NBA - no SLAM tier)
# GOVERNANCE: Use canonical caps from config/thresholds.py
CBB_CONFIDENCE_CAPS = CONFIDENCE_CAPS  # Imported from config/thresholds.py

# Global CBB max (no SLAM tier)
CBB_MAX_CONFIDENCE = 0.79

# CBB tier thresholds (from canonical config)
# GOVERNANCE: Use canonical thresholds from config/thresholds.py
CBB_TIER_THRESHOLDS = get_all_thresholds("CBB")  # Imported from config/thresholds.py


@dataclass
class CBBProbResult:
    """Result from probability calculation."""
    probability: float
    player_mean: float
    raw_prob: float
    model: str
    data_source: str
    capped: bool
    stat_class: str
    adjusted_prob: float = 0.0
    signal_flag: str = "OK"


def get_stat_class(stat: str) -> str:
    """Get stat classification for confidence capping."""
    return CBB_STAT_CLASS.get(stat.lower(), "core")


def get_confidence_cap(stat: str) -> float:
    """Get maximum confidence cap for a stat."""
    stat_class = get_stat_class(stat)
    class_cap = CBB_CONFIDENCE_CAPS.get(stat_class, 0.72)
    return min(class_cap, CBB_MAX_CONFIDENCE)


# ============================================================================
# POISSON MODEL (CBB-specific - different from NBA's Normal model)
# ============================================================================

def poisson_pmf(lam: float, k: int) -> float:
    """
    Poisson probability mass function: P(X = k).
    
    P(X=k) = (λ^k * e^-λ) / k!
    """
    if k < 0 or lam <= 0:
        return 0.0
    try:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)
    except (OverflowError, ValueError):
        return 0.0


def poisson_cdf(lam: float, k: int) -> float:
    """
    Poisson cumulative distribution function: P(X <= k).
    """
    if k < 0:
        return 0.0
    total = sum(poisson_pmf(lam, i) for i in range(k + 1))
    return min(1.0, total)


def poisson_probability(mean: float, line: float, direction: str) -> float:
    """
    Compute probability using Poisson distribution.
    
    For "higher": P(X > line) = 1 - P(X <= floor(line))
    For "lower":  P(X < line) = P(X <= ceil(line) - 1)
    
    This is different from NBA which uses Normal distribution:
    - NBA: P(X > line) = 1 - Φ((line - μ) / σ)
    - CBB: P(X > line) = 1 - Σ P(X=k) for k=0 to floor(line)
    """
    if mean <= 0:
        return 0.5
    
    if direction == "higher":
        # P(X > line) = 1 - P(X <= floor(line))
        target = int(math.floor(line))
        prob = 1 - poisson_cdf(mean, target)
    else:
        # P(X < line) = P(X <= ceil(line) - 1)
        target = int(math.ceil(line)) - 1
        prob = poisson_cdf(mean, target)
    
    return max(0.0, min(1.0, prob))


def compute_cbb_probability(
    player_mean: float,
    line: float,
    direction: str,
    stat: str,
) -> CBBProbResult:
    """
    Compute CBB probability with governance caps.
    
    Args:
        player_mean: Player's average for this stat
        line: Prop line
        direction: "higher" or "lower"
        stat: Stat type (for capping)
    
    Returns:
        CBBProbResult with capped probability and metadata
    """
    # Raw Poisson probability
    raw_prob = poisson_probability(player_mean, line, direction)
    
    # Apply stat-specific cap
    stat_class = get_stat_class(stat)
    cap = get_confidence_cap(stat)
    
    # Apply cap (NO FLOOR in v2.0)
    capped_prob = min(raw_prob, cap)
    signal_flag = "WEAK_SIGNAL" if capped_prob < 0.50 else "OK"
    
    return CBBProbResult(
        probability=round(capped_prob, 4),
        player_mean=round(player_mean, 2),
        raw_prob=round(raw_prob, 4),
        adjusted_prob=round(raw_prob, 4),
        model="poisson",
        data_source="espn_cbb",
        capped=raw_prob > cap,
        stat_class=stat_class,
        signal_flag=signal_flag,
    )


def assign_tier(probability: float) -> str:
    """
    Assign CBB tier based on probability.
    
    CBB Tiers (no SLAM):
    - STRONG: ≥70%
    - LEAN: ≥60%
    - SKIP: <60%
    """
    if probability >= CBB_TIER_THRESHOLDS["STRONG"]:
        return "STRONG"
    elif probability >= CBB_TIER_THRESHOLDS["LEAN"]:
        return "LEAN"
    else:
        return "SKIP"


# ============================================================================
# COMPARISON: NBA vs CBB Probability Methods
# ============================================================================

def _nba_normal_probability(mean: float, std: float, line: float, direction: str) -> float:
    """
    NBA uses Normal (Gaussian) distribution:
    P(X > line) = 1 - Φ((line - μ) / σ)
    
    This is NOT used for CBB - shown for reference only.
    """
    if std <= 0:
        std = mean * 0.25  # Estimate
    
    z = (line - mean) / std
    
    # Standard normal CDF approximation
    def phi(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    if direction == "higher":
        return 1 - phi(z)
    else:
        return phi(z)


"""
Why Poisson for CBB instead of Normal?

1. DISCRETE COUNTS: Points, rebounds, assists are integers, not continuous.
   Poisson naturally models discrete event counts.

2. LOWER MEANS: CBB players score fewer points (12-20 PPG vs 20-30 NBA).
   Normal approximation works better with higher means.

3. ASYMMETRY: You can't score -2 points. Poisson is bounded at 0.
   Normal allows negative values which is unrealistic.

4. VARIANCE = MEAN: Poisson assumes variance ≈ mean.
   CBB stat variance often tracks close to the mean.

5. SAMPLE SIZE: ~30 games vs 82 in NBA.
   Poisson is more robust with smaller samples.

NBA can use Normal because:
- Higher scoring (larger means)
- Longer season (more data)
- CLT applies better with larger samples
- GMM/mixture models smooth the distribution
"""
