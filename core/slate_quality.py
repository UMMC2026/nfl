"""
Slate Quality Score — HARD-GATED
SOP v2.2: Every slate is objectively scored BEFORE picks are tiered.
Low-quality slates cannot masquerade as "bad model days".
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SlateQualityResult:
    """Machine-readable slate quality assessment."""
    score: int  # 0-100
    grade: str  # A/B/C/D/F
    drivers: List[str]  # Why quality is degraded
    defensive_recommended: bool
    max_allowed_tier: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slate_quality_score": self.score,
            "grade": self.grade,
            "drivers": self.drivers,
            "defensive_recommended": self.defensive_recommended,
            "max_allowed_tier": self.max_allowed_tier
        }


def compute_slate_quality(context: Dict[str, Any]) -> SlateQualityResult:
    """
    Compute Slate Quality Score (0-100).
    
    Inputs:
        context: Dict containing:
            - api_health: float (0.0-1.0)
            - injury_density: float (% of props with injury uncertainty)
            - avg_sigma: float (average standard deviation across props)
            - sigma_threshold: float (baseline sigma for quality check)
            - pct_above_55: float (% of props with confidence ≥55%)
            - minutes_stability: float (% of props with stable minutes, optional)
            - correlation_conflicts: int (number of correlated prop conflicts, optional)
    
    Returns:
        SlateQualityResult with score, grade, and enforcement flags.
    """
    score = 100
    drivers = []
    
    # Extract context values with safe defaults
    api_health = context.get("api_health", 1.0)
    injury_density = context.get("injury_density", 0.0)
    avg_sigma = context.get("avg_sigma", 5.0)
    sigma_threshold = context.get("sigma_threshold", 7.0)
    pct_above_55 = context.get("pct_above_55", 0.5)
    minutes_stability = context.get("minutes_stability", 1.0)
    correlation_conflicts = context.get("correlation_conflicts", 0)
    
    # ========== SCORING RULES (HARD-CODED) ==========
    
    # 1. API Health (-20 max)
    if api_health < 0.9:
        penalty = int((0.9 - api_health) * 50)  # Up to -20
        score -= min(penalty, 20)
        drivers.append(f"API degraded ({api_health:.0%})")
    
    # 2. Injury Density (-25 max)
    if injury_density > 0.15:
        penalty = int((injury_density - 0.15) * 100)  # Up to -25
        score -= min(penalty, 25)
        drivers.append(f"High injury volatility ({injury_density:.0%})")
    
    # 3. Variance Inflation (-20 max)
    if avg_sigma > sigma_threshold:
        penalty = int((avg_sigma - sigma_threshold) * 5)  # Up to -20
        score -= min(penalty, 20)
        drivers.append(f"Variance inflation (σ={avg_sigma:.1f} vs threshold {sigma_threshold:.1f})")
    
    # 4. Directional Clarity (-20 max)
    if pct_above_55 < 0.10:
        penalty = int((0.10 - pct_above_55) * 200)  # Up to -20
        score -= min(penalty, 20)
        drivers.append(f"Low directional clarity ({pct_above_55:.1%} ≥55%)")
    
    # 5. Minutes Stability (-10 max)
    if minutes_stability < 0.7:
        penalty = int((0.7 - minutes_stability) * 33)  # Up to -10
        score -= min(penalty, 10)
        drivers.append(f"Minutes uncertainty ({minutes_stability:.0%} stable)")
    
    # 6. Correlation Conflicts (-5 max)
    if correlation_conflicts > 5:
        penalty = min(correlation_conflicts - 5, 5)
        score -= penalty
        drivers.append(f"Correlation conflicts ({correlation_conflicts})")
    
    # Clamp score
    score = max(0, min(100, score))
    
    # Determine grade
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"
    
    # Defensive mode recommendation
    defensive_recommended = score < 50
    
    # Max allowed tier
    if score < 40:
        max_allowed_tier = "LEAN"
    elif score < 50:
        max_allowed_tier = "STRONG"
    else:
        max_allowed_tier = "SLAM"
    
    result = SlateQualityResult(
        score=score,
        grade=grade,
        drivers=drivers if drivers else ["All metrics within normal range"],
        defensive_recommended=defensive_recommended,
        max_allowed_tier=max_allowed_tier
    )
    
    logger.info(f"Slate Quality: {score}/100 ({grade}) | Defensive: {defensive_recommended}")
    
    return result


def compute_slate_context_from_results(results: List[Dict[str, Any]], api_health: float = 1.0) -> Dict[str, Any]:
    """
    Build slate quality context from analysis results.
    
    This extracts the metrics needed for compute_slate_quality() from
    a list of analyzed prop results.
    """
    if not results:
        return {
            "api_health": api_health,
            "injury_density": 0.0,
            "avg_sigma": 5.0,
            "sigma_threshold": 7.0,
            "pct_above_55": 0.0,
            "minutes_stability": 1.0,
            "correlation_conflicts": 0
        }
    
    total = len(results)
    
    # Injury density
    injury_count = sum(1 for r in results if r.get("injury_return", False))
    injury_density = injury_count / total
    
    # Average sigma
    sigmas = [r.get("sigma", 5.0) for r in results if r.get("sigma")]
    avg_sigma = sum(sigmas) / len(sigmas) if sigmas else 5.0
    
    # Percentage above 55% confidence
    above_55 = sum(1 for r in results if r.get("model_confidence", 0) >= 55)
    pct_above_55 = above_55 / total
    
    # Minutes stability (based on minutes_cv)
    cvs = [r.get("minutes_cv", 0) for r in results if r.get("minutes_cv") is not None]
    if cvs:
        avg_cv = sum(cvs) / len(cvs)
        minutes_stability = max(0, 1 - avg_cv)  # Lower CV = higher stability
    else:
        minutes_stability = 1.0
    
    # Correlation conflicts (placeholder - can be computed from edge data)
    correlation_conflicts = 0
    
    return {
        "api_health": api_health,
        "injury_density": injury_density,
        "avg_sigma": avg_sigma,
        "sigma_threshold": 7.0,  # NBA baseline
        "pct_above_55": pct_above_55,
        "minutes_stability": minutes_stability,
        "correlation_conflicts": correlation_conflicts
    }
