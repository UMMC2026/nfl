"""
Confidence Calibration Module

Applies shrinkage, regression penalties, and confidence caps to raw probability estimates.
NBA player props rarely exceed 75-80% true probability due to variance factors.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import math


class ConfidenceTier(Enum):
    """Confidence bands - capped for realistic expectations."""
    SLAM = "SLAM"          # 68-75% displayed
    STRONG = "STRONG"      # 60-67% displayed  
    LEAN = "LEAN"          # 52-59% displayed
    COIN_FLIP = "FLIP"     # 48-51%
    FADE = "FADE"          # <48% - consider opposite direction


@dataclass
class CalibrationConfig:
    """Configuration for confidence calibration."""
    # Shrinkage toward league average (0 = no shrinkage, 1 = full shrinkage)
    shrinkage_factor: float = 0.15
    
    # Maximum displayable confidence (NBA props rarely exceed this truly)
    max_confidence: float = 0.78
    
    # Minimum sample size for full confidence (games)
    min_sample_size: int = 10
    
    # Regression penalty for hot/cold streaks
    streak_penalty: float = 0.05
    
    # Volatility penalty multiplier (applied to high-std players)
    volatility_penalty_mult: float = 0.02
    
    # Confidence floor (below this = no edge)
    min_confidence: float = 0.48
    # Blending parameters for prior/posterior soft blend
    blend_min_alpha: float = 0.20
    blend_max_alpha: float = 0.80


@dataclass
class CalibratedPick:
    """A pick with calibrated confidence metrics."""
    player: str
    team: str
    stat: str
    line: float
    direction: str
    
    # Raw probability from model
    raw_probability: float
    
    # Calibrated (adjusted) probability
    calibrated_probability: float
    
    # Display probability (capped for user presentation)
    display_probability: float
    
    # Confidence tier
    tier: ConfidenceTier
    
    # Adjustments applied
    shrinkage_applied: float = 0.0
    streak_penalty_applied: float = 0.0
    volatility_penalty_applied: float = 0.0
    sample_penalty_applied: float = 0.0
    
    # Metadata
    sample_size: int = 0
    std_dev: float = 0.0
    recent_trend: str = "neutral"  # hot, cold, neutral


class ConfidenceCalibrator:
    """
    Calibrates raw probability estimates to realistic confidence levels.
    
    Key principles:
    1. Shrink toward 50% (the prior) based on sample size
    2. Penalize hot streaks (regression to mean)
    3. Penalize high volatility players
    4. Cap maximum confidence at realistic levels
    """
    
    def __init__(self, config: Optional[CalibrationConfig] = None):
        self.config = config or CalibrationConfig()
    
    def calibrate(
        self,
        player: str,
        team: str,
        stat: str,
        line: float,
        direction: str,
        raw_prob: float,
        mu: float,
        sigma: float,
        recent_values: Optional[list[float]] = None,
        career_avg: Optional[float] = None,
        prior_prob: Optional[float] = None,
        prior_mu: Optional[float] = None,
        prior_sigma: Optional[float] = None,
    ) -> CalibratedPick:
        """
        Apply full calibration pipeline to a raw probability estimate.
        
        Args:
            raw_prob: Model's raw probability estimate
            mu: Recent mean (e.g., 10-game average)
            sigma: Standard deviation
            recent_values: List of recent game values
            career_avg: Player's career average for this stat (if available)
        """
        sample_size = len(recent_values) if recent_values else 0
        # Soft-blend prior and posterior based on available sample size.
        if prior_prob is not None:
            if sample_size == 0:
                alpha = 0.0
            else:
                frac = min(1.0, sample_size / self.config.min_sample_size)
                alpha = self.config.blend_min_alpha + (self.config.blend_max_alpha - self.config.blend_min_alpha) * frac
            adjusted = prior_prob + alpha * (raw_prob - prior_prob)
        else:
            adjusted = raw_prob
        
        # Track adjustments
        shrinkage = 0.0
        streak_pen = 0.0
        vol_pen = 0.0
        sample_pen = 0.0
        
        # 1. Apply shrinkage toward 50% prior
        # Scale penalties by (1 - alpha) so stronger blending reduces penalty impact.
        scale = 1.0
        if prior_prob is not None:
            # If alpha defined above, compute scale = (1 - alpha)
            try:
                scale = 1.0 - alpha
            except Exception:
                scale = 1.0

        shrinkage = self._apply_shrinkage(adjusted, sample_size) * scale
        adjusted -= shrinkage
        
        # 2. Detect and penalize streaks
        trend, streak_pen = self._detect_streak_penalty(
            mu, career_avg, recent_values, direction
        )
        adjusted -= streak_pen * scale
        
        # 3. Apply volatility penalty for high-std players
        vol_pen = self._apply_volatility_penalty(sigma, mu)
        adjusted -= vol_pen * scale
        
        # 4. Sample size penalty (less data = less confidence)
        sample_pen = self._apply_sample_penalty(sample_size)
        adjusted -= sample_pen * scale
        
        # 5. Clamp to valid probability range (allow lower probabilities; avoid hard 0.48 collapse)
        calibrated = max(0.01, min(self.config.max_confidence, adjusted))
        
        # 6. Cap display probability (what users see)
        display_prob = self._cap_display_probability(calibrated)
        
        # 7. Assign tier
        tier = self._assign_tier(display_prob)
        
        return CalibratedPick(
            player=player,
            team=team,
            stat=stat,
            line=line,
            direction=direction,
            raw_probability=raw_prob,
            calibrated_probability=calibrated,
            display_probability=display_prob,
            tier=tier,
            shrinkage_applied=shrinkage,
            streak_penalty_applied=streak_pen,
            volatility_penalty_applied=vol_pen,
            sample_penalty_applied=sample_pen,
            sample_size=sample_size,
            std_dev=sigma,
            recent_trend=trend,
        )
    
    def _apply_shrinkage(self, prob: float, sample_size: int) -> float:
        """
        Shrink probability toward 50% based on sample size.
        Less data = more shrinkage toward the prior.
        """
        if sample_size >= self.config.min_sample_size:
            shrinkage_weight = self.config.shrinkage_factor
        else:
            # More shrinkage for smaller samples
            shrinkage_weight = self.config.shrinkage_factor * (
                1 + (self.config.min_sample_size - sample_size) / self.config.min_sample_size
            )
        
        # Shrinkage pulls toward 0.5
        deviation_from_prior = prob - 0.5
        return deviation_from_prior * shrinkage_weight
    
    def _detect_streak_penalty(
        self,
        mu: float,
        career_avg: Optional[float],
        recent_values: Optional[list[float]],
        direction: str,
    ) -> tuple[str, float]:
        """
        Detect hot/cold streaks and apply regression penalty.
        """
        if not recent_values or len(recent_values) < 5:
            return "neutral", 0.0
        
        # Compare recent to career (if available) or estimate
        baseline = career_avg if career_avg else mu * 0.9  # Assume career is ~10% lower
        
        recent_5 = recent_values[:5]
        recent_avg = sum(recent_5) / len(recent_5)
        
        # Calculate deviation from baseline
        pct_deviation = (recent_avg - baseline) / baseline if baseline > 0 else 0
        
        penalty = 0.0
        trend = "neutral"
        
        if direction == "higher":
            # For overs, penalize hot streaks (regression coming)
            if pct_deviation > 0.15:  # 15%+ above career
                trend = "hot"
                penalty = min(self.config.streak_penalty * (pct_deviation / 0.15), 0.10)
            elif pct_deviation < -0.15:
                trend = "cold"
                # Cold streak for an over might mean opportunity, slight boost
                penalty = -0.02
        else:
            # For unders, penalize cold streaks
            if pct_deviation < -0.15:
                trend = "cold"
                penalty = min(self.config.streak_penalty * (abs(pct_deviation) / 0.15), 0.10)
            elif pct_deviation > 0.15:
                trend = "hot"
                penalty = -0.02
        
        return trend, penalty
    
    def _apply_volatility_penalty(self, sigma: float, mu: float) -> float:
        """
        Penalize high-volatility players (large std dev relative to mean).
        """
        if mu is None or mu <= 0:
            return 0.0
        if sigma is None:
            return 0.0
        
        # Coefficient of variation (CV)
        cv = sigma / mu
        
        # Penalty kicks in above 30% CV
        if cv > 0.30:
            excess_cv = cv - 0.30
            return min(excess_cv * self.config.volatility_penalty_mult * 100, 0.08)
        
        return 0.0
    
    def _apply_sample_penalty(self, sample_size: int) -> float:
        """
        Reduce confidence when sample size is small.
        """
        if sample_size >= self.config.min_sample_size:
            return 0.0
        
        # Linear penalty: 0 games = 5% penalty, 10 games = 0%
        missing = self.config.min_sample_size - sample_size
        return (missing / self.config.min_sample_size) * 0.05
    
    def _cap_display_probability(self, prob: float) -> float:
        """
        Cap probability for display to prevent overconfidence.
        
        NBA player props rarely have >75% true probability due to:
        - Minutes variance
        - Blowout risk
        - Injury mid-game
        - Coaching decisions
        """
        # Map internal probability to display bands
        if prob >= 0.75:
            # SLAM tier: display 68-75%
            return 0.68 + (prob - 0.75) / (self.config.max_confidence - 0.75) * 0.07
        elif prob >= 0.65:
            # STRONG tier: display 60-67%
            return 0.60 + (prob - 0.65) / 0.10 * 0.07
        elif prob >= 0.55:
            # LEAN tier: display 52-59%
            return 0.52 + (prob - 0.55) / 0.10 * 0.07
        else:
            # Below threshold: show actual
            return prob
    
    def _assign_tier(self, display_prob: float) -> ConfidenceTier:
        """Assign confidence tier based on calibrated probability."""
        if display_prob >= 0.68:
            return ConfidenceTier.SLAM
        elif display_prob >= 0.60:
            return ConfidenceTier.STRONG
        elif display_prob >= 0.52:
            return ConfidenceTier.LEAN
        elif display_prob >= 0.48:
            return ConfidenceTier.COIN_FLIP
        else:
            return ConfidenceTier.FADE


def calibrate_picks(picks: list[dict], config: Optional[CalibrationConfig] = None) -> list[CalibratedPick]:
    """
    Convenience function to calibrate a list of picks.
    
    Args:
        picks: List of pick dictionaries with keys:
            - player, team, stat, line, direction
            - mu, sigma, recent_values (optional)
    
    Returns:
        List of CalibratedPick objects
    """
    calibrator = ConfidenceCalibrator(config)
    calibrated = []
    
    for p in picks:
        # Calculate raw probability
        mu = p.get("mu")
        sigma = p.get("sigma")
        line = p.get("line", 0)
        direction = p.get("direction", "higher")
        
        if mu is None or sigma is None:
            # No data - coin flip
            raw_prob = 0.50
        else:
            # Normal CDF approximation
            from math import erf, sqrt
            z = (line - mu) / max(sigma, 0.001)
            p_under = 0.5 * (1 + erf(z / sqrt(2)))
            raw_prob = (1 - p_under) if direction == "higher" else p_under
        
        calibrated_pick = calibrator.calibrate(
            player=p.get("player", ""),
            team=p.get("team", ""),
            stat=p.get("stat", ""),
            line=line,
            direction=direction,
            raw_prob=raw_prob,
            mu=mu or 0,
            sigma=sigma or 1,
            recent_values=p.get("recent_values"),
            career_avg=p.get("career_avg"),
        )
        calibrated.append(calibrated_pick)
    
    return calibrated


# Quick test
if __name__ == "__main__":
    calibrator = ConfidenceCalibrator()
    
    # Test case: OG Anunoby with hot streak
    result = calibrator.calibrate(
        player="OG Anunoby",
        team="NYK",
        stat="points",
        line=16.5,
        direction="higher",
        raw_prob=0.90,  # Model says 90%
        mu=25.6,        # Recent average
        sigma=7.1,
        recent_values=[28, 22, 30, 25, 24, 27, 21, 29, 26, 24],
        career_avg=14.0,  # Career average much lower
    )
    
    print(f"OG Anunoby OVER 16.5 points:")
    print(f"  Raw: {result.raw_probability:.1%}")
    print(f"  Calibrated: {result.calibrated_probability:.1%}")
    print(f"  Display: {result.display_probability:.1%}")
    print(f"  Tier: {result.tier.value}")
    print(f"  Trend: {result.recent_trend}")
    print(f"  Adjustments:")
    print(f"    Shrinkage: -{result.shrinkage_applied:.1%}")
    print(f"    Streak penalty: -{result.streak_penalty_applied:.1%}")
    print(f"    Volatility penalty: -{result.volatility_penalty_applied:.1%}")
