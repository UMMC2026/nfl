"""
ESS + FAS MATHEMATICAL SPECIFICATION v1.0
==========================================

FORMAL SPECIFICATION: How ESS and FAS consume Universal Governance Objects (UGO)

This document provides the complete mathematical framework for:
1. Edge Stability Score (ESS) — Pre-game stability quantification
2. Failure Attribution Schema (FAS) — Post-game failure classification

Both systems operate on UGO-standardized edges for cross-sport compatibility.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum
import math


# =============================================================================
# PART 1: EDGE STABILITY SCORE (ESS)
# =============================================================================

"""
ESS PURPOSE:
Quantify pick fragility BEFORE game time to filter out unstable edges.

ESS FORMULA:
    ESS = Dislocation × Precision × Context × Safety
    
Where:
    Dislocation = |mu - line| / line        # Raw value gap (normalized)
    Precision   = 1 / (1 + CV)              # Inverse of Coefficient of Variation
    Context     = min_stability × (1 - role_entropy)
    Safety      = 1 - tail_risk
    
TIER THRESHOLDS:
    ESS >= 0.75 → SLAM     (elite stability)
    ESS >= 0.55 → STRONG   (high stability)
    ESS >= 0.40 → LEAN-A   (moderate stability)
    ESS >= 0.25 → LEAN-B   (weak stability)
    ESS <  0.25 → SKIP     (fragile, reject)

INPUT (from UGO):
    Required:
        - mu: float         # Projection
        - sigma: float      # Standard deviation
        - line: float       # Prop line
        - edge_std: float   # (mu - line) / sigma
        - sample_n: int     # Games in sample
    
    Optional (sport-specific from sport_context):
        - minute_stability: float   # 0.0-1.0 (NBA/CBB)
        - role_entropy: float       # 0.0-1.0 (NBA/CBB)
        - blowout_risk: float       # 0.0-1.0 (NBA/CBB/NFL)
        - sg_total_std: float       # Variance (Golf)
        - weather_variance: float   # (NFL/Soccer)

OUTPUT:
    - ess_score: float (0.0-1.0+)
    - tier: SLAM/STRONG/LEAN-A/LEAN-B/SKIP
    - stability_tags: List[StabilityTag]
    - component_breakdown: Dict[str, float]
"""


@dataclass
class ESSInput:
    """Standardized ESS input from UGO."""
    # Core (required)
    mu: float
    sigma: float
    line: float
    edge_std: float
    sample_n: int
    direction: str  # HIGHER or LOWER
    
    # Sport-specific (optional)
    minute_stability: Optional[float] = None    # NBA/CBB only
    role_entropy: Optional[float] = None        # NBA/CBB only
    blowout_risk: Optional[float] = None        # NBA/CBB/NFL
    sg_variance: Optional[float] = None         # Golf only
    weather_impact: Optional[float] = None      # NFL/Soccer
    
    # Fallback defaults
    DEFAULT_MINUTE_STABILITY = 0.70
    DEFAULT_ROLE_ENTROPY = 0.30
    DEFAULT_BLOWOUT_RISK = 0.20


@dataclass
class ESSOutput:
    """ESS calculation result."""
    ess_score: float
    tier: str  # SLAM/STRONG/LEAN-A/LEAN-B/SKIP
    components: Dict[str, float]
    stability_tags: List[str]
    recommendation: str  # OPTIMIZABLE, VETTED, REJECT


def calculate_ess(input: ESSInput) -> ESSOutput:
    """
    Calculate Edge Stability Score from UGO.
    
    MATHEMATICAL DEFINITION:
    
    1. DISLOCATION (Value Gap):
       D = |mu - line| / line
       
       Measures raw edge size relative to line.
       Higher = larger gap = more value
       
    2. PRECISION (Inverse Variance):
       CV = sigma / mu           # Coefficient of Variation
       P = 1 / (1 + CV)          # Normalized precision
       
       Measures consistency.
       Lower CV = higher precision = more stable
       
    3. CONTEXT (Role/Minute Certainty):
       C = minute_stability × (1 - role_entropy)
       
       NBA/CBB: Combines minute consistency and rotation certainty
       NFL: Usage entropy
       Golf: Component balance (putting dependency)
       Soccer/Tennis: Defaults to 0.70
       
    4. SAFETY (Tail Risk Protection):
       For HIGHER: tail_risk = P(X < 0.5 * mu)
       For LOWER: tail_risk = P(X > 2.0 * mu)
       S = 1 - tail_risk
       
       Protects against catastrophic outcomes.
       
    5. FINAL ESS:
       ESS = D × P × C × S × 10
       
       Multiplied by 10 to scale to [0, 1+] range
    """
    
    # 1. Dislocation
    dislocation = abs(input.mu - input.line) / input.line if input.line != 0 else 0
    
    # 2. Precision
    cv = input.sigma / input.mu if input.mu != 0 else 1.0
    precision = 1.0 / (1.0 + cv)
    
    # 3. Context (sport-specific)
    if input.minute_stability is not None and input.role_entropy is not None:
        # NBA/CBB: Use actual values
        context = input.minute_stability * (1.0 - input.role_entropy)
    else:
        # Other sports: Use defaults
        context = ESSInput.DEFAULT_MINUTE_STABILITY * (1.0 - ESSInput.DEFAULT_ROLE_ENTROPY)
    
    # 4. Safety (tail risk)
    # Calculate tail risk from normal distribution
    if input.direction == "HIGHER":
        # Tail risk: P(X < 0.5 * mu)
        z_tail = (0.5 * input.mu - input.mu) / input.sigma
        tail_risk = norm_cdf(z_tail)
    else:
        # Tail risk: P(X > 2.0 * mu)
        z_tail = (2.0 * input.mu - input.mu) / input.sigma
        tail_risk = 1.0 - norm_cdf(z_tail)
    
    safety = 1.0 - tail_risk
    
    # 5. Calculate ESS
    ess = dislocation * precision * context * safety * 10.0
    
    # Determine tier
    if ess >= 0.75:
        tier = "SLAM"
        recommendation = "OPTIMIZABLE"
    elif ess >= 0.55:
        tier = "STRONG"
        recommendation = "OPTIMIZABLE"
    elif ess >= 0.40:
        tier = "LEAN-A"
        recommendation = "OPTIMIZABLE"
    elif ess >= 0.25:
        tier = "LEAN-B"
        recommendation = "VETTED"  # Context only
    else:
        tier = "SKIP"
        recommendation = "REJECT"
    
    # Generate stability tags
    tags = []
    if cv > 0.5:
        tags.append("HIGH_VARIANCE")
    if input.sample_n < 5:
        tags.append("LOW_SAMPLE")
    if input.role_entropy and input.role_entropy > 0.5:
        tags.append("ROLE_UNCERTAINTY")
    if ess < 0.40:
        tags.append("FRAGILE")
    if input.blowout_risk and input.blowout_risk > 0.30:
        tags.append("BLOWOUT_RISK")
    if tail_risk > 0.15:
        tags.append("TAIL_RISK")
    
    return ESSOutput(
        ess_score=round(ess, 4),
        tier=tier,
        components={
            "dislocation": round(dislocation, 4),
            "precision": round(precision, 4),
            "context": round(context, 4),
            "safety": round(safety, 4),
            "cv": round(cv, 4),
            "tail_risk": round(tail_risk, 4),
        },
        stability_tags=tags,
        recommendation=recommendation
    )


# =============================================================================
# PART 2: FAILURE ATTRIBUTION SCHEMA (FAS)
# =============================================================================

"""
FAS PURPOSE:
Classify WHY a pick failed post-game for learning and model improvement.

FAS TAXONOMY:
    MIN_VAR     - Minute variance (played far less than projected)
    USG_DROP    - Usage drop (targets/touches down significantly)
    BLOWOUT_FN  - False negative blowout (garbage time didn't help as expected)
    BLOWOUT_FP  - False positive blowout (competitive game, no garbage time)
    TAIL_EVT    - Tail event (>2σ below expectation, pure bad luck)
    STAT_VAR    - Statistical variance (within 1σ, normal variance)
    OPPONENT    - Opponent adjustment was wrong (elite defense underestimated)
    COACHING    - Coaching decision (benched, rotation change)
    INJURY      - In-game injury or limitation
    SPECIALIST  - Specialist cap was wrong (shot type variance)

DECISION TREE:

    Did player play expected minutes?
    ├─ NO → MIN_VAR
    │     └─ Check: Was it coaching decision? → COACHING
    └─ YES → Continue
    
    Was usage (targets/FGA/touches) as expected?
    ├─ NO → USG_DROP
    │     └─ Check: Blowout-related? → BLOWOUT_FN/FP
    └─ YES → Continue
    
    Was game competitive (spread < 15 final)?
    ├─ NO (blowout)
    │   ├─ Proj assumed garbage time boost? → BLOWOUT_FN
    │   └─ Proj didn't account for blowout? → STAT_VAR
    └─ YES → Continue
    
    How far from projection?
    ├─ > 2σ → TAIL_EVT (bad luck)
    ├─ 1-2σ → OPPONENT (check defensive matchup)
    └─ < 1σ → STAT_VAR (normal variance)

OUTPUT:
    - primary_attribution: str (main failure reason)
    - secondary_attributions: List[str] (contributing factors)
    - sigma_distance: float (how far from projection)
    - is_learnable: bool (True if model can improve, False if bad luck)
    - model_adjustment: Optional[str] (what to change)
"""


@dataclass
class FASInput:
    """Post-game failure analysis input."""
    # Pre-game projection (from UGO)
    mu: float
    sigma: float
    line: float
    direction: str
    probability: float
    
    # Actual game outcome
    actual_stat: float
    actual_minutes: Optional[float] = None
    projected_minutes: Optional[float] = None
    actual_usage: Optional[float] = None  # FGA, targets, touches
    projected_usage: Optional[float] = None
    
    # Game context
    final_spread: Optional[float] = None
    was_blowout: bool = False
    opponent_defensive_rating: Optional[int] = None
    
    # Flags
    in_game_injury: bool = False
    coaching_change: bool = False  # Benched, rotation shift


@dataclass
class FASOutput:
    """Failure attribution result."""
    primary_attribution: str
    secondary_attributions: List[str]
    sigma_distance: float
    is_learnable: bool
    confidence: float  # 0.0-1.0 (attribution confidence)
    model_adjustment: Optional[str]
    learning_priority: str  # HIGH, MEDIUM, LOW


def attribute_failure(input: FASInput) -> FASOutput:
    """
    Classify failure reason using decision tree.
    
    ATTRIBUTION LOGIC:
    
    1. Calculate sigma distance:
       For HIGHER: sigma_dist = (mu - actual) / sigma
       For LOWER: sigma_dist = (actual - mu) / sigma
       
       (Positive = missed by that many std devs)
    
    2. Check minute variance:
       If |actual_min - projected_min| > 8 minutes → MIN_VAR
       
    3. Check usage drop:
       If actual_usage < 0.7 * projected_usage → USG_DROP
       
    4. Check blowout:
       If was_blowout and sigma_dist > 1.5 → BLOWOUT_FN/FP
       
    5. Check tail event:
       If sigma_dist > 2.0 → TAIL_EVT (bad luck)
       
    6. Check opponent:
       If sigma_dist > 1.0 and elite defense → OPPONENT
       
    7. Default:
       STAT_VAR (normal variance)
    """
    
    # Calculate sigma distance
    if input.direction == "HIGHER":
        sigma_dist = (input.mu - input.actual_stat) / input.sigma
    else:
        sigma_dist = (input.actual_stat - input.mu) / input.sigma
    
    # Initialize
    primary = "STAT_VAR"
    secondary = []
    is_learnable = True
    adjustment = None
    priority = "LOW"
    
    # 1. Minute variance check
    if input.actual_minutes and input.projected_minutes:
        min_diff = abs(input.actual_minutes - input.projected_minutes)
        if min_diff > 8:
            primary = "MIN_VAR"
            is_learnable = True
            adjustment = "Improve minute projection model"
            priority = "HIGH"
            
            if input.coaching_change:
                secondary.append("COACHING")
            if input.in_game_injury:
                secondary.append("INJURY")
    
    # 2. Usage drop check
    elif input.actual_usage and input.projected_usage:
        usage_ratio = input.actual_usage / input.projected_usage
        if usage_ratio < 0.70:
            primary = "USG_DROP"
            is_learnable = True
            adjustment = "Add usage entropy penalty"
            priority = "HIGH"
            
            if input.was_blowout:
                secondary.append("BLOWOUT_FN")
    
    # 3. Blowout check
    elif input.was_blowout and sigma_dist > 1.5:
        if input.final_spread and abs(input.final_spread) > 20:
            primary = "BLOWOUT_FN"  # Expected garbage time, didn't materialize
            is_learnable = True
            adjustment = "Improve blowout risk model"
            priority = "MEDIUM"
        else:
            primary = "BLOWOUT_FP"  # Didn't expect blowout
            is_learnable = True
            adjustment = "Add spread monitoring"
            priority = "MEDIUM"
    
    # 4. Tail event (bad luck)
    elif sigma_dist > 2.0:
        primary = "TAIL_EVT"
        is_learnable = False  # Pure variance
        adjustment = None
        priority = "LOW"
    
    # 5. Opponent mismatch
    elif sigma_dist > 1.0:
        if input.opponent_defensive_rating and input.opponent_defensive_rating <= 10:
            primary = "OPPONENT"
            is_learnable = True
            adjustment = "Increase elite defense penalty"
            priority = "MEDIUM"
            secondary.append("DEFENSIVE_ELITE")
    
    # 6. Normal variance
    else:
        primary = "STAT_VAR"
        is_learnable = False  # Expected variance
        adjustment = None
        priority = "LOW"
    
    # Confidence in attribution
    confidence = 0.90 if len(secondary) == 0 else 0.75
    
    return FASOutput(
        primary_attribution=primary,
        secondary_attributions=secondary,
        sigma_distance=round(sigma_dist, 2),
        is_learnable=is_learnable,
        confidence=confidence,
        model_adjustment=adjustment,
        learning_priority=priority
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def norm_cdf(z: float) -> float:
    """Normal CDF approximation (erf-based)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


# =============================================================================
# INTEGRATION WITH UGO
# =============================================================================

def ess_from_ugo(ugo) -> ESSOutput:
    """
    Convert UGO to ESS input and calculate.
    
    Usage:
        from core.universal_governance_object import UniversalGovernanceObject
        
        ugo = UniversalGovernanceObject(...)
        ess_result = ess_from_ugo(ugo)
        
        print(f"ESS: {ess_result.ess_score:.3f}")
        print(f"Tier: {ess_result.tier}")
        print(f"Stability Tags: {ess_result.stability_tags}")
    """
    ess_input = ESSInput(
        mu=ugo.mu,
        sigma=ugo.sigma,
        line=ugo.line,
        edge_std=ugo.edge_std,
        sample_n=ugo.sample_n,
        direction=ugo.direction.value,
        minute_stability=ugo.minute_stability,
        role_entropy=ugo.role_entropy,
        blowout_risk=ugo.blowout_risk,
    )
    
    return calculate_ess(ess_input)


def fas_from_ugo_and_outcome(ugo, actual_stat: float, **kwargs) -> FASOutput:
    """
    Convert UGO + outcome to FAS input and attribute.
    
    Usage:
        ugo = UniversalGovernanceObject(...)
        actual_stat = 22.0  # Player scored 22, projected 28.3
        
        fas_result = fas_from_ugo_and_outcome(
            ugo,
            actual_stat=22.0,
            actual_minutes=28,
            projected_minutes=34,
            was_blowout=True
        )
        
        print(f"Primary: {fas_result.primary_attribution}")
        print(f"Learnable: {fas_result.is_learnable}")
        print(f"Adjustment: {fas_result.model_adjustment}")
    """
    fas_input = FASInput(
        mu=ugo.mu,
        sigma=ugo.sigma,
        line=ugo.line,
        direction=ugo.direction.value,
        probability=ugo.probability,
        actual_stat=actual_stat,
        **kwargs
    )
    
    return attribute_failure(fas_input)


# =============================================================================
# EXAMPLES
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("ESS + FAS MATHEMATICAL SPECIFICATION — EXAMPLES")
    print("="*70)
    
    # Example 1: ESS Calculation
    print("\n📊 EXAMPLE 1: ESS Calculation")
    print("-" * 70)
    
    ess_input = ESSInput(
        mu=28.3,
        sigma=4.2,
        line=25.5,
        edge_std=0.67,
        sample_n=10,
        direction="HIGHER",
        minute_stability=0.75,
        role_entropy=0.25,
        blowout_risk=0.15,
    )
    
    ess_result = calculate_ess(ess_input)
    
    print(f"Input: mu={ess_input.mu}, sigma={ess_input.sigma}, line={ess_input.line}")
    print(f"ESS Score: {ess_result.ess_score:.3f}")
    print(f"Tier: {ess_result.tier}")
    print(f"Recommendation: {ess_result.recommendation}")
    print(f"Components:")
    for k, v in ess_result.components.items():
        print(f"  {k}: {v:.4f}")
    print(f"Stability Tags: {ess_result.stability_tags}")
    
    # Example 2: FAS Attribution
    print("\n📊 EXAMPLE 2: FAS Attribution (Minute Variance)")
    print("-" * 70)
    
    fas_input = FASInput(
        mu=28.3,
        sigma=4.2,
        line=25.5,
        direction="HIGHER",
        probability=0.72,
        actual_stat=18.0,
        actual_minutes=22,
        projected_minutes=34,
    )
    
    fas_result = attribute_failure(fas_input)
    
    print(f"Projected: {fas_input.mu:.1f}, Actual: {fas_input.actual_stat:.1f}")
    print(f"Primary Attribution: {fas_result.primary_attribution}")
    print(f"Secondary: {fas_result.secondary_attributions}")
    print(f"Sigma Distance: {fas_result.sigma_distance:.2f}σ")
    print(f"Is Learnable: {fas_result.is_learnable}")
    print(f"Model Adjustment: {fas_result.model_adjustment}")
    print(f"Learning Priority: {fas_result.learning_priority}")
    
    print("\n" + "="*70)
    print("✅ ESS + FAS SPEC COMPLETE")
    print("="*70)
