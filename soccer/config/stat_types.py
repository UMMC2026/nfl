"""
Soccer Stat Types Configuration
===============================
Defines stat categories, model types, and role dependencies for soccer props.

Based on PrizePicks/Underdog soccer market structure.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class StatCategory(Enum):
    """Soccer stat categories."""
    BINARY = "binary"      # 0.5 lines (goals, assists)
    COUNT = "count"        # Higher counts (passes, shots, tackles)
    COMPOSITE = "composite" # Combined stats (goal+assist)
    GOALKEEPER = "goalkeeper"


class ModelType(Enum):
    """Recommended model type for each stat."""
    BERNOULLI = "bernoulli"           # Binary outcomes
    POISSON = "poisson"               # Count data
    ZERO_INFLATED_POISSON = "zip"     # Zero-heavy count data
    NEGATIVE_BINOMIAL = "negbin"      # Overdispersed counts


class PlayerRole(Enum):
    """Soccer player roles (affects stat expectations)."""
    STRIKER = "striker"
    WINGER = "winger"
    ATTACKING_MID = "attacking_mid"
    CENTRAL_MID = "central_mid"
    DEFENSIVE_MID = "defensive_mid"
    FULLBACK = "fullback"
    CENTER_BACK = "center_back"
    GOALKEEPER = "goalkeeper"


@dataclass
class SoccerStatConfig:
    """Configuration for a soccer stat type."""
    name: str
    display_name: str
    category: StatCategory
    model_type: ModelType
    typical_lines: List[float]
    cap_probability: float  # Max probability allowed
    volatility_multiplier: float  # Penalty for high variance
    role_sensitive: bool
    zero_inflation_rate: float  # Expected % of zeros
    notes: str


# =============================================================================
# STAT TYPE DEFINITIONS
# =============================================================================

SOCCER_STATS: Dict[str, SoccerStatConfig] = {
    # BINARY PROPS (0.5 lines)
    "goals": SoccerStatConfig(
        name="goals",
        display_name="Goals",
        category=StatCategory.BINARY,
        model_type=ModelType.ZERO_INFLATED_POISSON,
        typical_lines=[0.5],
        cap_probability=0.65,  # Very high variance
        volatility_multiplier=0.85,
        role_sensitive=True,
        zero_inflation_rate=0.70,  # 70% of players score 0
        notes="Extremely volatile. Use xG + minutes. Strong blowout sensitivity."
    ),
    
    "assists": SoccerStatConfig(
        name="assists",
        display_name="Assists",
        category=StatCategory.BINARY,
        model_type=ModelType.ZERO_INFLATED_POISSON,
        typical_lines=[0.5],
        cap_probability=0.65,
        volatility_multiplier=0.85,
        role_sensitive=True,
        zero_inflation_rate=0.75,
        notes="Role-sensitive (creator vs finisher). Set piece takers favored."
    ),
    
    "goal_plus_assist": SoccerStatConfig(
        name="goal_plus_assist",
        display_name="Goal + Assist",
        category=StatCategory.COMPOSITE,
        model_type=ModelType.ZERO_INFLATED_POISSON,
        typical_lines=[0.5],
        cap_probability=0.60,  # Extra penalty for composite
        volatility_multiplier=0.80,
        role_sensitive=True,
        zero_inflation_rate=0.60,
        notes="COMPOSITE - requires SDG penalty. High correlation risk."
    ),
    
    # COUNT PROPS (higher lines)
    "shots": SoccerStatConfig(
        name="shots",
        display_name="Shots",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[1.5, 2.5, 3.5, 4.5],
        cap_probability=0.72,
        volatility_multiplier=0.92,
        role_sensitive=True,
        zero_inflation_rate=0.30,
        notes="More stable for forwards. Opponent defense matters."
    ),
    
    "shots_on_target": SoccerStatConfig(
        name="shots_on_target",
        display_name="Shots on Target (SOT)",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[0.5, 1.5, 2.5],
        cap_probability=0.70,
        volatility_multiplier=0.90,
        role_sensitive=True,
        zero_inflation_rate=0.40,
        notes="Correlates with xG. Forwards only reliable."
    ),
    
    "passes_attempted": SoccerStatConfig(
        name="passes_attempted",
        display_name="Passes Attempted",
        category=StatCategory.COUNT,
        model_type=ModelType.NEGATIVE_BINOMIAL,  # High variance
        typical_lines=[30, 40, 50, 60, 70, 80, 90],
        cap_probability=0.75,
        volatility_multiplier=0.95,
        role_sensitive=True,
        zero_inflation_rate=0.0,  # Everyone passes
        notes="Best for CBs/DMs. Formation and possession % critical."
    ),
    
    "tackles": SoccerStatConfig(
        name="tackles",
        display_name="Tackles",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[1.5, 2.5, 3.5],
        cap_probability=0.70,
        volatility_multiplier=0.88,
        role_sensitive=True,
        zero_inflation_rate=0.25,
        notes="Defensive stat. Opponent possession % affects this."
    ),
    
    "clearances": SoccerStatConfig(
        name="clearances",
        display_name="Clearances",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[2.5, 3.5, 4.5],
        cap_probability=0.70,
        volatility_multiplier=0.88,
        role_sensitive=True,
        zero_inflation_rate=0.20,
        notes="Center backs only. Increases when team is underdog."
    ),
    
    "fouls": SoccerStatConfig(
        name="fouls",
        display_name="Fouls Committed",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[1.5, 2.5],
        cap_probability=0.68,
        volatility_multiplier=0.85,
        role_sensitive=True,
        zero_inflation_rate=0.35,
        notes="Referee style matters. Often mispriced."
    ),
    
    "crosses": SoccerStatConfig(
        name="crosses",
        display_name="Crosses",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[0.5, 1.5, 2.5],
        cap_probability=0.68,
        volatility_multiplier=0.85,
        role_sensitive=True,
        zero_inflation_rate=0.45,
        notes="Wingers/fullbacks only. Game script dependent."
    ),
    
    "dribbles": SoccerStatConfig(
        name="dribbles",
        display_name="Attempted Dribbles",
        category=StatCategory.COUNT,
        model_type=ModelType.POISSON,
        typical_lines=[2.5, 3.5, 4.5, 5.5],
        cap_probability=0.70,
        volatility_multiplier=0.88,
        role_sensitive=True,
        zero_inflation_rate=0.30,
        notes="Wingers/attackers. Style-dependent."
    ),
    
    # GOALKEEPER PROPS
    "goalie_saves": SoccerStatConfig(
        name="goalie_saves",
        display_name="Goalie Saves",
        category=StatCategory.GOALKEEPER,
        model_type=ModelType.POISSON,
        typical_lines=[2.5, 3.5, 4.5],
        cap_probability=0.72,
        volatility_multiplier=0.90,
        role_sensitive=False,  # GK only
        zero_inflation_rate=0.05,
        notes="Depends on opponent xG + shots. Underdog GKs favored."
    ),
}


# =============================================================================
# ROLE-BASED STAT EXPECTATIONS
# =============================================================================

ROLE_STAT_EXPECTATIONS: Dict[str, Dict[str, float]] = {
    # Multipliers applied to league average for each role
    "striker": {
        "goals": 2.0,
        "assists": 0.8,
        "shots": 1.8,
        "shots_on_target": 1.6,
        "passes_attempted": 0.6,
        "tackles": 0.3,
        "dribbles": 1.2,
    },
    "winger": {
        "goals": 1.2,
        "assists": 1.5,
        "shots": 1.3,
        "shots_on_target": 1.2,
        "passes_attempted": 0.8,
        "crosses": 2.0,
        "dribbles": 1.8,
    },
    "attacking_mid": {
        "goals": 1.0,
        "assists": 1.8,
        "shots": 1.2,
        "passes_attempted": 1.0,
        "dribbles": 1.3,
    },
    "central_mid": {
        "goals": 0.5,
        "assists": 1.0,
        "passes_attempted": 1.2,
        "tackles": 1.2,
    },
    "defensive_mid": {
        "goals": 0.2,
        "assists": 0.5,
        "passes_attempted": 1.3,
        "tackles": 1.8,
        "clearances": 0.8,
    },
    "fullback": {
        "goals": 0.1,
        "assists": 0.8,
        "passes_attempted": 1.0,
        "tackles": 1.3,
        "crosses": 1.5,
        "clearances": 0.6,
    },
    "center_back": {
        "goals": 0.1,
        "assists": 0.2,
        "passes_attempted": 1.4,  # Ball-playing CBs high
        "tackles": 1.5,
        "clearances": 2.0,
    },
    "goalkeeper": {
        "goalie_saves": 1.0,
    },
}


# =============================================================================
# STAT NAME ALIASES (for parsing different formats)
# =============================================================================

STAT_ALIASES: Dict[str, str] = {
    # Common variations -> canonical name
    "sot": "shots_on_target",
    "shots on target": "shots_on_target",
    "passes": "passes_attempted",
    "passes attempted": "passes_attempted",
    "pass attempts": "passes_attempted",
    "goal + assist": "goal_plus_assist",
    "g+a": "goal_plus_assist",
    "saves": "goalie_saves",
    "goalkeeper saves": "goalie_saves",
    "attempted dribbles": "dribbles",
    "successful dribbles": "dribbles",
    "fouls committed": "fouls",
}


def normalize_stat_name(stat: str) -> str:
    """Normalize stat name to canonical form."""
    stat_lower = stat.lower().strip()
    return STAT_ALIASES.get(stat_lower, stat_lower.replace(" ", "_"))


def get_stat_config(stat: str) -> Optional[SoccerStatConfig]:
    """Get configuration for a stat type."""
    normalized = normalize_stat_name(stat)
    return SOCCER_STATS.get(normalized)


def get_role_multiplier(role: str, stat: str) -> float:
    """Get role-based multiplier for a stat."""
    role_lower = role.lower().replace(" ", "_").replace("-", "_")
    stat_normalized = normalize_stat_name(stat)
    
    if role_lower in ROLE_STAT_EXPECTATIONS:
        return ROLE_STAT_EXPECTATIONS[role_lower].get(stat_normalized, 1.0)
    return 1.0


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Soccer Stat Types Configuration")
    print("=" * 50)
    
    for name, config in SOCCER_STATS.items():
        print(f"\n{config.display_name}:")
        print(f"  Category: {config.category.value}")
        print(f"  Model: {config.model_type.value}")
        print(f"  Lines: {config.typical_lines}")
        print(f"  Cap: {config.cap_probability*100:.0f}%")
        print(f"  Zero-inflation: {config.zero_inflation_rate*100:.0f}%")
