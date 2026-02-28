"""
Matchup Safety Module
=====================

Provides SAFE/DANGEROUS classification for matchup data and
generates weighting math breakdowns for report output.

SOP v2.3: Three new matchup features:
1. Explicit weighting math in report output
2. SAFE/DANGEROUS flag per matchup
3. Direct integration into probability engine

IMPORTANT: This module provides classification metadata.
It does NOT override Monte Carlo probabilities directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MatchupSafetyLevel(Enum):
    """Classification of matchup reliability."""
    SAFE = "SAFE"             # ≥5 games, low variance, high confidence
    CAUTIOUS = "CAUTIOUS"     # 3-4 games, moderate confidence
    DANGEROUS = "DANGEROUS"   # <3 games, high variance, or insufficient data
    UNKNOWN = "UNKNOWN"       # No matchup data available


@dataclass
class MatchupWeightMath:
    """
    Explicit weighting math for a matchup adjustment.
    
    Shows exactly how the final adjustment was computed.
    """
    # Input values
    baseline_projection: float = 0.0
    matchup_sample_mean: float = 0.0
    league_mean: float = 0.0
    
    # Sample data
    games_vs_opponent: int = 0
    sample_std_dev: float = 0.0
    league_std_dev: float = 0.0
    
    # Bayesian shrinkage parameters
    prior_strength: float = 5.0      # Effective sample size of prior
    shrinkage_weight: float = 0.0    # 0=full prior, 1=full sample
    
    # Computed values
    shrunk_mean: float = 0.0
    adjustment_factor: float = 1.0
    confidence: float = 0.0
    
    # Final output
    adjusted_projection: float = 0.0
    
    def to_math_string(self) -> str:
        """
        Generate human-readable math breakdown.
        
        Example:
        ┌─ MATCHUP WEIGHTING MATH ─────────────────────┐
        │ Baseline: 22.5 pts                           │
        │ vs OPP: 18.2 pts (4 games, σ=3.1)           │
        │ League: 21.0 pts (σ=4.5)                    │
        │                                              │
        │ Shrinkage: w = 4/(4+5) = 0.44               │
        │ Shrunk μ = 0.44×18.2 + 0.56×21.0 = 19.8    │
        │ Factor = 19.8/22.5 = 0.88                   │
        │ Confidence = 0.55                            │
        │                                              │
        │ Adjusted: 22.5 × 0.88 = 19.8 pts           │
        └──────────────────────────────────────────────┘
        """
        lines = []
        lines.append("┌─ MATCHUP WEIGHTING MATH " + "─" * 30 + "┐")
        lines.append(f"│ Baseline: {self.baseline_projection:.1f}".ljust(55) + "│")
        lines.append(f"│ vs OPP: {self.matchup_sample_mean:.1f} ({self.games_vs_opponent} games, σ={self.sample_std_dev:.1f})".ljust(55) + "│")
        lines.append(f"│ League: {self.league_mean:.1f} (σ={self.league_std_dev:.1f})".ljust(55) + "│")
        lines.append("│" + " " * 55 + "│")
        
        w = self.shrinkage_weight
        one_minus_w = 1.0 - w
        lines.append(f"│ Shrinkage: w = {self.games_vs_opponent}/({self.games_vs_opponent}+{self.prior_strength:.0f}) = {w:.2f}".ljust(55) + "│")
        lines.append(f"│ Shrunk μ = {w:.2f}×{self.matchup_sample_mean:.1f} + {one_minus_w:.2f}×{self.league_mean:.1f} = {self.shrunk_mean:.1f}".ljust(55) + "│")
        lines.append(f"│ Factor = {self.shrunk_mean:.1f}/{self.baseline_projection:.1f} = {self.adjustment_factor:.2f}".ljust(55) + "│")
        lines.append(f"│ Confidence = {self.confidence:.2f}".ljust(55) + "│")
        lines.append("│" + " " * 55 + "│")
        lines.append(f"│ Adjusted: {self.baseline_projection:.1f} × {self.adjustment_factor:.2f} = {self.adjusted_projection:.1f}".ljust(55) + "│")
        lines.append("└" + "─" * 55 + "┘")
        
        return "\n".join(lines)
    
    def to_compact_string(self) -> str:
        """Single-line compact representation for reports."""
        if self.games_vs_opponent == 0:
            return "No matchup data"
        
        return (
            f"Matchup: {self.matchup_sample_mean:.1f}pts/{self.games_vs_opponent}g → "
            f"w={self.shrinkage_weight:.2f} → "
            f"{self.baseline_projection:.1f}×{self.adjustment_factor:.2f}={self.adjusted_projection:.1f}"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_projection": self.baseline_projection,
            "matchup_sample_mean": self.matchup_sample_mean,
            "league_mean": self.league_mean,
            "games_vs_opponent": self.games_vs_opponent,
            "sample_std_dev": self.sample_std_dev,
            "league_std_dev": self.league_std_dev,
            "prior_strength": self.prior_strength,
            "shrinkage_weight": self.shrinkage_weight,
            "shrunk_mean": self.shrunk_mean,
            "adjustment_factor": self.adjustment_factor,
            "confidence": self.confidence,
            "adjusted_projection": self.adjusted_projection,
        }


@dataclass  
class MatchupSafetyResult:
    """
    Complete matchup safety assessment with weighting math.
    
    Contains:
    1. SAFE/DANGEROUS flag
    2. Full weighting math breakdown
    3. Risk factors
    """
    # Core classification
    safety_level: MatchupSafetyLevel = MatchupSafetyLevel.UNKNOWN
    safety_flag: str = "UNKNOWN"  # User-facing string
    
    # Weighting math
    math: Optional[MatchupWeightMath] = None
    
    # Risk factors
    risk_factors: List[str] = field(default_factory=list)
    
    # Summary values
    games_vs_opponent: int = 0
    confidence: float = 0.0
    variance_ratio: float = 1.0  # Sample variance / league variance
    
    # Adjustment applied
    adjustment_applied: bool = False
    adjustment_factor: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "safety_level": self.safety_level.value,
            "safety_flag": self.safety_flag,
            "math": self.math.to_dict() if self.math else None,
            "risk_factors": self.risk_factors,
            "games_vs_opponent": self.games_vs_opponent,
            "confidence": self.confidence,
            "variance_ratio": self.variance_ratio,
            "adjustment_applied": self.adjustment_applied,
            "adjustment_factor": self.adjustment_factor,
        }
    
    def to_report_line(self) -> str:
        """Generate single report line with flag."""
        flag_emoji = {
            MatchupSafetyLevel.SAFE: "🟢",
            MatchupSafetyLevel.CAUTIOUS: "🟡",
            MatchupSafetyLevel.DANGEROUS: "🔴",
            MatchupSafetyLevel.UNKNOWN: "⚪",
        }
        
        emoji = flag_emoji.get(self.safety_level, "⚪")
        
        if self.games_vs_opponent == 0:
            return f"{emoji} {self.safety_flag}: No matchup history"
        
        factor_str = f"{self.adjustment_factor:.2f}x" if self.adjustment_applied else "N/A"
        return (
            f"{emoji} {self.safety_flag} | "
            f"{self.games_vs_opponent}g vs OPP | "
            f"Conf: {self.confidence:.0%} | "
            f"Factor: {factor_str}"
        )


def classify_matchup_safety(
    games_vs_opponent: int,
    confidence: float,
    variance_ratio: float,
    has_recent_game: bool = False,
) -> Tuple[MatchupSafetyLevel, List[str]]:
    """
    Classify matchup safety based on sample size and data quality.
    
    SAFE criteria (ALL must pass):
    - ≥5 games vs opponent
    - Confidence ≥ 0.5
    - Variance ratio < 2.0 (sample not wildly more variable than league)
    
    CAUTIOUS criteria:
    - 3-4 games vs opponent
    - Confidence ≥ 0.3
    - Variance ratio < 3.0
    
    DANGEROUS:
    - <3 games, or
    - Confidence < 0.3, or
    - Variance ratio ≥ 3.0
    
    Args:
        games_vs_opponent: Number of games played vs this opponent
        confidence: Bayesian confidence (0.0-1.0)
        variance_ratio: Sample variance / league variance
        has_recent_game: Whether there's a game in last 60 days
    
    Returns:
        (safety_level, risk_factors)
    """
    risk_factors = []
    
    # Check for DANGEROUS conditions first
    if games_vs_opponent < 3:
        risk_factors.append(f"Small sample: only {games_vs_opponent} games")
        
    if confidence < 0.3:
        risk_factors.append(f"Low confidence: {confidence:.0%}")
    
    if variance_ratio >= 3.0:
        risk_factors.append(f"High variance: {variance_ratio:.1f}x league avg")
    
    # Classify
    if len(risk_factors) > 0 and (games_vs_opponent < 3 or variance_ratio >= 3.0):
        return MatchupSafetyLevel.DANGEROUS, risk_factors
    
    if games_vs_opponent >= 5 and confidence >= 0.5 and variance_ratio < 2.0:
        # Check for staleness
        if not has_recent_game:
            risk_factors.append("No game vs OPP in last 60 days")
            return MatchupSafetyLevel.CAUTIOUS, risk_factors
        return MatchupSafetyLevel.SAFE, risk_factors
    
    if games_vs_opponent >= 3 and confidence >= 0.3 and variance_ratio < 3.0:
        return MatchupSafetyLevel.CAUTIOUS, risk_factors
    
    return MatchupSafetyLevel.DANGEROUS, risk_factors


def compute_matchup_safety(
    player_id: str,
    opponent_team: str,
    stat_type: str,
    baseline_projection: float,
    matchup_stats: Optional[Dict[str, Any]] = None,
    league_mean: float = 20.0,
    league_std: float = 5.0,
) -> MatchupSafetyResult:
    """
    Compute full matchup safety assessment with weighting math.
    
    This is the main entry point for matchup safety classification.
    
    Args:
        player_id: Player identifier
        opponent_team: Opponent team abbreviation
        stat_type: Stat category (PTS, REB, etc.)
        baseline_projection: Monte Carlo baseline projection
        matchup_stats: Pre-loaded matchup statistics (optional)
        league_mean: League average for this stat
        league_std: League standard deviation
    
    Returns:
        MatchupSafetyResult with safety flag and weighting math
    """
    result = MatchupSafetyResult()
    
    # If no matchup stats provided, try to load
    if matchup_stats is None:
        try:
            from features.nba.player_vs_opponent import MatchupIndex
            index = MatchupIndex()
            stats = index.get_stats(player_id, opponent_team, stat_type)
            if stats:
                matchup_stats = stats.to_dict()
        except Exception as e:
            logger.debug(f"Could not load matchup stats: {e}")
    
    # No data case
    if matchup_stats is None or matchup_stats.get("games_played", 0) == 0:
        result.safety_level = MatchupSafetyLevel.UNKNOWN
        result.safety_flag = "UNKNOWN"
        result.risk_factors = ["No matchup data available"]
        return result
    
    # Extract values
    games = matchup_stats.get("games_played", 0)
    sample_mean = matchup_stats.get("mean", 0.0)
    sample_std = matchup_stats.get("std_dev", 0.0)
    shrunk_mean = matchup_stats.get("shrunk_mean", sample_mean)
    shrinkage_weight = matchup_stats.get("shrinkage_weight", 0.0)
    confidence = matchup_stats.get("confidence", 0.0)
    
    # Compute variance ratio
    variance_ratio = 1.0
    if league_std > 0:
        variance_ratio = (sample_std ** 2) / (league_std ** 2) if sample_std > 0 else 1.0
    
    # Check recency
    from datetime import datetime, timedelta
    has_recent_game = False
    last_game_str = matchup_stats.get("last_game_date")
    if last_game_str:
        try:
            last_game = datetime.fromisoformat(last_game_str) if isinstance(last_game_str, str) else last_game_str
            has_recent_game = (datetime.now() - last_game) < timedelta(days=60)
        except Exception:
            pass
    
    # Classify safety
    safety_level, risk_factors = classify_matchup_safety(
        games_vs_opponent=games,
        confidence=confidence,
        variance_ratio=variance_ratio,
        has_recent_game=has_recent_game,
    )
    
    result.safety_level = safety_level
    result.safety_flag = safety_level.value
    result.risk_factors = risk_factors
    result.games_vs_opponent = games
    result.confidence = confidence
    result.variance_ratio = variance_ratio
    
    # Compute adjustment factor
    if baseline_projection > 0 and shrunk_mean > 0:
        result.adjustment_factor = shrunk_mean / baseline_projection
        result.adjustment_applied = safety_level != MatchupSafetyLevel.DANGEROUS
    
    # Build weighting math
    prior_strength = 5.0
    adjusted_projection = baseline_projection * result.adjustment_factor if result.adjustment_applied else baseline_projection
    
    result.math = MatchupWeightMath(
        baseline_projection=baseline_projection,
        matchup_sample_mean=sample_mean,
        league_mean=league_mean,
        games_vs_opponent=games,
        sample_std_dev=sample_std,
        league_std_dev=league_std,
        prior_strength=prior_strength,
        shrinkage_weight=shrinkage_weight,
        shrunk_mean=shrunk_mean,
        adjustment_factor=result.adjustment_factor,
        confidence=confidence,
        adjusted_projection=adjusted_projection,
    )
    
    return result


def enrich_pick_with_matchup_safety(pick: Dict[str, Any], league_stats: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Enrich a pick dictionary with matchup safety data.
    
    Adds:
    - matchup_safety_flag: SAFE/CAUTIOUS/DANGEROUS/UNKNOWN
    - matchup_weighting_math: Full math breakdown
    - matchup_risk_factors: List of risk factors
    
    Args:
        pick: Pick dictionary with player, opponent, stat_type, etc.
        league_stats: Optional dict of league averages by stat type
    
    Returns:
        Enriched pick dictionary
    """
    player = pick.get("player", "")
    player_id = pick.get("player_id", player)
    opponent = pick.get("opponent", pick.get("matchup", ""))
    stat_type = pick.get("stat_type", pick.get("market", "PTS"))
    baseline = pick.get("projection", pick.get("mean", pick.get("line", 20.0)))
    
    # Get league stats
    default_league_stats = {
        "PTS": (20.0, 8.0),
        "REB": (5.0, 3.0),
        "AST": (4.0, 3.0),
        "BLK": (0.5, 0.6),
        "STL": (1.0, 0.7),
        "3PM": (2.0, 1.5),
        "PRA": (30.0, 10.0),
        "PR": (25.0, 9.0),
        "PA": (24.0, 9.0),
        "RA": (9.0, 4.0),
    }
    
    stat_key = stat_type.upper()
    if league_stats and stat_key in league_stats:
        league_mean, league_std = league_stats[stat_key]
    elif stat_key in default_league_stats:
        league_mean, league_std = default_league_stats[stat_key]
    else:
        league_mean, league_std = 20.0, 5.0
    
    # Check for pre-loaded matchup stats in pick
    matchup_stats = pick.get("matchup_stats", pick.get("vs_opponent_stats"))
    
    # Compute safety
    safety_result = compute_matchup_safety(
        player_id=player_id,
        opponent_team=opponent,
        stat_type=stat_type,
        baseline_projection=baseline,
        matchup_stats=matchup_stats,
        league_mean=league_mean,
        league_std=league_std,
    )
    
    # Enrich pick
    pick["matchup_safety_flag"] = safety_result.safety_flag
    pick["matchup_safety_level"] = safety_result.safety_level.value
    pick["matchup_risk_factors"] = safety_result.risk_factors
    pick["matchup_confidence"] = safety_result.confidence
    pick["matchup_games_vs"] = safety_result.games_vs_opponent
    pick["matchup_adjustment_applied"] = safety_result.adjustment_applied
    pick["matchup_adjustment_factor"] = safety_result.adjustment_factor
    
    if safety_result.math:
        pick["matchup_weighting_math"] = safety_result.math.to_dict()
        pick["matchup_math_compact"] = safety_result.math.to_compact_string()
        pick["matchup_math_full"] = safety_result.math.to_math_string()
    
    pick["matchup_report_line"] = safety_result.to_report_line()
    
    return pick


# ============================================================================
# PROBABILITY ENGINE INTEGRATION
# ============================================================================

def integrate_matchup_into_probability(
    mu: float,
    sigma: float,
    player_id: str,
    opponent: str,
    stat_type: str,
    matchup_stats: Optional[Dict[str, Any]] = None,
    league_mean: float = 20.0,
    league_std: float = 5.0,
    force_apply: bool = False,
) -> Tuple[float, float, MatchupSafetyResult]:
    """
    Integrate matchup memory directly into probability engine.
    
    This is the REQUIRED entry point for probability calculations.
    Users cannot bypass this without explicitly setting force_apply=True.
    
    SAFETY ENFORCEMENT:
    - DANGEROUS matchups are NEVER applied (unless force_apply=True)
    - CAUTIOUS matchups are applied with 50% weight
    - SAFE matchups are applied fully
    
    Args:
        mu: Baseline mean (Monte Carlo)
        sigma: Baseline standard deviation
        player_id: Player identifier
        opponent: Opponent team
        stat_type: Stat category
        matchup_stats: Pre-loaded matchup stats
        league_mean: League average
        league_std: League std dev
        force_apply: Override safety checks (DANGEROUS)
    
    Returns:
        (adjusted_mu, adjusted_sigma, safety_result)
    """
    # Compute safety assessment
    safety_result = compute_matchup_safety(
        player_id=player_id,
        opponent_team=opponent,
        stat_type=stat_type,
        baseline_projection=mu,
        matchup_stats=matchup_stats,
        league_mean=league_mean,
        league_std=league_std,
    )
    
    # Apply safety rules
    if safety_result.safety_level == MatchupSafetyLevel.DANGEROUS:
        if force_apply:
            logger.warning(f"Force applying DANGEROUS matchup adjustment for {player_id} vs {opponent}")
        else:
            # Do not apply adjustment
            safety_result.adjustment_applied = False
            return mu, sigma, safety_result
    
    if safety_result.safety_level == MatchupSafetyLevel.UNKNOWN:
        return mu, sigma, safety_result
    
    # Compute adjustment
    factor = safety_result.adjustment_factor
    
    # For CAUTIOUS, reduce the adjustment magnitude by 50%
    if safety_result.safety_level == MatchupSafetyLevel.CAUTIOUS:
        # Move factor toward 1.0 by 50%
        factor = 1.0 + (factor - 1.0) * 0.5
    
    # Apply to mu (keep sigma unchanged for now)
    adjusted_mu = mu * factor
    adjusted_sigma = sigma  # Could adjust based on matchup variance
    
    # Update safety result with actual applied factor
    safety_result.adjustment_factor = factor
    safety_result.adjustment_applied = True
    
    if safety_result.math:
        safety_result.math.adjustment_factor = factor
        safety_result.math.adjusted_projection = adjusted_mu
    
    return adjusted_mu, adjusted_sigma, safety_result
