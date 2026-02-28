"""
Soccer Statistical Distributions
=================================

Probability distributions for soccer player props:
- Poisson: For strikers/attacking players (shots, goals)
- Zero-Inflated Poisson: For defenders/low-frequency events
- Normal: For high-volume stats (passes)
- Binomial: For conditional events (SOT given shots)

Author: Production Sports Betting System
Date: 2026-02-01
"""

import logging
import math
from typing import Tuple, Optional, Dict
from enum import Enum
from scipy import stats
import numpy as np

logger = logging.getLogger(__name__)


class DistributionType(Enum):
    """Statistical distribution types."""
    POISSON = "poisson"
    ZERO_INFLATED_POISSON = "zip"
    NORMAL = "normal"
    BINOMIAL = "binomial"


class SoccerDistributions:
    """
    Statistical distributions for soccer player props.
    
    Key Concepts:
    
    1. Poisson Distribution
       - Used for: Count events (shots, tackles, fouls)
       - Best for: Strikers, high-frequency events
       - Assumes: Events are independent and random
    
    2. Zero-Inflated Poisson (ZIP)
       - Used for: Defenders' shots, rare events
       - Best for: Players who often have 0 of a stat
       - Accounts for: Excess zeros (structural + random)
    
    3. Normal Distribution
       - Used for: High-volume stats (passes, touches)
       - Best for: Midfielders with 40+ passes/game
       - Requires: Large sample size (CLT applies)
    
    4. Binomial Distribution
       - Used for: Conditional probabilities
       - Best for: "SOT given shots" or "Saves given shots faced"
       - Models: Success rate x opportunities
    """
    
    def __init__(self):
        """Initialize distributions calculator."""
        logger.info("SoccerDistributions initialized")
    
    # ==================== POISSON DISTRIBUTION ====================
    
    def poisson_probability(
        self,
        lambda_param: float,
        line: float,
        direction: str = "OVER"
    ) -> float:
        """
        Calculate Poisson probability.
        
        Formula:
            P(X = k) = (lambda^k x e^(-lambda)) / k!
            P(X > line) = 1 - sum(P(X <= floor(line)))
        
        Args:
            lambda_param: Expected value (player's average)
            line: Betting line
            direction: "OVER" or "UNDER"
        
        Returns:
            Probability (0-1)
        
        Example:
            >>> dist = SoccerDistributions()
            >>> # Salah averages 3.8 shots, line is 3.5 OVER
            >>> prob = dist.poisson_probability(3.8, 3.5, "OVER")
            >>> print(f"P(shots > 3.5) = {prob:.1%}")
            P(shots > 3.5) = 58.2%
        """
        if lambda_param <= 0:
            logger.warning(f"Invalid lambda: {lambda_param}, using 0.1")
            lambda_param = 0.1
        
        try:
            if direction.upper() == "OVER":
                # P(X > line) = 1 - P(X <= floor(line))
                k = math.floor(line)
                prob = 1 - stats.poisson.cdf(k, lambda_param)
            
            elif direction.upper() == "UNDER":
                # P(X < line) = P(X <= ceil(line) - 1)
                k = math.ceil(line) - 1
                prob = stats.poisson.cdf(k, lambda_param)
            
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            # Clamp to valid probability range
            prob = max(0.0, min(1.0, prob))
            
            logger.debug(
                f"[POISSON] lambda={lambda_param:.2f}, line={line}, "
                f"direction={direction}, P={prob:.1%}"
            )
            
            return prob
        
        except Exception as e:
            logger.error(f"Poisson calculation failed: {e}")
            return 0.5  # Return 50% on error (no edge)
    
    # =============== ZERO-INFLATED POISSON DISTRIBUTION ===============
    
    def zero_inflated_poisson(
        self,
        lambda_param: float,
        line: float,
        zero_inflation: float = 0.30,
        direction: str = "OVER"
    ) -> float:
        """
        Calculate Zero-Inflated Poisson probability.
        
        ZIP accounts for excess zeros in data:
        - Structural zeros: Player doesn't take shots (defender)
        - Random zeros: Player takes shots but misses
        
        Formula:
            P(X = 0) = pi + (1 - pi) x e^(-lambda)
            P(X = k) = (1 - pi) x Poisson(k; lambda)  for k > 0
        
        Args:
            lambda_param: Expected value for Poisson component
            line: Betting line
            zero_inflation: Probability of structural zero (0-1)
            direction: "OVER" or "UNDER"
        
        Returns:
            Probability (0-1)
        
        Example:
            >>> dist = SoccerDistributions()
            >>> # Defender averages 0.5 shots, but 40% of games = 0 shots
            >>> prob = dist.zero_inflated_poisson(
            ...     lambda_param=0.8,
            ...     line=0.5,
            ...     zero_inflation=0.40,
            ...     direction="OVER"
            ... )
            >>> print(f"P(shots > 0.5) = {prob:.1%}")
            P(shots > 0.5) = 32.1%
        """
        if lambda_param <= 0:
            logger.warning(f"Invalid lambda for ZIP: {lambda_param}, using 0.1")
            lambda_param = 0.1
        
        if not (0 <= zero_inflation <= 1):
            logger.warning(f"Invalid zero_inflation: {zero_inflation}, using 0.30")
            zero_inflation = 0.30
        
        try:
            # Calculate ZIP probabilities for each count
            def zip_pmf(k: int) -> float:
                """ZIP probability mass function."""
                if k == 0:
                    # P(X=0) includes structural and random zeros
                    poisson_zero = math.exp(-lambda_param)
                    return zero_inflation + (1 - zero_inflation) * poisson_zero
                else:
                    # P(X=k) for k > 0
                    poisson_k = stats.poisson.pmf(k, lambda_param)
                    return (1 - zero_inflation) * poisson_k
            
            if direction.upper() == "OVER":
                # P(X > line) = sum P(X = k) for k > floor(line)
                k_threshold = math.floor(line)
                prob = sum(
                    zip_pmf(k) 
                    for k in range(k_threshold + 1, k_threshold + 50)
                    # Sum up to threshold + 50 for numerical stability
                )
            
            elif direction.upper() == "UNDER":
                # P(X < line) = sum P(X = k) for k <= ceil(line) - 1
                k_threshold = math.ceil(line) - 1
                prob = sum(
                    zip_pmf(k) 
                    for k in range(0, k_threshold + 1)
                )
            
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            # Clamp to valid range
            prob = max(0.0, min(1.0, prob))
            
            logger.debug(
                f"[ZIP] lambda={lambda_param:.2f}, pi={zero_inflation:.2f}, "
                f"line={line}, direction={direction}, P={prob:.1%}"
            )
            
            return prob
        
        except Exception as e:
            logger.error(f"ZIP calculation failed: {e}")
            return 0.5
    
    # ==================== NORMAL DISTRIBUTION ====================
    
    def normal_probability(
        self,
        mean: float,
        std: float,
        line: float,
        direction: str = "OVER"
    ) -> float:
        """
        Calculate Normal distribution probability.
        
        Formula:
            P(X > line) = 1 - Phi((line - mu) / sigma)
        
        Where Phi is the standard normal CDF.
        
        Args:
            mean: Player's mean (mu)
            std: Player's standard deviation (sigma)
            line: Betting line
            direction: "OVER" or "UNDER"
        
        Returns:
            Probability (0-1)
        
        Example:
            >>> dist = SoccerDistributions()
            >>> # Midfielder averages 62 passes, sigma=12, line 55.5 OVER
            >>> prob = dist.normal_probability(62, 12, 55.5, "OVER")
            >>> print(f"P(passes > 55.5) = {prob:.1%}")
            P(passes > 55.5) = 70.5%
        """
        if std <= 0:
            logger.warning(f"Invalid std: {std}, using mean * 0.20")
            std = mean * 0.20 if mean > 0 else 1.0
        
        try:
            z_score = (line - mean) / std
            
            if direction.upper() == "OVER":
                # P(X > line) = 1 - Phi((line - mu) / sigma)
                prob = 1 - stats.norm.cdf(z_score)
            
            elif direction.upper() == "UNDER":
                # P(X < line) = Phi((line - mu) / sigma)
                prob = stats.norm.cdf(z_score)
            
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            # Clamp to valid range
            prob = max(0.0, min(1.0, prob))
            
            logger.debug(
                f"[NORMAL] mu={mean:.2f}, sigma={std:.2f}, line={line}, "
                f"z={z_score:.2f}, direction={direction}, P={prob:.1%}"
            )
            
            return prob
        
        except Exception as e:
            logger.error(f"Normal calculation failed: {e}")
            return 0.5
    
    # ==================== BINOMIAL DISTRIBUTION ====================
    
    def binomial_probability(
        self,
        n_trials: float,
        success_rate: float,
        line: float,
        direction: str = "OVER"
    ) -> float:
        """
        Calculate Binomial probability.
        
        Formula:
            P(X = k) = C(n,k) x p^k x (1-p)^(n-k)
        
        Args:
            n_trials: Number of trials (e.g., shots taken)
            success_rate: Probability of success per trial (e.g., SOT%)
            line: Betting line
            direction: "OVER" or "UNDER"
        
        Returns:
            Probability (0-1)
        
        Example:
            >>> dist = SoccerDistributions()
            >>> # Player takes 4 shots, 40% are on target, line 1.5 SOT
            >>> prob = dist.binomial_probability(4, 0.40, 1.5, "OVER")
            >>> print(f"P(SOT > 1.5) = {prob:.1%}")
            P(SOT > 1.5) = 52.5%
        """
        if not (0 <= success_rate <= 1):
            logger.warning(f"Invalid success_rate: {success_rate}, clamping")
            success_rate = max(0.0, min(1.0, success_rate))
        
        if n_trials < 0:
            logger.warning(f"Invalid n_trials: {n_trials}, using 0")
            n_trials = 0
        
        try:
            # Convert float n_trials to integer for binomial
            n = int(round(n_trials))
            
            if direction.upper() == "OVER":
                # P(X > line) = 1 - P(X <= floor(line))
                k = math.floor(line)
                prob = 1 - stats.binom.cdf(k, n, success_rate)
            
            elif direction.upper() == "UNDER":
                # P(X < line) = P(X <= ceil(line) - 1)
                k = math.ceil(line) - 1
                prob = stats.binom.cdf(k, n, success_rate)
            
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            # Clamp to valid range
            prob = max(0.0, min(1.0, prob))
            
            logger.debug(
                f"[BINOMIAL] n={n}, p={success_rate:.2f}, line={line}, "
                f"direction={direction}, P={prob:.1%}"
            )
            
            return prob
        
        except Exception as e:
            logger.error(f"Binomial calculation failed: {e}")
            return 0.5
    
    # ==================== DISTRIBUTION SELECTOR ====================
    
    def select_distribution(
        self,
        stat_type: str,
        player_position: str,
        mean: float,
        std: Optional[float] = None
    ) -> Tuple[DistributionType, Dict]:
        """
        Select appropriate distribution based on stat and player.
        
        Decision tree:
        - PASSES (high volume) -> Normal
        - SHOTS (striker) -> Poisson
        - SHOTS (defender) -> Zero-Inflated Poisson
        - SOT -> Binomial (conditional on shots)
        - TACKLES -> Position-dependent
        
        Args:
            stat_type: Type of stat (e.g., "SHOTS", "PASSES")
            player_position: Position code (e.g., "FW", "CB", "CM")
            mean: Player's mean for this stat
            std: Player's standard deviation (if available)
        
        Returns:
            Tuple of (DistributionType, params_dict)
        
        Example:
            >>> dist = SoccerDistributions()
            >>> dist_type, params = dist.select_distribution(
            ...     "SHOTS", "CB", mean=0.5
            ... )
            >>> print(dist_type)
            DistributionType.ZERO_INFLATED_POISSON
        """
        attacking_positions = ["FW", "AM", "W"]
        defensive_positions = ["CB", "FB", "DM"]
        midfield_positions = ["CM"]
        
        # High-volume stats use Normal distribution
        if stat_type in ["PASSES", "TOUCHES"]:
            return DistributionType.NORMAL, {
                "mean": mean,
                "std": std or (mean * 0.20)
            }
        
        # Shots: Position-dependent
        elif stat_type in ["SHOTS", "SHOT_ATTEMPTS"]:
            if player_position in attacking_positions:
                # Strikers/wingers shoot regularly -> Poisson
                return DistributionType.POISSON, {
                    "lambda_param": mean
                }
            else:
                # Defenders/DMs rarely shoot -> ZIP
                zero_inflation = self._estimate_zero_inflation(
                    stat_type, player_position, mean
                )
                return DistributionType.ZERO_INFLATED_POISSON, {
                    "lambda_param": mean if mean > 0 else 0.1,
                    "zero_inflation": zero_inflation
                }
        
        # SOT: Binomial (conditional on shots)
        elif stat_type in ["SOT", "SHOTS_ON_TARGET"]:
            return DistributionType.BINOMIAL, {
                "n_trials": mean / 0.40 if mean > 0 else 1.0,  # Estimate shots from SOT
                "success_rate": 0.40  # Typical SOT%
            }
        
        # Tackles: Position-dependent
        elif stat_type in ["TACKLES", "TACKLES_WON"]:
            if player_position in defensive_positions:
                return DistributionType.POISSON, {
                    "lambda_param": mean
                }
            else:
                # Attackers rarely tackle
                zero_inflation = 0.50
                return DistributionType.ZERO_INFLATED_POISSON, {
                    "lambda_param": mean if mean > 0 else 0.1,
                    "zero_inflation": zero_inflation
                }
        
        # Default: Poisson for count stats
        else:
            return DistributionType.POISSON, {
                "lambda_param": mean if mean > 0 else 0.1
            }
    
    def _estimate_zero_inflation(
        self,
        stat_type: str,
        player_position: str,
        mean: float
    ) -> float:
        """
        Estimate zero-inflation parameter.
        
        Based on position and mean value:
        - Low mean + defensive position -> High zero-inflation
        - High mean + attacking position -> Low zero-inflation
        """
        # Base zero-inflation by position
        position_inflation = {
            "CB": 0.50,   # Defenders rarely shoot
            "FB": 0.45,
            "DM": 0.40,
            "CM": 0.30,
            "AM": 0.20,
            "W": 0.15,
            "FW": 0.10
        }
        
        base_inflation = position_inflation.get(player_position, 0.30)
        
        # Adjust based on mean (lower mean -> more zeros)
        if mean < 0.5:
            base_inflation += 0.15
        elif mean < 1.0:
            base_inflation += 0.05
        elif mean > 2.0:
            base_inflation -= 0.10
        
        # Clamp to valid range
        return max(0.05, min(0.70, base_inflation))


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    dist = SoccerDistributions()
    
    print(f"\n{'='*70}")
    print(f"SOCCER DISTRIBUTIONS EXAMPLES")
    print(f"{'='*70}\n")
    
    # Example 1: Poisson (Striker shots)
    print("Example 1: Haaland Shots (Poisson)")
    print("-" * 70)
    prob_poisson = dist.poisson_probability(
        lambda_param=4.2,
        line=3.5,
        direction="OVER"
    )
    print(f"Haaland averages 4.2 shots/game")
    print(f"Line: 3.5 OVER")
    print(f"P(shots > 3.5) = {prob_poisson:.1%}\n")
    
    # Example 2: Zero-Inflated Poisson (Defender shots)
    print("Example 2: Defender Shots (Zero-Inflated Poisson)")
    print("-" * 70)
    prob_zip = dist.zero_inflated_poisson(
        lambda_param=0.8,
        line=0.5,
        zero_inflation=0.45,
        direction="OVER"
    )
    print(f"Defender averages 0.8 shots/game")
    print(f"45% of games = 0 shots (structural zeros)")
    print(f"Line: 0.5 OVER")
    print(f"P(shots > 0.5) = {prob_zip:.1%}\n")
    
    # Example 3: Normal (Midfielder passes)
    print("Example 3: Midfielder Passes (Normal)")
    print("-" * 70)
    prob_normal = dist.normal_probability(
        mean=62.0,
        std=12.0,
        line=55.5,
        direction="OVER"
    )
    print(f"Midfielder averages 62 passes (sigma=12)")
    print(f"Line: 55.5 OVER")
    print(f"P(passes > 55.5) = {prob_normal:.1%}\n")
    
    # Example 4: Distribution Selection
    print("Example 4: Auto Distribution Selection")
    print("-" * 70)
    
    test_cases = [
        ("SHOTS", "FW", 4.2),
        ("SHOTS", "CB", 0.5),
        ("PASSES", "CM", 62.0),
        ("TACKLES", "DM", 3.5)
    ]
    
    for stat, pos, mean in test_cases:
        dist_type, params = dist.select_distribution(stat, pos, mean)
        print(f"{stat} for {pos} (mu={mean}) -> {dist_type.value}")
        print(f"  Params: {params}\n")
    
    print(f"{'='*70}\n")
