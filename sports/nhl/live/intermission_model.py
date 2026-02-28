"""
INTERMISSION MODEL — NHL v2.0 Live Adjustment Engine
=====================================================

Core logic for adjusting projections based on live game state.
Called ONLY during validated intermissions.

MODELS:
1. Game Total Adjustment (based on observed pace)
2. Goal Scorer Re-projection (based on TOI/shots)
3. Goalie Saves Re-projection (based on shot pace)

GLOBAL ASSERTION:
  assert live_bets_per_game <= 1
"""

import math
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum

from .ingest_live import LiveGameSnapshot, IntermissionWindow, GameState

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# ADJUSTMENT TYPES
# ─────────────────────────────────────────────────────────

class AdjustmentType(Enum):
    """Type of live adjustment."""
    GAME_TOTAL = "game_total"
    TEAM_TOTAL = "team_total"
    PLAYER_SHOTS = "player_shots"
    GOALIE_SAVES = "goalie_saves"


@dataclass
class LiveAdjustment:
    """A live model adjustment."""
    adjustment_type: AdjustmentType
    entity: str  # Team or player name
    
    # Original projection
    original_projection: float
    original_probability: float
    
    # Adjusted projection
    adjusted_projection: float
    adjusted_probability: float
    
    # Context
    line: float
    direction: str  # "OVER" or "UNDER"
    
    # Metadata
    intermission: IntermissionWindow
    period_score_home: int
    period_score_away: int
    observed_pace_factor: float  # 1.0 = expected pace
    
    # Gates
    is_actionable: bool
    rejection_reason: Optional[str] = None
    
    @property
    def edge_change(self) -> float:
        """Change in probability from original to adjusted."""
        return self.adjusted_probability - self.original_probability
    
    @property
    def projection_change(self) -> float:
        """Change in projection."""
        return self.adjusted_projection - self.original_projection
    
    def __repr__(self):
        status = "ACTIONABLE" if self.is_actionable else f"REJECTED: {self.rejection_reason}"
        return (
            f"LiveAdjustment({self.adjustment_type.value})\n"
            f"  Entity: {self.entity}\n"
            f"  Line: {self.line} {self.direction}\n"
            f"  Original: {self.original_projection:.2f} ({self.original_probability:.1%})\n"
            f"  Adjusted: {self.adjusted_projection:.2f} ({self.adjusted_probability:.1%})\n"
            f"  Pace factor: {self.observed_pace_factor:.2f}\n"
            f"  Status: {status}"
        )


# ─────────────────────────────────────────────────────────
# PACE CALCULATION
# ─────────────────────────────────────────────────────────

def calculate_observed_pace(
    snapshot: LiveGameSnapshot,
    expected_goals_per_game: float = 6.2,
    expected_shots_per_game: float = 62.0,
) -> Dict[str, float]:
    """
    Calculate observed pace factors from live data.
    
    Args:
        snapshot: Live game snapshot
        expected_goals_per_game: League average goals/game
        expected_shots_per_game: League average shots/game
    
    Returns:
        Dict with pace factors
    """
    # Periods completed
    if snapshot.game_state == GameState.INTERMISSION_1:
        periods_complete = 1
    elif snapshot.game_state == GameState.INTERMISSION_2:
        periods_complete = 2
    else:
        periods_complete = 0
    
    if periods_complete == 0:
        return {
            "goal_pace": 1.0,
            "shot_pace": 1.0,
            "periods_complete": 0,
            "time_fraction": 0.0,
        }
    
    # Time fraction (assuming 3x 20-minute periods)
    time_fraction = periods_complete / 3.0
    
    # Expected by now
    expected_goals_now = expected_goals_per_game * time_fraction
    expected_shots_now = expected_shots_per_game * time_fraction
    
    # Observed
    observed_goals = snapshot.total_goals
    observed_shots = snapshot.home_shots + snapshot.away_shots
    
    # Pace factors (with floor to avoid division issues)
    goal_pace = observed_goals / max(expected_goals_now, 0.5)
    shot_pace = observed_shots / max(expected_shots_now, 1.0)
    
    return {
        "goal_pace": goal_pace,
        "shot_pace": shot_pace,
        "periods_complete": periods_complete,
        "time_fraction": time_fraction,
        "expected_goals_now": expected_goals_now,
        "expected_shots_now": expected_shots_now,
        "observed_goals": observed_goals,
        "observed_shots": observed_shots,
    }


# ─────────────────────────────────────────────────────────
# GAME TOTAL MODEL
# ─────────────────────────────────────────────────────────

class GameTotalModel:
    """
    Adjust game total projections based on observed pace.
    
    Uses simple pace extrapolation with regression toward mean.
    """
    
    # How much to weight observed pace vs prior
    PACE_WEIGHT_INT1 = 0.4  # First intermission: 40% observed
    PACE_WEIGHT_INT2 = 0.6  # Second intermission: 60% observed
    
    # Minimum edge for actionability
    MIN_EDGE_THRESHOLD = 0.02  # 2%
    
    @classmethod
    def adjust(
        cls,
        snapshot: LiveGameSnapshot,
        original_projection: float,
        original_probability: float,
        line: float,
        direction: str,
    ) -> LiveAdjustment:
        """
        Adjust game total projection.
        
        Args:
            snapshot: Live game state
            original_projection: Pregame total projection
            original_probability: Pregame probability for direction
            line: Current line
            direction: "OVER" or "UNDER"
        
        Returns:
            LiveAdjustment with updated values
        """
        pace_data = calculate_observed_pace(snapshot)
        
        if pace_data["periods_complete"] == 0:
            return LiveAdjustment(
                adjustment_type=AdjustmentType.GAME_TOTAL,
                entity=f"{snapshot.away_team}@{snapshot.home_team}",
                original_projection=original_projection,
                original_probability=original_probability,
                adjusted_projection=original_projection,
                adjusted_probability=original_probability,
                line=line,
                direction=direction,
                intermission=snapshot.intermission_window,
                period_score_home=snapshot.home_score,
                period_score_away=snapshot.away_score,
                observed_pace_factor=1.0,
                is_actionable=False,
                rejection_reason="No periods complete",
            )
        
        # Select pace weight
        if snapshot.game_state == GameState.INTERMISSION_1:
            pace_weight = cls.PACE_WEIGHT_INT1
        else:
            pace_weight = cls.PACE_WEIGHT_INT2
        
        goal_pace = pace_data["goal_pace"]
        
        # Blend observed pace with prior
        # If pace = 1.5 (50% faster), and prior was 6.2, we adjust up
        blended_pace = (pace_weight * goal_pace) + ((1 - pace_weight) * 1.0)
        
        # Project remaining period(s) at blended pace
        periods_remaining = 3 - pace_data["periods_complete"]
        expected_per_period = original_projection / 3.0
        remaining_projection = expected_per_period * periods_remaining * blended_pace
        
        # Total projection = observed + remaining
        adjusted_projection = snapshot.total_goals + remaining_projection
        
        # Probability adjustment (simple linear interpolation)
        # More sophisticated: use Poisson with adjusted λ
        proj_diff = adjusted_projection - original_projection
        
        if direction.upper() == "OVER":
            # Higher projection -> higher OVER probability
            prob_adjustment = proj_diff * 0.05  # 5% per goal swing
        else:
            # Higher projection -> lower UNDER probability
            prob_adjustment = -proj_diff * 0.05
        
        adjusted_probability = max(0.0, min(1.0, original_probability + prob_adjustment))
        
        # Edge check
        edge_change = abs(adjusted_probability - original_probability)
        is_actionable = edge_change >= cls.MIN_EDGE_THRESHOLD
        
        return LiveAdjustment(
            adjustment_type=AdjustmentType.GAME_TOTAL,
            entity=f"{snapshot.away_team}@{snapshot.home_team}",
            original_projection=original_projection,
            original_probability=original_probability,
            adjusted_projection=adjusted_projection,
            adjusted_probability=adjusted_probability,
            line=line,
            direction=direction,
            intermission=snapshot.intermission_window,
            period_score_home=snapshot.home_score,
            period_score_away=snapshot.away_score,
            observed_pace_factor=goal_pace,
            is_actionable=is_actionable,
            rejection_reason=None if is_actionable else f"Edge change {edge_change:.1%} < {cls.MIN_EDGE_THRESHOLD:.1%}",
        )


# ─────────────────────────────────────────────────────────
# GOALIE SAVES MODEL
# ─────────────────────────────────────────────────────────

class GoalieSavesModel:
    """
    Adjust goalie saves projections based on shot pace.
    """
    
    MIN_EDGE_THRESHOLD = 0.02
    
    @classmethod
    def adjust(
        cls,
        snapshot: LiveGameSnapshot,
        goalie_name: str,
        goalie_team: str,  # "HOME" or "AWAY"
        original_projection: float,
        original_probability: float,
        line: float,
        direction: str,
    ) -> LiveAdjustment:
        """
        Adjust goalie saves projection.
        """
        pace_data = calculate_observed_pace(snapshot)
        
        if pace_data["periods_complete"] == 0:
            return LiveAdjustment(
                adjustment_type=AdjustmentType.GOALIE_SAVES,
                entity=goalie_name,
                original_projection=original_projection,
                original_probability=original_probability,
                adjusted_projection=original_projection,
                adjusted_probability=original_probability,
                line=line,
                direction=direction,
                intermission=snapshot.intermission_window,
                period_score_home=snapshot.home_score,
                period_score_away=snapshot.away_score,
                observed_pace_factor=1.0,
                is_actionable=False,
                rejection_reason="No periods complete",
            )
        
        # Get shots against this goalie
        if goalie_team.upper() == "HOME":
            shots_against = snapshot.away_shots
        else:
            shots_against = snapshot.home_shots
        
        # Extrapolate saves (assuming ~0.91 save rate)
        periods_remaining = 3 - pace_data["periods_complete"]
        shot_pace = pace_data["shot_pace"]
        
        # Expected remaining shots against
        expected_remaining_per_period = (original_projection / 3.0) / 0.91  # Shots per period
        remaining_shots = expected_remaining_per_period * periods_remaining * shot_pace
        
        # Projected saves
        current_saves = shots_against - (snapshot.home_score if goalie_team == "AWAY" else snapshot.away_score)
        remaining_saves = remaining_shots * 0.91
        
        adjusted_projection = current_saves + remaining_saves
        
        # Probability adjustment
        proj_diff = adjusted_projection - original_projection
        
        if direction.upper() == "OVER":
            prob_adjustment = proj_diff * 0.03  # 3% per save swing
        else:
            prob_adjustment = -proj_diff * 0.03
        
        adjusted_probability = max(0.0, min(1.0, original_probability + prob_adjustment))
        
        edge_change = abs(adjusted_probability - original_probability)
        is_actionable = edge_change >= cls.MIN_EDGE_THRESHOLD
        
        return LiveAdjustment(
            adjustment_type=AdjustmentType.GOALIE_SAVES,
            entity=goalie_name,
            original_projection=original_projection,
            original_probability=original_probability,
            adjusted_projection=adjusted_projection,
            adjusted_probability=adjusted_probability,
            line=line,
            direction=direction,
            intermission=snapshot.intermission_window,
            period_score_home=snapshot.home_score,
            period_score_away=snapshot.away_score,
            observed_pace_factor=shot_pace,
            is_actionable=is_actionable,
            rejection_reason=None if is_actionable else f"Edge change {edge_change:.1%} < {cls.MIN_EDGE_THRESHOLD:.1%}",
        )


# ─────────────────────────────────────────────────────────
# PLAYER SHOTS MODEL
# ─────────────────────────────────────────────────────────

class PlayerShotsLiveModel:
    """
    Adjust player SOG projections based on observed game pace.
    """
    
    MIN_EDGE_THRESHOLD = 0.02
    
    @classmethod
    def adjust(
        cls,
        snapshot: LiveGameSnapshot,
        player_name: str,
        player_team: str,  # "HOME" or "AWAY"
        original_projection: float,
        original_probability: float,
        line: float,
        direction: str,
        current_shots: int = 0,  # Player's SOG so far
    ) -> LiveAdjustment:
        """
        Adjust player SOG projection based on game state.
        """
        pace_data = calculate_observed_pace(snapshot)
        
        if pace_data["periods_complete"] == 0:
            return LiveAdjustment(
                adjustment_type=AdjustmentType.PLAYER_SHOTS,
                entity=player_name,
                original_projection=original_projection,
                original_probability=original_probability,
                adjusted_projection=original_projection,
                adjusted_probability=original_probability,
                line=line,
                direction=direction,
                intermission=snapshot.intermission_window,
                period_score_home=snapshot.home_score,
                period_score_away=snapshot.away_score,
                observed_pace_factor=1.0,
                is_actionable=False,
                rejection_reason="No periods complete",
            )
        
        shot_pace = pace_data["shot_pace"]
        periods_remaining = 3 - pace_data["periods_complete"]
        
        # Expected remaining shots (adjusted for pace)
        expected_per_period = original_projection / 3.0
        remaining_projection = expected_per_period * periods_remaining * shot_pace
        
        adjusted_projection = current_shots + remaining_projection
        
        proj_diff = adjusted_projection - original_projection
        
        if direction.upper() == "OVER":
            prob_adjustment = proj_diff * 0.08  # 8% per shot swing
        else:
            prob_adjustment = -proj_diff * 0.08
        
        adjusted_probability = max(0.0, min(1.0, original_probability + prob_adjustment))
        
        edge_change = abs(adjusted_probability - original_probability)
        is_actionable = edge_change >= cls.MIN_EDGE_THRESHOLD
        
        return LiveAdjustment(
            adjustment_type=AdjustmentType.PLAYER_SHOTS,
            entity=player_name,
            original_projection=original_projection,
            original_probability=original_probability,
            adjusted_projection=adjusted_projection,
            adjusted_probability=adjusted_probability,
            line=line,
            direction=direction,
            intermission=snapshot.intermission_window,
            period_score_home=snapshot.home_score,
            period_score_away=snapshot.away_score,
            observed_pace_factor=shot_pace,
            is_actionable=is_actionable,
            rejection_reason=None if is_actionable else f"Edge change {edge_change:.1%} < {cls.MIN_EDGE_THRESHOLD:.1%}",
        )


# ─────────────────────────────────────────────────────────
# UNIFIED ADJUSTMENT RUNNER
# ─────────────────────────────────────────────────────────

def run_all_adjustments(
    snapshot: LiveGameSnapshot,
    pregame_bets: List[Dict],
) -> List[LiveAdjustment]:
    """
    Run all live adjustments for active bets.
    
    Args:
        snapshot: Live game state
        pregame_bets: List of dicts with:
            - type: "game_total" | "goalie_saves" | "player_shots"
            - entity: Team matchup or player name
            - line: Betting line
            - direction: "OVER" or "UNDER"
            - original_projection: Pregame projection
            - original_probability: Pregame probability
    
    Returns:
        List of LiveAdjustment objects
    """
    adjustments = []
    
    for bet in pregame_bets:
        bet_type = bet.get("type", "")
        
        if bet_type == "game_total":
            adj = GameTotalModel.adjust(
                snapshot=snapshot,
                original_projection=bet["original_projection"],
                original_probability=bet["original_probability"],
                line=bet["line"],
                direction=bet["direction"],
            )
            adjustments.append(adj)
        
        elif bet_type == "goalie_saves":
            adj = GoalieSavesModel.adjust(
                snapshot=snapshot,
                goalie_name=bet["entity"],
                goalie_team=bet.get("team", "HOME"),
                original_projection=bet["original_projection"],
                original_probability=bet["original_probability"],
                line=bet["line"],
                direction=bet["direction"],
            )
            adjustments.append(adj)
        
        elif bet_type == "player_shots":
            adj = PlayerShotsLiveModel.adjust(
                snapshot=snapshot,
                player_name=bet["entity"],
                player_team=bet.get("team", "HOME"),
                original_projection=bet["original_projection"],
                original_probability=bet["original_probability"],
                line=bet["line"],
                direction=bet["direction"],
                current_shots=bet.get("current_shots", 0),
            )
            adjustments.append(adj)
    
    return adjustments


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("INTERMISSION MODEL — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Mock intermission snapshot (high-scoring game)
    snapshot = LiveGameSnapshot(
        game_id="2024020815",
        home_team="BOS",
        away_team="DET",
        home_score=3,
        away_score=2,
        period=2,
        period_time_remaining="00:00",
        game_state=GameState.INTERMISSION_2,
        intermission_window=IntermissionWindow.SECOND,
        intermission_time_remaining=1000,
        home_shots=25,
        away_shots=18,
        home_pp_time=120,
        away_pp_time=60,
        home_pims=4,
        away_pims=6,
    )
    
    print(f"\n{snapshot}")
    
    # Calculate pace
    pace = calculate_observed_pace(snapshot)
    print(f"\nPace Analysis:")
    print(f"  Goal pace: {pace['goal_pace']:.2f}x")
    print(f"  Shot pace: {pace['shot_pace']:.2f}x")
    print(f"  Observed goals: {pace['observed_goals']} (expected: {pace['expected_goals_now']:.1f})")
    print(f"  Observed shots: {pace['observed_shots']} (expected: {pace['expected_shots_now']:.1f})")
    
    # Demo adjustments
    print("\n" + "-" * 40)
    print("Game Total Adjustment:")
    
    total_adj = GameTotalModel.adjust(
        snapshot=snapshot,
        original_projection=6.2,
        original_probability=0.52,  # OVER 6.5
        line=6.5,
        direction="OVER",
    )
    print(total_adj)
    
    print("\n" + "-" * 40)
    print("Goalie Saves Adjustment:")
    
    saves_adj = GoalieSavesModel.adjust(
        snapshot=snapshot,
        goalie_name="Swayman",
        goalie_team="HOME",
        original_projection=27.0,
        original_probability=0.58,  # OVER 26.5
        line=26.5,
        direction="OVER",
    )
    print(saves_adj)
    
    print("\n" + "-" * 40)
    print("Player SOG Adjustment:")
    
    sog_adj = PlayerShotsLiveModel.adjust(
        snapshot=snapshot,
        player_name="Pastrnak",
        player_team="HOME",
        original_projection=4.2,
        original_probability=0.62,  # OVER 3.5
        line=3.5,
        direction="OVER",
        current_shots=3,  # Already has 3 SOG
    )
    print(sog_adj)
