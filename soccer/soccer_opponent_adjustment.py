"""
Soccer Opponent-Adjusted Lambda Calculator
==========================================

Adjusts player baseline statistics based on:
- Opponent defensive strength (KenPom-style rankings)
- Home/Away venue impact
- Recent form (L5 games)
- Tactical matchup factors

Author: Production Sports Betting System
Date: 2026-02-01
"""

import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Position(Enum):
    """Player positions with tactical relevance."""
    GK = "Goalkeeper"
    CB = "Center Back"
    FB = "Fullback"
    DM = "Defensive Midfielder"
    CM = "Central Midfielder"
    AM = "Attacking Midfielder"
    W = "Winger"
    FW = "Forward"


class StatType(Enum):
    """Prop bet stat types."""
    SHOTS = "shots"
    SOT = "shots_on_target"
    GOALS = "goals"
    ASSISTS = "assists"
    PASSES = "passes"
    TACKLES = "tackles"
    DRIBBLES = "dribbles"
    FOULS = "fouls"


@dataclass
class PlayerStats:
    """Player statistical profile."""
    name: str
    team: str
    position: Position
    
    # Season averages
    season_avg: float
    season_std: float
    games_played: int
    
    # Recent form (L5 games)
    L5_avg: float
    L5_games: int
    
    # Home/Away splits
    home_avg: float
    away_avg: float
    home_games: int
    away_games: int
    
    # Minutes tracking
    avg_minutes: float
    games_since_injury: Optional[int] = None


@dataclass
class OpponentProfile:
    """Opponent defensive profile."""
    name: str
    league: str
    
    # Defensive rankings (1 = best, 380 = worst across top leagues)
    defensive_rank: int
    
    # Stat-specific defensive ratings (goals conceded per 90)
    shots_conceded_p90: float
    sot_conceded_p90: float
    goals_conceded_p90: float
    
    # Tactical style
    possession_pct: float  # 0-100
    pressing_intensity: str  # "HIGH", "MEDIUM", "LOW"
    defensive_line: str  # "HIGH", "MEDIUM", "LOW"


@dataclass
class MatchContext:
    """Match context metadata."""
    location: str  # "HOME" or "AWAY"
    competition: str  # "PREMIER_LEAGUE", "FA_CUP", etc.
    is_derby: bool
    days_since_last_game: int
    implied_goal_diff: float  # From betting odds
    expected_possession: float  # Team's expected possession %
    
    # Team context
    team_games_under_new_manager: int
    rotation_risk: bool  # Midweek game, tired squad, etc.


class OpponentAdjustmentEngine:
    """
    Calculate opponent-adjusted lambda for soccer player props.
    
    Core Formula:
    lambda_adjusted = lambda_base x f_opponent x f_venue x f_form x f_tactical
    
    Where:
    - lambda_base: Player's baseline average
    - f_opponent: Opponent defensive strength factor (0.55 - 1.25)
    - f_venue: Home/Away factor (0.85 - 1.15)
    - f_form: Recent form factor (0.85 - 1.15)
    - f_tactical: Tactical matchup factor (0.90 - 1.10)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize with configuration.
        
        Args:
            config: Optional config dict with adjustment factors
        """
        self.config = config or self._default_config()
        logger.info("OpponentAdjustmentEngine initialized")
    
    def _default_config(self) -> Dict:
        """Default configuration for adjustment factors."""
        return {
            # Opponent defensive strength multipliers
            "OPPONENT_FACTORS": {
                "ELITE": 0.65,      # Rank 1-10 (Man City, Arsenal, Liverpool, etc.)
                "VERY_STRONG": 0.75,  # Rank 11-25
                "STRONG": 0.85,     # Rank 26-50
                "AVERAGE": 0.95,    # Rank 51-100
                "WEAK": 1.05,       # Rank 101-200
                "VERY_WEAK": 1.15,  # Rank 201-300
                "TERRIBLE": 1.25    # Rank 301+
            },
            
            # Home/Away venue impact
            "VENUE_FACTORS": {
                "HOME": 1.12,       # +12% at home
                "AWAY": 0.88,       # -12% away
                "NEUTRAL": 1.00     # Neutral venue
            },
            
            # Form thresholds (L5 avg vs season avg)
            "FORM_THRESHOLDS": {
                "HOT_STREAK": 1.30,   # L5 > 1.3x season avg
                "WARM": 1.15,         # L5 > 1.15x season avg
                "COLD_STREAK": 0.70,  # L5 < 0.7x season avg
                "COOL": 0.85          # L5 < 0.85x season avg
            },
            "FORM_FACTORS": {
                "HOT_STREAK": 1.12,
                "WARM": 1.05,
                "NORMAL": 1.00,
                "COOL": 0.95,
                "COLD_STREAK": 0.88
            },
            
            # Tactical matchup adjustments
            "TACTICAL_FACTORS": {
                # High pressing vs possession team
                "HIGH_PRESS_VS_POSSESSION": 0.92,
                # Low block vs attacking team
                "LOW_BLOCK_VS_ATTACK": 0.88,
                # Counter-attacking matchup
                "COUNTER_ATTACK_FAVORABLE": 1.08
            },
            
            # Stat-specific adjustments
            "STAT_MODIFIERS": {
                StatType.SHOTS: {
                    "vs_elite_defense": 0.70,  # Shots suppressed heavily
                    "vs_weak_defense": 1.20
                },
                StatType.PASSES: {
                    "vs_elite_defense": 0.95,  # Passes less affected
                    "vs_weak_defense": 1.05
                },
                StatType.TACKLES: {
                    "vs_possession_team": 1.15,  # More tackles needed
                    "vs_direct_team": 0.90
                }
            }
        }
    
    def calculate_adjusted_lambda(
        self,
        player: PlayerStats,
        opponent: OpponentProfile,
        match_context: MatchContext,
        stat_type: StatType
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate opponent-adjusted lambda.
        
        Args:
            player: Player statistical profile
            opponent: Opponent defensive profile
            match_context: Match context metadata
            stat_type: Type of stat being predicted
        
        Returns:
            Tuple of (adjusted_lambda, breakdown_dict)
            
        Example:
            >>> player = PlayerStats(name="Salah", season_avg=3.8, ...)
            >>> opponent = OpponentProfile(name="Man City", defensive_rank=2, ...)
            >>> context = MatchContext(location="AWAY", ...)
            >>> lambda_adj, breakdown = engine.calculate_adjusted_lambda(
            ...     player, opponent, context, StatType.SHOTS
            ... )
            >>> print(f"Adjusted lambda: {lambda_adj:.2f}")
            Adjusted lambda: 2.17
        """
        # Start with baseline
        base_lambda = self._select_baseline(player, match_context)
        
        # Calculate individual factors
        opponent_factor = self._calculate_opponent_factor(
            opponent, stat_type
        )
        venue_factor = self._calculate_venue_factor(
            player, match_context
        )
        form_factor = self._calculate_form_factor(player)
        tactical_factor = self._calculate_tactical_factor(
            opponent, match_context, stat_type
        )
        
        # Apply all adjustments
        adjusted_lambda = (
            base_lambda 
            * opponent_factor 
            * venue_factor 
            * form_factor 
            * tactical_factor
        )
        
        # Minimum floor (never go below 0.1)
        adjusted_lambda = max(adjusted_lambda, 0.1)
        
        # Build breakdown for transparency
        breakdown = {
            "base_lambda": base_lambda,
            "opponent_factor": opponent_factor,
            "venue_factor": venue_factor,
            "form_factor": form_factor,
            "tactical_factor": tactical_factor,
            "final_lambda": adjusted_lambda,
            "total_adjustment": adjusted_lambda / base_lambda if base_lambda > 0 else 1.0
        }
        
        logger.info(
            f"[LAMBDA ADJ] {player.name} vs {opponent.name}: "
            f"{base_lambda:.2f} -> {adjusted_lambda:.2f} "
            f"(opp={opponent_factor:.2f}, venue={venue_factor:.2f}, "
            f"form={form_factor:.2f}, tactic={tactical_factor:.2f})"
        )
        
        return adjusted_lambda, breakdown
    
    def _select_baseline(
        self, 
        player: PlayerStats, 
        match_context: MatchContext
    ) -> float:
        """
        Select appropriate baseline (season avg vs home/away split).
        
        Uses venue-specific average if enough games, else season average.
        """
        # If enough home/away data, use split
        if match_context.location == "HOME" and player.home_games >= 5:
            return player.home_avg
        elif match_context.location == "AWAY" and player.away_games >= 5:
            return player.away_avg
        else:
            # Fall back to season average
            return player.season_avg
    
    def _calculate_opponent_factor(
        self,
        opponent: OpponentProfile,
        stat_type: StatType
    ) -> float:
        """
        Calculate opponent defensive strength factor.
        
        Factors:
        1. Base factor from defensive ranking
        2. Stat-specific modifier (shots vs passes affected differently)
        """
        # Get base factor from defensive rank
        rank = opponent.defensive_rank
        
        if rank <= 10:
            base_factor = self.config["OPPONENT_FACTORS"]["ELITE"]
        elif rank <= 25:
            base_factor = self.config["OPPONENT_FACTORS"]["VERY_STRONG"]
        elif rank <= 50:
            base_factor = self.config["OPPONENT_FACTORS"]["STRONG"]
        elif rank <= 100:
            base_factor = self.config["OPPONENT_FACTORS"]["AVERAGE"]
        elif rank <= 200:
            base_factor = self.config["OPPONENT_FACTORS"]["WEAK"]
        elif rank <= 300:
            base_factor = self.config["OPPONENT_FACTORS"]["VERY_WEAK"]
        else:
            base_factor = self.config["OPPONENT_FACTORS"]["TERRIBLE"]
        
        # Apply stat-specific modifier
        stat_modifiers = self.config["STAT_MODIFIERS"].get(stat_type, {})
        
        if rank <= 25:  # Elite defense
            modifier = stat_modifiers.get("vs_elite_defense", 1.0)
        elif rank >= 200:  # Weak defense
            modifier = stat_modifiers.get("vs_weak_defense", 1.0)
        else:
            modifier = 1.0
        
        return base_factor * modifier
    
    def _calculate_venue_factor(
        self,
        player: PlayerStats,
        match_context: MatchContext
    ) -> float:
        """
        Calculate home/away venue impact.
        
        Uses player's actual home/away split if available,
        otherwise uses league average.
        """
        location = match_context.location
        
        # If player has enough split data, calculate personal factor
        if player.home_games >= 5 and player.away_games >= 5:
            if location == "HOME":
                # Player's home boost relative to season avg
                personal_factor = player.home_avg / player.season_avg if player.season_avg > 0 else 1.0
                # Blend with league average
                league_factor = self.config["VENUE_FACTORS"]["HOME"]
                return (personal_factor * 0.6) + (league_factor * 0.4)
            
            elif location == "AWAY":
                # Player's away penalty relative to season avg
                personal_factor = player.away_avg / player.season_avg if player.season_avg > 0 else 1.0
                league_factor = self.config["VENUE_FACTORS"]["AWAY"]
                return (personal_factor * 0.6) + (league_factor * 0.4)
        
        # Use league average factors
        return self.config["VENUE_FACTORS"].get(location, 1.0)
    
    def _calculate_form_factor(self, player: PlayerStats) -> float:
        """
        Calculate recent form adjustment.
        
        Compares L5 average to season average to detect hot/cold streaks.
        """
        if player.L5_games < 3:
            # Not enough recent data
            return 1.0
        
        if player.season_avg <= 0:
            return 1.0
            
        form_ratio = player.L5_avg / player.season_avg
        thresholds = self.config["FORM_THRESHOLDS"]
        factors = self.config["FORM_FACTORS"]
        
        if form_ratio >= thresholds["HOT_STREAK"]:
            return factors["HOT_STREAK"]
        elif form_ratio >= thresholds["WARM"]:
            return factors["WARM"]
        elif form_ratio <= thresholds["COLD_STREAK"]:
            return factors["COLD_STREAK"]
        elif form_ratio <= thresholds["COOL"]:
            return factors["COOL"]
        else:
            return factors["NORMAL"]
    
    def _calculate_tactical_factor(
        self,
        opponent: OpponentProfile,
        match_context: MatchContext,
        stat_type: StatType
    ) -> float:
        """
        Calculate tactical matchup factor.
        
        Considers:
        - Opponent pressing style
        - Expected possession
        - Defensive line height
        """
        factor = 1.0
        
        # High pressing opponents reduce passing stats
        if opponent.pressing_intensity == "HIGH":
            if stat_type == StatType.PASSES:
                factor *= 0.95
            elif stat_type == StatType.DRIBBLES:
                factor *= 0.92
        
        # Low block defenses reduce shooting opportunities
        if opponent.defensive_line == "LOW":
            if stat_type in [StatType.SHOTS, StatType.SOT]:
                factor *= 0.92
        
        # High possession teams create more chances
        if match_context.expected_possession > 60:
            if stat_type in [StatType.SHOTS, StatType.PASSES]:
                factor *= 1.05
        
        # Low possession teams tackle more
        if match_context.expected_possession < 40:
            if stat_type == StatType.TACKLES:
                factor *= 1.08
        
        return factor


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example: Mohamed Salah vs Man City away
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
    
    context = MatchContext(
        location="AWAY",
        competition="PREMIER_LEAGUE",
        is_derby=False,
        days_since_last_game=4,
        implied_goal_diff=-0.5,
        expected_possession=45.0,
        team_games_under_new_manager=25,
        rotation_risk=False
    )
    
    engine = OpponentAdjustmentEngine()
    adjusted_lambda, breakdown = engine.calculate_adjusted_lambda(
        salah, man_city, context, StatType.SHOTS
    )
    
    print(f"\n{'='*60}")
    print(f"OPPONENT-ADJUSTED LAMBDA CALCULATION")
    print(f"{'='*60}")
    print(f"Player: {salah.name} ({salah.position.value})")
    print(f"Opponent: {man_city.name} (Rank #{man_city.defensive_rank})")
    print(f"Venue: {context.location}")
    print(f"Stat: Shots")
    print(f"\n{'-'*60}")
    print(f"Baseline lambda:       {breakdown['base_lambda']:.2f}")
    print(f"Opponent Factor:   {breakdown['opponent_factor']:.2f}")
    print(f"Venue Factor:      {breakdown['venue_factor']:.2f}")
    print(f"Form Factor:       {breakdown['form_factor']:.2f}")
    print(f"Tactical Factor:   {breakdown['tactical_factor']:.2f}")
    print(f"{'-'*60}")
    print(f"ADJUSTED lambda:       {breakdown['final_lambda']:.2f}")
    print(f"Total Adjustment:  {breakdown['total_adjustment']:.1%}")
    print(f"{'='*60}\n")
