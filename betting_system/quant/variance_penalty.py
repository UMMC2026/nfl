#!/usr/bin/env python3
"""
VARIANCE_PENALTY.PY — SOP v2.1 QUANT FRAMEWORK
==============================================
Implements variance-based confidence penalties.

THIS WAS MISSING FROM YOUR SYSTEM.

High variance players should have LOWER confidence, even if their
average is above the line. A player averaging 7.6 assists with σ=3.9
is much riskier than one averaging 7.6 with σ=1.5.

Coefficient of Variation (CV) = σ / μ
- CV > 0.35: High variance → 10% penalty
- CV > 0.25: Medium variance → 5% penalty
- CV ≤ 0.25: Low variance → No penalty

Version: 2.1.0
Author: SOP v2.1 Integration
"""

from typing import Dict, Tuple
from dataclasses import dataclass


# ============================================================================
# CONFIGURATION
# ============================================================================

# CV thresholds and penalties
# RESTORED 2026-02-04: Weak penalties caused 28% overconfidence crisis
# Calibration showed predicted 73% vs actual 43.5% — penalties MUST be strong
CV_THRESHOLDS = {
    "extreme": {"threshold": 0.50, "penalty": 0.85},   # -15% confidence (CV > 0.50)
    "high": {"threshold": 0.35, "penalty": 0.90},      # -10% confidence (CV > 0.35)
    "medium": {"threshold": 0.25, "penalty": 0.95},    # -5% confidence (CV > 0.25)
    "low": {"threshold": 0.00, "penalty": 1.00}        # No penalty
}

# Sample size penalties
# RESTORED 2026-02-04: Small samples are genuinely risky
SAMPLE_SIZE_THRESHOLDS = {
    "minimum": 5,      # Below this = NO PLAY
    "low": 8,          # 5-8 games = -10% penalty
    "medium": 12,      # 8-12 games = -5% penalty
    "adequate": 15,    # 12-15 games = -3% penalty
    "full": 15         # 15+ games = no penalty
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class VariancePenaltyResult:
    """Result of variance penalty calculation"""
    original_confidence: float
    adjusted_confidence: float
    
    # Variance components
    std_dev: float
    mean: float
    cv: float
    cv_category: str
    cv_penalty: float
    
    # Sample size components
    sample_size: int
    sample_category: str
    sample_penalty: float
    
    # Combined
    total_penalty: float
    
    # Flags
    is_high_variance: bool
    is_low_sample: bool


# ============================================================================
# PENALTY CALCULATIONS
# ============================================================================

def calculate_cv(std_dev: float, mean: float) -> float:
    """
    Calculate Coefficient of Variation.
    
    CV = σ / μ
    
    Interpretation:
    - CV < 0.25: Low variance (consistent player)
    - CV 0.25-0.35: Medium variance (normal)
    - CV > 0.35: High variance (volatile player)
    - CV > 0.50: Extreme variance (very risky)
    """
    if mean <= 0:
        return 0.0
    return std_dev / mean


def get_cv_category(cv: float) -> Tuple[str, float]:
    """
    Get CV category and corresponding penalty.
    
    Returns: (category_name, penalty_multiplier)
    """
    if cv >= CV_THRESHOLDS["extreme"]["threshold"]:
        return "EXTREME", CV_THRESHOLDS["extreme"]["penalty"]
    elif cv >= CV_THRESHOLDS["high"]["threshold"]:
        return "HIGH", CV_THRESHOLDS["high"]["penalty"]
    elif cv >= CV_THRESHOLDS["medium"]["threshold"]:
        return "MEDIUM", CV_THRESHOLDS["medium"]["penalty"]
    else:
        return "LOW", CV_THRESHOLDS["low"]["penalty"]


def get_sample_size_penalty(n: int) -> Tuple[str, float]:
    """
    Get sample size category and penalty.
    
    Returns: (category_name, penalty_multiplier)
    """
    if n < SAMPLE_SIZE_THRESHOLDS["minimum"]:
        return "INSUFFICIENT", 0.0  # NO PLAY
    elif n < SAMPLE_SIZE_THRESHOLDS["low"]:
        return "LOW", 0.90  # -10%
    elif n < SAMPLE_SIZE_THRESHOLDS["medium"]:
        return "MEDIUM", 0.95  # -5%
    elif n < SAMPLE_SIZE_THRESHOLDS["adequate"]:
        return "ADEQUATE", 0.97  # -3%
    else:
        return "FULL", 1.00  # No penalty


def apply_variance_penalty(
    confidence: float,
    std_dev: float,
    mean: float,
    sample_size: int
) -> VariancePenaltyResult:
    """
    Apply variance and sample size penalties to confidence.
    
    Args:
        confidence: Original confidence (0.0 to 1.0)
        std_dev: Standard deviation of player's stat
        mean: Mean of player's stat (the projection)
        sample_size: Number of games in sample
        
    Returns:
        VariancePenaltyResult with all calculations
    """
    
    # Calculate CV
    cv = calculate_cv(std_dev, mean)
    cv_category, cv_penalty = get_cv_category(cv)
    
    # Get sample size penalty
    sample_category, sample_penalty = get_sample_size_penalty(sample_size)
    
    # Combined penalty (multiply both)
    total_penalty = cv_penalty * sample_penalty
    
    # Apply to confidence
    adjusted_confidence = confidence * total_penalty
    
    # Flags
    is_high_variance = cv >= CV_THRESHOLDS["high"]["threshold"]
    is_low_sample = sample_size < SAMPLE_SIZE_THRESHOLDS["medium"]
    
    return VariancePenaltyResult(
        original_confidence=round(confidence, 4),
        adjusted_confidence=round(adjusted_confidence, 4),
        std_dev=round(std_dev, 2),
        mean=round(mean, 2),
        cv=round(cv, 3),
        cv_category=cv_category,
        cv_penalty=cv_penalty,
        sample_size=sample_size,
        sample_category=sample_category,
        sample_penalty=sample_penalty,
        total_penalty=round(total_penalty, 3),
        is_high_variance=is_high_variance,
        is_low_sample=is_low_sample
    )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def quick_variance_check(std_dev: float, mean: float) -> Dict:
    """
    Quick check for variance risk without full penalty calculation.
    
    Returns dict with cv, category, and risk flag.
    """
    cv = calculate_cv(std_dev, mean)
    category, penalty = get_cv_category(cv)
    
    return {
        "cv": round(cv, 3),
        "category": category,
        "penalty": penalty,
        "is_risky": cv >= CV_THRESHOLDS["medium"]["threshold"],
        "recommendation": _get_variance_recommendation(cv)
    }


def _get_variance_recommendation(cv: float) -> str:
    """Get human-readable recommendation based on CV"""
    if cv >= 0.50:
        return "EXTREME VARIANCE — Strongly consider NO PLAY or reduce units by 50%"
    elif cv >= 0.35:
        return "HIGH VARIANCE — Reduce confidence by 10%, consider smaller bet"
    elif cv >= 0.25:
        return "MEDIUM VARIANCE — Standard risk, apply 5% haircut"
    else:
        return "LOW VARIANCE — Consistent player, no adjustment needed"


def format_variance_report(result: VariancePenaltyResult) -> str:
    """Format variance penalty result as readable report"""
    
    lines = []
    lines.append(f"┌─ VARIANCE PENALTY ANALYSIS ─────────────────────────────────")
    lines.append(f"│")
    lines.append(f"│  Original Confidence:  {result.original_confidence:.1%}")
    lines.append(f"│  Adjusted Confidence:  {result.adjusted_confidence:.1%}")
    lines.append(f"│")
    lines.append(f"│  Variance Analysis:")
    lines.append(f"│    Mean (μ):           {result.mean}")
    lines.append(f"│    Std Dev (σ):        {result.std_dev}")
    lines.append(f"│    CV (σ/μ):           {result.cv:.1%}")
    lines.append(f"│    CV Category:        {result.cv_category}")
    lines.append(f"│    CV Penalty:         {result.cv_penalty:.0%}")
    lines.append(f"│")
    lines.append(f"│  Sample Size Analysis:")
    lines.append(f"│    Games:              {result.sample_size}")
    lines.append(f"│    Category:           {result.sample_category}")
    lines.append(f"│    Sample Penalty:     {result.sample_penalty:.0%}")
    lines.append(f"│")
    lines.append(f"│  Combined Penalty:     {result.total_penalty:.0%}")
    lines.append(f"│")
    
    # Risk flags
    flags = []
    if result.is_high_variance:
        flags.append("⚠️ HIGH VARIANCE")
    if result.is_low_sample:
        flags.append("⚠️ LOW SAMPLE SIZE")
    
    if flags:
        lines.append(f"│  Risk Flags: {', '.join(flags)}")
    else:
        lines.append(f"│  Risk Flags: None")
    
    lines.append(f"└───────────────────────────────────────────────────────────")
    
    return "\n".join(lines)


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    # Test with Amen Thompson example
    # assists: mean=7.6, std=3.9, n=10
    
    print("=" * 60)
    print("VARIANCE PENALTY TEST — Amen Thompson Assists")
    print("=" * 60)
    
    result = apply_variance_penalty(
        confidence=0.645,  # Original confidence
        std_dev=3.9,
        mean=7.6,
        sample_size=10
    )
    
    print(format_variance_report(result))
    
    print()
    print("Quick check:")
    quick = quick_variance_check(3.9, 7.6)
    print(f"  CV: {quick['cv']}")
    print(f"  Category: {quick['category']}")
    print(f"  Recommendation: {quick['recommendation']}")
    
    # Compare with a more consistent player
    print()
    print("=" * 60)
    print("COMPARISON — Consistent Player (same mean, lower variance)")
    print("=" * 60)
    
    result2 = apply_variance_penalty(
        confidence=0.645,
        std_dev=1.5,  # Much lower variance
        mean=7.6,
        sample_size=25
    )
    
    print(format_variance_report(result2))
