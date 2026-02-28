"""
GOLF SHADOW ANCHOR FORMULA v1.0
================================

CHALLENGE:
Golf uses multiplier-based edges (market efficiency), not stat projections.
But ESS/FAS need mu, sigma, edge_std to measure stability and attribute failures.

SOLUTION: SHADOW ANCHOR
Golf maintains TWO parallel representations:

1. PRIMARY (Market Efficiency):
   - Multiplier-based (e.g., 0.85x better_mult = 15% edge)
   - Captures pricing inefficiency
   - Used for probability/tier assignment

2. SHADOW (Performance Anchor):
   - SG:Total → Expected Score
   - Enables ESS stability scoring
   - Enables FAS failure attribution

HYBRID APPROACH:
- probability comes from multipliers (market edge)
- mu/sigma come from SG:Total (performance anchor)
- Both stored in UGO for different purposes

This preserves golf's unique pricing advantage while enabling governance.
"""

from typing import Tuple, Dict, Optional
from dataclasses import dataclass
import statistics


# =============================================================================
# STROKES GAINED (SG) FRAMEWORK
# =============================================================================

@dataclass
class SGPerformanceProfile:
    """Strokes Gained performance metrics for a golfer."""
    sg_total: float          # Total strokes gained per round
    sg_off_tee: float        # Driving performance
    sg_approach: float       # Approach shots
    sg_around_green: float   # Short game
    sg_putting: float        # Putting
    
    # Historical variance (key for ESS)
    sg_total_std: float      # Standard deviation of SG:Total
    recent_rounds: int       # Sample size
    
    # Course fit (affects projection)
    course_difficulty: float = 0.0  # 0=neutral, +1=harder, -1=easier
    
    def get_variance_cv(self) -> float:
        """Coefficient of Variation for SG:Total."""
        if self.sg_total == 0:
            return 0.0
        return abs(self.sg_total_std / self.sg_total)


# =============================================================================
# SHADOW ANCHOR CALCULATION
# =============================================================================

def sg_to_expected_score(
    sg_total: float,
    course_baseline: float = 72.0,  # Par (default)
    course_difficulty: float = 0.0,  # Course adjustment
) -> float:
    """
    Convert Strokes Gained Total to Expected Score.
    
    Formula:
        Expected Score = Baseline - SG:Total + Course Difficulty Adjustment
    
    Example:
        Player: Scottie Scheffler
        SG:Total: +2.5 (2.5 strokes better than field average)
        Course: Augusta National, Par 72
        Expected Score: 72 - 2.5 = 69.5
    
    Lower score = better in golf (inverted metric).
    """
    expected_score = course_baseline - sg_total + course_difficulty
    return expected_score


def sg_variance_to_sigma(
    sg_total: float,
    sg_total_std: float,
    course_variance_multiplier: float = 1.0,
) -> float:
    """
    Convert SG:Total variance to score sigma.
    
    Variance in golf comes from:
    1. Player consistency (sg_total_std)
    2. Course difficulty/setup (variance multiplier)
    3. Weather/conditions (captured in multiplier)
    
    Returns:
        sigma: Standard deviation of expected score
    """
    # Base variance from player's historical SG variance
    base_sigma = abs(sg_total_std)
    
    # Adjust for course variance (major championships = higher variance)
    sigma = base_sigma * course_variance_multiplier
    
    # Floor at 2.0 (even most consistent players have 2-stroke variance)
    return max(sigma, 2.0)


def calculate_golf_shadow_anchor(
    sg_profile: SGPerformanceProfile,
    prop_line: float,
    course_baseline: float = 72.0,
    course_variance_multiplier: float = 1.0,
) -> Tuple[float, float, float]:
    """
    Generate shadow anchor (mu, sigma, edge_std) from SG:Total.
    
    Returns:
        (mu, sigma, edge_std)
        
    Where:
        mu = Expected score (performance anchor)
        sigma = Score variance (uncertainty)
        edge_std = (mu - line) / sigma  ← For finishing position, INVERTED
                                           (lower score = better finish)
    """
    # Calculate expected score (mu)
    mu = sg_to_expected_score(
        sg_profile.sg_total,
        course_baseline,
        sg_profile.course_difficulty
    )
    
    # Calculate variance (sigma)
    sigma = sg_variance_to_sigma(
        sg_profile.sg_total,
        sg_profile.sg_total_std,
        course_variance_multiplier
    )
    
    # Calculate edge_std (z-score)
    # NOTE: For score-based props, lower is better
    # For finishing position props, this gets inverted in adapter
    edge_std = (mu - prop_line) / sigma if sigma > 0 else 0.0
    
    return mu, sigma, edge_std


# =============================================================================
# COURSE ADJUSTMENTS
# =============================================================================

COURSE_DIFFICULTY_MAP = {
    # Major Championships (harder)
    "Masters": 2.5,
    "US Open": 3.0,
    "The Open Championship": 2.0,
    "PGA Championship": 2.0,
    
    # Designated Events (moderate)
    "THE PLAYERS Championship": 1.5,
    "Genesis Invitational": 1.0,
    "Arnold Palmer Invitational": 1.5,
    
    # Regular Events (neutral)
    "default": 0.0,
}

COURSE_VARIANCE_MULTIPLIER = {
    # Major Championships = higher variance (tougher conditions)
    "Masters": 1.3,
    "US Open": 1.5,
    "The Open Championship": 1.4,  # Weather variability
    "PGA Championship": 1.2,
    
    # Regular events = lower variance
    "default": 1.0,
}


def get_course_adjustments(tournament: str) -> Tuple[float, float]:
    """Get difficulty and variance adjustments for tournament."""
    difficulty = COURSE_DIFFICULTY_MAP.get(tournament, 0.0)
    variance_mult = COURSE_VARIANCE_MULTIPLIER.get(tournament, 1.0)
    return difficulty, variance_mult


# =============================================================================
# ESS / FAS INTEGRATION
# =============================================================================

def calculate_golf_stability_score(sg_profile: SGPerformanceProfile) -> float:
    """
    Calculate stability score for golf (0.0-1.0).
    
    Based on:
    1. SG:Total consistency (CV)
    2. Sample size (recent rounds)
    3. Component balance (not over-reliant on putting)
    
    Returns:
        stability: 0.0 (fragile) to 1.0 (stable)
    """
    # 1. Consistency (lower CV = more stable)
    cv = sg_profile.get_variance_cv()
    consistency_score = max(0.0, 1.0 - cv)  # CV > 1.0 = very unstable
    
    # 2. Sample size penalty (need ≥10 rounds for confidence)
    sample_score = min(1.0, sg_profile.recent_rounds / 10.0)
    
    # 3. Component balance (avoid putting-dependent players)
    # If SG:Putting > 50% of SG:Total, that's risky (variance amplifier)
    putting_ratio = abs(sg_profile.sg_putting / sg_profile.sg_total) if sg_profile.sg_total != 0 else 0
    balance_score = 1.0 - min(0.5, putting_ratio)  # Max 50% penalty
    
    # Combined stability
    stability = (consistency_score * 0.4 + sample_score * 0.3 + balance_score * 0.3)
    return max(0.0, min(1.0, stability))


def golf_failure_attribution_tags(
    sg_profile: SGPerformanceProfile,
    actual_score: Optional[float] = None,
    expected_score: Optional[float] = None,
) -> list[str]:
    """
    Generate FAS tags for golf failures.
    
    Tags:
    - SG_VARIANCE: High SG:Total variance
    - PUTTING_DEPENDENT: Over-reliant on putting
    - SMALL_SAMPLE: < 10 rounds
    - SG_COLLAPSE: Major SG component underperformed
    - COURSE_MISMATCH: Course didn't suit player
    """
    tags = []
    
    # Variance check
    cv = sg_profile.get_variance_cv()
    if cv > 0.5:
        tags.append("SG_VARIANCE")
    
    # Putting dependency
    if abs(sg_profile.sg_putting / sg_profile.sg_total) > 0.5:
        tags.append("PUTTING_DEPENDENT")
    
    # Sample size
    if sg_profile.recent_rounds < 10:
        tags.append("SMALL_SAMPLE")
    
    # Post-mortem: If actual score available
    if actual_score and expected_score:
        score_diff = actual_score - expected_score
        if score_diff > 3.0:  # Shot 3+ strokes worse
            tags.append("SG_COLLAPSE")
        if abs(score_diff) > 2 * sg_profile.sg_total_std:
            tags.append("TAIL_EVENT")
    
    return tags


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("GOLF SHADOW ANCHOR FORMULA — EXAMPLES")
    print("="*70)
    
    # Example 1: Scottie Scheffler (elite, consistent)
    scheffler = SGPerformanceProfile(
        sg_total=2.5,
        sg_off_tee=0.6,
        sg_approach=1.2,
        sg_around_green=0.4,
        sg_putting=0.3,
        sg_total_std=1.8,
        recent_rounds=12,
        course_difficulty=2.5  # Masters
    )
    
    mu, sigma, edge_std = calculate_golf_shadow_anchor(
        scheffler,
        prop_line=69.5,  # First Round Score
        course_baseline=72.0,
        course_variance_multiplier=1.3
    )
    
    stability = calculate_golf_stability_score(scheffler)
    
    print(f"\n📊 EXAMPLE 1: Scottie Scheffler @ Masters")
    print(f"   SG:Total: +{scheffler.sg_total:.1f}")
    print(f"   Expected Score (mu): {mu:.1f}")
    print(f"   Uncertainty (sigma): {sigma:.1f}")
    print(f"   Prop Line: {69.5}")
    print(f"   Edge Z-Score: {edge_std:.2f}")
    print(f"   Stability Score: {stability:.2f}")
    print(f"   Interpretation: Expected to shoot {mu:.1f}, line is {69.5}")
    print(f"                   Edge is {edge_std:.2f} standard deviations")
    
    # Example 2: Journeyman (inconsistent)
    journeyman = SGPerformanceProfile(
        sg_total=0.2,
        sg_off_tee=-0.1,
        sg_approach=0.1,
        sg_around_green=0.0,
        sg_putting=0.2,
        sg_total_std=2.5,
        recent_rounds=8,
        course_difficulty=0.0
    )
    
    mu2, sigma2, edge_std2 = calculate_golf_shadow_anchor(
        journeyman,
        prop_line=72.5,
        course_baseline=72.0,
        course_variance_multiplier=1.0
    )
    
    stability2 = calculate_golf_stability_score(journeyman)
    tags = golf_failure_attribution_tags(journeyman)
    
    print(f"\n📊 EXAMPLE 2: Journeyman @ Regular Event")
    print(f"   SG:Total: +{journeyman.sg_total:.1f}")
    print(f"   Expected Score (mu): {mu2:.1f}")
    print(f"   Uncertainty (sigma): {sigma2:.1f}")
    print(f"   Prop Line: {72.5}")
    print(f"   Edge Z-Score: {edge_std2:.2f}")
    print(f"   Stability Score: {stability2:.2f}")
    print(f"   FAS Tags: {tags}")
    print(f"   ⚠️ Fragile pick due to high variance + small sample")
    
    print("\n" + "="*70)
    print("✅ SHADOW ANCHOR ENABLES:")
    print("   • ESS stability scoring (CV-based)")
    print("   • FAS failure attribution (SG component breakdown)")
    print("   • Cross-sport governance (edge_std comparability)")
    print("   • Preserves multiplier edge (pricing inefficiency)")
    print("="*70)
