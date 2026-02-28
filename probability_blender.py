"""
Probability Blender - Hybrid Model Implementation

Blends multiple probability estimation methods:
1. Normal CDF (parametric)
2. Empirical hit rate (historical)
3. Bayesian posterior (shrinkage toward prior)

Implements the "Hybrid" mode from analysis_config.py
"""

import math
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class BlendedProbability:
    """Result of probability blending."""
    p_final: float              # Final blended probability
    p_normal: float             # Normal CDF probability
    p_empirical: float          # Historical hit rate
    p_bayesian: float           # Bayesian posterior
    blend_weights: Dict[str, float]  # Weights used
    confidence: str             # "high", "medium", "low"
    sample_size: int
    mu: float                   # Mean used
    sigma: float                # Std dev used
    notes: List[str]


def _norm_cdf(x: float, mu: float, sigma: float) -> float:
    """Standard normal CDF."""
    if sigma <= 0:
        sigma = 1e-6
    z = (x - mu) / (sigma * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def _mean_std(values: List[float]) -> Tuple[float, float]:
    """Calculate mean and standard deviation."""
    n = len(values)
    if n < 1:
        raise ValueError("Need at least 1 value")
    mu = sum(values) / n
    if n < 2:
        return mu, mu * 0.2  # Default 20% CV for single value
    var = sum((x - mu) ** 2 for x in values) / (n - 1)
    return mu, max(math.sqrt(var), 1e-6)


def calc_normal_prob(line: float, direction: str, mu: float, sigma: float) -> float:
    """Calculate probability using Normal CDF."""
    p_under = _norm_cdf(line, mu, sigma)
    if direction.lower() == "higher":
        return 1.0 - p_under
    return p_under


def calc_empirical_prob(line: float, direction: str, recent_values: List[float]) -> float:
    """Calculate probability using historical hit rate."""
    if not recent_values:
        return 0.5
    
    if direction.lower() == "higher":
        hits = sum(1 for v in recent_values if v > line)
    else:
        hits = sum(1 for v in recent_values if v < line)
    
    # Laplace smoothing to avoid 0% or 100%
    return (hits + 0.5) / (len(recent_values) + 1)


def calc_bayesian_prob(
    line: float,
    direction: str,
    recent_values: List[float],
    prior_mu: Optional[float] = None,
    prior_sigma: Optional[float] = None,
    shrinkage: float = 0.3
) -> Tuple[float, float, float]:
    """
    Calculate Bayesian posterior probability with shrinkage.
    
    Returns: (p_bayesian, posterior_mu, posterior_sigma)
    """
    if len(recent_values) < 1:
        # No data, return prior or 50%
        if prior_mu is not None and prior_sigma is not None:
            return calc_normal_prob(line, direction, prior_mu, prior_sigma), prior_mu, prior_sigma
        return 0.5, line, 5.0
    
    sample_mu, sample_sigma = _mean_std(recent_values)
    n = len(recent_values)
    
    # Default prior: slightly wider than sample
    if prior_mu is None:
        prior_mu = sample_mu
    if prior_sigma is None:
        prior_sigma = sample_sigma * 1.5
    
    # Bayesian shrinkage: weight toward prior for small samples
    if n >= 30:
        effective_shrinkage = 0.1  # Minimal shrinkage with 30+ games
    elif n >= 20:
        effective_shrinkage = 0.2
    elif n >= 10:
        effective_shrinkage = shrinkage  # Default
    elif n >= 5:
        effective_shrinkage = shrinkage + 0.15
    else:
        effective_shrinkage = 0.5  # Heavy shrinkage with <5 games
    
    # Posterior mean (shrunk toward prior)
    posterior_mu = (1 - effective_shrinkage) * sample_mu + effective_shrinkage * prior_mu
    
    # Posterior sigma (shrunk less aggressively)
    posterior_sigma = (1 - effective_shrinkage * 0.5) * sample_sigma + (effective_shrinkage * 0.5) * prior_sigma
    
    p_bayesian = calc_normal_prob(line, direction, posterior_mu, posterior_sigma)
    
    return p_bayesian, posterior_mu, posterior_sigma


def blend_probabilities(
    line: float,
    direction: str,
    recent_values: List[float],
    *,
    blend_mode: str = "hybrid",
    hybrid_weight: float = 0.65,  # 65% model, 35% empirical
    prior_mu: Optional[float] = None,
    prior_sigma: Optional[float] = None,
    bayesian_shrinkage: float = 0.3,
    mu: Optional[float] = None,
    sigma: Optional[float] = None,
) -> BlendedProbability:
    """
    Blend multiple probability methods.
    
    Args:
        line: Prop line
        direction: "higher" or "lower"
        recent_values: Historical game values
        blend_mode: "normal_cdf", "empirical", "hybrid", or "bayesian"
        hybrid_weight: Weight for parametric model (rest goes to empirical)
        prior_mu: Prior mean for Bayesian
        prior_sigma: Prior sigma for Bayesian
        bayesian_shrinkage: Shrinkage factor (0-1)
        mu: Override mean (if not using recent_values)
        sigma: Override sigma (if not using recent_values)
    
    Returns:
        BlendedProbability with all components
    """
    notes = []
    n = len(recent_values) if recent_values else 0
    
    # Calculate mu/sigma from recent values or use overrides
    if mu is not None and sigma is not None:
        calc_mu, calc_sigma = mu, sigma
    elif n >= 2:
        calc_mu, calc_sigma = _mean_std(recent_values)
    elif n == 1:
        calc_mu = recent_values[0]
        calc_sigma = calc_mu * 0.2
        notes.append("Single data point - using 20% CV estimate")
    else:
        calc_mu = line
        calc_sigma = line * 0.15
        notes.append("No data - using line as mean with 15% CV")
    
    # Calculate all probability methods
    p_normal = calc_normal_prob(line, direction, calc_mu, calc_sigma)
    p_empirical = calc_empirical_prob(line, direction, recent_values) if recent_values else 0.5
    p_bayesian, post_mu, post_sigma = calc_bayesian_prob(
        line, direction, recent_values, prior_mu, prior_sigma, bayesian_shrinkage
    )
    
    # Determine confidence level
    if n >= 20:
        confidence = "high"
    elif n >= 10:
        confidence = "medium"
    else:
        confidence = "low"
        if n > 0:
            notes.append(f"Low sample size ({n} games)")
    
    # Blend based on mode
    blend_weights = {"normal": 0.0, "empirical": 0.0, "bayesian": 0.0}
    
    if blend_mode == "normal_cdf":
        p_final = p_normal
        blend_weights["normal"] = 1.0
        
    elif blend_mode == "empirical":
        p_final = p_empirical
        blend_weights["empirical"] = 1.0
        
    elif blend_mode == "bayesian":
        p_final = p_bayesian
        blend_weights["bayesian"] = 1.0
        calc_mu, calc_sigma = post_mu, post_sigma
        
    elif blend_mode == "hybrid":
        # Hybrid: Blend Normal CDF with Empirical
        # Adjust weights based on sample size
        if n >= 20:
            # Trust empirical more with more data
            model_weight = hybrid_weight * 0.8
            emp_weight = 1.0 - model_weight
        elif n >= 10:
            model_weight = hybrid_weight
            emp_weight = 1.0 - model_weight
        elif n >= 5:
            # Trust model more with less data
            model_weight = hybrid_weight * 1.15
            emp_weight = 1.0 - model_weight
        else:
            # Very little data - trust model heavily
            model_weight = 0.85
            emp_weight = 0.15
        
        # Normalize
        total = model_weight + emp_weight
        model_weight /= total
        emp_weight /= total
        
        p_final = model_weight * p_normal + emp_weight * p_empirical
        blend_weights["normal"] = model_weight
        blend_weights["empirical"] = emp_weight
        
        notes.append(f"Hybrid: {model_weight:.0%} model + {emp_weight:.0%} empirical")
        
    elif blend_mode == "gmm":
        # GMM not implemented yet - fall back to hybrid
        notes.append("GMM not implemented - using hybrid")
        model_weight = hybrid_weight
        emp_weight = 1.0 - hybrid_weight
        p_final = model_weight * p_normal + emp_weight * p_empirical
        blend_weights["normal"] = model_weight
        blend_weights["empirical"] = emp_weight
        
    else:
        # Default to normal
        p_final = p_normal
        blend_weights["normal"] = 1.0
    
    # Clamp to valid range
    p_final = max(0.01, min(0.99, p_final))
    
    return BlendedProbability(
        p_final=p_final,
        p_normal=p_normal,
        p_empirical=p_empirical,
        p_bayesian=p_bayesian,
        blend_weights=blend_weights,
        confidence=confidence,
        sample_size=n,
        mu=calc_mu,
        sigma=calc_sigma,
        notes=notes
    )


# ============================================================================
# INTEGRATION WITH ANALYSIS CONFIG
# ============================================================================

def get_probability_from_config(
    line: float,
    direction: str,
    recent_values: List[float],
    *,
    prior_mu: Optional[float] = None,
    prior_sigma: Optional[float] = None,
    mu: Optional[float] = None,
    sigma: Optional[float] = None,
) -> BlendedProbability:
    """
    Get probability using current analysis configuration.
    """
    try:
        from analysis_config import get_active_config
        config = get_active_config()
        
        # Map config probability_model to blend_mode
        blend_mode = config.probability_model
        
        # Get hybrid weight from config
        hybrid_weight = config.hybrid_blend
        
        # Get Bayesian settings
        if config.bayesian_mode == "off":
            bayesian_shrinkage = 0.0
        elif config.bayesian_mode == "aggressive":
            bayesian_shrinkage = 0.5
        elif config.bayesian_mode == "hierarchical":
            bayesian_shrinkage = 0.2
        else:
            bayesian_shrinkage = 0.3  # Standard
            
    except ImportError:
        # Fallback defaults
        blend_mode = "hybrid"
        hybrid_weight = 0.65
        bayesian_shrinkage = 0.3
    
    return blend_probabilities(
        line=line,
        direction=direction,
        recent_values=recent_values,
        blend_mode=blend_mode,
        hybrid_weight=hybrid_weight,
        prior_mu=prior_mu,
        prior_sigma=prior_sigma,
        bayesian_shrinkage=bayesian_shrinkage,
        mu=mu,
        sigma=sigma,
    )


def apply_graduated_penalty(
    p_hit: float,
    gate_type: str,
    severity: str = "medium"
) -> Tuple[float, str]:
    """
    Apply graduated penalty instead of hard block.
    
    Args:
        p_hit: Original probability
        gate_type: Type of gate violation (composite_stat, elite_defense, etc.)
        severity: Penalty severity (conservative, medium, aggressive)
    
    Returns:
        (adjusted_probability, explanation)
    """
    try:
        from analysis_config import PENALTY_MULTIPLIERS, PenaltySeverity
        penalties = PENALTY_MULTIPLIERS.get(
            PenaltySeverity(severity),
            PENALTY_MULTIPLIERS[PenaltySeverity.MEDIUM]
        )
    except (ImportError, ValueError):
        # Default medium penalties
        penalties = {
            "composite_stat": 0.70,
            "elite_defense": 0.85,
            "role_mismatch": 0.95,
            "bench_player": 0.75,
            "b2b_fatigue": 0.90,
        }
    
    multiplier = penalties.get(gate_type, 0.90)
    adjusted = p_hit * multiplier
    pct_reduction = (1 - multiplier) * 100
    
    explanation = f"Soft gate ({gate_type}): {p_hit:.1%} → {adjusted:.1%} ({pct_reduction:.0f}% penalty)"
    
    return adjusted, explanation


def calculate_kelly_edge(
    p_hit: float,
    implied_odds: float = 0.5,
    kelly_fraction: float = 0.25
) -> Dict[str, float]:
    """
    Calculate Kelly criterion edge and bet sizing.
    
    Args:
        p_hit: Probability of hitting
        implied_odds: Implied probability from line (default 0.5 for -110)
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
    
    Returns:
        Dict with edge metrics
    """
    # Edge = p_hit - implied_odds
    edge = p_hit - implied_odds
    
    # Kelly formula: f* = (bp - q) / b
    # Where b = odds, p = prob win, q = prob lose
    # For even money: f* = p - q = 2p - 1
    if implied_odds > 0:
        b = (1 - implied_odds) / implied_odds  # Convert to decimal odds - 1
        q = 1 - p_hit
        if b > 0:
            full_kelly = (b * p_hit - q) / b
        else:
            full_kelly = 0
    else:
        full_kelly = 0
    
    # Apply fraction
    kelly_bet = max(0, full_kelly * kelly_fraction)
    
    # Calculate expected value
    ev = edge  # Simple EV for 1 unit bet
    
    # Z-score (edge in standard deviations)
    # Assuming binomial variance: sqrt(p * (1-p))
    std = math.sqrt(p_hit * (1 - p_hit)) if 0 < p_hit < 1 else 0.25
    z_score = edge / std if std > 0 else 0
    
    return {
        "edge": edge,
        "edge_pct": edge * 100,
        "z_score": z_score,
        "full_kelly": full_kelly,
        "kelly_bet": kelly_bet,
        "ev": ev,
    }


if __name__ == "__main__":
    # Test the blender
    test_values = [22, 28, 25, 31, 19, 24, 27, 23, 26, 20]
    
    print("=" * 60)
    print("PROBABILITY BLENDER TEST")
    print("=" * 60)
    print(f"Line: 24.5 HIGHER")
    print(f"Recent values: {test_values}")
    print(f"Mean: {sum(test_values)/len(test_values):.1f}")
    print()
    
    for mode in ["normal_cdf", "empirical", "hybrid", "bayesian"]:
        result = blend_probabilities(
            line=24.5,
            direction="higher",
            recent_values=test_values,
            blend_mode=mode
        )
        print(f"{mode.upper():15} → P(hit) = {result.p_final:.1%}")
        print(f"  Normal: {result.p_normal:.1%}, Empirical: {result.p_empirical:.1%}, Bayesian: {result.p_bayesian:.1%}")
        print(f"  Confidence: {result.confidence}, μ={result.mu:.1f}, σ={result.sigma:.1f}")
        
        # Calculate Kelly edge
        kelly = calculate_kelly_edge(result.p_final)
        print(f"  Edge: {kelly['edge_pct']:+.1f}%, Z-score: {kelly['z_score']:.2f}, Kelly: {kelly['kelly_bet']:.1%}")
        print()
    
    # Test graduated penalty
    print("=" * 60)
    print("GRADUATED PENALTY TEST")
    print("=" * 60)
    test_p = 0.72
    for gate in ["composite_stat", "elite_defense", "bench_player"]:
        adj_p, explanation = apply_graduated_penalty(test_p, gate, "medium")
        print(f"{gate}: {explanation}")
