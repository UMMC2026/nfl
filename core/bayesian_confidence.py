"""
BAYESIAN CONFIDENCE CALCULATOR
==============================
Replace arbitrary multiplicative penalties with proper statistical confidence.

Core principle: If mu > line, you have an edge. 
The question is: HOW CERTAIN are we about mu?

Instead of: raw_prob * penalty1 * penalty2 * penalty3
We use:     P(player_stat > line | data, uncertainty)
"""
import numpy as np
from scipy import stats
from typing import Dict, Tuple, Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def calculate_bayesian_probability(
    mu: float,              # Model's predicted mean
    sigma: float,           # Observed standard deviation
    line: float,            # Betting line
    n_games: int,           # Sample size
    direction: str = "higher",  # "higher" or "lower"
    prior_mu: Optional[float] = None,  # League average (optional)
    prior_strength: int = 5  # How much to weight the prior
) -> Dict:
    """
    Calculate Bayesian probability that player exceeds/misses line.
    
    This PROPERLY accounts for:
    1. Sample size uncertainty (small n = wider CI)
    2. Variance in player performance
    3. Shrinkage toward prior (optional)
    
    Returns dict with:
    - probability: Prob of beating line
    - confidence_interval: 95% CI for player's true mean
    - uncertainty_factor: How much to trust this estimate
    - edge: Probability - implied_prob
    """
    # === HANDLE EDGE CASES ===
    if n_games < 3:
        return {
            'probability': 0.50,
            'confidence_interval': (mu - 3*sigma, mu + 3*sigma),
            'uncertainty_factor': 0.0,
            'edge': 0.0,
            'decision': 'VETO',
            'reason': 'Insufficient sample size (n < 3)'
        }
    
    if sigma <= 0:
        sigma = mu * 0.20  # Assume 20% CV if no variance data
    
    # === BAYESIAN UPDATING (optional) ===
    if prior_mu is not None:
        # Weighted average of prior and observed
        posterior_mu = (prior_mu * prior_strength + mu * n_games) / (prior_strength + n_games)
    else:
        posterior_mu = mu
    
    # === STANDARD ERROR OF THE MEAN ===
    # This is the KEY improvement: we account for uncertainty in our estimate
    sem = sigma / np.sqrt(n_games)
    
    # === 95% CONFIDENCE INTERVAL ===
    t_crit = stats.t.ppf(0.975, df=n_games - 1)  # t-distribution for small samples
    ci_lower = posterior_mu - t_crit * sem
    ci_upper = posterior_mu + t_crit * sem
    
    # === CALCULATE PROBABILITY ===
    # P(X > line) where X ~ N(mu, sigma)
    # But we also account for uncertainty in mu itself
    
    if direction.lower() in ["higher", "over"]:
        # For OVER: we want P(true_mean > line)
        # Using the sampling distribution of the mean
        z_score = (line - posterior_mu) / sigma
        prob = 1 - stats.norm.cdf(z_score)
        
        # Conservative adjustment: use lower bound of CI for edge calculation
        conservative_mu = ci_lower
        conservative_z = (line - conservative_mu) / sigma
        conservative_prob = 1 - stats.norm.cdf(conservative_z)
    else:
        # For UNDER: we want P(true_mean < line)
        z_score = (line - posterior_mu) / sigma
        prob = stats.norm.cdf(z_score)
        
        # Conservative adjustment: use upper bound of CI
        conservative_mu = ci_upper
        conservative_z = (line - conservative_mu) / sigma
        conservative_prob = stats.norm.cdf(conservative_z)
    
    # === UNCERTAINTY FACTOR ===
    # How much we trust this estimate (0-1)
    # Based on: sample size, CV, CI width
    ci_width = ci_upper - ci_lower
    cv = sigma / mu if mu > 0 else 1.0
    
    # Factors that increase uncertainty:
    # - Small n (penalize below 15 games)
    # - High CV (penalize above 0.35)
    # - Wide CI relative to line
    
    n_factor = min(1.0, n_games / 15)  # Maxes at 15 games
    cv_factor = max(0.5, 1.0 - (cv - 0.25))  # Penalize CV > 0.25
    ci_factor = max(0.5, 1.0 - ci_width / (2 * line)) if line > 0 else 0.5
    
    uncertainty_factor = n_factor * cv_factor * ci_factor
    
    # === EDGE CALCULATION ===
    implied_prob = 0.5238  # At -110 odds (100/190.91)
    raw_edge = prob - implied_prob
    conservative_edge = conservative_prob - implied_prob
    
    # Use conservative edge for decision
    effective_edge = conservative_edge * uncertainty_factor
    
    # === DECISION ===
    if effective_edge >= 0.15:
        decision = "SLAM"
    elif effective_edge >= 0.07:
        decision = "STRONG"
    elif effective_edge >= 0.02:
        decision = "LEAN"
    elif effective_edge >= 0:
        decision = "WATCH"
    else:
        decision = "NO_PLAY"
    
    return {
        'probability': round(prob * 100, 1),
        'conservative_probability': round(conservative_prob * 100, 1),
        'confidence_interval': (round(ci_lower, 2), round(ci_upper, 2)),
        'uncertainty_factor': round(uncertainty_factor, 3),
        'raw_edge': round(raw_edge * 100, 2),
        'conservative_edge': round(conservative_edge * 100, 2),
        'effective_edge': round(effective_edge * 100, 2),
        'decision': decision,
        'z_score': round(z_score, 2),
        'sem': round(sem, 2),
        'cv': round(cv, 3),
        'n_games': n_games
    }


def kelly_criterion(edge: float, odds: int = -110) -> float:
    """
    Calculate optimal bet size using Kelly Criterion.
    
    f* = (bp - q) / b
    where:
    - b = decimal odds - 1 (net profit per unit)
    - p = probability of winning
    - q = probability of losing (1-p)
    
    Returns: fraction of bankroll to bet (0-1)
    """
    if edge <= 0:
        return 0.0
    
    # Convert American odds to decimal
    if odds < 0:
        decimal_odds = 1 + (100 / abs(odds))
    else:
        decimal_odds = 1 + (odds / 100)
    
    b = decimal_odds - 1  # Net profit per unit bet
    p = 0.5238 + edge  # Probability of winning (implied + edge)
    q = 1 - p
    
    kelly = (b * p - q) / b
    
    # Cap at 25% for safety (fractional Kelly)
    return max(0, min(0.25, kelly))


def compare_approaches(
    mu: float,
    sigma: float, 
    line: float,
    n_games: int,
    direction: str = "higher"
) -> Dict:
    """
    Compare demon_mode vs Bayesian approach.
    
    Shows what each system would decide.
    """
    # === DEMON MODE (simple) ===
    if direction.lower() in ["higher", "over"]:
        demon_prob = 1 - stats.norm.cdf((line - mu) / sigma)
    else:
        demon_prob = stats.norm.cdf((line - mu) / sigma)
    
    demon_edge = demon_prob - 0.5238
    
    if demon_edge >= 0.15:
        demon_decision = "SLAM"
    elif demon_edge >= 0.07:
        demon_decision = "STRONG"
    elif demon_edge >= 0.02:
        demon_decision = "LEAN"
    else:
        demon_decision = "NO_PLAY"
    
    # === BAYESIAN (uncertainty-aware) ===
    bayesian = calculate_bayesian_probability(mu, sigma, line, n_games, direction)
    
    return {
        'demon_mode': {
            'probability': round(demon_prob * 100, 1),
            'edge': round(demon_edge * 100, 2),
            'decision': demon_decision
        },
        'bayesian': {
            'probability': bayesian['probability'],
            'conservative_prob': bayesian['conservative_probability'],
            'effective_edge': bayesian['effective_edge'],
            'uncertainty_factor': bayesian['uncertainty_factor'],
            'decision': bayesian['decision'],
            'ci': bayesian['confidence_interval']
        }
    }


# === TEST ===
if __name__ == "__main__":
    # Test with Embiid example
    print("=" * 60)
    print("BAYESIAN vs DEMON_MODE COMPARISON")
    print("=" * 60)
    
    # Embiid: mu=28.4, sigma=6.5, line=27.5, n=15 games
    result = compare_approaches(
        mu=28.4,
        sigma=6.5,
        line=27.5,
        n_games=15,
        direction="higher"
    )
    
    print(f"\nPlayer: Joel Embiid | Stat: PTS | Line: 27.5 OVER")
    print(f"Model: μ={28.4}, σ={6.5}, n=15 games")
    print()
    
    print("DEMON_MODE (simple):")
    print(f"  Probability: {result['demon_mode']['probability']}%")
    print(f"  Edge: {result['demon_mode']['edge']}%")
    print(f"  Decision: {result['demon_mode']['decision']}")
    print()
    
    print("BAYESIAN (uncertainty-aware):")
    print(f"  Raw Probability: {result['bayesian']['probability']}%")
    print(f"  Conservative Prob: {result['bayesian']['conservative_prob']}%")
    print(f"  Uncertainty Factor: {result['bayesian']['uncertainty_factor']}")
    print(f"  Effective Edge: {result['bayesian']['effective_edge']}%")
    print(f"  95% CI for μ: {result['bayesian']['ci']}")
    print(f"  Decision: {result['bayesian']['decision']}")
    
    # Test high variance player
    print("\n" + "=" * 60)
    print("HIGH VARIANCE PLAYER TEST")
    print("=" * 60)
    
    result2 = compare_approaches(
        mu=15.0,
        sigma=8.0,  # High variance (CV = 0.53)
        line=14.5,
        n_games=8,  # Small sample
        direction="higher"
    )
    
    print(f"\nPlayer: High Variance | Stat: PTS | Line: 14.5 OVER")
    print(f"Model: μ={15.0}, σ={8.0}, n=8 games, CV=0.53")
    print()
    
    print("DEMON_MODE (simple):")
    print(f"  Probability: {result2['demon_mode']['probability']}%")
    print(f"  Decision: {result2['demon_mode']['decision']}")
    print()
    
    print("BAYESIAN (uncertainty-aware):")
    print(f"  Raw Probability: {result2['bayesian']['probability']}%")
    print(f"  Conservative Prob: {result2['bayesian']['conservative_prob']}%")
    print(f"  Uncertainty Factor: {result2['bayesian']['uncertainty_factor']}")
    print(f"  Decision: {result2['bayesian']['decision']}")
    
    # Kelly sizing
    print("\n" + "=" * 60)
    print("KELLY CRITERION BET SIZING")
    print("=" * 60)
    
    edges = [0.02, 0.05, 0.10, 0.15, 0.20]
    for edge in edges:
        kelly = kelly_criterion(edge)
        print(f"  Edge {edge*100:>4.0f}% → Kelly: {kelly*100:>5.1f}% of bankroll")
