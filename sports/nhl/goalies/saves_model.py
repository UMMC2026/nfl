"""
GOALIE SAVES MODEL — NHL v1.1 Extension
========================================

Market: Goalie Saves (OVER/UNDER)
Pre-game only. Starter must be CONFIRMED.

Model:
  Expected Saves = Shots_Against × (1 - Goals / Shots)
  Shots_Against ~ Poisson(λ_shots)

Gates (additive to v1.0):
  S1: Goalie CONFIRMED (≥2 sources) → else ABORT
  S2: <5 recent starts → NO PLAY
  S3: Opponent shots <26/gm → cap prob ≤60%
  S4: |model - implied| < 3% → NO EDGE
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class SavesTier(Enum):
    """Stricter tiers for goalie saves props."""
    STRONG = "STRONG"   # 63-67%
    LEAN = "LEAN"       # 58-62%
    NO_PLAY = "NO_PLAY" # <58%


# ─────────────────────────────────────────────────────────
# CONFIDENCE CAPS (stricter than game model)
# ─────────────────────────────────────────────────────────
SAVES_TIER_THRESHOLDS = {
    SavesTier.STRONG: (0.63, 0.67),
    SavesTier.LEAN: (0.58, 0.62),
    SavesTier.NO_PLAY: (0.0, 0.579),
}

# Minimum shots against to qualify for modeling
MIN_OPP_SHOTS_THRESHOLD = 26.0

# Minimum starts for goalie to be modeled
MIN_GOALIE_STARTS = 5

# Edge threshold (model vs implied)
MIN_EDGE_THRESHOLD = 0.03

# Maximum probability cap for low-shot opponents
LOW_SHOT_OPP_CAP = 0.60


@dataclass
class GoalieProfile:
    """Goalie statistics for saves modeling."""
    name: str
    team: str
    
    # Core stats
    games_started: int
    save_percentage: float      # Career/season SV%
    saves_per_game: float       # Average saves per start
    
    # Advanced
    gsaa: float = 0.0           # Goals Saved Above Average
    high_danger_sv_pct: float = 0.85  # High-danger save %
    
    # Confirmation status
    confirmed: bool = False
    confirmation_sources: int = 0
    
    @property
    def meets_start_threshold(self) -> bool:
        return self.games_started >= MIN_GOALIE_STARTS


@dataclass
class OpponentProfile:
    """Opponent shooting statistics."""
    team: str
    shots_per_game: float       # Shots on goal per game
    xg_per_game: float          # Expected goals per game
    shooting_pct: float         # Shooting percentage
    
    # Breakdown
    high_danger_chances: float = 10.0
    medium_danger_chances: float = 12.0
    
    @property
    def is_low_volume(self) -> bool:
        """Opponent generates fewer than threshold shots."""
        return self.shots_per_game < MIN_OPP_SHOTS_THRESHOLD


@dataclass
class SavesProjection:
    """Model projection for goalie saves."""
    goalie: str
    opponent: str
    
    # Core projections
    expected_shots_against: float
    expected_saves: float
    expected_goals_against: float
    
    # Distribution parameters
    lambda_shots: float         # Poisson parameter for shots
    save_std: float             # Standard deviation
    
    # Line analysis
    line: float                 # Underdog/PrizePicks line
    over_prob: float
    under_prob: float
    
    # Edge analysis
    model_prob: float           # Probability of recommended side
    implied_prob: float
    edge: float
    direction: str              # "OVER" or "UNDER"
    
    # Tier assignment
    tier: SavesTier
    playable: bool
    
    # Risk flags
    risk_flags: list = None
    
    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []
    
    def to_dict(self) -> Dict:
        return {
            "goalie": self.goalie,
            "opponent": self.opponent,
            "market": "Goalie Saves",
            "line": self.line,
            "direction": self.direction,
            "expected_saves": round(self.expected_saves, 1),
            "expected_shots": round(self.expected_shots_against, 1),
            "over_prob": round(self.over_prob, 4),
            "under_prob": round(self.under_prob, 4),
            "model_prob": round(self.model_prob, 4),
            "implied_prob": round(self.implied_prob, 4),
            "edge": round(self.edge, 4),
            "tier": self.tier.value,
            "playable": self.playable,
            "risk_flags": self.risk_flags,
        }


def compute_expected_saves(
    goalie: GoalieProfile,
    opponent: OpponentProfile,
) -> Tuple[float, float, float]:
    """
    Compute expected saves projection.
    
    Returns:
        (expected_shots, expected_saves, expected_goals_against)
    """
    # Base shots against (Poisson λ)
    lambda_shots = opponent.shots_per_game
    
    # Adjust for goalie quality (better goalies face harder shots due to game state)
    goalie_quality_adj = (goalie.save_percentage - 0.905) * -5.0  # Slight reduction for elite goalies
    lambda_shots = lambda_shots + goalie_quality_adj
    
    # Expected saves = shots × SV%
    expected_saves = lambda_shots * goalie.save_percentage
    
    # Expected goals against
    expected_ga = lambda_shots * (1 - goalie.save_percentage)
    
    return lambda_shots, expected_saves, expected_ga


def check_saves_gates(
    goalie: GoalieProfile,
    opponent: OpponentProfile,
    model_prob: float,
    implied_prob: float,
) -> Tuple[bool, list]:
    """
    Check all saves-specific gates.
    
    Returns:
        (passes_all_gates, risk_flags)
    """
    risk_flags = []
    playable = True
    
    # GATE S1: Goalie CONFIRMED (inherits from v1.0)
    if not goalie.confirmed or goalie.confirmation_sources < 2:
        logger.warning(f"GATE S1 FAIL: {goalie.name} not confirmed (sources={goalie.confirmation_sources})")
        risk_flags.append("GOALIE_NOT_CONFIRMED")
        playable = False
    
    # GATE S2: <5 recent starts → NO PLAY
    if not goalie.meets_start_threshold:
        logger.warning(f"GATE S2 FAIL: {goalie.name} has <5 starts ({goalie.games_started})")
        risk_flags.append("INSUFFICIENT_STARTS")
        playable = False
    
    # GATE S3: Opponent shots <26/gm → cap prob ≤60%
    if opponent.is_low_volume:
        logger.info(f"GATE S3 CAP: {opponent.team} is low-shot team ({opponent.shots_per_game:.1f}/gm)")
        risk_flags.append("LOW_SHOT_OPPONENT")
        # Don't reject, but cap applied in tier assignment
    
    # GATE S4: |model - implied| < 3% → NO EDGE
    edge = abs(model_prob - implied_prob)
    if edge < MIN_EDGE_THRESHOLD:
        logger.info(f"GATE S4 FAIL: Edge too small ({edge:.3f} < {MIN_EDGE_THRESHOLD})")
        risk_flags.append("INSUFFICIENT_EDGE")
        playable = False
    
    return playable, risk_flags


def assign_saves_tier(
    probability: float,
    opponent: OpponentProfile,
) -> SavesTier:
    """
    Assign tier with saves-specific caps.
    
    Note: If opponent is low-volume, cap probability at 60%.
    """
    # Apply low-shot opponent cap
    if opponent.is_low_volume:
        probability = min(probability, LOW_SHOT_OPP_CAP)
    
    # Assign tier
    if 0.63 <= probability <= 0.67:
        return SavesTier.STRONG
    elif 0.58 <= probability < 0.63:
        return SavesTier.LEAN
    else:
        return SavesTier.NO_PLAY


def project_goalie_saves(
    goalie: GoalieProfile,
    opponent: OpponentProfile,
    line: float,
    implied_prob: float = 0.50,
) -> SavesProjection:
    """
    Full projection pipeline for goalie saves prop.
    
    Args:
        goalie: Goalie statistics
        opponent: Opponent shooting profile
        line: The saves line (e.g., 28.5)
        implied_prob: Market implied probability (default 50%)
    
    Returns:
        SavesProjection with all analysis
    """
    # Step 1: Compute expectations
    lambda_shots, expected_saves, expected_ga = compute_expected_saves(goalie, opponent)
    
    # Step 2: Simulate to get over/under probs (see saves_simulate.py)
    # For now, use normal approximation
    from scipy.stats import norm
    
    # Saves standard deviation (sqrt of Poisson variance adjusted)
    save_std = (lambda_shots * goalie.save_percentage * (1 - goalie.save_percentage)) ** 0.5
    
    # Adjust std for goalie consistency
    if goalie.gsaa > 5:
        save_std *= 0.92  # Elite goalies are more consistent
    elif goalie.gsaa < -5:
        save_std *= 1.08  # Struggling goalies more volatile
    
    # Over/under probabilities
    z_score = (line - expected_saves) / save_std if save_std > 0 else 0
    under_prob = norm.cdf(z_score)
    over_prob = 1 - under_prob
    
    # Determine direction
    if over_prob > under_prob:
        direction = "OVER"
        model_prob = over_prob
    else:
        direction = "UNDER"
        model_prob = under_prob
    
    # Edge calculation
    edge = model_prob - implied_prob
    
    # Step 3: Check gates
    passes_gates, risk_flags = check_saves_gates(
        goalie, opponent, model_prob, implied_prob
    )
    
    # Step 4: Assign tier
    tier = assign_saves_tier(model_prob, opponent)
    
    # Playable = passes gates AND tier is not NO_PLAY
    playable = passes_gates and tier != SavesTier.NO_PLAY
    
    return SavesProjection(
        goalie=goalie.name,
        opponent=opponent.team,
        expected_shots_against=lambda_shots,
        expected_saves=expected_saves,
        expected_goals_against=expected_ga,
        lambda_shots=lambda_shots,
        save_std=save_std,
        line=line,
        over_prob=over_prob,
        under_prob=under_prob,
        model_prob=model_prob,
        implied_prob=implied_prob,
        edge=edge,
        direction=direction,
        tier=tier,
        playable=playable,
        risk_flags=risk_flags,
    )


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Demo goalie
    swayman = GoalieProfile(
        name="Jeremy Swayman",
        team="BOS",
        games_started=35,
        save_percentage=0.918,
        saves_per_game=26.8,
        gsaa=12.4,
        high_danger_sv_pct=0.862,
        confirmed=True,
        confirmation_sources=2,
    )
    
    # Demo opponent
    nyr = OpponentProfile(
        team="NYR",
        shots_per_game=31.2,
        xg_per_game=2.85,
        shooting_pct=0.096,
    )
    
    # Project saves
    projection = project_goalie_saves(
        goalie=swayman,
        opponent=nyr,
        line=27.5,
        implied_prob=0.52,
    )
    
    print("\n" + "=" * 60)
    print("GOALIE SAVES PROJECTION — NHL v1.1")
    print("=" * 60)
    for k, v in projection.to_dict().items():
        print(f"  {k}: {v}")
