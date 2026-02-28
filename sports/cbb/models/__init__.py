"""
CBB Probability Models Module

Model choice: Poisson / Negative Binomial
Normal distribution is fragile in CBB.

Architecture mirrors NBA's ufa/analysis/ with:
- Poisson instead of Normal distribution
- Stricter confidence caps (no SLAM tier)
- CBB-specific stat classifications
"""
from .probability import compute_probability
from .calibration import calibrate_probabilities
from .prob import (
    poisson_probability,
    compute_cbb_probability,
    assign_tier,
    CBB_STAT_CLASS,
    CBB_CONFIDENCE_CAPS,
    CBB_TIER_THRESHOLDS,
)

__all__ = [
    "compute_probability",
    "calibrate_probabilities",
    "poisson_probability",
    "compute_cbb_probability",
    "assign_tier",
    "CBB_STAT_CLASS",
    "CBB_CONFIDENCE_CAPS",
    "CBB_TIER_THRESHOLDS",
]
