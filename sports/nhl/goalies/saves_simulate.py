"""
GOALIE SAVES SIMULATOR — NHL v1.1 Monte Carlo Engine
=====================================================

Full Monte Carlo simulation for goalie saves props.
Uses Poisson distribution for shots against, then derives saves.

Key insight: Saves = Shots - Goals
- Shots ~ Poisson(λ_shots)
- Goals | Shots ~ Binomial(shots, 1 - SV%)
- Saves = Shots - Goals

Simulation count: 20,000 (matches game model)
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Default simulation count
DEFAULT_SIMULATIONS = 20_000


@dataclass
class SavesSimulationResult:
    """Results from saves Monte Carlo simulation."""
    goalie: str
    opponent: str
    simulations: int
    
    # Lambda parameters
    lambda_shots: float
    save_percentage: float
    
    # Distribution statistics
    saves_mean: float
    saves_std: float
    saves_median: float
    
    # Line-specific probabilities
    line: float
    over_prob: float
    under_prob: float
    push_prob: float
    
    # Distribution (saves count -> probability)
    saves_distribution: Dict[int, float]
    
    # Percentiles
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    
    def __repr__(self):
        return (
            f"SavesSimulationResult({self.goalie} vs {self.opponent})\n"
            f"  λ_shots={self.lambda_shots:.2f}, SV%={self.save_percentage:.3f}\n"
            f"  Expected: {self.saves_mean:.1f} ± {self.saves_std:.1f}\n"
            f"  Line {self.line}: OVER {self.over_prob:.1%} | UNDER {self.under_prob:.1%}"
        )


class SavesSimulator:
    """
    Monte Carlo simulator for goalie saves.
    
    Uses a two-stage simulation:
    1. Sample shots against from Poisson(λ_shots)
    2. Sample goals from Binomial(shots, 1 - SV%)
    3. Saves = Shots - Goals
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
        logger.info(f"SavesSimulator initialized: n={simulations}, seed={seed}")
    
    def simulate(
        self,
        goalie_name: str,
        opponent_name: str,
        lambda_shots: float,
        save_percentage: float,
        line: float,
    ) -> SavesSimulationResult:
        """
        Run full Monte Carlo simulation for saves.
        
        Args:
            goalie_name: Goalie name (for output)
            opponent_name: Opponent team
            lambda_shots: Expected shots against (Poisson λ)
            save_percentage: Goalie save percentage (e.g., 0.918)
            line: Saves line to evaluate (e.g., 27.5)
        
        Returns:
            SavesSimulationResult with full probability analysis
        """
        # Step 1: Simulate shots against
        shots = self.rng.poisson(lambda_shots, self.simulations)
        
        # Step 2: Simulate goals against (binomial for each simulation)
        # Goals | Shots ~ Binomial(shots, 1 - SV%)
        goal_prob = 1 - save_percentage
        goals = self.rng.binomial(shots, goal_prob)
        
        # Step 3: Saves = Shots - Goals
        saves = shots - goals
        
        # Distribution statistics
        saves_mean = saves.mean()
        saves_std = saves.std()
        saves_median = np.median(saves)
        
        # Percentiles
        p10, p25, p50, p75, p90 = np.percentile(saves, [10, 25, 50, 75, 90])
        
        # Line probabilities
        over_prob = (saves > line).mean()
        under_prob = (saves < line).mean()
        push_prob = 1.0 - over_prob - under_prob  # Exactly on line
        
        # Build distribution (count frequencies)
        unique, counts = np.unique(saves, return_counts=True)
        saves_distribution = {
            int(val): count / self.simulations 
            for val, count in zip(unique, counts)
        }
        
        return SavesSimulationResult(
            goalie=goalie_name,
            opponent=opponent_name,
            simulations=self.simulations,
            lambda_shots=lambda_shots,
            save_percentage=save_percentage,
            saves_mean=saves_mean,
            saves_std=saves_std,
            saves_median=saves_median,
            line=line,
            over_prob=over_prob,
            under_prob=under_prob,
            push_prob=push_prob,
            saves_distribution=saves_distribution,
            p10=p10,
            p25=p25,
            p50=p50,
            p75=p75,
            p90=p90,
        )
    
    def simulate_multiple_lines(
        self,
        goalie_name: str,
        opponent_name: str,
        lambda_shots: float,
        save_percentage: float,
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
        goal_prob = 1 - save_percentage
        goals = self.rng.binomial(shots, goal_prob)
        saves = shots - goals
        
        # Evaluate each line
        results = {}
        for line in lines:
            over_prob = (saves > line).mean()
            under_prob = (saves < line).mean()
            results[line] = (over_prob, under_prob)
        
        return results


def simulate_goalie_saves(
    goalie_name: str,
    opponent_name: str,
    lambda_shots: float,
    save_percentage: float,
    line: float,
    n_sims: int = DEFAULT_SIMULATIONS,
    seed: int = None,
) -> SavesSimulationResult:
    """
    Convenience function for single simulation.
    
    Args:
        goalie_name: Goalie name
        opponent_name: Opponent team
        lambda_shots: Expected shots against
        save_percentage: Goalie SV%
        line: Saves line to evaluate
        n_sims: Number of simulations
        seed: Random seed
    
    Returns:
        SavesSimulationResult
    """
    simulator = SavesSimulator(simulations=n_sims, seed=seed)
    return simulator.simulate(
        goalie_name=goalie_name,
        opponent_name=opponent_name,
        lambda_shots=lambda_shots,
        save_percentage=save_percentage,
        line=line,
    )


# ─────────────────────────────────────────────────────────
# ADVANCED: ADJUSTED SAVES SIMULATION
# ─────────────────────────────────────────────────────────

def simulate_adjusted_saves(
    goalie_name: str,
    opponent_name: str,
    base_lambda_shots: float,
    save_percentage: float,
    high_danger_sv_pct: float,
    opponent_hd_chances: float,
    line: float,
    n_sims: int = DEFAULT_SIMULATIONS,
    seed: int = None,
) -> SavesSimulationResult:
    """
    Advanced simulation with shot quality adjustment.
    
    Separates high-danger and medium/low-danger shots
    for more accurate save projections.
    
    Args:
        base_lambda_shots: Total expected shots
        save_percentage: Overall SV%
        high_danger_sv_pct: High-danger save %
        opponent_hd_chances: Opponent high-danger chances per game
        line: Saves line
        n_sims: Simulations
        seed: Random seed
    
    Returns:
        SavesSimulationResult
    """
    rng = np.random.default_rng(seed)
    
    # Split shots into high-danger and other
    hd_shots_lambda = opponent_hd_chances * 0.35  # ~35% of HD chances become shots
    other_shots_lambda = base_lambda_shots - hd_shots_lambda
    
    # Simulate separately
    hd_shots = rng.poisson(hd_shots_lambda, n_sims)
    other_shots = rng.poisson(other_shots_lambda, n_sims)
    
    total_shots = hd_shots + other_shots
    
    # Goals by danger level
    hd_goals = rng.binomial(hd_shots, 1 - high_danger_sv_pct)
    
    # Calculate implied low-danger SV% to match overall
    # Overall SV% = (HD_saves + Other_saves) / Total_shots
    # Solve for other_sv_pct
    other_sv_pct = (save_percentage * base_lambda_shots - high_danger_sv_pct * hd_shots_lambda) / other_shots_lambda
    other_sv_pct = np.clip(other_sv_pct, 0.92, 0.98)  # Reasonable bounds
    
    other_goals = rng.binomial(other_shots, 1 - other_sv_pct)
    
    # Total saves
    total_goals = hd_goals + other_goals
    saves = total_shots - total_goals
    
    # Statistics
    saves_mean = saves.mean()
    saves_std = saves.std()
    saves_median = np.median(saves)
    
    p10, p25, p50, p75, p90 = np.percentile(saves, [10, 25, 50, 75, 90])
    
    over_prob = (saves > line).mean()
    under_prob = (saves < line).mean()
    push_prob = 1.0 - over_prob - under_prob
    
    unique, counts = np.unique(saves, return_counts=True)
    saves_distribution = {
        int(val): count / n_sims 
        for val, count in zip(unique, counts)
    }
    
    return SavesSimulationResult(
        goalie=goalie_name,
        opponent=opponent_name,
        simulations=n_sims,
        lambda_shots=base_lambda_shots,
        save_percentage=save_percentage,
        saves_mean=saves_mean,
        saves_std=saves_std,
        saves_median=saves_median,
        line=line,
        over_prob=over_prob,
        under_prob=under_prob,
        push_prob=push_prob,
        saves_distribution=saves_distribution,
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
    print("GOALIE SAVES SIMULATOR — NHL v1.1 DEMO")
    print("=" * 60)
    
    # Demo: Jeremy Swayman vs NYR
    result = simulate_goalie_saves(
        goalie_name="Jeremy Swayman",
        opponent_name="NYR",
        lambda_shots=31.2,
        save_percentage=0.918,
        line=27.5,
        n_sims=20_000,
        seed=42,
    )
    
    print(f"\n{result}")
    print(f"\nPercentiles:")
    print(f"  10th: {result.p10:.0f}")
    print(f"  25th: {result.p25:.0f}")
    print(f"  50th: {result.p50:.0f} (median)")
    print(f"  75th: {result.p75:.0f}")
    print(f"  90th: {result.p90:.0f}")
    
    # Test multiple lines
    print("\n" + "-" * 40)
    print("Multi-line evaluation:")
    simulator = SavesSimulator(simulations=20_000, seed=42)
    lines_result = simulator.simulate_multiple_lines(
        goalie_name="Swayman",
        opponent_name="NYR",
        lambda_shots=31.2,
        save_percentage=0.918,
        lines=[25.5, 26.5, 27.5, 28.5, 29.5],
    )
    
    for line, (over_p, under_p) in lines_result.items():
        print(f"  Line {line}: OVER {over_p:.1%} | UNDER {under_p:.1%}")
    
    # Advanced simulation with shot quality
    print("\n" + "-" * 40)
    print("Advanced (shot-quality adjusted):")
    
    adv_result = simulate_adjusted_saves(
        goalie_name="Swayman",
        opponent_name="NYR",
        base_lambda_shots=31.2,
        save_percentage=0.918,
        high_danger_sv_pct=0.862,
        opponent_hd_chances=10.5,
        line=27.5,
        n_sims=20_000,
        seed=42,
    )
    
    print(f"  Basic: {result.saves_mean:.1f} saves (OVER 27.5 = {result.over_prob:.1%})")
    print(f"  Advanced: {adv_result.saves_mean:.1f} saves (OVER 27.5 = {adv_result.over_prob:.1%})")
