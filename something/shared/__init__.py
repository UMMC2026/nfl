"""
FUOOM DARK MATTER - Math Fixes Package
=======================================
Core mathematical corrections per System Stability Audit.

Modules:
    math_utils: Foundation calculations (Kelly, EV, tiers, odds)
    validate_output: Hard gate validation for picks
    diagnostic_audit: Historical analysis for error quantification
"""

from .math_utils import (
    # Tiers
    Tier,
    TIER_THRESHOLDS,
    probability_to_tier,
    validate_tier_probability_alignment,
    
    # Odds
    american_to_implied,
    american_to_decimal,
    decimal_to_american,
    remove_vig,
    calculate_vig,
    
    # Edge & EV
    calculate_edge,
    calculate_ev,
    
    # Kelly
    KellyResult,
    KELLY_FRACTIONS,
    MAX_KELLY_CAP,
    calculate_kelly,
    validate_kelly_edge,
    
    # Sigma & Compression
    SIGMA_TABLE,
    get_sigma,
    compression_check,
    
    # Calibration
    BRIER_THRESHOLDS,
    calculate_brier_score,
    is_calibration_acceptable,
)

__version__ = "1.0.0"
__all__ = [
    'Tier',
    'TIER_THRESHOLDS', 
    'probability_to_tier',
    'validate_tier_probability_alignment',
    'american_to_implied',
    'american_to_decimal',
    'decimal_to_american',
    'remove_vig',
    'calculate_vig',
    'calculate_edge',
    'calculate_ev',
    'KellyResult',
    'KELLY_FRACTIONS',
    'MAX_KELLY_CAP',
    'calculate_kelly',
    'validate_kelly_edge',
    'SIGMA_TABLE',
    'get_sigma',
    'compression_check',
    'BRIER_THRESHOLDS',
    'calculate_brier_score',
    'is_calibration_acceptable',
]
