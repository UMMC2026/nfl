"""
POISSON GAME SIMULATOR — NHL Probability Engine
================================================

Hockey is a low-scoring sport where Poisson distribution fits well.
This module simulates games using expected goals (xG) as λ parameters.

Simulation count: 20,000 games per matchup (configurable)
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from scipy.stats import poisson
import logging

logger = logging.getLogger(__name__)


@dataclass
class TeamXG:
    """Expected goals input for a team."""
    team: str
    xgf_5v5: float          # 5v5 expected goals for
    xga_5v5: float          # 5v5 expected goals against
    pp_xg_per_60: float     # Power play xG per 60
    pk_xga_per_60: float    # Penalty kill xG against per 60
    goalie_sv_pct: float    # Starting goalie save %
    is_home: bool = False
    
    @property
    def goalie_adjustment(self) -> float:
        """
        Goalie quality adjustment.
        Positive = better than average, saves more goals.
        """
        league_avg_sv_pct = 0.905
        expected_shots = 30.5  # League average
        return (self.goalie_sv_pct - league_avg_sv_pct) * expected_shots


@dataclass 
class SimulationResult:
    """Results from game simulation."""
    home_team: str
    away_team: str
    simulations: int
    
    # Win probabilities
    home_win_prob: float
    away_win_prob: float
    tie_regulation_prob: float  # Goes to OT
    
    # Puck line probabilities
    home_cover_1_5: float       # Home wins by 2+
    away_cover_1_5: float       # Away wins or loses by 1
    
    # Total probabilities
    over_5_5: float
    under_5_5: float
    over_6_0: float
    under_6_0: float
    over_6_5: float
    under_6_5: float
    
    # Distribution stats
    home_goals_mean: float
    away_goals_mean: float
    total_goals_mean: float
    
    # Raw simulation data (for debugging)
    home_goals_dist: Optional[Dict[int, float]] = None
    away_goals_dist: Optional[Dict[int, float]] = None


class PoissonSimulator:
    """
    Poisson-based game simulator for NHL.
    
    Uses expected goals (xG) to derive λ parameters,
    then simulates thousands of games to extract probabilities.
    """
    
    # Home ice advantage multiplier (applied to home λ)
    HOME_ICE_MULTIPLIER = 1.035  # ~3.5% boost
    
    # Default simulation count
    DEFAULT_SIMULATIONS = 20000
    
    # xG weight factors for composite calculation
    XG_WEIGHTS = {
        "team_5v5_xgf": 0.45,
        "opponent_5v5_xga": 0.25,
        "goalie_adjustment": 0.20,
        "special_teams_delta": 0.10,
    }
    
    def __init__(self, simulations: int = DEFAULT_SIMULATIONS, seed: int = None):
        """
        Initialize simulator.
        
        Args:
            simulations: Number of games to simulate
            seed: Random seed for reproducibility
        """
        self.simulations = simulations
        self.rng = np.random.default_rng(seed)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_lambda(self, team: TeamXG, opponent: TeamXG) -> float:
        """
        Calculate expected goals (λ) for a team.
        
        Formula:
            λ = 0.45 * team_5v5_xgf
              + 0.25 * opponent_5v5_xga
              + 0.20 * goalie_adjustment (opponent's goalie)
              + 0.10 * special_teams_delta
              
        Args:
            team: Attacking team's xG data
            opponent: Defending team's xG data (with their goalie)
            
        Returns:
            Expected goals (λ) for the team
        """
        # Base 5v5 contribution
        base_xg = (
            self.XG_WEIGHTS["team_5v5_xgf"] * team.xgf_5v5 +
            self.XG_WEIGHTS["opponent_5v5_xga"] * opponent.xga_5v5
        )
        
        # Goalie adjustment (opponent's goalie quality reduces our goals)
        # Better goalie = negative adjustment = fewer goals
        goalie_adj = -self.XG_WEIGHTS["goalie_adjustment"] * opponent.goalie_adjustment
        
        # Special teams delta (simplified)
        pp_advantage = team.pp_xg_per_60 / 60 * 4  # ~4 min PP per game
        pk_disadvantage = opponent.pk_xga_per_60 / 60 * 4
        special_teams = self.XG_WEIGHTS["special_teams_delta"] * (pp_advantage - pk_disadvantage)
        
        lambda_raw = base_xg + goalie_adj + special_teams
        
        # Apply home ice advantage
        if team.is_home:
            lambda_raw *= self.HOME_ICE_MULTIPLIER
        
        # Floor at 1.5 goals (no team is THAT bad)
        return max(1.5, lambda_raw)
    
    def simulate_game(
        self,
        home: TeamXG,
        away: TeamXG,
    ) -> SimulationResult:
        """
        Simulate a game between two teams.
        
        Args:
            home: Home team xG data
            away: Away team xG data
            
        Returns:
            SimulationResult with all probabilities
        """
        # Calculate expected goals for each team
        lambda_home = self.calculate_lambda(home, away)
        lambda_away = self.calculate_lambda(away, home)
        
        self.logger.debug(
            f"Simulating {away.team} @ {home.team}: "
            f"λ_home={lambda_home:.2f}, λ_away={lambda_away:.2f}"
        )
        
        # Simulate games using Poisson distribution
        home_goals = self.rng.poisson(lambda_home, self.simulations)
        away_goals = self.rng.poisson(lambda_away, self.simulations)
        
        # Calculate outcomes
        home_wins = np.sum(home_goals > away_goals)
        away_wins = np.sum(away_goals > home_goals)
        ties = np.sum(home_goals == away_goals)
        
        # Puck line (home -1.5 / away +1.5)
        home_cover = np.sum(home_goals - away_goals > 1.5)
        away_cover = np.sum(away_goals - home_goals > -1.5)  # Away wins or loses by 1
        
        # Totals
        total_goals = home_goals + away_goals
        over_5_5 = np.sum(total_goals > 5.5)
        under_5_5 = np.sum(total_goals < 5.5)
        over_6_0 = np.sum(total_goals > 6.0)
        under_6_0 = np.sum(total_goals < 6.0)
        over_6_5 = np.sum(total_goals > 6.5)
        under_6_5 = np.sum(total_goals < 6.5)
        
        # Goal distributions (for analysis)
        home_dist = {}
        away_dist = {}
        for g in range(0, 10):
            home_dist[g] = np.sum(home_goals == g) / self.simulations
            away_dist[g] = np.sum(away_goals == g) / self.simulations
        
        return SimulationResult(
            home_team=home.team,
            away_team=away.team,
            simulations=self.simulations,
            
            # Win probabilities (regulation only)
            home_win_prob=home_wins / self.simulations,
            away_win_prob=away_wins / self.simulations,
            tie_regulation_prob=ties / self.simulations,
            
            # Puck line
            home_cover_1_5=home_cover / self.simulations,
            away_cover_1_5=away_cover / self.simulations,
            
            # Totals
            over_5_5=over_5_5 / self.simulations,
            under_5_5=under_5_5 / self.simulations,
            over_6_0=over_6_0 / self.simulations,
            under_6_0=under_6_0 / self.simulations,
            over_6_5=over_6_5 / self.simulations,
            under_6_5=under_6_5 / self.simulations,
            
            # Stats
            home_goals_mean=np.mean(home_goals),
            away_goals_mean=np.mean(away_goals),
            total_goals_mean=np.mean(total_goals),
            
            # Distributions
            home_goals_dist=home_dist,
            away_goals_dist=away_dist,
        )
    
    def get_moneyline_probs(
        self,
        result: SimulationResult,
        include_ot: bool = True,
    ) -> Tuple[float, float]:
        """
        Get moneyline probabilities.
        
        In NHL, moneyline includes OT/SO. We split ties 50/50 to home/away.
        
        Args:
            result: Simulation result
            include_ot: Whether to include OT/SO split
            
        Returns:
            (home_ml_prob, away_ml_prob)
        """
        if include_ot:
            # Split regulation ties 50/50 (simplified)
            ot_split = result.tie_regulation_prob / 2
            home_ml = result.home_win_prob + ot_split
            away_ml = result.away_win_prob + ot_split
        else:
            home_ml = result.home_win_prob
            away_ml = result.away_win_prob
        
        return home_ml, away_ml


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def simulate_nhl_game(
    home_team: str,
    away_team: str,
    home_xg: Dict,
    away_xg: Dict,
    simulations: int = 20000,
) -> SimulationResult:
    """
    Convenience function to simulate an NHL game.
    
    Args:
        home_team: Home team abbreviation
        away_team: Away team abbreviation
        home_xg: Dict with xgf_5v5, xga_5v5, pp_xg_per_60, pk_xga_per_60, goalie_sv_pct
        away_xg: Same structure for away team
        simulations: Number of simulations
        
    Returns:
        SimulationResult
    """
    home = TeamXG(
        team=home_team,
        xgf_5v5=home_xg["xgf_5v5"],
        xga_5v5=home_xg["xga_5v5"],
        pp_xg_per_60=home_xg["pp_xg_per_60"],
        pk_xga_per_60=home_xg["pk_xga_per_60"],
        goalie_sv_pct=home_xg["goalie_sv_pct"],
        is_home=True,
    )
    
    away = TeamXG(
        team=away_team,
        xgf_5v5=away_xg["xgf_5v5"],
        xga_5v5=away_xg["xga_5v5"],
        pp_xg_per_60=away_xg["pp_xg_per_60"],
        pk_xga_per_60=away_xg["pk_xga_per_60"],
        goalie_sv_pct=away_xg["goalie_sv_pct"],
        is_home=False,
    )
    
    simulator = PoissonSimulator(simulations=simulations)
    return simulator.simulate_game(home, away)
