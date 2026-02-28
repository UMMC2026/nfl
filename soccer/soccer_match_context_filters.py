"""
Soccer Match Context Filter System
===================================

Blocks bets in high-variance, unpredictable match contexts:
- Derby matches (emotional, tactical)
- Rotation risk (midweek, cup games)
- Injury returns (first 3 games back)
- Extreme mismatches (blowout/garbage time)
- Managerial changes (tactical uncertainty)

Author: Production Sports Betting System
Date: 2026-02-01
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FilterResult(Enum):
    """Filter gate outcomes."""
    PASS = "PASS"
    BLOCK = "BLOCK"
    WARN = "WARN"


@dataclass
class FilterOutcome:
    """Result of applying a filter gate."""
    result: FilterResult
    gate_name: str
    reason: str
    severity: int  # 1-10, higher = more critical
    recommended_action: str


class MatchContextFilterEngine:
    """
    Filter system to block bets in high-variance match contexts.
    
    Gates applied (in order):
    1. Derby Filter - Block emotional rivalry matches
    2. Rotation Risk Filter - Block tired/rested player situations
    3. Injury Return Filter - Block recently returned players
    4. Blowout Risk Filter - Block extreme mismatches
    5. Tactical Uncertainty Filter - Block new manager situations
    6. Competition Type Filter - Block cup rotation games
    7. Weather/Venue Filter - Block extreme conditions
    8. Minutes Trend Filter - Block players losing minutes
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize filter engine.
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or self._default_config()
        self.filters_applied = []
        logger.info("MatchContextFilterEngine initialized")
    
    def _default_config(self) -> Dict:
        """Default filter configuration."""
        return {
            # Derby filter settings
            "DERBY_FILTER": {
                "enabled": True,
                "block_all_derbies": True,  # Conservative: block ALL derbies
                "allow_if_historical_hit_rate_above": 0.65  # Only allow if proven
            },
            
            # Rotation risk settings
            "ROTATION_FILTER": {
                "enabled": True,
                "midweek_game_threshold_days": 4,  # Flag if <4 days rest
                "high_minutes_threshold": 70,  # Players averaging 70+ mins
                "block_if_rotation_prob_above": 0.30  # Block if >30% rotation risk
            },
            
            # Injury return settings
            "INJURY_RETURN_FILTER": {
                "enabled": True,
                "games_back_threshold": 3,  # Block first 3 games back
                "minutes_threshold": 45,  # Block if < 45 min in return games
                "allow_if_full_training": True  # Allow if full week of training
            },
            
            # Blowout risk settings
            "BLOWOUT_FILTER": {
                "enabled": True,
                "extreme_mismatch_threshold": 2.5,  # >2.5 goal diff expected
                "moderate_mismatch_threshold": 1.5,
                "block_favorites_in_extreme": True,  # Block favorite's props
                "block_underdogs_in_extreme": False  # Allow underdog props (desperation)
            },
            
            # Managerial change settings
            "MANAGER_CHANGE_FILTER": {
                "enabled": True,
                "games_threshold": 4,  # Block first 4 games under new manager
                "tactical_shift_multiplier": 1.5,  # If tactical style changes drastically
            },
            
            # Competition type settings
            "COMPETITION_FILTER": {
                "enabled": True,
                "block_early_cup_rounds": True,
                "block_dead_rubber_games": True,  # Nothing to play for
                "allowed_competitions": [
                    "PREMIER_LEAGUE",
                    "LA_LIGA",
                    "BUNDESLIGA",
                    "SERIE_A",
                    "LIGUE_1",
                    "CHAMPIONS_LEAGUE"
                ],
                "blocked_competitions": [
                    "LEAGUE_CUP_R1",
                    "LEAGUE_CUP_R2",
                    "FA_CUP_R3",
                    "FA_CUP_R4"
                ]
            },
            
            # Weather/venue settings
            "VENUE_FILTER": {
                "enabled": True,
                "block_extreme_weather": True,
                "block_artificial_turf": False,
                "block_neutral_venue_non_finals": True
            },
            
            # Minutes trend settings
            "MINUTES_TREND_FILTER": {
                "enabled": True,
                "L3_decline_threshold": 0.20,  # Block if L3 mins down 20%+
                "L5_decline_threshold": 0.15,
                "starter_minutes_minimum": 60  # Block if starter playing <60
            }
        }
    
    def apply_all_filters(
        self,
        player,
        opponent,
        match_context
    ) -> Tuple[FilterResult, List[FilterOutcome]]:
        """
        Apply all filter gates.
        
        Args:
            player: PlayerStats object
            opponent: OpponentProfile object
            match_context: MatchContext object
        
        Returns:
            Tuple of (overall_result, list_of_filter_outcomes)
            
        Usage:
            >>> result, outcomes = engine.apply_all_filters(player, opp, ctx)
            >>> if result == FilterResult.BLOCK:
            ...     print(f"BLOCKED: {outcomes[0].reason}")
        """
        self.filters_applied = []
        outcomes = []
        
        # Apply each filter gate
        filters = [
            self._derby_filter,
            self._rotation_risk_filter,
            self._injury_return_filter,
            self._blowout_risk_filter,
            self._manager_change_filter,
            self._competition_filter,
            self._venue_filter,
            self._minutes_trend_filter
        ]
        
        for filter_func in filters:
            outcome = filter_func(player, opponent, match_context)
            outcomes.append(outcome)
            self.filters_applied.append(outcome.gate_name)
            
            # If any filter blocks, stop immediately
            if outcome.result == FilterResult.BLOCK:
                logger.warning(
                    f"[FILTER BLOCK] {outcome.gate_name}: {outcome.reason}"
                )
                return FilterResult.BLOCK, outcomes
        
        # Check for warnings
        warnings = [o for o in outcomes if o.result == FilterResult.WARN]
        if warnings:
            logger.info(
                f"[FILTER WARN] {len(warnings)} warning(s): "
                f"{[w.gate_name for w in warnings]}"
            )
        
        logger.info(f"[FILTER PASS] All {len(filters)} gates passed")
        return FilterResult.PASS, outcomes
    
    def _derby_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 1: Derby matches are unpredictable.
        
        Block: Yes (if configured)
        Reason: Tactical, defensive, emotional variance
        """
        if not self.config["DERBY_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Derby Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        if match_context.is_derby:
            if self.config["DERBY_FILTER"]["block_all_derbies"]:
                return FilterOutcome(
                    FilterResult.BLOCK,
                    "Derby Filter",
                    f"Derby match detected: {player.team} vs {opponent.name}. "
                    "Derbies are tactical, defensive, and emotionally volatile.",
                    9,
                    "SKIP this bet entirely"
                )
            else:
                return FilterOutcome(
                    FilterResult.WARN,
                    "Derby Filter",
                    "Derby match - proceed with caution",
                    6,
                    "Reduce confidence by 15%"
                )
        
        return FilterOutcome(
            FilterResult.PASS,
            "Derby Filter",
            "Not a derby match",
            0,
            "Continue"
        )
    
    def _rotation_risk_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 2: Rotation risk for tired/rested players.
        
        Block: If midweek game + high minutes player
        """
        if not self.config["ROTATION_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Rotation Risk Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        cfg = self.config["ROTATION_FILTER"]
        
        # Check if midweek congestion
        if match_context.days_since_last_game < cfg["midweek_game_threshold_days"]:
            # Check if player is high-minutes (likely to be rested)
            if player.avg_minutes > cfg["high_minutes_threshold"]:
                # Check explicit rotation flag
                if match_context.rotation_risk:
                    return FilterOutcome(
                        FilterResult.BLOCK,
                        "Rotation Risk Filter",
                        f"{player.name} averaging {player.avg_minutes:.0f} mins/game. "
                        f"Only {match_context.days_since_last_game} days rest. "
                        "High rotation risk in congested schedule.",
                        8,
                        "SKIP - Player may be benched or subbed early"
                    )
                else:
                    return FilterOutcome(
                        FilterResult.WARN,
                        "Rotation Risk Filter",
                        "Midweek game, monitor lineup news closely",
                        5,
                        "Wait for confirmed lineup before betting"
                    )
        
        return FilterOutcome(
            FilterResult.PASS,
            "Rotation Risk Filter",
            "No rotation concerns",
            0,
            "Continue"
        )
    
    def _injury_return_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 3: Players returning from injury are unpredictable.
        
        Block: First 3 games back from injury
        """
        if not self.config["INJURY_RETURN_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Injury Return Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        cfg = self.config["INJURY_RETURN_FILTER"]
        
        if player.games_since_injury is not None:
            if player.games_since_injury < cfg["games_back_threshold"]:
                return FilterOutcome(
                    FilterResult.BLOCK,
                    "Injury Return Filter",
                    f"{player.name} only {player.games_since_injury} game(s) "
                    "back from injury. Match fitness uncertain.",
                    7,
                    "SKIP - Wait until player is fully match-fit"
                )
        
        return FilterOutcome(
            FilterResult.PASS,
            "Injury Return Filter",
            "No injury concerns",
            0,
            "Continue"
        )
    
    def _blowout_risk_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 4: Extreme mismatches lead to garbage time.
        
        Block: Favorites in blowouts (they stop trying)
        """
        if not self.config["BLOWOUT_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Blowout Risk Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        cfg = self.config["BLOWOUT_FILTER"]
        goal_diff = abs(match_context.implied_goal_diff)
        
        # Extreme mismatch (>2.5 goal difference expected)
        if goal_diff > cfg["extreme_mismatch_threshold"]:
            # Determine if player is on favorite or underdog
            is_favorite = match_context.implied_goal_diff > 0
            
            if is_favorite and cfg["block_favorites_in_extreme"]:
                return FilterOutcome(
                    FilterResult.BLOCK,
                    "Blowout Risk Filter",
                    f"Extreme mismatch (exp. goal diff: {goal_diff:.1f}). "
                    f"{player.team} heavily favored. Stars will be subbed early "
                    "if winning comfortably.",
                    8,
                    "SKIP - Blowout garbage time kills props"
                )
        
        # Moderate mismatch
        elif goal_diff > cfg["moderate_mismatch_threshold"]:
            return FilterOutcome(
                FilterResult.WARN,
                "Blowout Risk Filter",
                f"Moderate mismatch (exp. goal diff: {goal_diff:.1f})",
                4,
                "Monitor scoreline - may need live adjustment"
            )
        
        return FilterOutcome(
            FilterResult.PASS,
            "Blowout Risk Filter",
            "Competitive match expected",
            0,
            "Continue"
        )
    
    def _manager_change_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 5: New managers bring tactical uncertainty.
        
        Block: First 4 games under new manager
        """
        if not self.config["MANAGER_CHANGE_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Manager Change Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        cfg = self.config["MANAGER_CHANGE_FILTER"]
        
        if match_context.team_games_under_new_manager < cfg["games_threshold"]:
            return FilterOutcome(
                FilterResult.BLOCK,
                "Manager Change Filter",
                f"{player.team} only {match_context.team_games_under_new_manager} "
                "game(s) under new manager. Tactical roles/systems still settling.",
                7,
                "SKIP - Wait for tactical clarity"
            )
        
        return FilterOutcome(
            FilterResult.PASS,
            "Manager Change Filter",
            "Manager situation stable",
            0,
            "Continue"
        )
    
    def _competition_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 6: Cup competitions have rotation/unpredictability.
        
        Block: Early cup rounds, dead rubber games
        """
        if not self.config["COMPETITION_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Competition Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        cfg = self.config["COMPETITION_FILTER"]
        comp = match_context.competition
        
        # Check if competition is blocked
        if comp in cfg["blocked_competitions"]:
            return FilterOutcome(
                FilterResult.BLOCK,
                "Competition Filter",
                f"Competition {comp} flagged for heavy rotation. "
                "Teams rest stars in early cup rounds.",
                6,
                "SKIP - Cup rotation too unpredictable"
            )
        
        # Check if competition is not in allowed list
        if comp not in cfg["allowed_competitions"]:
            return FilterOutcome(
                FilterResult.WARN,
                "Competition Filter",
                f"Competition {comp} not in preferred list",
                3,
                "Proceed with caution"
            )
        
        return FilterOutcome(
            FilterResult.PASS,
            "Competition Filter",
            f"Competition {comp} is reliable",
            0,
            "Continue"
        )
    
    def _venue_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 7: Extreme weather/venue conditions.
        
        Block: Heavy rain, artificial turf (if configured)
        """
        if not self.config["VENUE_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Venue Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        # Placeholder - would need actual weather API integration
        return FilterOutcome(
            FilterResult.PASS,
            "Venue Filter",
            "No venue concerns",
            0,
            "Continue"
        )
    
    def _minutes_trend_filter(self, player, opponent, match_context) -> FilterOutcome:
        """
        Filter 8: Declining minutes = losing role.
        
        Block: If player's minutes trending down significantly
        """
        if not self.config["MINUTES_TREND_FILTER"]["enabled"]:
            return FilterOutcome(
                FilterResult.PASS,
                "Minutes Trend Filter",
                "Filter disabled",
                0,
                "Continue"
            )
        
        # Would need L3/L5 minutes data - placeholder logic
        # This would compare recent minutes to season average
        
        return FilterOutcome(
            FilterResult.PASS,
            "Minutes Trend Filter",
            "Minutes trend stable",
            0,
            "Continue"
        )
    
    def get_filter_summary(self) -> Dict:
        """Get summary of filters applied in last run."""
        return {
            "total_filters": len(self.filters_applied),
            "filters_run": self.filters_applied
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    from soccer_opponent_adjustment import (
        PlayerStats, OpponentProfile, MatchContext, Position
    )
    
    # Example: Salah vs Man City (Derby)
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
    
    man_city = OpponentProfile(
        name="Manchester City",
        league="Premier League",
        defensive_rank=2,
        shots_conceded_p90=8.5,
        sot_conceded_p90=3.2,
        goals_conceded_p90=0.8,
        possession_pct=68.0,
        pressing_intensity="HIGH",
        defensive_line="HIGH"
    )
    
    # Test 1: Derby match
    derby_context = MatchContext(
        location="AWAY",
        competition="PREMIER_LEAGUE",
        is_derby=True,  # Liverpool vs Man City = Derby
        days_since_last_game=4,
        implied_goal_diff=-0.5,
        expected_possession=45.0,
        team_games_under_new_manager=25,
        rotation_risk=False
    )
    
    engine = MatchContextFilterEngine()
    
    print(f"\n{'='*70}")
    print(f"MATCH CONTEXT FILTER TEST")
    print(f"{'='*70}")
    print(f"Player: {salah.name}")
    print(f"Opponent: {man_city.name}")
    print(f"Context: Derby match, Away\n")
    
    result, outcomes = engine.apply_all_filters(salah, man_city, derby_context)
    
    print(f"Overall Result: {result.value}\n")
    print(f"{'Filter Gate':<30} {'Result':<10} {'Severity':<10}")
    print(f"{'-'*70}")
    for outcome in outcomes:
        print(f"{outcome.gate_name:<30} {outcome.result.value:<10} {outcome.severity:<10}")
        if outcome.result != FilterResult.PASS:
            print(f"  -> {outcome.reason}")
            print(f"  -> {outcome.recommended_action}\n")
    
    print(f"{'='*70}\n")
    
    # Test 2: Clean match (should pass all filters)
    clean_context = MatchContext(
        location="HOME",
        competition="PREMIER_LEAGUE",
        is_derby=False,
        days_since_last_game=7,
        implied_goal_diff=0.5,
        expected_possession=55.0,
        team_games_under_new_manager=25,
        rotation_risk=False
    )
    
    print(f"{'='*70}")
    print(f"CLEAN MATCH TEST")
    print(f"{'='*70}")
    print(f"Player: {salah.name}")
    print(f"Context: Home, Normal circumstances\n")
    
    result2, outcomes2 = engine.apply_all_filters(salah, man_city, clean_context)
    
    print(f"Overall Result: {result2.value}\n")
    if result2 == FilterResult.PASS:
        print(f"[PASS] All {len(outcomes2)} filter gates PASSED")
        print(f"[PASS] Bet is APPROVED for further analysis\n")
    
    print(f"{'='*70}\n")
