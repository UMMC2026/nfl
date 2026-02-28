"""
Tennis Monte Carlo Simulation Engine
====================================
Simulates player prop outcomes using statistical distributions.

Same methodology as NBA system:
- Normal distribution modeling
- 10,000+ simulation iterations
- Variance modeling (σ)
- Probability calculations vs line
"""

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict
from tennis_stats_api import TennisPlayerStats


@dataclass
class MonteCarloResult:
    """Result of Monte Carlo simulation"""
    stat_type: str
    player: str
    line: float
    
    # Simulation results
    mean: float
    std: float
    simulations: int
    
    # Probabilities
    prob_over: float
    prob_under: float
    
    # Distribution info
    percentile_25: float
    percentile_50: float  # median
    percentile_75: float
    
    # Confidence
    confidence: str  # "HIGH" / "MEDIUM" / "LOW"
    sample_size: int


class TennisMonteCarloEngine:
    """Monte Carlo simulation engine for tennis props"""
    
    def __init__(self, num_simulations: int = 10000):
        self.num_simulations = num_simulations
        np.random.seed(42)  # Reproducible results
    
    def simulate_prop(
        self,
        stats: TennisPlayerStats,
        stat_type: str,
        line: float
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation for a prop.
        
        Args:
            stats: Player statistics
            stat_type: "Aces", "Breakpoints Won", "Games Won", "Fantasy Score"
            line: O/U line
        
        Returns:
            MonteCarloResult with probabilities
        """
        # Get stat-specific parameters
        mean, std, sample_size = self._get_stat_parameters(stats, stat_type)
        
        # Run simulations
        simulated_values = np.random.normal(mean, std, self.num_simulations)
        
        # Ensure non-negative (can't have negative aces, etc.)
        simulated_values = np.maximum(simulated_values, 0)
        
        # Calculate probabilities
        prob_over = np.mean(simulated_values > line)
        prob_under = np.mean(simulated_values < line)
        
        # Distribution percentiles
        p25 = np.percentile(simulated_values, 25)
        p50 = np.percentile(simulated_values, 50)
        p75 = np.percentile(simulated_values, 75)
        
        # Determine confidence based on sample size and std
        confidence = self._calculate_confidence(std, sample_size, mean)
        
        return MonteCarloResult(
            stat_type=stat_type,
            player=stats.player,
            line=line,
            mean=mean,
            std=std,
            simulations=self.num_simulations,
            prob_over=prob_over,
            prob_under=prob_under,
            percentile_25=p25,
            percentile_50=p50,
            percentile_75=p75,
            confidence=confidence,
            sample_size=sample_size
        )
    
    def _get_stat_parameters(
        self,
        stats: TennisPlayerStats,
        stat_type: str
    ) -> Tuple[float, float, int]:
        """
        Get mean, std, and sample size for stat.
        
        Prioritizes recent performance (L5 > L10 > Season)
        """
        stat_map = {
            'Aces': (stats.aces_l10, stats.aces_std),
            'Breakpoints Won': (stats.breakpoints_won_l10, stats.breakpoints_won_std),
            'Break Points Won': (stats.breakpoints_won_l10, stats.breakpoints_won_std),
            'Games Won': (stats.games_won_l10, stats.games_won_std),
            'Total Games Won': (stats.games_won_l10, stats.games_won_std),
            'Games Played': (stats.total_games_l10, stats.total_games_std),  # Underdog format
            'Fantasy Score': (stats.fantasy_score_l10, stats.fantasy_score_std),
            'Fantasy Points': (stats.fantasy_score_l10, stats.fantasy_score_std),
            'Total Games': (stats.total_games_l10, stats.total_games_std),
            'Double Faults': (stats.double_faults_l10, stats.double_faults_std),
            'Tiebreakers Played': (stats.tiebreakers_l10, stats.tiebreakers_std),
            'Tiebreakers': (stats.tiebreakers_l10, stats.tiebreakers_std),
            'Sets Won': (stats.sets_won_l10, stats.sets_won_std),
            'Sets Played': (stats.sets_played_l10, stats.sets_played_std),
            '1st Set Games Won': (stats.games_won_l10 * 0.5, stats.games_won_std * 0.7),  # Approximation
            '1st Set Games Played': (stats.total_games_l10 * 0.4, stats.total_games_std * 0.6),  # Approximation
        }
        
        if stat_type not in stat_map:
            # Fallback
            return (10.0, 3.0, 5)
        
        mean, std = stat_map[stat_type]
        sample_size = stats.matches_played if stats.matches_played > 0 else 10
        
        return (mean, std, sample_size)
    
    def _calculate_confidence(self, std: float, sample_size: int, mean: float) -> str:
        """
        Calculate confidence level.
        
        HIGH: Low variance, large sample
        MEDIUM: Moderate variance or medium sample
        LOW: High variance or small sample
        """
        cv = std / mean if mean > 0 else 1.0  # Coefficient of variation
        
        if sample_size >= 10 and cv < 0.3:
            return "HIGH"
        elif sample_size >= 5 and cv < 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def simulate_multiple_props(
        self,
        stats_list: list[TennisPlayerStats],
        props: list[tuple[str, str, float]]  # (player, stat, line)
    ) -> Dict[str, MonteCarloResult]:
        """
        Simulate multiple props at once.
        
        Args:
            stats_list: List of player stats
            props: List of (player_name, stat_type, line)
        
        Returns:
            Dict mapping prop_key to MonteCarloResult
        """
        results = {}
        
        # Build stats lookup
        stats_by_player = {s.player: s for s in stats_list}
        
        for player, stat_type, line in props:
            if player not in stats_by_player:
                continue
            
            stats = stats_by_player[player]
            result = self.simulate_prop(stats, stat_type, line)
            
            # Create unique key
            prop_key = f"{player}|{stat_type}|{line}"
            results[prop_key] = result
        
        return results


# Test
if __name__ == "__main__":
    from tennis_stats_api import TennisStatsAPI
    
    # Get player stats
    api = TennisStatsAPI()
    sinner_stats = api.get_player_stats("Jannik Sinner")
    alcaraz_stats = api.get_player_stats("Carlos Alcaraz")
    
    # Create engine
    engine = TennisMonteCarloEngine(num_simulations=10000)
    
    # Test props
    props = [
        ("Jannik Sinner", "Fantasy Score", 34.0),
        ("Jannik Sinner", "Aces", 8.0),
        ("Carlos Alcaraz", "Games Won", 20.5),
        ("Carlos Alcaraz", "Breakpoints Won", 4.5),
    ]
    
    # Run simulations
    results = engine.simulate_multiple_props(
        [sinner_stats, alcaraz_stats],
        props
    )
    
    # Display results
    print("\n" + "=" * 80)
    print("TENNIS MONTE CARLO SIMULATION RESULTS")
    print("=" * 80)
    
    for prop_key, result in results.items():
        print(f"\n{result.player} - {result.stat_type} O/U {result.line}")
        print(f"  Mean: {result.mean:.2f} ± {result.std:.2f}")
        print(f"  P(Over): {result.prob_over:.1%} | P(Under): {result.prob_under:.1%}")
        print(f"  Distribution: P25={result.percentile_25:.1f}, P50={result.percentile_50:.1f}, P75={result.percentile_75:.1f}")
        print(f"  Confidence: {result.confidence} ({result.sample_size} match sample)")
        
        # Recommendation
        if result.prob_over > 0.60:
            print(f"  → LEAN OVER ({result.prob_over:.1%} confidence)")
        elif result.prob_under > 0.60:
            print(f"  → LEAN UNDER ({result.prob_under:.1%} confidence)")
        else:
            print(f"  → PASS (too close)")
