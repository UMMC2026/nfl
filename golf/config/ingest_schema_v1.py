"""
Golf Ingest Schema v1
======================
STRICT UI-DERIVED STATS ONLY

This schema is derived DIRECTLY from the Underdog UI screenshot.
No inference, no extrapolation, no model-layer enrichment.

If a stat is not in GOLF_STATS_UI_ONLY, it MUST NOT be ingested
from props — it can only come from enrichment layer.

Frozen: 2026-02-05
"""

from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class PropScope(Enum):
    """Scope of the prop (round vs tournament)."""
    ROUND = "round"           # Per-round props (R1, R2, R3, R4)
    TOURNAMENT = "tournament" # Full tournament props
    CUT = "cut"               # Make/miss cut (binary)


@dataclass
class GolfStatConfig:
    """Configuration for a single golf stat type."""
    key: str                    # Internal key
    ui_label: str               # Exact label from Underdog UI
    scope: PropScope            # Round or tournament
    is_binary: bool = False     # True for made_cut
    direction_labels: Tuple[str, str] = ("higher", "lower")  # or ("better", "worse")
    

# =============================================================================
# CANONICAL UI STATS — DIRECTLY FROM UNDERDOG SCREENSHOT
# =============================================================================

GOLF_STATS_UI_ONLY: Dict[str, GolfStatConfig] = {
    "round_strokes": GolfStatConfig(
        key="round_strokes",
        ui_label="Round Strokes",
        scope=PropScope.ROUND,
        direction_labels=("higher", "lower"),  # Higher = more strokes = worse
    ),
    
    "finishing_position": GolfStatConfig(
        key="finishing_position",
        ui_label="Tourney Finishing Position",
        scope=PropScope.TOURNAMENT,
        direction_labels=("better", "worse"),  # Better = lower number
    ),
    
    "birdies_or_better": GolfStatConfig(
        key="birdies_or_better",
        ui_label="Birdies or Better",
        scope=PropScope.ROUND,
        direction_labels=("higher", "lower"),
    ),
    
    "made_cut": GolfStatConfig(
        key="made_cut",
        ui_label="Made Cuts",
        scope=PropScope.CUT,
        is_binary=True,
        direction_labels=("yes", "no"),
    ),
    
    "greens_in_regulation": GolfStatConfig(
        key="greens_in_regulation",
        ui_label="Greens in Regulation",
        scope=PropScope.ROUND,
        direction_labels=("higher", "lower"),
    ),
    
    "fairways_hit": GolfStatConfig(
        key="fairways_hit",
        ui_label="Fairways Hit",
        scope=PropScope.ROUND,
        direction_labels=("higher", "lower"),
    ),
}

# Quick lookup set for validation
VALID_UI_STATS: Set[str] = set(GOLF_STATS_UI_ONLY.keys())

# Aliases (UI variations → canonical key)
UI_STAT_ALIASES: Dict[str, str] = {
    # Round strokes
    "round_strokes": "round_strokes",
    "strokes": "round_strokes",
    "score": "round_strokes",
    "round_score": "round_strokes",
    
    # Finishing position
    "finishing_position": "finishing_position",
    "tourney_finishing_position": "finishing_position",
    "finish": "finishing_position",
    "position": "finishing_position",
    "placement": "finishing_position",
    
    # Birdies
    "birdies_or_better": "birdies_or_better",
    "birdies": "birdies_or_better",
    "birdie": "birdies_or_better",
    
    # Made cut
    "made_cut": "made_cut",
    "make_cut": "made_cut",
    "cut_made": "made_cut",
    "miss_cut": "made_cut",
    
    # GIR
    "greens_in_regulation": "greens_in_regulation",
    "gir": "greens_in_regulation",
    "greens": "greens_in_regulation",
    
    # Fairways
    "fairways_hit": "fairways_hit",
    "fairways": "fairways_hit",
    "fir": "fairways_hit",
}


def normalize_stat(stat: str) -> str:
    """Normalize stat name to canonical key."""
    stat_lower = stat.lower().strip().replace(" ", "_").replace("-", "_")
    return UI_STAT_ALIASES.get(stat_lower, stat_lower)


def is_valid_ui_stat(stat: str) -> bool:
    """Check if stat is a valid UI-derived stat."""
    normalized = normalize_stat(stat)
    return normalized in VALID_UI_STATS


def validate_prop_for_ingest(prop: Dict) -> Tuple[bool, str]:
    """
    Validate a prop for ingest. Rejects non-UI stats.
    
    Args:
        prop: Parsed prop dict with 'market' key
        
    Returns:
        (is_valid, reason)
    """
    market = prop.get("market", "")
    normalized = normalize_stat(market)
    
    if normalized not in VALID_UI_STATS:
        return False, f"[INGEST REJECTED] '{market}' is not a UI-derived stat. Valid: {list(VALID_UI_STATS)}"
    
    return True, "OK"


def get_stat_config(stat: str) -> GolfStatConfig:
    """Get configuration for a stat."""
    normalized = normalize_stat(stat)
    return GOLF_STATS_UI_ONLY.get(normalized)


def get_prop_scope(stat: str) -> PropScope:
    """Get the scope (round/tournament/cut) for a stat."""
    config = get_stat_config(stat)
    if config:
        return config.scope
    return PropScope.ROUND  # Default


# =============================================================================
# MODEL-LAYER STATS (NOT from UI — for enrichment only)
# =============================================================================

MODEL_ENRICHMENT_STATS: Set[str] = {
    "sg_total",           # Strokes Gained: Total
    "sg_off_tee",         # Strokes Gained: Off the Tee
    "sg_approach",        # Strokes Gained: Approach
    "sg_around_green",    # Strokes Gained: Around Green
    "sg_putting",         # Strokes Gained: Putting
    "scrambling",         # Scrambling %
    "driving_distance",   # Driving Distance
    "putting_avg",        # Putting Average
}


def is_model_stat(stat: str) -> bool:
    """Check if stat is a model-layer enrichment stat (not from UI)."""
    return stat.lower() in MODEL_ENRICHMENT_STATS


# =============================================================================
# SCHEMA VERSION
# =============================================================================

SCHEMA_VERSION = "v1"
SCHEMA_FROZEN_DATE = "2026-02-05"
SCHEMA_SOURCE = "Underdog UI Screenshot"


def get_schema_info() -> Dict:
    """Get schema metadata."""
    return {
        "version": SCHEMA_VERSION,
        "frozen_date": SCHEMA_FROZEN_DATE,
        "source": SCHEMA_SOURCE,
        "ui_stats": list(VALID_UI_STATS),
        "model_stats": list(MODEL_ENRICHMENT_STATS),
    }


if __name__ == "__main__":
    print("=" * 60)
    print("GOLF INGEST SCHEMA v1")
    print("=" * 60)
    print(f"\nSource: {SCHEMA_SOURCE}")
    print(f"Frozen: {SCHEMA_FROZEN_DATE}")
    print(f"\nUI-Derived Stats ({len(VALID_UI_STATS)}):")
    for key, config in GOLF_STATS_UI_ONLY.items():
        print(f"  • {key}: '{config.ui_label}' [{config.scope.value}]")
    print(f"\nModel Enrichment Stats ({len(MODEL_ENRICHMENT_STATS)}):")
    for stat in sorted(MODEL_ENRICHMENT_STATS):
        print(f"  • {stat}")
