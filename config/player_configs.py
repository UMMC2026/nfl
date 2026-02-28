"""
FUOOM PLAYER CONFIGURATION SYSTEM v1.0
======================================
SOP v2.1 Compliant - Truth-Enforced Player Archetypes

10 Star Players with Distinct Statistical Profiles
Designed to address the 28% overconfidence calibration issue
by treating different player archetypes appropriately.

Author: FUOOM Data Analysis Team
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal
from enum import Enum
import json


# =============================================================================
# ARCHETYPE DEFINITIONS
# =============================================================================

class PlayerArchetype(Enum):
    """Player statistical behavior archetypes"""
    HIGH_FLOOR_STAR = "high_floor_star"           # Consistent superstars
    STREAKY_SCORER = "streaky_scorer"             # Hot/cold volume scorers
    PLAYMAKING_GUARD = "playmaking_guard"         # Assist-first point guards
    TWO_WAY_WING = "two_way_wing"                 # Versatile forwards
    STRETCH_BIG = "stretch_big"                   # Shooting centers/PFs
    TRADITIONAL_BIG = "traditional_big"           # Paint-dominant bigs
    THREE_POINT_SPECIALIST = "three_point_specialist"  # High-volume 3PT shooters
    YOUNG_VOLATILE = "young_volatile"             # High-upside, inconsistent
    MINUTES_MANAGED = "minutes_managed"           # Load management candidates
    ROLE_PLAYER_3D = "role_player_3d"             # 3-and-D specialists


@dataclass
class WindowWeights:
    """Multi-window projection weights"""
    L3: float = 0.20
    L5: float = 0.25
    L10: float = 0.30
    L20: float = 0.15
    season: float = 0.10
    
    def __post_init__(self):
        total = self.L3 + self.L5 + self.L10 + self.L20 + self.season
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Window weights must sum to 1.0, got {total}")
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "L3": self.L3,
            "L5": self.L5,
            "L10": self.L10,
            "L20": self.L20,
            "season": self.season
        }


@dataclass
class DirectionBias:
    """OVER/UNDER direction adjustments"""
    OVER: float = 0.0
    UNDER: float = 0.0


@dataclass
class StatSpecificOverrides:
    """Stat-type specific configuration overrides"""
    stat_type: str
    confidence_cap: Optional[int] = None
    variance_multiplier: Optional[float] = None
    direction_bias: Optional[DirectionBias] = None
    exclude_from_tiers: List[str] = field(default_factory=list)
    distribution: str = "normal"  # "normal" or "negative_binomial"


@dataclass 
class PlayerConfig:
    """Complete player configuration"""
    player_name: str
    player_id: str
    team: str
    archetype: PlayerArchetype
    
    # Core projection settings
    window_weights: WindowWeights
    variance_penalty_multiplier: float = 1.0
    shrinkage_factor: float = 0.5  # How much to regress toward league average
    
    # Confidence controls
    confidence_cap: Optional[int] = None  # Max confidence % allowed
    min_games_required: int = 5  # Minimum games for projection
    
    # Direction biases (OVER/UNDER adjustments)
    direction_bias: DirectionBias = field(default_factory=DirectionBias)
    
    # Stat-specific overrides
    stat_overrides: Dict[str, StatSpecificOverrides] = field(default_factory=dict)
    
    # Special flags
    minutes_adjustment_required: bool = False
    exclude_from_parlays: bool = False
    high_variance_warning: bool = False
    
    # Metadata
    notes: str = ""
    last_updated: str = "2026-01-31"
    
    def get_effective_config(self, stat_type: str) -> dict:
        """Get configuration with stat-specific overrides applied"""
        base_config = {
            "window_weights": self.window_weights.to_dict(),
            "variance_penalty_multiplier": self.variance_penalty_multiplier,
            "shrinkage_factor": self.shrinkage_factor,
            "confidence_cap": self.confidence_cap,
            "direction_bias": {
                "OVER": self.direction_bias.OVER,
                "UNDER": self.direction_bias.UNDER
            },
            "distribution": "normal",
            "exclude_from_tiers": []
        }
        
        # Apply stat-specific overrides
        if stat_type in self.stat_overrides:
            override = self.stat_overrides[stat_type]
            if override.confidence_cap is not None:
                base_config["confidence_cap"] = override.confidence_cap
            if override.variance_multiplier is not None:
                base_config["variance_penalty_multiplier"] = override.variance_multiplier
            if override.direction_bias is not None:
                base_config["direction_bias"] = {
                    "OVER": override.direction_bias.OVER,
                    "UNDER": override.direction_bias.UNDER
                }
            if override.distribution:
                base_config["distribution"] = override.distribution
            if override.exclude_from_tiers:
                base_config["exclude_from_tiers"] = override.exclude_from_tiers
        
        return base_config


# =============================================================================
# 10 STAR PLAYER CONFIGURATIONS
# =============================================================================

PLAYER_CONFIGS: Dict[str, PlayerConfig] = {}

# -----------------------------------------------------------------------------
# PLAYER 1: NIKOLA JOKIC - High Floor Superstar
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["nikola_jokic"] = PlayerConfig(
    player_name="Nikola Jokic",
    player_id="jokic_nikola",
    team="DEN",
    archetype=PlayerArchetype.HIGH_FLOOR_STAR,
    
    # Jokic is EXTREMELY consistent - weight toward longer windows
    window_weights=WindowWeights(
        L3=0.10,   # Low weight on recent (already consistent)
        L5=0.15,
        L10=0.35,  # Heavy weight on medium-term
        L20=0.25,
        season=0.15
    ),
    
    # LOW variance penalty - he's reliable
    variance_penalty_multiplier=0.80,
    shrinkage_factor=0.20,  # Minimal regression - he IS the mean
    
    # No confidence cap - SLAM eligible
    confidence_cap=None,
    
    # Slight OVER bias on assists (playmaking excellence)
    direction_bias=DirectionBias(OVER=0.02, UNDER=-0.01),
    
    stat_overrides={
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.75,  # Even more reliable on assists
            direction_bias=DirectionBias(OVER=0.04, UNDER=-0.02)
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=0.75,
            distribution="negative_binomial"
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            confidence_cap=65,  # Cap on 3PM - not his strength
            distribution="negative_binomial",
            exclude_from_tiers=["SLAM"]
        )
    },
    
    notes="Triple-double machine. Most consistent superstar in NBA. Trust long-term averages."
)

# -----------------------------------------------------------------------------
# PLAYER 2: ANTHONY EDWARDS - Streaky Scorer
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["anthony_edwards"] = PlayerConfig(
    player_name="Anthony Edwards",
    player_id="edwards_anthony",
    team="MIN",
    archetype=PlayerArchetype.STREAKY_SCORER,
    
    # ANT is streaky - weight toward recent form
    window_weights=WindowWeights(
        L3=0.40,   # Heavy recent weight
        L5=0.30,
        L10=0.15,
        L20=0.10,
        season=0.05
    ),
    
    # HIGH variance penalty - hot/cold player
    variance_penalty_multiplier=1.20,
    shrinkage_factor=0.55,
    
    # Cap confidence - never SLAM on ANT
    confidence_cap=72,
    
    # UNDER bias on scoring (prone to cold streaks)
    direction_bias=DirectionBias(OVER=-0.04, UNDER=0.02),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.30,
            direction_bias=DirectionBias(OVER=-0.05, UNDER=0.03)
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            confidence_cap=62,
            variance_multiplier=1.35,
            distribution="negative_binomial"
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            confidence_cap=65,  # Not primary playmaker
            distribution="negative_binomial"
        )
    },
    
    high_variance_warning=True,
    notes="Elite ceiling but highly variable. Recent form is critical. Avoid SLAM tier."
)

# -----------------------------------------------------------------------------
# PLAYER 3: LUKA DONCIC - Playmaking Superstar
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["luka_doncic"] = PlayerConfig(
    player_name="Luka Doncic",
    player_id="doncic_luka",
    team="LAL",  # Traded mid-season 2025-26
    archetype=PlayerArchetype.PLAYMAKING_GUARD,
    
    # Luka is consistent but can have off nights
    window_weights=WindowWeights(
        L3=0.20,
        L5=0.25,
        L10=0.30,
        L20=0.15,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.90,
    shrinkage_factor=0.30,
    
    # SLAM eligible but with caution
    confidence_cap=78,
    
    direction_bias=DirectionBias(OVER=0.01, UNDER=0.0),
    
    stat_overrides={
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.80,
            direction_bias=DirectionBias(OVER=0.05, UNDER=-0.02)
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=0.85,
            distribution="negative_binomial"
        ),
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=0.95
        ),
        "TO": StatSpecificOverrides(
            stat_type="TO",
            direction_bias=DirectionBias(OVER=0.06, UNDER=-0.03),  # High usage = turnovers
            confidence_cap=68
        )
    },
    
    notes="Elite playmaker. Trust assists heavily. Watch for load management games."
)

# -----------------------------------------------------------------------------
# PLAYER 4: JAYSON TATUM - Two-Way Wing
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["jayson_tatum"] = PlayerConfig(
    player_name="Jayson Tatum",
    player_id="tatum_jayson",
    team="BOS",
    archetype=PlayerArchetype.TWO_WAY_WING,
    
    window_weights=WindowWeights(
        L3=0.15,
        L5=0.25,
        L10=0.30,
        L20=0.20,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.95,
    shrinkage_factor=0.35,
    
    confidence_cap=None,  # SLAM eligible
    
    direction_bias=DirectionBias(OVER=-0.02, UNDER=0.01),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.0
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=0.90,
            distribution="negative_binomial"
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.15,
            distribution="negative_binomial",
            confidence_cap=68
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            confidence_cap=65,
            distribution="negative_binomial"
        )
    },
    
    notes="Consistent two-way star. Scoring and rebounds most reliable. 3PM volatile."
)

# -----------------------------------------------------------------------------
# PLAYER 5: STEPHEN CURRY - Three-Point Specialist (Elite)
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["stephen_curry"] = PlayerConfig(
    player_name="Stephen Curry",
    player_id="curry_stephen",
    team="GSW",
    archetype=PlayerArchetype.THREE_POINT_SPECIALIST,
    
    # Curry is unique - recent form matters for shooting rhythm
    window_weights=WindowWeights(
        L3=0.30,
        L5=0.30,
        L10=0.20,
        L20=0.10,
        season=0.10
    ),
    
    variance_penalty_multiplier=1.05,  # Slightly elevated due to 3PT variance
    shrinkage_factor=0.25,  # He's the GOAT shooter - minimal regression
    
    confidence_cap=75,  # Cap due to 3PT inherent variance
    
    direction_bias=DirectionBias(OVER=-0.02, UNDER=0.03),  # Books inflate his lines
    
    stat_overrides={
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.10,
            distribution="negative_binomial",
            direction_bias=DirectionBias(OVER=-0.04, UNDER=0.05),
            confidence_cap=70
        ),
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.05
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.90,
            confidence_cap=72
        )
    },
    
    notes="GOAT shooter but 3PM inherently volatile. UNDER bias on 3PM - books inflate."
)

# -----------------------------------------------------------------------------
# PLAYER 6: GIANNIS ANTETOKOUNMPO - Traditional Big (Elite)
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["giannis_antetokounmpo"] = PlayerConfig(
    player_name="Giannis Antetokounmpo",
    player_id="antetokounmpo_giannis",
    team="MIL",
    archetype=PlayerArchetype.TRADITIONAL_BIG,
    
    # Giannis is extremely consistent - weight toward longer windows
    window_weights=WindowWeights(
        L3=0.10,
        L5=0.20,
        L10=0.35,
        L20=0.25,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.80,  # Very consistent
    shrinkage_factor=0.20,
    
    confidence_cap=None,  # SLAM eligible
    
    direction_bias=DirectionBias(OVER=0.02, UNDER=-0.01),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=0.85
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=0.80,
            distribution="negative_binomial",
            direction_bias=DirectionBias(OVER=0.03, UNDER=-0.01)
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.90,
            distribution="negative_binomial"
        ),
        "BLK": StatSpecificOverrides(
            stat_type="BLK",
            distribution="negative_binomial",
            confidence_cap=65
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            confidence_cap=55,  # DO NOT trust Giannis 3PM
            exclude_from_tiers=["SLAM", "STRONG"],
            distribution="negative_binomial"
        ),
        "FT": StatSpecificOverrides(
            stat_type="FT",
            variance_multiplier=1.10,  # FT variance due to hacking
            confidence_cap=65
        )
    },
    
    notes="Elite paint scorer. PTS/REB extremely reliable. NEVER bet Giannis 3PM."
)

# -----------------------------------------------------------------------------
# PLAYER 7: SHAI GILGEOUS-ALEXANDER - Efficient Scorer
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["shai_gilgeous_alexander"] = PlayerConfig(
    player_name="Shai Gilgeous-Alexander",
    player_id="gilgeous_alexander_shai",
    team="OKC",
    archetype=PlayerArchetype.HIGH_FLOOR_STAR,
    
    window_weights=WindowWeights(
        L3=0.15,
        L5=0.25,
        L10=0.30,
        L20=0.20,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.85,
    shrinkage_factor=0.25,
    
    confidence_cap=None,  # SLAM eligible
    
    direction_bias=DirectionBias(OVER=0.01, UNDER=0.0),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=0.85,
            direction_bias=DirectionBias(OVER=0.02, UNDER=-0.01)
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.90,
            distribution="negative_binomial"
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            confidence_cap=68,
            distribution="negative_binomial"
        ),
        "STL": StatSpecificOverrides(
            stat_type="STL",
            variance_multiplier=0.85,
            distribution="negative_binomial",
            direction_bias=DirectionBias(OVER=0.03, UNDER=-0.01)
        )
    },
    
    notes="Most efficient high-volume scorer. PTS is most reliable. Strong on steals."
)

# -----------------------------------------------------------------------------
# PLAYER 8: VICTOR WEMBANYAMA - Young Volatile
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["victor_wembanyama"] = PlayerConfig(
    player_name="Victor Wembanyama",
    player_id="wembanyama_victor",
    team="SAS",
    archetype=PlayerArchetype.YOUNG_VOLATILE,
    
    # Young player - recent form critical but don't overweight
    window_weights=WindowWeights(
        L3=0.30,
        L5=0.30,
        L10=0.20,
        L20=0.10,
        season=0.10
    ),
    
    variance_penalty_multiplier=1.25,  # HIGH variance - still developing
    shrinkage_factor=0.65,  # Heavy regression toward mean
    
    confidence_cap=65,  # NEVER SLAM on Wemby
    
    direction_bias=DirectionBias(OVER=-0.03, UNDER=0.02),
    
    stat_overrides={
        "BLK": StatSpecificOverrides(
            stat_type="BLK",
            variance_multiplier=1.15,
            distribution="negative_binomial",
            confidence_cap=62
        ),
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.20,
            confidence_cap=65
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=1.10,
            distribution="negative_binomial"
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            confidence_cap=58,
            variance_multiplier=1.30,
            distribution="negative_binomial",
            exclude_from_tiers=["SLAM", "STRONG"]
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            confidence_cap=60,
            distribution="negative_binomial"
        )
    },
    
    high_variance_warning=True,
    notes="Generational talent but HIGHLY volatile. Cap all confidence. LEAN tier max."
)

# -----------------------------------------------------------------------------
# PLAYER 9: KEVIN DURANT - Minutes Managed Veteran
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["kevin_durant"] = PlayerConfig(
    player_name="Kevin Durant",
    player_id="durant_kevin",
    team="PHX",
    archetype=PlayerArchetype.MINUTES_MANAGED,
    
    window_weights=WindowWeights(
        L3=0.25,
        L5=0.30,
        L10=0.25,
        L20=0.15,
        season=0.05
    ),
    
    variance_penalty_multiplier=1.0,
    shrinkage_factor=0.35,
    
    confidence_cap=72,  # Minutes uncertainty caps confidence
    
    direction_bias=DirectionBias(OVER=-0.02, UNDER=0.01),
    
    minutes_adjustment_required=True,  # CRITICAL
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=0.95
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            confidence_cap=68,
            distribution="negative_binomial"
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            confidence_cap=65,
            distribution="negative_binomial"
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.10,
            distribution="negative_binomial",
            confidence_cap=65
        )
    },
    
    notes="Elite scorer but MINUTES UNCERTAIN. Always check injury report. Never SLAM."
)

# -----------------------------------------------------------------------------
# PLAYER 10: TYRESE HALIBURTON - Playmaking Guard
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["tyrese_haliburton"] = PlayerConfig(
    player_name="Tyrese Haliburton",
    player_id="haliburton_tyrese",
    team="IND",
    archetype=PlayerArchetype.PLAYMAKING_GUARD,
    
    window_weights=WindowWeights(
        L3=0.20,
        L5=0.30,
        L10=0.25,
        L20=0.15,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.90,
    shrinkage_factor=0.35,
    
    confidence_cap=None,  # SLAM eligible on assists
    
    direction_bias=DirectionBias(OVER=0.01, UNDER=0.0),
    
    stat_overrides={
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.80,  # VERY reliable on assists
            direction_bias=DirectionBias(OVER=0.05, UNDER=-0.02)
        ),
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.05,
            confidence_cap=70
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.15,
            distribution="negative_binomial",
            confidence_cap=65
        ),
        "STL": StatSpecificOverrides(
            stat_type="STL",
            variance_multiplier=0.90,
            distribution="negative_binomial"
        )
    },
    
    notes="Elite playmaker. ASSISTS are his bread and butter - SLAM eligible. PTS less reliable."
)


# -----------------------------------------------------------------------------
# PLAYER 11: DEVIN BOOKER - Consistent Volume Scorer
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["devin_booker"] = PlayerConfig(
    player_name="Devin Booker",
    player_id="booker_devin",
    team="PHX",
    archetype=PlayerArchetype.HIGH_FLOOR_STAR,
    
    window_weights=WindowWeights(
        L3=0.15,
        L5=0.25,
        L10=0.30,
        L20=0.20,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.90,
    shrinkage_factor=0.30,
    
    confidence_cap=None,  # SLAM eligible
    
    direction_bias=DirectionBias(OVER=0.01, UNDER=0.0),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=0.85,
            direction_bias=DirectionBias(OVER=0.02, UNDER=-0.01)
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.90,
            distribution="negative_binomial"
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.05,
            distribution="negative_binomial",
            confidence_cap=68
        )
    },
    
    notes="Elite consistent scorer. PTS most reliable. Good on assists too."
)


# -----------------------------------------------------------------------------
# PLAYER 12: JALEN BRUNSON - Playmaking Guard (High Floor)
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["jalen_brunson"] = PlayerConfig(
    player_name="Jalen Brunson",
    player_id="brunson_jalen",
    team="NYK",
    archetype=PlayerArchetype.PLAYMAKING_GUARD,
    
    window_weights=WindowWeights(
        L3=0.20,
        L5=0.25,
        L10=0.30,
        L20=0.15,
        season=0.10
    ),
    
    variance_penalty_multiplier=0.85,  # Very consistent
    shrinkage_factor=0.30,
    
    confidence_cap=None,  # SLAM eligible
    
    direction_bias=DirectionBias(OVER=0.02, UNDER=0.0),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=0.85,
            direction_bias=DirectionBias(OVER=0.02, UNDER=-0.01)
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.80,
            distribution="negative_binomial",
            direction_bias=DirectionBias(OVER=0.03, UNDER=-0.01)
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.10,
            distribution="negative_binomial",
            confidence_cap=65
        )
    },
    
    notes="Ultra-reliable. PTS and AST both SLAM eligible. Trust this man."
)


# -----------------------------------------------------------------------------
# PLAYER 13: DAMIAN LILLARD - Streaky Volume Scorer
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["damian_lillard"] = PlayerConfig(
    player_name="Damian Lillard",
    player_id="lillard_damian",
    team="MIL",
    archetype=PlayerArchetype.STREAKY_SCORER,
    
    window_weights=WindowWeights(
        L3=0.35,  # Recent form critical
        L5=0.30,
        L10=0.20,
        L20=0.10,
        season=0.05
    ),
    
    variance_penalty_multiplier=1.10,  # Streaky
    shrinkage_factor=0.45,
    
    confidence_cap=72,  # Cap due to hot/cold nature
    
    direction_bias=DirectionBias(OVER=-0.02, UNDER=0.01),
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.10,
            direction_bias=DirectionBias(OVER=-0.03, UNDER=0.02)
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=0.90,
            distribution="negative_binomial",
            confidence_cap=70
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.20,
            distribution="negative_binomial",
            confidence_cap=65
        )
    },
    
    high_variance_warning=True,
    notes="Hot/cold scorer. Recent form matters. AST more reliable than PTS."
)


# -----------------------------------------------------------------------------
# PLAYER 14: JOEL EMBIID - Minutes Managed Big
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["joel_embiid"] = PlayerConfig(
    player_name="Joel Embiid",
    player_id="embiid_joel",
    team="PHI",
    archetype=PlayerArchetype.MINUTES_MANAGED,
    
    window_weights=WindowWeights(
        L3=0.30,
        L5=0.30,
        L10=0.20,
        L20=0.10,
        season=0.10
    ),
    
    variance_penalty_multiplier=1.15,  # Injury concern + rest
    shrinkage_factor=0.50,
    
    confidence_cap=68,  # Cap due to load management
    
    direction_bias=DirectionBias(OVER=-0.03, UNDER=0.02),
    
    minutes_adjustment_required=True,  # CRITICAL
    
    stat_overrides={
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.10,
            confidence_cap=68
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=1.05,
            distribution="negative_binomial",
            confidence_cap=68
        ),
        "AST": StatSpecificOverrides(
            stat_type="AST",
            confidence_cap=62,
            distribution="negative_binomial"
        ),
        "BLK": StatSpecificOverrides(
            stat_type="BLK",
            distribution="negative_binomial",
            confidence_cap=62
        )
    },
    
    high_variance_warning=True,
    notes="ALWAYS CHECK INJURY REPORT. When healthy = elite. Minutes uncertainty kills confidence."
)


# -----------------------------------------------------------------------------
# PLAYER 15: LAMELO BALL - Young Volatile Playmaker
# -----------------------------------------------------------------------------
PLAYER_CONFIGS["lamelo_ball"] = PlayerConfig(
    player_name="LaMelo Ball",
    player_id="ball_lamelo",
    team="CHA",
    archetype=PlayerArchetype.YOUNG_VOLATILE,
    
    window_weights=WindowWeights(
        L3=0.35,
        L5=0.30,
        L10=0.20,
        L20=0.10,
        season=0.05
    ),
    
    variance_penalty_multiplier=1.20,  # Volatile
    shrinkage_factor=0.55,
    
    confidence_cap=68,  # Cap due to variance
    
    direction_bias=DirectionBias(OVER=-0.02, UNDER=0.01),
    
    stat_overrides={
        "AST": StatSpecificOverrides(
            stat_type="AST",
            variance_multiplier=1.0,
            distribution="negative_binomial",
            confidence_cap=70
        ),
        "PTS": StatSpecificOverrides(
            stat_type="PTS",
            variance_multiplier=1.15,
            confidence_cap=65
        ),
        "REB": StatSpecificOverrides(
            stat_type="REB",
            variance_multiplier=1.10,
            distribution="negative_binomial",
            confidence_cap=65
        ),
        "3PM": StatSpecificOverrides(
            stat_type="3PM",
            variance_multiplier=1.25,
            distribution="negative_binomial",
            confidence_cap=60,
            exclude_from_tiers=["SLAM"]
        )
    },
    
    high_variance_warning=True,
    notes="Flashy but volatile. AST is most reliable. Watch for injury history."
)


# =============================================================================
# CONFIGURATION MANAGER
# =============================================================================

class PlayerConfigManager:
    """Manages player configurations and provides lookup functionality"""
    
    def __init__(self, configs: Dict[str, PlayerConfig] = None):
        self.configs = configs or PLAYER_CONFIGS
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build lookup tables for fast access"""
        self.by_team: Dict[str, List[str]] = {}
        self.by_archetype: Dict[PlayerArchetype, List[str]] = {}
        
        for key, config in self.configs.items():
            # By team
            if config.team not in self.by_team:
                self.by_team[config.team] = []
            self.by_team[config.team].append(key)
            
            # By archetype
            if config.archetype not in self.by_archetype:
                self.by_archetype[config.archetype] = []
            self.by_archetype[config.archetype].append(key)
    
    def get_config(self, player_key: str) -> Optional[PlayerConfig]:
        """Get configuration for a player"""
        # Normalize the key
        normalized = player_key.lower().replace(" ", "_").replace("-", "_").replace("'", "")
        
        # Direct lookup
        if normalized in self.configs:
            return self.configs[normalized]
        
        # Try partial match on player name
        for key, config in self.configs.items():
            config_name = config.player_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
            if normalized in config_name or config_name in normalized:
                return config
            # Also check just last name
            last_name = config.player_name.split()[-1].lower()
            if last_name in normalized or normalized in last_name:
                return config
        
        return None
    
    def get_effective_config(self, player_key: str, stat_type: str) -> dict:
        """Get effective configuration with stat-specific overrides"""
        config = self.get_config(player_key)
        if config is None:
            return self._get_default_config(stat_type)
        return config.get_effective_config(stat_type.upper())
    
    def _get_default_config(self, stat_type: str) -> dict:
        """Default configuration for unlisted players"""
        return {
            "window_weights": {"L3": 0.20, "L5": 0.25, "L10": 0.30, "L20": 0.15, "season": 0.10},
            "variance_penalty_multiplier": 1.0,
            "shrinkage_factor": 0.50,
            "confidence_cap": 70,
            "direction_bias": {"OVER": 0.0, "UNDER": 0.0},
            "distribution": "negative_binomial" if stat_type.upper() in ["REB", "AST", "3PM", "BLK", "STL"] else "normal",
            "exclude_from_tiers": []
        }
    
    def list_players(self) -> List[str]:
        """List all configured players"""
        return list(self.configs.keys())
    
    def get_players_by_archetype(self, archetype: PlayerArchetype) -> List[str]:
        """Get all players of a specific archetype"""
        return self.by_archetype.get(archetype, [])
    
    def get_slam_eligible_players(self) -> List[str]:
        """Get players eligible for SLAM tier"""
        return [
            key for key, config in self.configs.items()
            if config.confidence_cap is None or config.confidence_cap >= 75
        ]
    
    def export_configs(self, filepath: str):
        """Export configurations to JSON"""
        export_data = {}
        for key, config in self.configs.items():
            export_data[key] = {
                "player_name": config.player_name,
                "team": config.team,
                "archetype": config.archetype.value,
                "window_weights": config.window_weights.to_dict(),
                "variance_penalty_multiplier": config.variance_penalty_multiplier,
                "shrinkage_factor": config.shrinkage_factor,
                "confidence_cap": config.confidence_cap,
                "direction_bias": {
                    "OVER": config.direction_bias.OVER,
                    "UNDER": config.direction_bias.UNDER
                },
                "minutes_adjustment_required": config.minutes_adjustment_required,
                "high_variance_warning": config.high_variance_warning,
                "notes": config.notes
            }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def generate_report(self) -> str:
        """Generate a summary report of all configurations"""
        report = []
        report.append("=" * 80)
        report.append("FUOOM PLAYER CONFIGURATION REPORT")
        report.append("=" * 80)
        report.append("")
        
        for key, config in self.configs.items():
            report.append(f"PLAYER: {config.player_name} ({config.team})")
            report.append(f"  Archetype: {config.archetype.value}")
            report.append(f"  Variance Penalty: {config.variance_penalty_multiplier}")
            report.append(f"  Shrinkage Factor: {config.shrinkage_factor}")
            report.append(f"  Confidence Cap: {config.confidence_cap or 'None (SLAM eligible)'}")
            report.append(f"  Minutes Adjustment: {'REQUIRED' if config.minutes_adjustment_required else 'No'}")
            report.append(f"  High Variance Warning: {'YES' if config.high_variance_warning else 'No'}")
            report.append(f"  Notes: {config.notes}")
            report.append("")
        
        return "\n".join(report)


# =============================================================================
# QUICK REFERENCE TABLE
# =============================================================================

PLAYER_QUICK_REFERENCE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    FUOOM PLAYER CONFIGURATION QUICK REFERENCE                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ PLAYER               │ ARCHETYPE          │ VAR PEN │ CAP  │ BEST STAT       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Nikola Jokic         │ HIGH_FLOOR_STAR    │ 0.80    │ None │ AST, REB        ║
║ Anthony Edwards      │ STREAKY_SCORER     │ 1.20    │ 72%  │ None reliable   ║
║ Luka Doncic          │ PLAYMAKING_GUARD   │ 0.90    │ 78%  │ AST             ║
║ Jayson Tatum         │ TWO_WAY_WING       │ 0.95    │ None │ PTS, REB        ║
║ Stephen Curry        │ 3PT_SPECIALIST     │ 1.05    │ 75%  │ AST             ║
║ Giannis              │ TRADITIONAL_BIG    │ 0.80    │ None │ PTS, REB        ║
║ Shai Gilgeous-Alex   │ HIGH_FLOOR_STAR    │ 0.85    │ None │ PTS, STL        ║
║ Victor Wembanyama    │ YOUNG_VOLATILE     │ 1.25    │ 65%  │ None - too vol  ║
║ Kevin Durant         │ MINUTES_MANAGED    │ 1.00    │ 72%  │ PTS (if mins)   ║
║ Tyrese Haliburton    │ PLAYMAKING_GUARD   │ 0.90    │ None │ AST (SLAM OK)   ║
║ Devin Booker         │ HIGH_FLOOR_STAR    │ 0.90    │ None │ PTS, AST        ║
║ Jalen Brunson        │ PLAYMAKING_GUARD   │ 0.85    │ None │ PTS, AST (SLAM) ║
║ Damian Lillard       │ STREAKY_SCORER     │ 1.10    │ 72%  │ AST             ║
║ Joel Embiid          │ MINUTES_MANAGED    │ 1.15    │ 68%  │ PTS (check mins)║
║ LaMelo Ball          │ YOUNG_VOLATILE     │ 1.20    │ 68%  │ AST             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ VAR PEN < 1.0 = More confidence allowed                                      ║
║ VAR PEN > 1.0 = Confidence compressed                                        ║
║ CAP = Max confidence % (None = SLAM eligible)                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""


# Singleton instance
_manager_instance = None

def get_player_config_manager() -> PlayerConfigManager:
    """Get singleton instance of PlayerConfigManager"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PlayerConfigManager()
    return _manager_instance


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Initialize manager
    manager = PlayerConfigManager()
    
    # Print quick reference
    print(PLAYER_QUICK_REFERENCE)
    
    # Example: Get Jokic's effective config for assists
    jokic_ast_config = manager.get_effective_config("nikola_jokic", "AST")
    print("\nJokic AST Config:")
    print(json.dumps(jokic_ast_config, indent=2))
    
    # Example: Get Wemby's effective config for 3PM (should be heavily capped)
    wemby_3pm_config = manager.get_effective_config("victor_wembanyama", "3PM")
    print("\nWembanyama 3PM Config:")
    print(json.dumps(wemby_3pm_config, indent=2))
    
    # List SLAM-eligible players
    print("\nSLAM-Eligible Players:")
    for player in manager.get_slam_eligible_players():
        print(f"  - {player}")
    
    # Generate full report
    print("\n" + manager.generate_report())
