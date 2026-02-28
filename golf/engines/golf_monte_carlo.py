"""
Golf Monte Carlo Simulator
==========================
Advanced simulation for golf props with course fit and weather adjustments.

Quant Enhancements:
- Skew-Normal distribution for "fat tail" blow-up rounds
- Leaderboard Friction coefficient for top-5 psychological volatility
- Bayesian probability blend (MC + Market Intelligence)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats  # For skew-normal distribution
from pathlib import Path
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# =============================================================================
# QUANT CONFIG: Non-Gaussian Parameters
# =============================================================================

# Golf scores are RIGHT-SKEWED (easier to shoot +8 than -8)
# Skewness parameter: positive = right tail (blow-up rounds)
SCORING_SKEWNESS = 2.5  # Moderate right skew for Torrey-level difficulty

# Leaderboard Friction: Top players have higher psychological volatility
LEADERBOARD_FRICTION = {
    "leader": 1.15,      # 15% more variance for tournament leader
    "top_3": 1.10,       # 10% more for T2-T3
    "top_5": 1.05,       # 5% more for T4-T5
    "chasing": 0.95,     # Chasers play safer
}

# Market Intelligence Weights (Bayesian blend)
MARKET_WEIGHT = 0.30    # Books know more than simulation
SIM_WEIGHT = 0.70       # Sim knows player/course physics


@dataclass
class SimulationResult:
    """Result of Monte Carlo simulation."""
    mean: float
    median: float
    stddev: float
    percentile_10: float
    percentile_25: float
    percentile_75: float
    percentile_90: float
    prob_over: Dict[float, float]  # line -> probability
    prob_under: Dict[float, float]
    iterations: int = 10000


class GolfMonteCarloSimulator:
    """
    Monte Carlo simulator for golf props.
    
    Supports:
    - Round score simulation (normal distribution)
    - Birdie/bogey counts (Poisson)
    - Tournament finish position (log-normal)
    - Head-to-head matchups
    """
    
    def __init__(self, iterations: int = 10000, seed: int = None):
        self.iterations = iterations
        self.seed = seed
        if seed:
            np.random.seed(seed)
    
    def simulate_round_score(
        self,
        player_avg: float,
        player_stddev: float = 3.0,
        course_adjustment: float = 0.0,
        weather_adjustment: float = 0.0,
        sg_total: Optional[float] = None,
        lines: List[float] = None,
        leaderboard_position: Optional[int] = None,
        use_skew_normal: bool = True,
    ) -> SimulationResult:
        """
        Simulate round score distribution with Non-Gaussian fat tails.
        
        Args:
            player_avg: Player's average round score
            player_stddev: Standard deviation in scoring
            course_adjustment: Course difficulty factor (+/- strokes)
            weather_adjustment: Weather impact (+/- strokes)
            sg_total: Strokes Gained total (if available)
            lines: Prop lines to calculate probabilities for
            leaderboard_position: Current position (1=leader) for friction calc
            use_skew_normal: Use skew-normal for fat-tail modeling
            
        Returns:
            SimulationResult with distributions
        """
        # Adjust mean for factors
        adj_mean = player_avg + course_adjustment + weather_adjustment
        
        # SG adjustment (negative SG = better player)
        if sg_total is not None:
            adj_mean -= sg_total * 0.7  # SG converts to ~70% of scoring
        
        # LEADERBOARD FRICTION: Top players have higher psychological volatility
        adj_stddev = player_stddev
        if leaderboard_position is not None:
            if leaderboard_position == 1:
                adj_stddev *= LEADERBOARD_FRICTION["leader"]
            elif leaderboard_position <= 3:
                adj_stddev *= LEADERBOARD_FRICTION["top_3"]
            elif leaderboard_position <= 5:
                adj_stddev *= LEADERBOARD_FRICTION["top_5"]
            else:
                adj_stddev *= LEADERBOARD_FRICTION["chasing"]
        
        # SKEW-NORMAL DISTRIBUTION: Models "blow-up" rounds (fat right tail)
        if use_skew_normal:
            # Convert to skew-normal parameters
            # Higher skewness = more likely to shoot high (blow up)
            scores = stats.skewnorm.rvs(
                a=SCORING_SKEWNESS,  # Skewness parameter
                loc=adj_mean - 0.5,  # Shift left slightly to compensate for right skew
                scale=adj_stddev,
                size=self.iterations
            )
        else:
            # Standard Gaussian (legacy)
            scores = np.random.normal(adj_mean, adj_stddev, self.iterations)
        
        # Default lines
        if lines is None:
            lines = [67.5, 68.5, 69.5, 70.5, 71.5, 72.5, 73.5, 74.5]
        
        prob_over = {}
        prob_under = {}
        for line in lines:
            prob_over[line] = float(np.mean(scores > line))
            prob_under[line] = float(np.mean(scores <= line))
        
        return SimulationResult(
            mean=float(np.mean(scores)),
            median=float(np.median(scores)),
            stddev=float(np.std(scores)),
            percentile_10=float(np.percentile(scores, 10)),
            percentile_25=float(np.percentile(scores, 25)),
            percentile_75=float(np.percentile(scores, 75)),
            percentile_90=float(np.percentile(scores, 90)),
            prob_over=prob_over,
            prob_under=prob_under,
            iterations=self.iterations,
        )
    
    def simulate_birdies(
        self,
        avg_birdies: float,
        course_birdie_factor: float = 1.0,
        lines: List[float] = None
    ) -> SimulationResult:
        """
        Simulate birdie count using Poisson distribution.
        
        Args:
            avg_birdies: Player's average birdies per round
            course_birdie_factor: Course multiplier (easier course > 1.0)
            lines: Prop lines to calculate
            
        Returns:
            SimulationResult
        """
        lambda_birdies = avg_birdies * course_birdie_factor
        
        birdies = np.random.poisson(lambda_birdies, self.iterations)
        
        if lines is None:
            lines = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
        
        prob_over = {}
        prob_under = {}
        for line in lines:
            prob_over[line] = float(np.mean(birdies > line))
            prob_under[line] = float(np.mean(birdies <= line))
        
        return SimulationResult(
            mean=float(np.mean(birdies)),
            median=float(np.median(birdies)),
            stddev=float(np.std(birdies)),
            percentile_10=float(np.percentile(birdies, 10)),
            percentile_25=float(np.percentile(birdies, 25)),
            percentile_75=float(np.percentile(birdies, 75)),
            percentile_90=float(np.percentile(birdies, 90)),
            prob_over=prob_over,
            prob_under=prob_under,
            iterations=self.iterations,
        )
    
    def simulate_tournament_finish(
        self,
        expected_finish: float,
        skill_variance: float = 0.5,
        field_strength: float = 1.0,
        lines: List[float] = None
    ) -> SimulationResult:
        """
        Simulate tournament finish position.
        
        Uses log-normal distribution (heavy right tail - can finish much worse).
        
        Args:
            expected_finish: Expected finishing position
            skill_variance: Variance in finish positions
            field_strength: Stronger field = higher positions (>1.0)
            lines: Position lines to check
            
        Returns:
            SimulationResult with "better" (lower) and "worse" (higher) probs
        """
        # Adjust for field strength
        adj_finish = expected_finish * field_strength
        
        # Log-normal parameters
        mu = np.log(adj_finish) - (skill_variance ** 2) / 2
        sigma = skill_variance
        
        finishes = np.random.lognormal(mu, sigma, self.iterations)
        
        # Clamp to valid range (1 to field size, assume ~150)
        finishes = np.clip(finishes, 1, 150)
        
        if lines is None:
            lines = [5.5, 10.5, 20.5, 30.5, 40.5]
        
        # For finish position: "better" = lower number
        prob_over = {}  # worse than line
        prob_under = {}  # better than line
        for line in lines:
            prob_over[line] = float(np.mean(finishes > line))
            prob_under[line] = float(np.mean(finishes <= line))
        
        return SimulationResult(
            mean=float(np.mean(finishes)),
            median=float(np.median(finishes)),
            stddev=float(np.std(finishes)),
            percentile_10=float(np.percentile(finishes, 10)),
            percentile_25=float(np.percentile(finishes, 25)),
            percentile_75=float(np.percentile(finishes, 75)),
            percentile_90=float(np.percentile(finishes, 90)),
            prob_over=prob_over,  # Prob worse than line
            prob_under=prob_under,  # Prob better than line
            iterations=self.iterations,
        )
    
    def simulate_head_to_head(
        self,
        player_1_avg: float,
        player_2_avg: float,
        player_1_stddev: float = 3.0,
        player_2_stddev: float = 3.0,
        rounds: int = 4
    ) -> Dict:
        """
        Simulate head-to-head matchup over tournament.
        
        Args:
            player_1_avg: Player 1 scoring average
            player_2_avg: Player 2 scoring average
            player_1_stddev: Player 1 std dev
            player_2_stddev: Player 2 std dev
            rounds: Number of rounds (1 for single round, 4 for tournament)
            
        Returns:
            {"p1_win": prob, "p2_win": prob, "tie": prob}
        """
        p1_total = np.zeros(self.iterations)
        p2_total = np.zeros(self.iterations)
        
        for _ in range(rounds):
            p1_total += np.random.normal(player_1_avg, player_1_stddev, self.iterations)
            p2_total += np.random.normal(player_2_avg, player_2_stddev, self.iterations)
        
        p1_wins = np.mean(p1_total < p2_total)  # Lower score wins
        p2_wins = np.mean(p2_total < p1_total)
        ties = np.mean(p1_total == p2_total)
        
        return {
            "p1_win": float(p1_wins),
            "p2_win": float(p2_wins),
            "tie": float(ties),
            "sg_differential": player_2_avg - player_1_avg,  # Positive = P1 advantage
        }
    
    def simulate_make_cut(
        self,
        player_avg: float,
        player_stddev: float = 3.0,
        cut_line: float = 144.0,  # 36-hole score
        rounds: int = 2
    ) -> Dict:
        """
        Simulate probability of making the cut.
        
        Args:
            player_avg: Player round average
            player_stddev: Player std dev
            cut_line: Expected cut line (36-hole total)
            rounds: Rounds before cut (usually 2)
            
        Returns:
            {"make_cut": prob, "miss_cut": prob}
        """
        total_score = np.zeros(self.iterations)
        
        for _ in range(rounds):
            total_score += np.random.normal(player_avg, player_stddev, self.iterations)
        
        make_cut = np.mean(total_score <= cut_line)
        
        return {
            "make_cut": float(make_cut),
            "miss_cut": float(1 - make_cut),
            "expected_36_hole": float(np.mean(total_score)),
        }


# Convenience functions
def simulate_round_score(player_avg: float, line: float, **kwargs) -> Tuple[float, float]:
    """Quick round score simulation returning (prob_over, prob_under)."""
    sim = GolfMonteCarloSimulator()
    result = sim.simulate_round_score(player_avg, lines=[line], **kwargs)
    return result.prob_over[line], result.prob_under[line]


def simulate_birdies(avg_birdies: float, line: float, **kwargs) -> Tuple[float, float]:
    """Quick birdie simulation returning (prob_over, prob_under)."""
    sim = GolfMonteCarloSimulator()
    result = sim.simulate_birdies(avg_birdies, lines=[line], **kwargs)
    return result.prob_over[line], result.prob_under[line]


def simulate_tournament_finish(expected_finish: float, line: float, **kwargs) -> Tuple[float, float]:
    """Quick finish simulation returning (prob_better, prob_worse)."""
    sim = GolfMonteCarloSimulator()
    result = sim.simulate_tournament_finish(expected_finish, lines=[line], **kwargs)
    return result.prob_under[line], result.prob_over[line]  # under = better for position


# =============================================================================
# BAYESIAN PROBABILITY BLEND: MC Simulation + Market Intelligence
# =============================================================================

def calculate_bayesian_prob(
    mc_prob: float,
    multiplier_edge: float,
    market_weight: float = MARKET_WEIGHT,
    sim_weight: float = SIM_WEIGHT,
) -> float:
    """
    Blend Monte Carlo simulation probability with Market Intelligence.
    
    The books (via multiplier asymmetry) provide a "second opinion" that
    can boost or diminish confidence in the MC result.
    
    Args:
        mc_prob: Probability from Monte Carlo simulation (0.0-1.0)
        multiplier_edge: Asymmetry from Underdog multipliers (0.0-0.4 typical)
        market_weight: Weight given to market signal (default 0.30)
        sim_weight: Weight given to simulation (default 0.70)
        
    Returns:
        Bayesian-blended final probability
        
    Example:
        MC says 62% prob, multiplier edge is 0.15 (books agree)
        -> Final prob = (0.62 * 0.70) + ((0.62 + 0.05) * 0.30) = 0.635
        
        MC says 62% prob, multiplier edge is -0.10 (books disagree)
        -> Final prob = (0.62 * 0.70) + ((0.62 - 0.033) * 0.30) = 0.610
    """
    # Normalize multiplier edge to probability adjustment
    # 0.15 edge -> ~5% probability boost
    # 0.30 edge -> ~10% probability boost
    market_influence = multiplier_edge * 0.33
    
    # Market-adjusted probability
    market_adjusted_prob = mc_prob + market_influence
    market_adjusted_prob = max(0.30, min(0.85, market_adjusted_prob))  # Clamp
    
    # Bayesian blend
    final_prob = (mc_prob * sim_weight) + (market_adjusted_prob * market_weight)
    
    return round(final_prob, 4)


def calculate_confidence_score(
    mc_prob: float,
    multiplier_edge: float,
    sample_size: int = 10,
    data_freshness_days: int = 7,
) -> str:
    """
    Calculate confidence tier based on multiple factors.
    
    Args:
        mc_prob: Monte Carlo probability
        multiplier_edge: Market asymmetry
        sample_size: Number of rounds in player's dataset
        data_freshness_days: Days since last data update
        
    Returns:
        Confidence tier: "HIGH", "MEDIUM", "LOW", "EXPERIMENTAL"
    """
    score = 0
    
    # MC probability strength
    if mc_prob >= 0.65:
        score += 3
    elif mc_prob >= 0.58:
        score += 2
    elif mc_prob >= 0.52:
        score += 1
    
    # Market agreement
    if multiplier_edge >= 0.15:
        score += 2  # Strong market agreement
    elif multiplier_edge >= 0.08:
        score += 1  # Moderate agreement
    elif multiplier_edge < 0:
        score -= 1  # Market disagrees
    
    # Data quality
    if sample_size >= 20:
        score += 1
    elif sample_size < 5:
        score -= 2  # Cold start penalty
    
    if data_freshness_days > 30:
        score -= 1  # Stale data
    
    # Map score to tier
    if score >= 5:
        return "HIGH"
    elif score >= 3:
        return "MEDIUM"
    elif score >= 1:
        return "LOW"
    else:
        return "EXPERIMENTAL"


if __name__ == "__main__":
    print("=" * 60)
    print("GOLF MONTE CARLO SIMULATOR TEST")
    print("=" * 60)
    
    sim = GolfMonteCarloSimulator(iterations=10000, seed=42)
    
    # Test round score
    print("\n--- Round Score Simulation ---")
    print("Player: 71.0 avg, 3.0 stddev")
    result = sim.simulate_round_score(71.0, 3.0, lines=[69.5, 70.5, 71.5, 72.5])
    print(f"Mean: {result.mean:.2f}")
    print(f"Probabilities:")
    for line in [69.5, 70.5, 71.5, 72.5]:
        print(f"  {line}: Over {result.prob_over[line]:.1%} | Under {result.prob_under[line]:.1%}")
    
    # Test birdies
    print("\n--- Birdie Simulation ---")
    print("Player: 4.0 avg birdies")
    result = sim.simulate_birdies(4.0, lines=[3.5, 4.5, 5.5])
    print(f"Mean: {result.mean:.2f}")
    print(f"Probabilities:")
    for line in [3.5, 4.5, 5.5]:
        print(f"  {line}: Over {result.prob_over[line]:.1%} | Under {result.prob_under[line]:.1%}")
    
    # Test finish position
    print("\n--- Tournament Finish Simulation ---")
    print("Player: Expected finish ~20th")
    result = sim.simulate_tournament_finish(20.0, lines=[10.5, 20.5, 30.5])
    print(f"Mean finish: {result.mean:.1f}")
    print(f"Probabilities:")
    for line in [10.5, 20.5, 30.5]:
        print(f"  Top {line:.0f}: {result.prob_under[line]:.1%}")
    
    # Test H2H
    print("\n--- Head-to-Head Simulation ---")
    print("Player 1: 70.0 avg vs Player 2: 71.5 avg (4 rounds)")
    h2h = sim.simulate_head_to_head(70.0, 71.5)
    print(f"Player 1 wins: {h2h['p1_win']:.1%}")
    print(f"Player 2 wins: {h2h['p2_win']:.1%}")
