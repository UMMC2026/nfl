"""
Soccer Configuration — Tier Thresholds & Market Settings
=========================================================
Soccer is HIGH VARIANCE for goals/assists, MODERATE for shots/passes.

Key Markets:
- Shots: Poisson distribution (λ = player avg shots/game)
- Shots on Target: Poisson (λ = player avg SOT/game)  
- Goals: Zero-Inflated Poisson (most players score 0)
- Assists: Zero-Inflated Poisson (rare event)
- Passes: Normal distribution (high volume, stable)
- Tackles: Poisson (defensive stat)
- Saves (GK): Poisson (depends on opponent shots)
"""

from dataclasses import dataclass
from typing import Dict, Optional

# =============================================================================
# TIER THRESHOLDS — Soccer-specific (NO SLAM due to goal volatility)
# =============================================================================
SOCCER_TIERS = {
    "SLAM": None,      # DISABLED — Goals/assists too volatile
    "STRONG": 0.70,    # 70%+ confidence
    "LEAN": 0.58,      # 58%+ confidence  
    "SPEC": 0.50,      # 50%+ speculative
    "AVOID": 0.0       # Below 50%
}

def get_tier(probability: float) -> str:
    """Get tier label from probability."""
    if probability >= 0.70:
        return "STRONG"
    elif probability >= 0.58:
        return "LEAN"
    elif probability >= 0.50:
        return "SPEC"
    else:
        return "AVOID"

# =============================================================================
# MARKET CONFIDENCE CAPS — Maximum allowed confidence per market type
# =============================================================================
MARKET_CONFIDENCE_CAPS = {
    # High-volume stats (more predictable)
    "passes": 0.82,
    "passes_completed": 0.80,
    "touches": 0.80,
    
    # Shots (moderate predictability)
    "shots": 0.75,
    "shots_on_target": 0.72,
    
    # Goals/Assists (high variance — CAPPED LOW)
    "goals": 0.60,           # Goals are rare events
    "assists": 0.58,         # Assists even rarer
    "goal_contributions": 0.55,  # Goals + Assists
    
    # Defensive stats
    "tackles": 0.70,
    "interceptions": 0.68,
    "clearances": 0.72,
    "blocks": 0.65,
    
    # Goalkeeper
    "saves": 0.70,
    "clean_sheet": 0.55,     # Binary outcome
    
    # Combo markets
    "shots_assists": 0.65,
    "tackles_interceptions": 0.68,
}

# =============================================================================
# STAT DISTRIBUTIONS — Which distribution to use per market
# =============================================================================
STAT_DISTRIBUTIONS = {
    # Poisson (count data, discrete)
    "shots": "poisson",
    "shots_on_target": "poisson",
    "tackles": "poisson",
    "interceptions": "poisson",
    "clearances": "poisson",
    "blocks": "poisson",
    "saves": "poisson",
    "fouls_committed": "poisson",
    "fouls_drawn": "poisson",
    "corners": "poisson",
    "offsides": "poisson",
    
    # Zero-Inflated Poisson (rare events with many zeros)
    "goals": "zero_inflated_poisson",
    "assists": "zero_inflated_poisson",
    "goal_contributions": "zero_inflated_poisson",
    
    # Normal (high-volume continuous-ish)
    "passes": "normal",
    "passes_completed": "normal",
    "touches": "normal",
    "pass_accuracy": "normal",
    
    # Binary
    "clean_sheet": "binary",
    "anytime_scorer": "binary",
}

# =============================================================================
# LEAGUE ADJUSTMENTS — Scoring rates vary by league
# =============================================================================
LEAGUE_ADJUSTMENTS = {
    "premier_league": {
        "goals_per_game": 2.85,
        "shots_per_game": 24.5,
        "pace_factor": 1.05,  # Fast-paced
    },
    "la_liga": {
        "goals_per_game": 2.55,
        "shots_per_game": 23.0,
        "pace_factor": 0.95,  # More possession-based
    },
    "bundesliga": {
        "goals_per_game": 3.15,
        "shots_per_game": 25.0,
        "pace_factor": 1.10,  # Highest scoring
    },
    "serie_a": {
        "goals_per_game": 2.65,
        "shots_per_game": 24.0,
        "pace_factor": 0.98,
    },
    "ligue_1": {
        "goals_per_game": 2.75,
        "shots_per_game": 23.5,
        "pace_factor": 1.00,
    },
    "mls": {
        "goals_per_game": 2.95,
        "shots_per_game": 26.0,
        "pace_factor": 1.02,
    },
    "champions_league": {
        "goals_per_game": 2.90,
        "shots_per_game": 25.0,
        "pace_factor": 1.08,  # High-intensity knockout
    },
}

# =============================================================================
# POSITION ADJUSTMENTS — Expected stats by position
# =============================================================================
POSITION_BASELINES = {
    "striker": {
        "shots": 3.2,
        "shots_on_target": 1.4,
        "goals": 0.45,
        "assists": 0.15,
        "passes": 25,
        "tackles": 0.5,
    },
    "winger": {
        "shots": 2.0,
        "shots_on_target": 0.8,
        "goals": 0.25,
        "assists": 0.25,
        "passes": 35,
        "tackles": 1.2,
    },
    "attacking_mid": {
        "shots": 2.2,
        "shots_on_target": 0.9,
        "goals": 0.20,
        "assists": 0.30,
        "passes": 50,
        "tackles": 1.5,
    },
    "central_mid": {
        "shots": 1.2,
        "shots_on_target": 0.4,
        "goals": 0.08,
        "assists": 0.15,
        "passes": 55,
        "tackles": 2.5,
    },
    "defensive_mid": {
        "shots": 0.8,
        "shots_on_target": 0.3,
        "goals": 0.05,
        "assists": 0.10,
        "passes": 50,
        "tackles": 3.5,
        "interceptions": 2.0,
    },
    "fullback": {
        "shots": 0.5,
        "shots_on_target": 0.2,
        "goals": 0.03,
        "assists": 0.12,
        "passes": 45,
        "tackles": 2.8,
        "interceptions": 1.5,
    },
    "centerback": {
        "shots": 0.4,
        "shots_on_target": 0.15,
        "goals": 0.04,
        "assists": 0.03,
        "passes": 55,
        "tackles": 2.0,
        "interceptions": 1.8,
        "clearances": 4.5,
    },
    "goalkeeper": {
        "saves": 3.0,
        "passes": 30,
        "clean_sheet": 0.35,  # ~35% of games
    },
}

# =============================================================================
# MONTE CARLO SETTINGS
# =============================================================================
MC_SIMULATIONS = 10000
MC_RANDOM_SEED = None  # Set for reproducibility in testing

# =============================================================================
# STAT NAME NORMALIZATION
# =============================================================================
STAT_NORMALIZE = {
    "shot": "shots",
    "sog": "shots_on_target",
    "shots on goal": "shots_on_target",
    "shots on target": "shots_on_target",
    "goal": "goals",
    "assist": "assists",
    "g+a": "goal_contributions",
    "goals+assists": "goal_contributions",
    "pass": "passes",
    "passes completed": "passes_completed",
    "tackle": "tackles",
    "interception": "interceptions",
    "clearance": "clearances",
    "block": "blocks",
    "save": "saves",
    "foul": "fouls_committed",
    "fouls": "fouls_committed",
}

def normalize_stat(stat: str) -> str:
    """Normalize stat name to canonical form."""
    stat_lower = stat.lower().strip()
    return STAT_NORMALIZE.get(stat_lower, stat_lower)


@dataclass
class SoccerConfig:
    """Runtime configuration for soccer analysis."""
    league: str = "premier_league"
    mc_simulations: int = MC_SIMULATIONS
    min_games_required: int = 5
    confidence_floor: float = 0.50
    
    def get_league_adjustment(self) -> dict:
        """Get league-specific adjustments."""
        return LEAGUE_ADJUSTMENTS.get(self.league.lower(), LEAGUE_ADJUSTMENTS["premier_league"])
