"""
Soccer Betting Pipeline Integration
====================================

Complete end-to-end pipeline combining:
1. Match context filtering (8 gates)
2. Opponent-adjusted lambda calculation
3. Distribution-based probability calculation
4. Market efficiency adjustments
5. Tier assignment and recommendation
6. Calibration logging

Author: Production Sports Betting System
Date: 2026-02-01
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from soccer_opponent_adjustment import (
    OpponentAdjustmentEngine,
    PlayerStats,
    OpponentProfile,
    MatchContext,
    StatType,
    Position
)
from soccer_match_context_filters import (
    MatchContextFilterEngine,
    FilterResult
)
from soccer_distributions import (
    SoccerDistributions,
    DistributionType
)
from soccer_calibration_validator import (
    CalibrationValidator
)

logger = logging.getLogger(__name__)


@dataclass
class BetRecommendation:
    """Complete bet recommendation with all analysis."""
    player_name: str
    opponent: str
    stat_type: str
    line: float
    direction: str
    
    # Analysis results
    raw_probability: float
    adjusted_probability: float
    tier: str
    recommendation: str  # "BET", "MONITOR", "SKIP", "BLOCKED"
    
    # Breakdown
    lambda_breakdown: Dict
    filter_result: str
    filter_reason: Optional[str]
    
    # Metadata
    book: str
    timestamp: datetime


class SoccerBettingPipeline:
    """
    Complete soccer betting analysis pipeline.
    
    Pipeline Steps:
    1. Apply match context filters (8 gates)
    2. Calculate opponent-adjusted lambda
    3. Select appropriate distribution
    4. Calculate probability
    5. Apply market efficiency penalty
    6. Assign confidence tier
    7. Log to calibration validator
    8. Return recommendation
    """
    
    def __init__(
        self,
        enable_calibration: bool = True,
        strict_filters: bool = True
    ):
        """
        Initialize pipeline components.
        
        Args:
            enable_calibration: Whether to log predictions for calibration
            strict_filters: Whether to use strict filter settings
        """
        self.filter_engine = MatchContextFilterEngine()
        self.adjustment_engine = OpponentAdjustmentEngine()
        self.distributions = SoccerDistributions()
        
        if enable_calibration:
            self.calibration = CalibrationValidator()
        else:
            self.calibration = None
        
        self.strict_filters = strict_filters
        
        # Tier thresholds (after all adjustments)
        self.tier_thresholds = {
            "ELITE": 0.78,    # 78%+ -> BET
            "STRONG": 0.72,   # 72-78% -> MONITOR
            "LEAN": 0.65,     # 65-72% -> SKIP
            "AVOID": 0.0      # <65% -> SKIP
        }
        
        # Market efficiency penalties
        self.market_penalties = {
            "PRIZEPICKS": 0.02,     # 2% penalty (soft book)
            "UNDERDOG": 0.02,       # 2% penalty (soft book)
            "DRAFTKINGS": 0.04,     # 4% penalty (sharper book)
            "FANDUEL": 0.04,        # 4% penalty (sharper book)
            "BETMGM": 0.03,         # 3% penalty
            "DEFAULT": 0.03
        }
        
        # Probability caps by stat type (prevents overconfidence)
        self.probability_caps = {
            StatType.SHOTS: 0.75,
            StatType.SOT: 0.72,
            StatType.GOALS: 0.70,
            StatType.ASSISTS: 0.70,
            StatType.PASSES: 0.78,
            StatType.TACKLES: 0.72,
            "DEFAULT": 0.75
        }
        
        logger.info("SoccerBettingPipeline initialized")
    
    def analyze_bet(
        self,
        player: PlayerStats,
        opponent: OpponentProfile,
        match_context: MatchContext,
        stat_type: StatType,
        line: float,
        direction: str,
        book: str = "PRIZEPICKS"
    ) -> Dict:
        """
        Complete bet analysis pipeline.
        
        Args:
            player: Player statistics
            opponent: Opponent profile
            match_context: Match context
            stat_type: Stat type to analyze
            line: Betting line
            direction: "OVER" or "UNDER"
            book: Sportsbook name
        
        Returns:
            Dict with recommendation and full analysis
        """
        timestamp = datetime.now()
        
        # Step 1: Apply filters
        filter_result, filter_outcomes = self.filter_engine.apply_all_filters(
            player, opponent, match_context
        )
        
        if filter_result == FilterResult.BLOCK:
            # Find the blocking filter
            blocker = next(
                (o for o in filter_outcomes if o.result == FilterResult.BLOCK),
                None
            )
            
            return {
                "player_name": player.name,
                "opponent": opponent.name,
                "stat_type": stat_type.value,
                "line": line,
                "direction": direction,
                "recommendation": "BLOCKED",
                "tier": "BLOCKED",
                "probability": 0.0,
                "filter_result": "BLOCKED",
                "filter_reason": blocker.reason if blocker else "Unknown",
                "book": book,
                "timestamp": timestamp.isoformat()
            }
        
        # Step 2: Calculate opponent-adjusted lambda
        adjusted_lambda, lambda_breakdown = self.adjustment_engine.calculate_adjusted_lambda(
            player, opponent, match_context, stat_type
        )
        
        # Step 3: Select distribution and calculate raw probability
        dist_type, dist_params = self.distributions.select_distribution(
            stat_type=stat_type.value,
            player_position=player.position.name,
            mean=adjusted_lambda,
            std=player.season_std
        )
        
        raw_probability = self._calculate_probability(
            dist_type, dist_params, line, direction
        )
        
        # Step 4: Apply market efficiency penalty
        market_penalty = self.market_penalties.get(
            book.upper(), 
            self.market_penalties["DEFAULT"]
        )
        adjusted_probability = raw_probability - market_penalty
        
        # Step 5: Apply probability cap
        prob_cap = self.probability_caps.get(
            stat_type,
            self.probability_caps["DEFAULT"]
        )
        adjusted_probability = min(adjusted_probability, prob_cap)
        
        # Ensure valid range
        adjusted_probability = max(0.0, min(1.0, adjusted_probability))
        
        # Step 6: Assign tier and recommendation
        tier, recommendation = self._assign_tier(adjusted_probability)
        
        # Step 7: Log to calibration (if enabled and actionable)
        if self.calibration and tier in ["ELITE", "STRONG"]:
            self.calibration.add_prediction(
                player_name=player.name,
                opponent=opponent.name,
                stat_type=stat_type.value,
                line=line,
                direction=direction,
                predicted_prob=adjusted_probability,
                tier=tier,
                book=book,
                competition=match_context.competition
            )
        
        # Build result
        result = {
            "player_name": player.name,
            "opponent": opponent.name,
            "stat_type": stat_type.value,
            "line": line,
            "direction": direction,
            "recommendation": recommendation,
            "tier": tier,
            "probability": round(adjusted_probability, 4),
            "raw_probability": round(raw_probability, 4),
            "market_penalty": market_penalty,
            "lambda_adjusted": round(adjusted_lambda, 2),
            "lambda_breakdown": lambda_breakdown,
            "distribution_used": dist_type.value,
            "filter_result": filter_result.value,
            "filter_warnings": [
                o.reason for o in filter_outcomes 
                if o.result == FilterResult.WARN
            ],
            "book": book,
            "timestamp": timestamp.isoformat()
        }
        
        # Log result
        logger.info(
            f"[ANALYSIS] {player.name} {stat_type.value} {direction} {line}: "
            f"{adjusted_probability:.1%} ({tier}) -> {recommendation}"
        )
        
        return result
    
    def _calculate_probability(
        self,
        dist_type: DistributionType,
        params: Dict,
        line: float,
        direction: str
    ) -> float:
        """Calculate probability using selected distribution."""
        
        if dist_type == DistributionType.POISSON:
            return self.distributions.poisson_probability(
                lambda_param=params["lambda_param"],
                line=line,
                direction=direction
            )
        
        elif dist_type == DistributionType.ZERO_INFLATED_POISSON:
            return self.distributions.zero_inflated_poisson(
                lambda_param=params["lambda_param"],
                line=line,
                zero_inflation=params.get("zero_inflation", 0.30),
                direction=direction
            )
        
        elif dist_type == DistributionType.NORMAL:
            return self.distributions.normal_probability(
                mean=params["mean"],
                std=params["std"],
                line=line,
                direction=direction
            )
        
        elif dist_type == DistributionType.BINOMIAL:
            return self.distributions.binomial_probability(
                n_trials=params["n_trials"],
                success_rate=params["success_rate"],
                line=line,
                direction=direction
            )
        
        else:
            logger.error(f"Unknown distribution type: {dist_type}")
            return 0.5
    
    def _assign_tier(self, probability: float) -> Tuple[str, str]:
        """
        Assign confidence tier and recommendation.
        
        Returns:
            Tuple of (tier, recommendation)
        """
        if probability >= self.tier_thresholds["ELITE"]:
            return "ELITE", "BET"
        elif probability >= self.tier_thresholds["STRONG"]:
            return "STRONG", "MONITOR"
        elif probability >= self.tier_thresholds["LEAN"]:
            return "LEAN", "SKIP"
        else:
            return "AVOID", "SKIP"
    
    def batch_analyze(
        self,
        bets: list,
        book: str = "PRIZEPICKS"
    ) -> list:
        """
        Analyze multiple bets.
        
        Args:
            bets: List of (player, opponent, context, stat_type, line, direction) tuples
            book: Sportsbook name
        
        Returns:
            List of analysis results
        """
        results = []
        for player, opponent, context, stat_type, line, direction in bets:
            result = self.analyze_bet(
                player=player,
                opponent=opponent,
                match_context=context,
                stat_type=stat_type,
                line=line,
                direction=direction,
                book=book
            )
            results.append(result)
        
        return results
    
    def get_calibration_report(self) -> Optional[Dict]:
        """Get calibration report if enabled."""
        if self.calibration:
            return self.calibration.generate_calibration_report()
        return None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize pipeline
    pipeline = SoccerBettingPipeline(enable_calibration=True)
    
    print(f"\n{'='*70}")
    print(f"SOCCER BETTING PIPELINE INTEGRATION TEST")
    print(f"{'='*70}\n")
    
    # Test Case 1: Standard bet (should pass filters)
    salah = PlayerStats(
        name="Mohamed Salah",
        team="Liverpool",
        position=Position.W,
        season_avg=3.8,
        season_std=1.9,
        games_played=25,
        L5_avg=4.2,
        L5_games=5,
        home_avg=4.5,
        away_avg=3.2,
        home_games=12,
        away_games=13,
        avg_minutes=85.0,
        games_since_injury=None
    )
    
    burnley = OpponentProfile(
        name="Burnley",
        league="Premier League",
        defensive_rank=305,  # Weak defense
        shots_conceded_p90=16.5,
        sot_conceded_p90=6.2,
        goals_conceded_p90=1.8,
        possession_pct=38.0,
        pressing_intensity="LOW",
        defensive_line="LOW"
    )
    
    home_context = MatchContext(
        location="HOME",
        competition="PREMIER_LEAGUE",
        is_derby=False,
        days_since_last_game=7,
        implied_goal_diff=1.5,
        expected_possession=65.0,
        team_games_under_new_manager=25,
        rotation_risk=False
    )
    
    print("Test 1: Salah vs Burnley (Home, Weak Defense)")
    print("-" * 70)
    result1 = pipeline.analyze_bet(
        player=salah,
        opponent=burnley,
        match_context=home_context,
        stat_type=StatType.SHOTS,
        line=3.5,
        direction="OVER",
        book="PRIZEPICKS"
    )
    
    print(f"Player: {result1['player_name']}")
    print(f"Opponent: {result1['opponent']}")
    print(f"Bet: {result1['stat_type']} {result1['direction']} {result1['line']}")
    print(f"Adjusted Lambda: {result1['lambda_adjusted']}")
    print(f"Raw Probability: {result1['raw_probability']:.1%}")
    print(f"Final Probability: {result1['probability']:.1%}")
    print(f"Tier: {result1['tier']}")
    print(f"Recommendation: {result1['recommendation']}")
    print(f"Distribution: {result1['distribution_used']}")
    print()
    
    # Test Case 2: Derby match (should be blocked)
    man_city = OpponentProfile(
        name="Manchester City",
        league="Premier League",
        defensive_rank=2,  # Elite defense
        shots_conceded_p90=8.5,
        sot_conceded_p90=3.2,
        goals_conceded_p90=0.8,
        possession_pct=68.0,
        pressing_intensity="HIGH",
        defensive_line="HIGH"
    )
    
    derby_context = MatchContext(
        location="AWAY",
        competition="PREMIER_LEAGUE",
        is_derby=True,  # DERBY!
        days_since_last_game=4,
        implied_goal_diff=-0.5,
        expected_possession=45.0,
        team_games_under_new_manager=25,
        rotation_risk=False
    )
    
    print("Test 2: Salah vs Man City (Derby - Should Block)")
    print("-" * 70)
    result2 = pipeline.analyze_bet(
        player=salah,
        opponent=man_city,
        match_context=derby_context,
        stat_type=StatType.SHOTS,
        line=3.5,
        direction="OVER",
        book="PRIZEPICKS"
    )
    
    print(f"Recommendation: {result2['recommendation']}")
    print(f"Filter Result: {result2['filter_result']}")
    if result2.get('filter_reason'):
        print(f"Reason: {result2['filter_reason']}")
    print()
    
    # Test Case 3: Defender shots (should use ZIP distribution)
    defender = PlayerStats(
        name="Van Dijk",
        team="Liverpool",
        position=Position.CB,
        season_avg=0.4,
        season_std=0.6,
        games_played=25,
        L5_avg=0.2,
        L5_games=5,
        home_avg=0.5,
        away_avg=0.3,
        home_games=12,
        away_games=13,
        avg_minutes=90.0,
        games_since_injury=None
    )
    
    print("Test 3: Van Dijk Shots (Defender - Should Use ZIP)")
    print("-" * 70)
    result3 = pipeline.analyze_bet(
        player=defender,
        opponent=burnley,
        match_context=home_context,
        stat_type=StatType.SHOTS,
        line=0.5,
        direction="OVER",
        book="UNDERDOG"
    )
    
    print(f"Player: {result3['player_name']} ({defender.position.value})")
    print(f"Adjusted Lambda: {result3['lambda_adjusted']}")
    print(f"Distribution: {result3['distribution_used']}")
    print(f"Probability: {result3['probability']:.1%}")
    print(f"Tier: {result3['tier']}")
    print(f"Recommendation: {result3['recommendation']}")
    print()
    
    print(f"{'='*70}")
    print(f"PIPELINE TESTS COMPLETE")
    print(f"{'='*70}\n")
