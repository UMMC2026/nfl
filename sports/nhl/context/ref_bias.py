"""
REFEREE SPECIAL-TEAMS BIAS — NHL v2.0 Module
=============================================

Exploits PP/PK inflation or suppression driven by officiating crews.

Data:
- Ref penalties per game (historical)
- Home/away penalty asymmetry
- PP conversion interaction (team-specific)

Adjustment formula:
    ST_Adjust = League_Avg_PP × Ref_Penalty_Multiplier × Team_PP_Efficiency

Gates:
- R1: Ref sample <30 games → ignore (use neutral)
- R2: Adjustment cap ±0.15 goals
- R3: Only affects totals & goalie saves (not ML directly)
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────

# League averages (2023-24 season baseline)
LEAGUE_AVG_PENALTIES_PER_GAME = 7.2  # Combined both teams
LEAGUE_AVG_PP_PCT = 0.212            # Power play conversion
LEAGUE_AVG_PK_PCT = 0.788            # Penalty kill success

# Gate thresholds
MIN_REF_SAMPLE_GAMES = 30
MAX_ADJUSTMENT_GOALS = 0.15

# Ref crew types based on penalty patterns
class RefTendency(str, Enum):
    WHISTLE_HAPPY = "WHISTLE_HAPPY"   # >8.0 calls/game
    LEAGUE_AVG = "LEAGUE_AVG"         # 6.5-8.0 calls/game
    LET_THEM_PLAY = "LET_THEM_PLAY"   # <6.5 calls/game


@dataclass
class RefereeProfile:
    """Profile for an NHL referee crew."""
    name: str                          # Primary ref name
    games_officiated: int              # Sample size
    
    # Penalty patterns
    penalties_per_game: float          # Average total penalties called
    home_penalty_rate: float           # Penalties on home team (ratio)
    away_penalty_rate: float           # Penalties on away team (ratio)
    
    # Power play impacts
    pp_opportunities_per_game: float   # Average PP chances per game
    avg_game_total_goals: float        # Average total goals in games officiated
    
    # Derived
    tendency: RefTendency = RefTendency.LEAGUE_AVG
    
    def __post_init__(self):
        # Classify tendency
        if self.penalties_per_game > 8.0:
            self.tendency = RefTendency.WHISTLE_HAPPY
        elif self.penalties_per_game < 6.5:
            self.tendency = RefTendency.LET_THEM_PLAY
        else:
            self.tendency = RefTendency.LEAGUE_AVG
    
    @property
    def meets_sample_threshold(self) -> bool:
        return self.games_officiated >= MIN_REF_SAMPLE_GAMES
    
    @property
    def penalty_multiplier(self) -> float:
        """Ratio vs league average penalties."""
        return self.penalties_per_game / LEAGUE_AVG_PENALTIES_PER_GAME
    
    @property
    def home_bias(self) -> float:
        """Home penalty bias (>1 means more away penalties)."""
        if self.home_penalty_rate == 0:
            return 1.0
        return self.away_penalty_rate / self.home_penalty_rate


@dataclass
class TeamPPProfile:
    """Team power play and penalty kill profile."""
    team: str
    pp_pct: float           # Power play conversion %
    pk_pct: float           # Penalty kill %
    pp_xg_per_60: float     # Expected goals per 60 min on PP
    pk_xga_per_60: float    # Expected goals against per 60 on PK
    
    @property
    def pp_efficiency_vs_league(self) -> float:
        """PP efficiency relative to league average."""
        return self.pp_pct / LEAGUE_AVG_PP_PCT
    
    @property
    def pk_efficiency_vs_league(self) -> float:
        """PK efficiency relative to league average (>1 is better)."""
        return self.pk_pct / LEAGUE_AVG_PK_PCT


@dataclass
class RefBiasAdjustment:
    """Result of referee bias calculation."""
    ref_name: str
    ref_tendency: RefTendency
    sample_games: int
    
    # Raw adjustments
    penalty_multiplier: float
    expected_extra_pp: float        # Additional PP opportunities vs baseline
    
    # Goal adjustments (capped)
    home_goal_adjust: float
    away_goal_adjust: float
    total_goal_adjust: float
    
    # Application flags
    is_applicable: bool             # Passes R1 gate
    is_capped: bool                 # Hit R2 cap
    affected_markets: List[str]     # R3: totals, goalie_saves
    
    # Risk tag
    risk_tag: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "ref_name": self.ref_name,
            "ref_tendency": self.ref_tendency.value,
            "sample_games": self.sample_games,
            "penalty_multiplier": round(self.penalty_multiplier, 3),
            "expected_extra_pp": round(self.expected_extra_pp, 2),
            "home_goal_adjust": round(self.home_goal_adjust, 3),
            "away_goal_adjust": round(self.away_goal_adjust, 3),
            "total_goal_adjust": round(self.total_goal_adjust, 3),
            "is_applicable": self.is_applicable,
            "is_capped": self.is_capped,
            "affected_markets": self.affected_markets,
            "risk_tag": self.risk_tag,
        }


# ─────────────────────────────────────────────────────────
# REFEREE BIAS CALCULATOR
# ─────────────────────────────────────────────────────────

class RefereeBiasCalculator:
    """
    Calculates expected goal adjustments based on referee tendencies.
    
    Key insight: High-penalty refs create more PP opportunities,
    which benefits teams with strong PP and hurts weak PK teams.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_adjustment(
        self,
        referee: RefereeProfile,
        home_team: TeamPPProfile,
        away_team: TeamPPProfile,
    ) -> RefBiasAdjustment:
        """
        Calculate goal adjustment based on ref + team profiles.
        
        Args:
            referee: Referee crew profile
            home_team: Home team PP/PK profile
            away_team: Away team PP/PK profile
        
        Returns:
            RefBiasAdjustment with capped goal adjustments
        """
        # GATE R1: Sample size check
        if not referee.meets_sample_threshold:
            self.logger.info(
                f"R1 GATE: Ref {referee.name} has insufficient sample "
                f"({referee.games_officiated} < {MIN_REF_SAMPLE_GAMES})"
            )
            return RefBiasAdjustment(
                ref_name=referee.name,
                ref_tendency=referee.tendency,
                sample_games=referee.games_officiated,
                penalty_multiplier=1.0,
                expected_extra_pp=0.0,
                home_goal_adjust=0.0,
                away_goal_adjust=0.0,
                total_goal_adjust=0.0,
                is_applicable=False,
                is_capped=False,
                affected_markets=[],
                risk_tag=None,
            )
        
        # Calculate extra PP opportunities vs baseline
        extra_penalties = (
            referee.penalties_per_game - LEAGUE_AVG_PENALTIES_PER_GAME
        )
        extra_pp_each = extra_penalties / 2  # Split between teams (rough)
        
        # Adjust for home/away bias
        home_extra_pp = extra_pp_each * referee.home_bias
        away_extra_pp = extra_penalties - home_extra_pp
        
        # Calculate expected goal impact
        # Home team PP goals when away has penalty
        home_pp_goals = away_extra_pp * (home_team.pp_pct * 0.8)  # Not full game PP
        
        # Away team PP goals when home has penalty  
        away_pp_goals = home_extra_pp * (away_team.pp_pct * 0.8)
        
        # Net adjustments
        raw_home_adjust = home_pp_goals - away_pp_goals * (1 - home_team.pk_pct)
        raw_away_adjust = away_pp_goals - home_pp_goals * (1 - away_team.pk_pct)
        raw_total_adjust = raw_home_adjust + raw_away_adjust
        
        # GATE R2: Cap adjustment
        is_capped = False
        
        if abs(raw_home_adjust) > MAX_ADJUSTMENT_GOALS:
            raw_home_adjust = MAX_ADJUSTMENT_GOALS * (1 if raw_home_adjust > 0 else -1)
            is_capped = True
        
        if abs(raw_away_adjust) > MAX_ADJUSTMENT_GOALS:
            raw_away_adjust = MAX_ADJUSTMENT_GOALS * (1 if raw_away_adjust > 0 else -1)
            is_capped = True
        
        if abs(raw_total_adjust) > MAX_ADJUSTMENT_GOALS * 2:
            raw_total_adjust = MAX_ADJUSTMENT_GOALS * 2 * (1 if raw_total_adjust > 0 else -1)
            is_capped = True
        
        # GATE R3: Only affects totals & goalie saves
        affected_markets = ["totals", "goalie_saves"]
        
        # Determine risk tag
        risk_tag = None
        if referee.tendency == RefTendency.WHISTLE_HAPPY:
            risk_tag = "REF_WHISTLE_HAPPY"
        elif referee.tendency == RefTendency.LET_THEM_PLAY:
            risk_tag = "REF_LET_THEM_PLAY"
        
        return RefBiasAdjustment(
            ref_name=referee.name,
            ref_tendency=referee.tendency,
            sample_games=referee.games_officiated,
            penalty_multiplier=referee.penalty_multiplier,
            expected_extra_pp=extra_penalties,
            home_goal_adjust=raw_home_adjust,
            away_goal_adjust=raw_away_adjust,
            total_goal_adjust=raw_total_adjust,
            is_applicable=True,
            is_capped=is_capped,
            affected_markets=affected_markets,
            risk_tag=risk_tag,
        )


# ─────────────────────────────────────────────────────────
# REFEREE DATABASE (Sample Data)
# ─────────────────────────────────────────────────────────

# Sample referee profiles (would be loaded from data source)
SAMPLE_REFEREES: Dict[str, RefereeProfile] = {
    "wes_mccauley": RefereeProfile(
        name="Wes McCauley",
        games_officiated=45,
        penalties_per_game=7.8,
        home_penalty_rate=0.48,
        away_penalty_rate=0.52,
        pp_opportunities_per_game=6.2,
        avg_game_total_goals=5.9,
    ),
    "chris_rooney": RefereeProfile(
        name="Chris Rooney",
        games_officiated=42,
        penalties_per_game=8.4,
        home_penalty_rate=0.46,
        away_penalty_rate=0.54,
        pp_opportunities_per_game=6.8,
        avg_game_total_goals=6.3,
    ),
    "kelly_sutherland": RefereeProfile(
        name="Kelly Sutherland",
        games_officiated=38,
        penalties_per_game=6.2,
        home_penalty_rate=0.50,
        away_penalty_rate=0.50,
        pp_opportunities_per_game=5.0,
        avg_game_total_goals=5.4,
    ),
    "francois_stlauvent": RefereeProfile(
        name="François St. Laurent",
        games_officiated=50,
        penalties_per_game=7.1,
        home_penalty_rate=0.49,
        away_penalty_rate=0.51,
        pp_opportunities_per_game=5.6,
        avg_game_total_goals=5.7,
    ),
}


def get_referee_profile(ref_name: str) -> Optional[RefereeProfile]:
    """Look up referee profile by name."""
    key = ref_name.lower().replace(" ", "_").replace(".", "")
    return SAMPLE_REFEREES.get(key)


def calculate_ref_bias_for_game(
    ref_name: str,
    home_pp_pct: float,
    home_pk_pct: float,
    away_pp_pct: float,
    away_pk_pct: float,
) -> RefBiasAdjustment:
    """
    Convenience function to calculate ref bias for a game.
    
    Args:
        ref_name: Name of primary referee
        home_pp_pct: Home team PP%
        home_pk_pct: Home team PK%
        away_pp_pct: Away team PP%
        away_pk_pct: Away team PK%
    
    Returns:
        RefBiasAdjustment
    """
    referee = get_referee_profile(ref_name)
    
    if referee is None:
        # Unknown ref - return neutral
        return RefBiasAdjustment(
            ref_name=ref_name,
            ref_tendency=RefTendency.LEAGUE_AVG,
            sample_games=0,
            penalty_multiplier=1.0,
            expected_extra_pp=0.0,
            home_goal_adjust=0.0,
            away_goal_adjust=0.0,
            total_goal_adjust=0.0,
            is_applicable=False,
            is_capped=False,
            affected_markets=[],
            risk_tag="REF_UNKNOWN",
        )
    
    home_team = TeamPPProfile(
        team="HOME",
        pp_pct=home_pp_pct,
        pk_pct=home_pk_pct,
        pp_xg_per_60=home_pp_pct * 6.0,  # Rough estimate
        pk_xga_per_60=(1 - home_pk_pct) * 6.0,
    )
    
    away_team = TeamPPProfile(
        team="AWAY",
        pp_pct=away_pp_pct,
        pk_pct=away_pk_pct,
        pp_xg_per_60=away_pp_pct * 6.0,
        pk_xga_per_60=(1 - away_pk_pct) * 6.0,
    )
    
    calculator = RefereeBiasCalculator()
    return calculator.calculate_adjustment(referee, home_team, away_team)


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("REFEREE BIAS MODULE — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Demo: High-penalty ref with mismatched PP teams
    adjustment = calculate_ref_bias_for_game(
        ref_name="Chris Rooney",
        home_pp_pct=0.26,   # Strong PP team
        home_pk_pct=0.82,
        away_pp_pct=0.18,   # Weak PP team
        away_pk_pct=0.76,
    )
    
    print(f"\nRef: {adjustment.ref_name}")
    print(f"Tendency: {adjustment.ref_tendency.value}")
    print(f"Sample: {adjustment.sample_games} games")
    print(f"Penalty Multiplier: {adjustment.penalty_multiplier:.2f}x")
    print(f"Expected Extra PP/game: {adjustment.expected_extra_pp:+.1f}")
    print(f"\nGoal Adjustments:")
    print(f"  Home: {adjustment.home_goal_adjust:+.3f}")
    print(f"  Away: {adjustment.away_goal_adjust:+.3f}")
    print(f"  Total: {adjustment.total_goal_adjust:+.3f}")
    print(f"\nApplicable: {adjustment.is_applicable}")
    print(f"Capped: {adjustment.is_capped}")
    print(f"Risk Tag: {adjustment.risk_tag}")
    print(f"Affects: {adjustment.affected_markets}")
    
    # Demo: Low-sample ref (should be ignored)
    print("\n" + "-" * 40)
    print("Testing R1 gate (low sample):")
    
    unknown_adj = calculate_ref_bias_for_game(
        ref_name="Unknown Referee",
        home_pp_pct=0.22,
        home_pk_pct=0.80,
        away_pp_pct=0.20,
        away_pk_pct=0.78,
    )
    
    print(f"Ref: {unknown_adj.ref_name}")
    print(f"Applicable: {unknown_adj.is_applicable}")
    print(f"Risk Tag: {unknown_adj.risk_tag}")
