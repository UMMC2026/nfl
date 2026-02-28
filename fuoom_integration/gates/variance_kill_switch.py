"""
FUOOM DARK MATTER - Variance Kill Switch
==========================================
Pre-model gate that determines if variance is existential or cosmetic.

This is GATE 3 in the pre-model pipeline.
It answers: "Can this stat behave predictably enough to model?"

Key Insight:
  Variance can be EXISTENTIAL (kills the prop entirely) or
  COSMETIC (just affects confidence).
  
  Most systems treat all variance as cosmetic.
  This gate identifies when variance should KILL.

Version: 1.0.0
Date: February 10, 2026
"""

from dataclasses import dataclass
from typing import Tuple, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

class VarianceLevel(Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class VarianceAction(Enum):
    ALLOW = "ALLOW"
    CAP_SLAM = "CAP_SLAM"
    CAP_STRONG = "CAP_STRONG"
    BLOCK = "BLOCK"


# Base CV thresholds (coefficient of variation = σ/μ)
CV_THRESHOLDS = {
    "extreme": 0.60,    # CV > 60% → BLOCK
    "high": 0.45,       # CV > 45% → CAP at STRONG
    "moderate": 0.30,   # CV > 30% → CAP at SLAM
    "low": 0.00,        # CV ≤ 30% → ALLOW
}

# Stat-specific volatility multipliers (some stats are inherently more volatile)
STAT_VOLATILITY = {
    # High volatility stats (stricter thresholds)
    "3pm": 0.75,
    "threes": 0.75,
    "steals": 0.80,
    "blocks": 0.80,
    "turnovers": 0.85,
    
    # Moderate volatility
    "assists": 0.90,
    "fantasy": 0.90,
    "fpts": 0.90,
    
    # Normal volatility
    "points": 1.00,
    "rebounds": 1.00,
    
    # Combo stats (inherit highest component volatility + penalty)
    "pra": 0.80,
    "pts+reb+ast": 0.80,
    "pts+reb": 0.85,
    "pts+ast": 0.85,
    "reb+ast": 0.85,
    
    "default": 1.00,
}

# Small sample penalties
SAMPLE_SIZE_MULTIPLIERS = {
    "tiny": (3, 0.60),     # n < 3: multiply thresholds by 0.60
    "small": (5, 0.75),    # n < 5: multiply by 0.75
    "limited": (10, 0.90), # n < 10: multiply by 0.90
    "adequate": (float('inf'), 1.00),  # n >= 10: normal
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VarianceResult:
    """Result from the variance kill switch."""
    allowed: bool
    action: str
    reason: str
    cv: float
    variance_level: str
    adjusted_thresholds: dict
    checks_performed: list
    
    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "reason": self.reason,
            "cv": self.cv,
            "variance_level": self.variance_level,
            "adjusted_thresholds": self.adjusted_thresholds,
            "checks_performed": self.checks_performed,
        }


# =============================================================================
# VARIANCE CALCULATIONS
# =============================================================================

def calculate_cv(mu: float, sigma: float) -> float:
    """
    Calculate coefficient of variation.
    CV = σ / μ (standard deviation relative to mean)
    
    Higher CV = more volatile relative to expected value.
    """
    if mu <= 0:
        # If mean is zero or negative, treat as maximally volatile
        return 1.0
    return sigma / mu


def get_stat_volatility_multiplier(stat_type: str) -> float:
    """Get the volatility multiplier for a stat type."""
    stat_lower = stat_type.lower().replace(" ", "").replace("+", "_")
    
    # Check direct match
    if stat_lower in STAT_VOLATILITY:
        return STAT_VOLATILITY[stat_lower]
    
    # Check for partial matches
    for key, mult in STAT_VOLATILITY.items():
        if key in stat_lower or stat_lower in key:
            return mult
    
    return STAT_VOLATILITY["default"]


def get_sample_size_multiplier(n: int) -> float:
    """Get threshold multiplier based on sample size."""
    for label, (threshold, mult) in SAMPLE_SIZE_MULTIPLIERS.items():
        if n < threshold:
            return mult
    return 1.0


def calculate_adjusted_thresholds(
    stat_type: str,
    sample_size: int
) -> dict:
    """
    Calculate adjusted CV thresholds based on stat type and sample size.
    
    More volatile stats and smaller samples get stricter thresholds.
    """
    stat_mult = get_stat_volatility_multiplier(stat_type)
    sample_mult = get_sample_size_multiplier(sample_size)
    combined_mult = stat_mult * sample_mult
    
    return {
        "extreme": CV_THRESHOLDS["extreme"] * combined_mult,
        "high": CV_THRESHOLDS["high"] * combined_mult,
        "moderate": CV_THRESHOLDS["moderate"] * combined_mult,
        "stat_multiplier": stat_mult,
        "sample_multiplier": sample_mult,
        "combined_multiplier": combined_mult,
    }


def classify_variance(
    cv: float,
    thresholds: dict
) -> Tuple[VarianceLevel, VarianceAction]:
    """
    Classify variance level and determine action.
    
    Returns (level, action) tuple.
    """
    if cv > thresholds["extreme"]:
        return VarianceLevel.EXTREME, VarianceAction.BLOCK
    elif cv > thresholds["high"]:
        return VarianceLevel.HIGH, VarianceAction.CAP_STRONG
    elif cv > thresholds["moderate"]:
        return VarianceLevel.MODERATE, VarianceAction.CAP_SLAM
    else:
        return VarianceLevel.LOW, VarianceAction.ALLOW


# =============================================================================
# SPECIAL CASE HANDLERS
# =============================================================================

def check_pra_over_trap(
    cv: float,
    stat_type: str,
    direction: str
) -> Tuple[bool, str]:
    """
    Special check for PRA OVER traps.
    
    PRA combines three stats = triple variance.
    OVER is especially vulnerable.
    """
    stat_lower = stat_type.lower().replace(" ", "").replace("+", "_")
    
    pra_variants = ["pra", "pts_reb_ast", "ptsrebast"]
    
    if any(v in stat_lower for v in pra_variants):
        if direction.upper() in ["OVER", "HIGHER"]:
            if cv > 0.35:
                return False, (
                    f"PRA OVER with CV={cv:.1%} - "
                    f"triple variance makes OVER extremely fragile"
                )
    
    return True, "Not a PRA OVER trap"


def check_low_volume_volatility(
    mu: float,
    sigma: float,
    stat_type: str
) -> Tuple[bool, str]:
    """
    Check for low-volume stats where even small σ is problematic.
    
    E.g., Steals line 0.5 with σ=0.8 → CV=160%, but looks normal.
    """
    stat_lower = stat_type.lower()
    
    low_volume_stats = ["steals", "blocks", "3pm", "threes"]
    
    if any(s in stat_lower for s in low_volume_stats):
        if mu < 2.0 and sigma > mu * 0.8:
            return False, (
                f"Low-volume volatility: μ={mu:.1f} with σ={sigma:.1f} "
                f"means outcomes are essentially binary"
            )
    
    return True, "Volume sufficient for modeling"


# =============================================================================
# MAIN GATE CLASS
# =============================================================================

class VarianceKillSwitch:
    """
    Pre-model gate that determines if variance should kill a prop.
    
    This gate answers: "Is variance existential or cosmetic?"
    
    EXISTENTIAL variance → BLOCK (prop should not exist)
    COSMETIC variance → CAP or ALLOW (adjust confidence downstream)
    
    It does NOT:
    - Calculate probabilities
    - Adjust projections
    - Apply calibration
    
    It ONLY:
    - Classifies variance level
    - Blocks extremely volatile props
    - Sets caps for downstream confidence
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
    
    def check(
        self,
        mu: float,
        sigma: float,
        stat_type: str,
        sample_size: int,
        direction: str = "OVER",
    ) -> VarianceResult:
        """
        Check if variance is existential (kills the prop) or cosmetic.
        
        Args:
            mu: Mean (projection)
            sigma: Standard deviation
            stat_type: Type of stat
            sample_size: Number of games in sample
            direction: OVER or UNDER
            
        Returns:
            VarianceResult with allowed/blocked status and action
        """
        checks_performed = []
        
        # Calculate CV
        cv = calculate_cv(mu, sigma)
        checks_performed.append(f"CV calculated: {cv:.1%}")
        
        # Get adjusted thresholds
        thresholds = calculate_adjusted_thresholds(stat_type, sample_size)
        checks_performed.append(
            f"Thresholds adjusted: stat={thresholds['stat_multiplier']:.2f}, "
            f"sample={thresholds['sample_multiplier']:.2f}"
        )
        
        # Special check: PRA OVER trap
        allowed, reason = check_pra_over_trap(cv, stat_type, direction)
        checks_performed.append(f"PRA check: {reason}")
        
        if not allowed:
            self._log_block(mu, sigma, stat_type, cv, reason)
            return VarianceResult(
                allowed=False,
                action="BLOCK",
                reason=reason,
                cv=cv,
                variance_level="EXTREME",
                adjusted_thresholds=thresholds,
                checks_performed=checks_performed,
            )
        
        # Special check: Low-volume volatility
        allowed, reason = check_low_volume_volatility(mu, sigma, stat_type)
        checks_performed.append(f"Low-volume check: {reason}")
        
        if not allowed:
            self._log_block(mu, sigma, stat_type, cv, reason)
            return VarianceResult(
                allowed=False,
                action="BLOCK",
                reason=reason,
                cv=cv,
                variance_level="EXTREME",
                adjusted_thresholds=thresholds,
                checks_performed=checks_performed,
            )
        
        # Standard variance classification
        level, action = classify_variance(cv, thresholds)
        checks_performed.append(f"Classification: {level.value} → {action.value}")
        
        if action == VarianceAction.BLOCK:
            reason = (
                f"VARIANCE KILL: CV={cv:.1%} exceeds threshold "
                f"{thresholds['extreme']:.1%} for {stat_type}"
            )
            self._log_block(mu, sigma, stat_type, cv, reason)
            return VarianceResult(
                allowed=False,
                action=action.value,
                reason=reason,
                cv=cv,
                variance_level=level.value,
                adjusted_thresholds=thresholds,
                checks_performed=checks_performed,
            )
        
        # Allowed (possibly with cap)
        if action == VarianceAction.CAP_STRONG:
            reason = f"CV={cv:.1%} is HIGH - capped at STRONG tier"
        elif action == VarianceAction.CAP_SLAM:
            reason = f"CV={cv:.1%} is MODERATE - capped at SLAM tier"
        else:
            reason = f"CV={cv:.1%} is LOW - no restrictions"
        
        return VarianceResult(
            allowed=True,
            action=action.value,
            reason=reason,
            cv=cv,
            variance_level=level.value,
            adjusted_thresholds=thresholds,
            checks_performed=checks_performed,
        )
    
    def _log_block(
        self,
        mu: float,
        sigma: float,
        stat_type: str,
        cv: float,
        reason: str
    ):
        """Log blocked props for audit trail."""
        logger.info(
            f"[BLOCKED][VARIANCE_KILL_SWITCH] "
            f"Stat: {stat_type} | "
            f"μ={mu:.2f}, σ={sigma:.2f}, CV={cv:.1%} | "
            f"Reason: {reason}"
        )


# =============================================================================
# CLI / DEMO
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    gate = VarianceKillSwitch()
    
    print("=" * 70)
    print("VARIANCE KILL SWITCH - DEMO")
    print("=" * 70)
    
    # Test cases
    tests = [
        # Should ALLOW - normal variance
        {"mu": 20.0, "sigma": 5.0, "stat_type": "points", 
         "sample_size": 10, "direction": "OVER",
         "desc": "Normal variance (CV=25%)"},
        
        # Should BLOCK - extreme variance
        {"mu": 5.0, "sigma": 4.0, "stat_type": "3pm",
         "sample_size": 10, "direction": "OVER",
         "desc": "Extreme 3PM variance (CV=80%)"},
        
        # Should BLOCK - PRA OVER trap
        {"mu": 35.0, "sigma": 15.0, "stat_type": "PRA",
         "sample_size": 10, "direction": "OVER",
         "desc": "PRA OVER trap (CV=43%)"},
        
        # Should CAP_STRONG - high variance
        {"mu": 10.0, "sigma": 5.0, "stat_type": "assists",
         "sample_size": 10, "direction": "OVER",
         "desc": "High variance assists (CV=50%)"},
        
        # Should BLOCK - low volume steals
        {"mu": 0.8, "sigma": 0.9, "stat_type": "steals",
         "sample_size": 10, "direction": "OVER",
         "desc": "Low volume steals (binary outcome)"},
        
        # Should CAP_STRONG - small sample penalty
        {"mu": 15.0, "sigma": 5.0, "stat_type": "points",
         "sample_size": 4, "direction": "OVER",
         "desc": "Small sample (n=4, CV=33%)"},
        
        # Should ALLOW - PRA UNDER is safer
        {"mu": 35.0, "sigma": 15.0, "stat_type": "PRA",
         "sample_size": 10, "direction": "UNDER",
         "desc": "PRA UNDER (protected direction)"},
    ]
    
    for i, test in enumerate(tests, 1):
        desc = test.pop("desc")
        result = gate.check(**test)
        
        status = "✓ " + result.action if result.allowed else "✗ BLOCK"
        print(f"\nTest {i}: {desc}")
        print(f"  CV: {result.cv:.1%}")
        print(f"  Level: {result.variance_level}")
        print(f"  Result: {status}")
        print(f"  Reason: {result.reason}")
