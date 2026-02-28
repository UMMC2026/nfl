"""
Soccer Monte Carlo Simulation Engine
=====================================
Simulates soccer prop outcomes using appropriate distributions:

- Shots/SOT/Tackles: Poisson (discrete count data)
- Goals/Assists: Zero-Inflated Poisson (rare events with many zeros)
- Passes/Touches: Normal (high-volume, approximately continuous)
- Binary outcomes: Bernoulli

Mathematical Foundation:
------------------------
Poisson: P(X=k) = (λ^k * e^(-λ)) / k!
  - λ = player's average per game
  - Good for: shots, tackles, saves, fouls

Zero-Inflated Poisson (ZIP):
  - P(X=0) = π + (1-π) * e^(-λ)
  - P(X=k) = (1-π) * (λ^k * e^(-λ)) / k!  for k > 0
  - π = probability of "structural zero" (player won't score at all)
  - Good for: goals, assists (many players have 0 in most games)

Normal: X ~ N(μ, σ²)
  - μ = player's average
  - σ = standard deviation (typically 15-20% of mean for passes)
  - Good for: passes, touches (high-volume stats)
"""

import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from ..config.soccer_config import (
    MC_SIMULATIONS,
    STAT_DISTRIBUTIONS,
    MARKET_CONFIDENCE_CAPS,
    POSITION_BASELINES,
    LEAGUE_ADJUSTMENTS,
)


@dataclass
class SimulationResult:
    """Result of a Monte Carlo simulation."""
    mean: float
    std: float
    probability_over: float
    probability_under: float
    simulations: int
    distribution: str


class SoccerMonteCarloSimulator:
    """
    Monte Carlo simulator for soccer props.
    
    Uses appropriate statistical distributions based on stat type.
    """
    
    def __init__(self, n_simulations: int = MC_SIMULATIONS, seed: Optional[int] = None):
        self.n_simulations = n_simulations
        if seed is not None:
            np.random.seed(seed)
    
    def simulate_stat(
        self,
        stat: str,
        player_avg: float,
        line: float,
        player_std: Optional[float] = None,
        position: Optional[str] = None,
        league: str = "premier_league",
        games_played: int = 10,
    ) -> SimulationResult:
        """
        Simulate a stat and calculate probability of going over/under the line.
        
        Args:
            stat: Stat type (shots, goals, passes, etc.)
            player_avg: Player's average for this stat
            line: The prop line
            player_std: Standard deviation (estimated if not provided)
            position: Player position for baseline adjustments
            league: League for pace adjustments
            games_played: Games in sample (affects variance)
            
        Returns:
            SimulationResult with probabilities
        """
        stat = stat.lower().strip()
        distribution = STAT_DISTRIBUTIONS.get(stat, "poisson")
        
        # Apply league adjustments
        league_adj = LEAGUE_ADJUSTMENTS.get(league, LEAGUE_ADJUSTMENTS["premier_league"])
        pace_factor = league_adj.get("pace_factor", 1.0)
        
        # Adjust mean based on league pace (higher pace = more events)
        adjusted_avg = player_avg * pace_factor
        
        # Generate simulations based on distribution type
        if distribution == "poisson":
            simulations = self._simulate_poisson(adjusted_avg, games_played)
        elif distribution == "zero_inflated_poisson":
            simulations = self._simulate_zip(adjusted_avg, stat, position, games_played)
        elif distribution == "normal":
            std = player_std if player_std else adjusted_avg * 0.18  # ~18% CV for passes
            simulations = self._simulate_normal(adjusted_avg, std, games_played)
        elif distribution == "binary":
            simulations = self._simulate_binary(adjusted_avg)
        else:
            simulations = self._simulate_poisson(adjusted_avg, games_played)
        
        # Calculate probabilities
        prob_over = np.mean(simulations > line)
        prob_under = np.mean(simulations < line)
        
        return SimulationResult(
            mean=np.mean(simulations),
            std=np.std(simulations),
            probability_over=prob_over,
            probability_under=prob_under,
            simulations=self.n_simulations,
            distribution=distribution,
        )
    
    def _simulate_poisson(self, lambda_: float, games_played: int) -> np.ndarray:
        """
        Simulate using Poisson distribution.
        
        For count data like shots, tackles, saves.
        Adds uncertainty based on sample size.
        """
        # Add uncertainty to lambda based on sample size
        lambda_std = np.sqrt(lambda_ / max(games_played, 3))
        
        # Sample lambda from normal distribution to account for uncertainty
        lambda_samples = np.maximum(
            np.random.normal(lambda_, lambda_std, self.n_simulations),
            0.1  # Minimum lambda
        )
        
        # Generate Poisson samples with varying lambda
        return np.random.poisson(lambda_samples)
    
    def _simulate_zip(
        self,
        lambda_: float,
        stat: str,
        position: Optional[str],
        games_played: int
    ) -> np.ndarray:
        """
        Simulate using Zero-Inflated Poisson distribution.
        
        For rare events like goals and assists where many players have 0.
        """
        # Estimate zero-inflation probability based on stat and position
        if stat == "goals":
            if position in ["striker"]:
                pi = 0.30  # 30% chance of structural zero
            elif position in ["winger", "attacking_mid"]:
                pi = 0.50
            elif position in ["central_mid"]:
                pi = 0.70
            else:
                pi = 0.75  # Defenders rarely score
        elif stat == "assists":
            if position in ["winger", "attacking_mid"]:
                pi = 0.45
            elif position in ["striker", "central_mid"]:
                pi = 0.55
            else:
                pi = 0.70
        else:
            pi = 0.40  # Default
        
        # Add uncertainty to lambda
        lambda_std = np.sqrt(lambda_ / max(games_played, 3))
        lambda_samples = np.maximum(
            np.random.normal(lambda_, lambda_std, self.n_simulations),
            0.05
        )
        
        # Generate ZIP samples
        # First, determine if it's a structural zero
        is_structural_zero = np.random.random(self.n_simulations) < pi
        
        # For non-structural zeros, sample from Poisson
        poisson_samples = np.random.poisson(lambda_samples)
        
        # Combine: structural zeros get 0, others get Poisson
        return np.where(is_structural_zero, 0, poisson_samples)
    
    def _simulate_normal(self, mu: float, sigma: float, games_played: int) -> np.ndarray:
        """
        Simulate using Normal distribution.
        
        For high-volume stats like passes and touches.
        """
        # Add uncertainty to mean based on sample size
        mu_std = sigma / np.sqrt(max(games_played, 3))
        
        # Sample mean from distribution
        mu_samples = np.random.normal(mu, mu_std, self.n_simulations)
        
        # Generate normal samples (allow variance in sigma too)
        sigma_samples = sigma * np.random.uniform(0.85, 1.15, self.n_simulations)
        
        samples = np.random.normal(mu_samples, sigma_samples)
        
        # Passes can't be negative
        return np.maximum(samples, 0)
    
    def _simulate_binary(self, probability: float) -> np.ndarray:
        """
        Simulate binary outcome (e.g., clean sheet, anytime scorer).
        """
        return np.random.random(self.n_simulations) < probability
    
    def get_confidence_cap(self, stat: str) -> float:
        """Get maximum allowed confidence for a stat type."""
        return MARKET_CONFIDENCE_CAPS.get(stat.lower(), 0.75)
    
    def cap_probability(self, stat: str, raw_probability: float) -> float:
        """Apply confidence cap to raw probability."""
        cap = self.get_confidence_cap(stat)
        return min(raw_probability, cap)


# Convenience function
def simulate_prop(
    stat: str,
    player_avg: float,
    line: float,
    direction: str = "over",
    **kwargs
) -> Tuple[float, str]:
    """
    Quick simulation for a single prop.
    
    Returns:
        (probability, distribution_used)
    """
    simulator = SoccerMonteCarloSimulator()
    result = simulator.simulate_stat(stat, player_avg, line, **kwargs)
    
    if direction.lower() in ["over", "higher", "more"]:
        prob = result.probability_over
    else:
        prob = result.probability_under
    
    # Apply confidence cap
    prob = simulator.cap_probability(stat, prob)
    
    return prob, result.distribution


if __name__ == "__main__":
    # Test simulations
    sim = SoccerMonteCarloSimulator(n_simulations=10000, seed=42)
    
    # Test shots (Poisson)
    print("=== SHOTS TEST (Haaland avg 4.2) ===")
    result = sim.simulate_stat("shots", 4.2, 4.5)
    print(f"Mean: {result.mean:.2f}, Std: {result.std:.2f}")
    print(f"P(Over 4.5): {result.probability_over:.1%}")
    print(f"P(Under 4.5): {result.probability_under:.1%}")
    
    # Test goals (ZIP)
    print("\n=== GOALS TEST (Haaland avg 0.9) ===")
    result = sim.simulate_stat("goals", 0.9, 0.5, position="striker")
    print(f"Mean: {result.mean:.2f}, Std: {result.std:.2f}")
    print(f"P(Over 0.5): {result.probability_over:.1%}")
    print(f"P(Under 0.5): {result.probability_under:.1%}")
    
    # Test passes (Normal)
    print("\n=== PASSES TEST (Fernandes avg 52) ===")
    result = sim.simulate_stat("passes", 52.0, 50.5)
    print(f"Mean: {result.mean:.2f}, Std: {result.std:.2f}")
    print(f"P(Over 50.5): {result.probability_over:.1%}")
    print(f"P(Under 50.5): {result.probability_under:.1%}")
