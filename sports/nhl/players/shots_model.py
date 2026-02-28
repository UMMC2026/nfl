"""
PLAYER SHOTS-ON-GOAL MODEL — NHL v2.0 Module
=============================================

Player-level SOG props modeling using Poisson distribution.

Model:
    Shots ~ Poisson(λ_player)
    λ_player = TOI × Shot_Rate_per_min × Opponent_Suppression × Game_Script

Player Gates:
- P1: TOI <12 min → NO PLAY
- P2: L10 shot CV >45% → cap prob 60%
- P3: Line movement adverse → NO PLAY

Tier Caps (stricter than game-level):
- STRONG: 62–66%
- LEAN: 58–61%
- NO PLAY: <58%
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────

# Gate thresholds
MIN_TOI_MINUTES = 12.0
MAX_SHOT_CV = 0.45
MIN_EDGE_PCT = 0.02

# Tier thresholds (stricter than game-level)
class SOGTier(str, Enum):
    STRONG = "STRONG"   # 62-66%
    LEAN = "LEAN"       # 58-61%
    NO_PLAY = "NO_PLAY" # <58%

SOG_TIER_THRESHOLDS = {
    SOGTier.STRONG: (0.62, 0.66),
    SOGTier.LEAN: (0.58, 0.61),
    SOGTier.NO_PLAY: (0.0, 0.579),
}

# High-CV player cap
HIGH_CV_PROB_CAP = 0.60

# Game script multipliers
GAME_SCRIPT_MULTIPLIERS = {
    "trailing": 1.15,       # Team losing → more shots
    "leading_late": 0.85,   # Protecting lead → fewer shots
    "close": 1.00,          # Neutral
    "tied": 1.00,           # Neutral
}


@dataclass
class PlayerProfile:
    """Player shooting statistics."""
    name: str
    team: str
    position: str           # F (forward) or D (defenseman)
    
    # Time on ice
    avg_toi: float          # Average minutes per game
    toi_std: float          # TOI standard deviation
    
    # Shooting stats (L10 games)
    l10_shots_per_game: float
    l10_shot_std: float     # Standard deviation
    l10_shot_rate: float    # Shots per 60 min
    
    # Season totals
    season_shots: int
    season_games: int
    
    # Quality metrics
    shooting_pct: float     # Goals / Shots
    ixg_per_60: float       # Individual xG per 60
    
    # Line information
    line: int = 1           # 1-4 for forwards, 1-3 for D
    pp_unit: Optional[int] = None  # 1, 2, or None
    
    @property
    def coefficient_of_variation(self) -> float:
        """CV = std / mean (volatility measure)."""
        if self.l10_shots_per_game == 0:
            return 1.0
        return self.l10_shot_std / self.l10_shots_per_game
    
    @property
    def is_high_volatility(self) -> bool:
        """Check if player has high shot variance."""
        return self.coefficient_of_variation > MAX_SHOT_CV
    
    @property
    def meets_toi_threshold(self) -> bool:
        """Check if player meets minimum TOI."""
        return self.avg_toi >= MIN_TOI_MINUTES
    
    @property
    def expected_shots_baseline(self) -> float:
        """Baseline expected shots from rate."""
        return self.l10_shot_rate * (self.avg_toi / 60)


@dataclass
class OpponentDefense:
    """Opponent defensive profile for shot suppression."""
    team: str
    
    # Shot suppression
    shots_against_per_game: float
    shots_against_rank: int         # 1-32 (1 = best defense)
    
    # Quality suppression
    xga_per_60: float
    high_danger_chances_against: float
    
    # By position
    shots_allowed_vs_forwards: float
    shots_allowed_vs_defensemen: float
    
    @property
    def suppression_factor(self) -> float:
        """
        Shot suppression factor (1.0 = average).
        >1 = allows more shots, <1 = suppresses shots.
        """
        league_avg_sa = 30.5
        return self.shots_against_per_game / league_avg_sa


@dataclass
class SOGProjection:
    """Player shots-on-goal projection."""
    player: str
    opponent: str
    
    # Inputs
    baseline_shots: float
    toi_projection: float
    suppression_factor: float
    game_script_factor: float
    
    # Lambda (Poisson parameter)
    lambda_shots: float
    
    # Line analysis
    line: float
    over_prob: float
    under_prob: float
    
    # Edge
    model_prob: float
    implied_prob: float
    edge: float
    direction: str          # "OVER" or "UNDER"
    
    # Tier
    tier: SOGTier
    playable: bool
    
    # Risk flags
    risk_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "player": self.player,
            "opponent": self.opponent,
            "market": "Player SOG",
            "line": self.line,
            "direction": self.direction,
            "lambda_shots": round(self.lambda_shots, 2),
            "toi_projection": round(self.toi_projection, 1),
            "suppression_factor": round(self.suppression_factor, 3),
            "over_prob": round(self.over_prob, 4),
            "under_prob": round(self.under_prob, 4),
            "model_prob": round(self.model_prob, 4),
            "implied_prob": round(self.implied_prob, 4),
            "edge": round(self.edge, 4),
            "tier": self.tier.value,
            "playable": self.playable,
            "risk_flags": self.risk_flags,
        }


# ─────────────────────────────────────────────────────────
# SHOTS MODEL
# ─────────────────────────────────────────────────────────

class PlayerShotsModel:
    """
    Player shots-on-goal projection model.
    
    Uses Poisson distribution with λ derived from:
    - TOI projection
    - Shot rate per minute
    - Opponent suppression
    - Game script adjustment
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_lambda(
        self,
        player: PlayerProfile,
        opponent: OpponentDefense,
        game_script: str = "close",
        toi_adjustment: float = 0.0,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate Poisson λ for player shots.
        
        Args:
            player: Player shooting profile
            opponent: Opponent defensive profile
            game_script: Expected game state
            toi_adjustment: Manual TOI adjustment (+ or -)
        
        Returns:
            (lambda, components_dict)
        """
        # Base TOI projection
        toi_proj = player.avg_toi + toi_adjustment
        
        # Base shots from rate
        base_shots = player.l10_shot_rate * (toi_proj / 60)
        
        # Opponent suppression
        # Adjust based on position
        if player.position == "D":
            suppression = opponent.shots_allowed_vs_defensemen / 10.0  # Normalize
        else:
            suppression = opponent.shots_allowed_vs_forwards / 20.0  # Normalize
        
        # Use overall suppression factor
        suppression = opponent.suppression_factor
        
        # Game script
        script_mult = GAME_SCRIPT_MULTIPLIERS.get(game_script, 1.0)
        
        # PP boost (if on PP unit)
        pp_boost = 1.0
        if player.pp_unit is not None:
            pp_boost = 1.10 if player.pp_unit == 1 else 1.05
        
        # Calculate λ
        lambda_shots = base_shots * suppression * script_mult * pp_boost
        
        components = {
            "toi_projection": toi_proj,
            "base_shots": base_shots,
            "suppression_factor": suppression,
            "game_script_factor": script_mult,
            "pp_boost": pp_boost,
        }
        
        return lambda_shots, components
    
    def check_gates(
        self,
        player: PlayerProfile,
        model_prob: float,
        implied_prob: float,
        line_movement: Optional[float] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Check player-level gates.
        
        Returns:
            (passes_gates, risk_flags)
        """
        risk_flags = []
        playable = True
        
        # GATE P1: Minimum TOI
        if not player.meets_toi_threshold:
            self.logger.info(f"P1 GATE FAIL: {player.name} TOI {player.avg_toi:.1f} < {MIN_TOI_MINUTES}")
            risk_flags.append("LOW_TOI")
            playable = False
        
        # GATE P2: High volatility
        if player.is_high_volatility:
            self.logger.info(f"P2 GATE: {player.name} CV {player.coefficient_of_variation:.2f} > {MAX_SHOT_CV}")
            risk_flags.append("HIGH_SHOT_VARIANCE")
            # Don't reject, but cap probability
        
        # GATE P3: Line movement (if provided)
        if line_movement is not None and line_movement < -0.5:
            # Line moved against our side significantly
            self.logger.info(f"P3 GATE FAIL: Adverse line movement {line_movement}")
            risk_flags.append("ADVERSE_LINE_MOVEMENT")
            playable = False
        
        # Minimum edge check
        edge = abs(model_prob - implied_prob)
        if edge < MIN_EDGE_PCT:
            risk_flags.append("INSUFFICIENT_EDGE")
            playable = False
        
        return playable, risk_flags
    
    def assign_tier(
        self,
        probability: float,
        player: PlayerProfile,
    ) -> SOGTier:
        """
        Assign tier with player-specific caps.
        """
        # High volatility cap
        if player.is_high_volatility:
            probability = min(probability, HIGH_CV_PROB_CAP)
        
        # Assign tier
        if 0.62 <= probability <= 0.66:
            return SOGTier.STRONG
        elif 0.58 <= probability < 0.62:
            return SOGTier.LEAN
        else:
            return SOGTier.NO_PLAY


def project_player_sog(
    player: PlayerProfile,
    opponent: OpponentDefense,
    line: float,
    implied_prob: float = 0.50,
    game_script: str = "close",
) -> SOGProjection:
    """
    Full projection for player SOG prop.
    
    Args:
        player: Player shooting profile
        opponent: Opponent defense profile
        line: SOG line (e.g., 3.5)
        implied_prob: Market implied probability
        game_script: Expected game state
    
    Returns:
        SOGProjection with full analysis
    """
    from scipy.stats import poisson
    
    model = PlayerShotsModel()
    
    # Calculate λ
    lambda_shots, components = model.calculate_lambda(player, opponent, game_script)
    
    # Poisson probabilities
    over_prob = 1 - poisson.cdf(line, lambda_shots)
    under_prob = poisson.cdf(line - 1, lambda_shots)  # Strictly under
    
    # Determine direction
    if over_prob > under_prob:
        direction = "OVER"
        model_prob = over_prob
    else:
        direction = "UNDER"
        model_prob = under_prob
    
    # Edge
    edge = model_prob - implied_prob
    
    # Check gates
    passes_gates, risk_flags = model.check_gates(player, model_prob, implied_prob)
    
    # Assign tier
    tier = model.assign_tier(model_prob, player)
    
    # Playable
    playable = passes_gates and tier != SOGTier.NO_PLAY
    
    return SOGProjection(
        player=player.name,
        opponent=opponent.team,
        baseline_shots=components["base_shots"],
        toi_projection=components["toi_projection"],
        suppression_factor=components["suppression_factor"],
        game_script_factor=components["game_script_factor"],
        lambda_shots=lambda_shots,
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
    
    print("\n" + "=" * 60)
    print("PLAYER SHOTS MODEL — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Demo player: High-volume shooter
    pastrnak = PlayerProfile(
        name="David Pastrnak",
        team="BOS",
        position="F",
        avg_toi=20.5,
        toi_std=2.1,
        l10_shots_per_game=4.2,
        l10_shot_std=1.5,
        l10_shot_rate=12.3,
        season_shots=285,
        season_games=68,
        shooting_pct=0.142,
        ixg_per_60=1.12,
        line=1,
        pp_unit=1,
    )
    
    # Opponent: Below-average defense
    opponent = OpponentDefense(
        team="DET",
        shots_against_per_game=32.8,
        shots_against_rank=25,
        xga_per_60=2.85,
        high_danger_chances_against=12.4,
        shots_allowed_vs_forwards=22.5,
        shots_allowed_vs_defensemen=10.3,
    )
    
    # Project
    projection = project_player_sog(
        player=pastrnak,
        opponent=opponent,
        line=3.5,
        implied_prob=0.52,
        game_script="close",
    )
    
    print(f"\nPlayer: {projection.player}")
    print(f"vs: {projection.opponent}")
    print(f"\nInputs:")
    print(f"  TOI projection: {projection.toi_projection:.1f} min")
    print(f"  Suppression: {projection.suppression_factor:.3f}")
    print(f"  Game script: {projection.game_script_factor:.2f}")
    print(f"\nλ (expected shots): {projection.lambda_shots:.2f}")
    print(f"\nLine: {projection.line}")
    print(f"  OVER: {projection.over_prob:.1%}")
    print(f"  UNDER: {projection.under_prob:.1%}")
    print(f"\nRecommendation: {projection.direction}")
    print(f"Model prob: {projection.model_prob:.1%}")
    print(f"Implied prob: {projection.implied_prob:.1%}")
    print(f"Edge: {projection.edge:+.1%}")
    print(f"\nTier: {projection.tier.value}")
    print(f"Playable: {projection.playable}")
    print(f"Risk flags: {projection.risk_flags}")
    
    # Demo: Low TOI player (should fail P1)
    print("\n" + "-" * 40)
    print("Testing P1 Gate (Low TOI):")
    
    low_toi_player = PlayerProfile(
        name="4th Line Grinder",
        team="BOS",
        position="F",
        avg_toi=8.5,
        toi_std=2.0,
        l10_shots_per_game=0.8,
        l10_shot_std=0.9,
        l10_shot_rate=5.6,
        season_shots=42,
        season_games=55,
        shooting_pct=0.095,
        ixg_per_60=0.35,
        line=4,
        pp_unit=None,
    )
    
    proj2 = project_player_sog(
        player=low_toi_player,
        opponent=opponent,
        line=0.5,
        implied_prob=0.52,
    )
    
    print(f"Player: {proj2.player}")
    print(f"TOI: {low_toi_player.avg_toi:.1f} min")
    print(f"Playable: {proj2.playable}")
    print(f"Risk flags: {proj2.risk_flags}")
