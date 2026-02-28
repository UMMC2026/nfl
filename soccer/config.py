# Allow import * to expose SOCCER_REGISTRY and other config symbols
__all__ = [
    "SOCCER_REGISTRY",
    "SOCCER_MARKETS",
    "CONFIDENCE_CAPS",
    "GLOBAL_CONFIDENCE_CAP",
    "TIER_THRESHOLDS",
    "SoccerMarketPolicy",
    "SoccerHardGates",
    "SoccerRiskControls",
    "LEAGUE_TIERS",
    "ENABLED_LEAGUES",
    "HOME_ADV_FACTOR",
]
"""soccer/config.py

Soccer Configuration — v1.0

CRITICAL:
- Soccer is low-scoring and high-variance.
- Draw probability must be explicitly modeled.
- v1.0 blocks player props, corners, cards, SGP, and live.
- No scraping. Odds/lines are manual input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


SOCCER_REGISTRY = {
    "sport": "SOCCER",
    "enabled": False,  # RESEARCH until calibration/backtest
    "status": "RESEARCH",
    "version": "1.0.0",
    "frozen": False,
}


LEAGUE_TIERS: Dict[str, List[str]] = {
    "TIER_1": ["EPL", "UCL", "UEL"],
    "TIER_2": ["LALIGA", "BUNDESLIGA", "SERIE_A", "LIGUE_1"],
    "TIER_3": ["MLS", "WORLD_CUP", "EUROS", "COPA_AMERICA"],
}

ENABLED_LEAGUES: List[str] = list(LEAGUE_TIERS["TIER_1"])


# ------------------------------
# Modeling + caps
# ------------------------------
# Simple home advantage multiplier on goal intensity
HOME_ADV_FACTOR = 1.12

# Confidence caps (strict)
GLOBAL_CONFIDENCE_CAP = 0.78
CONFIDENCE_CAPS = {
    "match_result": 0.72,
    "over_under": 0.75,
    "btts": 0.72,
    "team_total": 0.70,
    "asian_handicap": 0.72,
}

# Tier thresholds (strict)
TIER_THRESHOLDS = {
    "SLAM": 0.78,
    "STRONG": 0.68,
    "LEAN": 0.60,
    "NO_PLAY": 0.0,
}


# ------------------------------
# Allowed markets (v1.0)
# ------------------------------
@dataclass
class SoccerMarketPolicy:
    approved: List[str] = field(default_factory=list)
    blocked: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.approved = [
            "match_result",     # 1X2
            "asian_handicap",
            "over_under",       # totals
            "btts",
            "team_total",
        ]
        self.blocked = [
            "player_goals",
            "player_shots",
            "player_assists",
            "corners",
            "cards",
            "sgp",
            "live",
        ]


SOCCER_MARKETS = SoccerMarketPolicy()


# ------------------------------
# HARD gates
# ------------------------------
@dataclass
class SoccerHardGates:
    # S1: competition validity
    enabled_leagues: List[str] = field(default_factory=lambda: list(ENABLED_LEAGUES))

    # S2: data sufficiency
    min_team_matches: int = 20
    min_recent_matches: int = 10
    min_xg_sources: int = 2

    # S3: match state
    block_live: bool = True

    # S4: line sanity
    require_decimal_odds: bool = True
    normalize_asian: bool = True


SOCCER_GATES = SoccerHardGates()


# ------------------------------
# Risk controls
# ------------------------------
@dataclass
class SoccerRiskControls:
    max_daily_exposure_pct: float = 0.20
    max_primary_per_match: int = 1
    allow_correlated_same_match: bool = False

    # volatility penalties
    red_card_conf_penalty: float = 0.15
    early_goal_vol_penalty: float = 0.10


SOCCER_RISK = SoccerRiskControls()


DATA_SOURCES = {
    "primary": "manual",
    "secondary": "manual",
    "odds": "manual",
}
