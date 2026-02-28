"""
PLAYER SHOTS SIMULATOR — NHL v2.0 Monte Carlo Engine
=====================================================

Full Monte Carlo simulation for player SOG props.
Uses Poisson distribution for shot attempts.

Simulation count: 20,000 (matches other modules)
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

DEFAULT_SIMULATIONS = 20_000


@dataclass
class SOGSimulationResult:
    """Results from SOG Monte Carlo simulation."""
    player: str
    opponent: str
    simulations: int
    
    # Lambda parameter
    lambda_shots: float
    
    # Distribution statistics
    shots_mean: float
    shots_std: float
    shots_median: float
    
    # Line-specific probabilities
    line: float
    over_prob: float
    under_prob: float
    exactly_on_prob: float
    
    # Distribution (shot count -> probability)
    shots_distribution: Dict[int, float]
    
    # Percentiles
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    
    def __repr__(self):
        return (
            f"SOGSimulationResult({self.player} vs {self.opponent})\n"
            f"  λ={self.lambda_shots:.2f}\n"
            f"  Expected: {self.shots_mean:.1f} ± {self.shots_std:.1f}\n"
            f"  Line {self.line}: OVER {self.over_prob:.1%} | UNDER {self.under_prob:.1%}"
        )


class SOGSimulator:
    """
    Monte Carlo simulator for player shots-on-goal.
    
    Uses Poisson distribution with λ derived from player model.
    """
    
    def __init__(self, simulations: int = DEFAULT_SIMULATIONS, seed: int = None):
        """
        Initialize simulator.
        
        Args:
            simulations: Number of MC simulations
            seed: Random seed for reproducibility
        """
        self.simulations = simulations
        self.rng = np.random.default_rng(seed)
        logger.info(f"SOGSimulator initialized: n={simulations}, seed={seed}")
    
    def simulate(
        self,
        player_name: str,
        opponent_name: str,
        lambda_shots: float,
        line: float,
    ) -> SOGSimulationResult:
        """
        Run full Monte Carlo simulation for SOG.
        
        Args:
            player_name: Player name
            opponent_name: Opponent team
            lambda_shots: Poisson λ parameter
            line: SOG line to evaluate
        
        Returns:
            SOGSimulationResult with full analysis
        """
        # Simulate shots
        shots = self.rng.poisson(lambda_shots, self.simulations)
        
        # Statistics
        shots_mean = shots.mean()
        shots_std = shots.std()
        shots_median = np.median(shots)
        
        # Percentiles
        p10, p25, p50, p75, p90 = np.percentile(shots, [10, 25, 50, 75, 90])
        
        # Line probabilities
        over_prob = (shots > line).mean()
        under_prob = (shots < line).mean()
        exactly_on_prob = (shots == int(line)).mean() if line == int(line) else 0.0
        
        # Build distribution
        unique, counts = np.unique(shots, return_counts=True)
        shots_distribution = {
            int(val): count / self.simulations
            for val, count in zip(unique, counts)
        }
        
        return SOGSimulationResult(
            player=player_name,
            opponent=opponent_name,
            simulations=self.simulations,
            lambda_shots=lambda_shots,
            shots_mean=shots_mean,
            shots_std=shots_std,
            shots_median=shots_median,
            line=line,
            over_prob=over_prob,
            under_prob=under_prob,
            exactly_on_prob=exactly_on_prob,
            shots_distribution=shots_distribution,
            p10=p10,
            p25=p25,
            p50=p50,
            p75=p75,
            p90=p90,
        )
    
    def simulate_multiple_lines(
        self,
        player_name: str,
        opponent_name: str,
        lambda_shots: float,
        lines: List[float],
    ) -> Dict[float, Tuple[float, float]]:
        """
        Simulate and evaluate multiple lines efficiently.
        
        Args:
            lines: List of lines to evaluate
        
        Returns:
            Dict mapping line -> (over_prob, under_prob)
        """
        # Single simulation pass
        shots = self.rng.poisson(lambda_shots, self.simulations)
        
        results = {}
        for line in lines:
            over_prob = (shots > line).mean()
            under_prob = (shots < line).mean()
            results[line] = (over_prob, under_prob)
        
        return results


def simulate_player_sog(
    player_name: str,
    opponent_name: str,
    lambda_shots: float,
    line: float,
    n_sims: int = DEFAULT_SIMULATIONS,
    seed: int = None,
) -> SOGSimulationResult:
    """
    Convenience function for single simulation.
    
    Args:
        player_name: Player name
        opponent_name: Opponent team
        lambda_shots: Expected shots (Poisson λ)
        line: SOG line to evaluate
        n_sims: Number of simulations
        seed: Random seed
    
    Returns:
        SOGSimulationResult
    """
    simulator = SOGSimulator(simulations=n_sims, seed=seed)
    return simulator.simulate(
        player_name=player_name,
        opponent_name=opponent_name,
        lambda_shots=lambda_shots,
        line=line,
    )


# ─────────────────────────────────────────────────────────
# TOI-ADJUSTED SIMULATION
# ─────────────────────────────────────────────────────────

def simulate_with_toi_variance(
    player_name: str,
    opponent_name: str,
    base_lambda: float,
    avg_toi: float,
    toi_std: float,
    line: float,
    n_sims: int = DEFAULT_SIMULATIONS,
    seed: int = None,
) -> SOGSimulationResult:
    """
    Simulation with TOI variance incorporated.
    
    First simulates TOI, then shots conditional on TOI.
    More accurate for players with high TOI variance.
    
    Args:
        base_lambda: Expected shots at avg TOI
        avg_toi: Average time on ice (minutes)
        toi_std: TOI standard deviation
        line: SOG line
        n_sims: Simulations
        seed: Random seed
    
    Returns:
        SOGSimulationResult
    """
    rng = np.random.default_rng(seed)
    
    # Simulate TOI (truncated normal to avoid negative)
    toi_sims = rng.normal(avg_toi, toi_std, n_sims)
    toi_sims = np.clip(toi_sims, 5.0, 30.0)  # Reasonable bounds
    
    # Adjust λ for each TOI realization
    toi_factor = toi_sims / avg_toi
    adjusted_lambdas = base_lambda * toi_factor
    
    # Simulate shots for each adjusted λ
    shots = np.array([
        rng.poisson(lam) for lam in adjusted_lambdas
    ])
    
    # Statistics
    shots_mean = shots.mean()
    shots_std = shots.std()
    shots_median = np.median(shots)
    
    p10, p25, p50, p75, p90 = np.percentile(shots, [10, 25, 50, 75, 90])
    
    over_prob = (shots > line).mean()
    under_prob = (shots < line).mean()
    exactly_on_prob = (shots == int(line)).mean() if line == int(line) else 0.0
    
    unique, counts = np.unique(shots, return_counts=True)
    shots_distribution = {
        int(val): count / n_sims
        for val, count in zip(unique, counts)
    }
    
    return SOGSimulationResult(
        player=player_name,
        opponent=opponent_name,
        simulations=n_sims,
        lambda_shots=base_lambda,
        shots_mean=shots_mean,
        shots_std=shots_std,
        shots_median=shots_median,
        line=line,
        over_prob=over_prob,
        under_prob=under_prob,
        exactly_on_prob=exactly_on_prob,
        shots_distribution=shots_distribution,
        p10=p10,
        p25=p25,
        p50=p50,
        p75=p75,
        p90=p90,
    )


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("PLAYER SOG SIMULATOR — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Demo: High-volume shooter
    result = simulate_player_sog(
        player_name="David Pastrnak",
        opponent_name="DET",
        lambda_shots=4.2,
        line=3.5,
        n_sims=20_000,
        seed=42,
    )
    
    print(f"\n{result}")
    print(f"\nDistribution (most likely):")
    sorted_dist = sorted(result.shots_distribution.items(), key=lambda x: -x[1])
    for shots, prob in sorted_dist[:6]:
        print(f"  {shots} shots: {prob:.1%}")
    
    # Multi-line evaluation
    print("\n" + "-" * 40)
    print("Multi-line evaluation:")
    
    simulator = SOGSimulator(simulations=20_000, seed=42)
    lines_result = simulator.simulate_multiple_lines(
        player_name="Pastrnak",
        opponent_name="DET",
        lambda_shots=4.2,
        lines=[2.5, 3.5, 4.5, 5.5],
    )
    
    for line, (over_p, under_p) in lines_result.items():
        print(f"  Line {line}: OVER {over_p:.1%} | UNDER {under_p:.1%}")
    
    # TOI-adjusted simulation
    print("\n" + "-" * 40)
    print("TOI-adjusted simulation:")
    
    toi_result = simulate_with_toi_variance(
        player_name="Pastrnak",
        opponent_name="DET",
        base_lambda=4.2,
        avg_toi=20.5,
        toi_std=3.5,  # High variance
        line=3.5,
        n_sims=20_000,
        seed=42,
    )
    
    print(f"  Standard: {result.shots_mean:.2f} ± {result.shots_std:.2f}")
    print(f"  TOI-adj:  {toi_result.shots_mean:.2f} ± {toi_result.shots_std:.2f}")
    print(f"  OVER 3.5 (standard): {result.over_prob:.1%}")
    print(f"  OVER 3.5 (TOI-adj):  {toi_result.over_prob:.1%}")
