"""soccer/sim/soccer_props_monte_carlo.py

Soccer Player Props Monte Carlo Engine
======================================
Simulates player prop outcomes using statistical distributions.

Same methodology as NBA/Tennis systems:
- Normal distribution modeling with floor at 0
- 10,000 simulation iterations
- Variance modeling (σ)
- Probability calculations vs line
- Confidence caps per project rules
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.soccer_stats_api import SoccerPlayerStats


@dataclass
class SoccerMCResult:
    """Result of Monte Carlo simulation for a soccer prop."""
    
    player: str
    team: str
    stat_type: str
    line: float
    
    # Simulation outputs
    mean: float
    std: float
    simulations: int
    
    # Probabilities
    prob_over: float
    prob_under: float
    
    # Distribution percentiles
    p10: float
    p25: float
    p50: float  # median
    p75: float
    p90: float
    
    # Confidence / sample size
    sample_size: int
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    
    # Direction recommendation
    direction: str  # "OVER" | "UNDER" | "NO_EDGE"
    edge: float     # prob - 0.5 (simple edge measure)


# Project-level probability caps (from copilot-instructions.md)
CONFIDENCE_CAPS = {
    "core": 0.75,
    "volume_micro": 0.68,
    "sequence_early": 0.65,
    "event_binary": 0.55,
}


class SoccerPropsMCEngine:
    """Monte Carlo simulation engine for soccer player props."""
    
    def __init__(self, num_simulations: int = 10000):
        self.num_simulations = num_simulations
        np.random.seed(42)  # Reproducible
    
    def simulate_prop(
        self,
        stats: SoccerPlayerStats,
        stat_type: str,
        line: float,
    ) -> SoccerMCResult:
        """
        Run Monte Carlo simulation for a player prop.
        
        Args:
            stats: Player stats (from cache or manual input)
            stat_type: tackles, shots, goals, goalie_saves, etc.
            line: The O/U line from Underdog
        
        Returns:
            SoccerMCResult with probabilities and recommendation
        """
        mean, std, sample_size = self._get_stat_params(stats, stat_type)
        
        # Run simulations (normal distribution, floor at 0)
        sims = np.random.normal(mean, std, self.num_simulations)
        sims = np.maximum(sims, 0)
        
        # Probabilities
        prob_over = float(np.mean(sims > line))
        prob_under = float(np.mean(sims < line))
        
        # Percentiles
        p10 = float(np.percentile(sims, 10))
        p25 = float(np.percentile(sims, 25))
        p50 = float(np.percentile(sims, 50))
        p75 = float(np.percentile(sims, 75))
        p90 = float(np.percentile(sims, 90))
        
        # Confidence based on sample size + variance
        confidence = self._calc_confidence(std, sample_size, mean)
        
        # Direction + edge
        if prob_over > prob_under:
            direction = "OVER"
            edge = prob_over - 0.5
        elif prob_under > prob_over:
            direction = "UNDER"
            edge = prob_under - 0.5
        else:
            direction = "NO_EDGE"
            edge = 0.0
        
        # Apply confidence cap (core = 0.75)
        cap = CONFIDENCE_CAPS.get("core", 0.75)
        prob_over = min(prob_over, cap)
        prob_under = min(prob_under, cap)
        
        return SoccerMCResult(
            player=stats.player,
            team=stats.team,
            stat_type=stat_type,
            line=line,
            mean=round(mean, 2),
            std=round(std, 2),
            simulations=self.num_simulations,
            prob_over=round(prob_over, 4),
            prob_under=round(prob_under, 4),
            p10=round(p10, 2),
            p25=round(p25, 2),
            p50=round(p50, 2),
            p75=round(p75, 2),
            p90=round(p90, 2),
            sample_size=sample_size,
            confidence=confidence,
            direction=direction,
            edge=round(edge, 4),
        )
    
    def _get_stat_params(
        self,
        stats: SoccerPlayerStats,
        stat_type: str,
    ) -> Tuple[float, float, int]:
        """
        Extract (mean, std, sample_size) for the requested stat.
        
        Uses L10 as primary, falls back to L5, then season.
        """
        stat_map = {
            "tackles": (
                stats.tackles_l10 if stats.tackles_l10 > 0 else stats.tackles_l5,
                stats.tackles_std if stats.tackles_std > 0 else 0.5,
            ),
            "clearances": (
                stats.clearances_l10 if stats.clearances_l10 > 0 else stats.clearances_l5,
                stats.clearances_std if stats.clearances_std > 0 else 0.8,
            ),
            "shots": (
                stats.shots_l10 if stats.shots_l10 > 0 else stats.shots_l5,
                stats.shots_std if stats.shots_std > 0 else 0.8,
            ),
            "shots_on_target": (
                stats.sot_l10 if stats.sot_l10 > 0 else stats.sot_l5,
                stats.sot_std if stats.sot_std > 0 else 0.5,
            ),
            "sot": (
                stats.sot_l10 if stats.sot_l10 > 0 else stats.sot_l5,
                stats.sot_std if stats.sot_std > 0 else 0.5,
            ),
            "goals": (
                stats.goals_l10 if stats.goals_l10 > 0 else stats.goals_l5,
                stats.goals_std if stats.goals_std > 0 else 0.3,
            ),
            "goalie_saves": (
                stats.saves_l10 if stats.saves_l10 > 0 else stats.saves_l5,
                stats.saves_std if stats.saves_std > 0 else 1.2,
            ),
            "saves": (
                stats.saves_l10 if stats.saves_l10 > 0 else stats.saves_l5,
                stats.saves_std if stats.saves_std > 0 else 1.2,
            ),
            "shots_assisted": (
                stats.shots_assisted_l10 if stats.shots_assisted_l10 > 0 else stats.shots_assisted_l5,
                stats.shots_assisted_std if stats.shots_assisted_std > 0 else 0.5,
            ),
            "assists": (
                stats.assists_l10 if stats.assists_l10 > 0 else stats.assists_l5,
                stats.assists_std if stats.assists_std > 0 else 0.25,
            ),
        }
        
        if stat_type not in stat_map:
            # Fallback for unknown stat
            return (1.0, 0.5, 5)
        
        mean, std = stat_map[stat_type]
        sample_size = stats.matches_played if stats.matches_played > 0 else 5
        
        # If mean is still 0 (no data), return neutral
        if mean <= 0:
            mean = 1.0  # Default baseline
        
        return (mean, std, sample_size)
    
    def _calc_confidence(self, std: float, sample_size: int, mean: float) -> str:
        """
        Calculate confidence level.
        
        HIGH: Low variance relative to mean, large sample
        MEDIUM: Moderate variance or medium sample
        LOW: High variance or small sample
        """
        if sample_size < 3:
            return "LOW"
        
        # Coefficient of variation (CV) = std / mean
        cv = std / mean if mean > 0 else 1.0
        
        if sample_size >= 10 and cv < 0.4:
            return "HIGH"
        elif sample_size >= 5 and cv < 0.6:
            return "MEDIUM"
        else:
            return "LOW"


def run_simulation_for_prop(
    player: str,
    team: str,
    stat_type: str,
    line: float,
    stats: Optional[SoccerPlayerStats] = None,
    position: str = "unknown",
) -> SoccerMCResult:
    """
    Convenience function to run MC for a single prop.
    
    If stats is None, uses BASELINE estimates based on position/stat type.
    This allows meaningful analysis even without player-specific data.
    """
    if stats is None:
        # Use baseline estimates instead of NO_DATA
        mean, std = _get_baseline_estimate(stat_type, position, line)
        
        if mean > 0:
            # Run simulation with baseline
            engine = SoccerPropsMCEngine()
            sims = np.random.normal(mean, std, engine.num_simulations)
            sims = np.maximum(sims, 0)
            
            prob_over = float(np.mean(sims > line))
            prob_under = float(np.mean(sims < line))
            
            # Cap at 70% for baseline estimates (lower confidence)
            prob_over = min(prob_over, 0.70)
            prob_under = min(prob_under, 0.70)
            
            if prob_over > prob_under:
                direction = "OVER"
                edge = prob_over - 0.5
            elif prob_under > prob_over:
                direction = "UNDER"
                edge = prob_under - 0.5
            else:
                direction = "NO_EDGE"
                edge = 0.0
            
            return SoccerMCResult(
                player=player,
                team=team,
                stat_type=stat_type,
                line=line,
                mean=round(mean, 2),
                std=round(std, 2),
                simulations=engine.num_simulations,
                prob_over=round(prob_over, 4),
                prob_under=round(prob_under, 4),
                p10=round(float(np.percentile(sims, 10)), 2),
                p25=round(float(np.percentile(sims, 25)), 2),
                p50=round(float(np.percentile(sims, 50)), 2),
                p75=round(float(np.percentile(sims, 75)), 2),
                p90=round(float(np.percentile(sims, 90)), 2),
                sample_size=0,
                confidence="BASELINE",  # Mark as baseline estimate
                direction=direction,
                edge=round(edge, 4),
            )
        else:
            # Truly unknown stat type - return NO_DATA
            return SoccerMCResult(
                player=player,
                team=team,
                stat_type=stat_type,
                line=line,
                mean=0.0,
                std=0.0,
                simulations=0,
                prob_over=0.5,
                prob_under=0.5,
                p10=0.0,
                p25=0.0,
                p50=0.0,
                p75=0.0,
                p90=0.0,
                sample_size=0,
                confidence="NO_DATA",
                direction="NO_EDGE",
                edge=0.0,
            )
    
    engine = SoccerPropsMCEngine()
    return engine.simulate_prop(stats, stat_type, line)


# =============================================================================
# BASELINE ESTIMATES — League averages when player data is missing
# =============================================================================
BASELINE_ESTIMATES = {
    # Attacking stats (per 90 minutes)
    "shots": {"mean": 2.2, "std": 1.5},          # Avg outfield player
    "shots_attempted": {"mean": 2.2, "std": 1.5},
    "shots_on_target": {"mean": 0.8, "std": 0.7},
    "goals": {"mean": 0.25, "std": 0.5},         # ~0.25 goals/game avg
    "goal_plus_assist": {"mean": 0.35, "std": 0.6},
    "assists": {"mean": 0.12, "std": 0.4},
    
    # Goalkeeper stats
    "goalie_saves": {"mean": 3.2, "std": 1.8},   # Avg GK saves ~3/game
    "saves": {"mean": 3.2, "std": 1.8},
    "goals_allowed": {"mean": 1.2, "std": 1.0},
    
    # Defensive stats
    "tackles": {"mean": 2.5, "std": 1.5},
    "interceptions": {"mean": 1.2, "std": 1.0},
    "clearances": {"mean": 2.0, "std": 1.8},
    
    # Passing stats
    "passes": {"mean": 45.0, "std": 15.0},
    "key_passes": {"mean": 1.2, "std": 1.0},
}

# Position adjustments (multipliers)
POSITION_MULTIPLIERS = {
    "striker": {"shots": 1.6, "shots_on_target": 1.5, "goals": 2.0, "goal_plus_assist": 1.8},
    "winger": {"shots": 1.3, "shots_on_target": 1.2, "goals": 1.2, "assists": 1.5},
    "midfielder": {"passes": 1.2, "key_passes": 1.3, "assists": 1.2},
    "defender": {"tackles": 1.3, "clearances": 1.5, "interceptions": 1.3},
    "goalkeeper": {"goalie_saves": 1.0, "saves": 1.0, "goals_allowed": 1.0},
}


def _get_baseline_estimate(stat_type: str, position: str, line: float) -> tuple:
    """
    Get baseline (mean, std) estimate for a stat type.
    
    Uses league averages adjusted by position if known.
    Infers position from stat type when position is UNKNOWN.
    """
    stat_lower = stat_type.lower().replace(" ", "_")
    pos_lower = position.lower() if position else "unknown"
    
    # INFER POSITION FROM STAT TYPE when UNKNOWN
    if pos_lower in ["unknown", "none", ""]:
        if stat_lower in ["goalie_saves", "saves", "goals_allowed"]:
            pos_lower = "goalkeeper"
        elif stat_lower in ["goals", "goal_plus_assist"]:
            pos_lower = "striker"  # Assume attacking player for goal props
        elif stat_lower in ["shots", "shots_attempted", "shots_on_target"]:
            pos_lower = "striker"  # Shots props = attacking player
        elif stat_lower in ["tackles", "clearances", "interceptions"]:
            pos_lower = "defender"
        elif stat_lower in ["assists", "key_passes"]:
            pos_lower = "midfielder"  # Playmaker
    
    # Try direct match
    if stat_lower in BASELINE_ESTIMATES:
        base = BASELINE_ESTIMATES[stat_lower]
        mean = base["mean"]
        std = base["std"]
    else:
        # Try partial match
        for key, val in BASELINE_ESTIMATES.items():
            if key in stat_lower or stat_lower in key:
                mean = val["mean"]
                std = val["std"]
                break
        else:
            # Unknown stat - return 0
            return 0.0, 0.0
    
    # Apply position multiplier if available
    if pos_lower in POSITION_MULTIPLIERS:
        multipliers = POSITION_MULTIPLIERS[pos_lower]
        if stat_lower in multipliers:
            mean *= multipliers[stat_lower]
    
    # Adjust std proportionally
    std = mean * 0.5 if mean > 0 else 0.5
    
    return mean, std
