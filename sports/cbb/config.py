"""
CBB Configuration — Sport-Specific Settings

IMPORTANT: CBB ≠ NBA. Do not copy NBA assumptions blindly.
- 350+ teams with massive rotation volatility
- Inconsistent pace & minutes
- Market lines are softer but noisier

GOVERNANCE: Tier thresholds imported from config/thresholds.py (single source of truth).
"""
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.thresholds import get_all_thresholds

# =============================================================================
# SPORT REGISTRY
# =============================================================================
CBB_REGISTRY = {
    "sport": "CBB",
    "enabled": True,  # Activated 2026-01-24 (Tier 1 complete)
    "status": "PRODUCTION",
    "version": "1.0.0",
}

# =============================================================================
# PROBABILITY MODELING (CBB-SPECIFIC)
# =============================================================================
# CBB uses L10 rolling windows with 0.40 blend (40% recent, 60% stable)
# Aligned with NBA Tier 1 fix (2026-01-24)
L10_BLEND_WEIGHT = 0.40  # Reduced from 1.0 to match NBA recency bias fix

# Market alignment gate threshold (updated 2026-01-24, aligned with Tennis)
MARKET_ALIGNMENT_THRESHOLD = 12.0  # Reduced from 15% to 12% (Tier 1 fix)

# =============================================================================
# CONFIDENCE CAPS (STRICTER THAN NBA)
# =============================================================================
# CBB has higher variance — we cap harder
CONFIDENCE_CAPS = {
    "core": 0.70,           # Points, rebounds, assists
    "volume_micro": 0.65,   # FGA, FTA, etc.
    "event_binary": 0.55,   # Blocks, steals, dunks
}

# =============================================================================
# TIER THRESHOLDS (NO SLAM TIER INITIALLY)
# GOVERNANCE: Use canonical thresholds from config/thresholds.py
# =============================================================================
TIER_THRESHOLDS = get_all_thresholds("CBB")  # Imported from config/thresholds.py

# =============================================================================
# EDGE GATES (CBB-SPECIFIC BLOCKS)
# =============================================================================
@dataclass
class CBBEdgeGates:
    """Hard blocks specific to college basketball chaos"""
    
    # Minimum minutes average to consider a player
    min_minutes_avg: float = 20.0
    
    # Ban composite stats initially (PRA, PR, PA)
    allow_composite_stats: bool = False
    
    # Block unders on low-minute players
    block_under_low_minutes: bool = True
    
    # Block overs if blowout probability exceeds threshold
    max_blowout_probability: float = 0.25
    
    # Minimum sample size for edge creation
    min_games_played: int = 5
    
    # High variance penalty threshold (std_dev > mean * factor)
    variance_penalty_factor: float = 0.6
    variance_confidence_cap: float = 0.65


CBB_EDGE_GATES = CBBEdgeGates()

# =============================================================================
# BLOCKED STATS (Phase 1 restrictions)
# =============================================================================
BLOCKED_STATS: List[str] = [
    "pts+reb",
    "pts+ast",
    "pts+reb+ast",
    "reb+ast",
    "fantasy_points",
]

# =============================================================================
# DATA SOURCES
# =============================================================================
DATA_SOURCES = {
    "primary": "sportsreference",  # NCAA stats
    "secondary": "espn",           # Team box scores
    "backup": None,
}

# =============================================================================
# GAME CONTEXT FLAGS
# =============================================================================
CONTEXT_FLAGS = {
    "conference_weight": 1.2,      # Conference games more predictable
    "non_conference_weight": 0.8,  # Early season chaos
    "back_to_back_penalty": 0.05,  # Travel fatigue adjustment
    "early_season_cutoff": 10,     # Games before sample is reliable
}

# =============================================================================
# SDG CONFIGURATION (2026-02-01 UPGRADE)
# =============================================================================
# Stat Deviation Gate — Soft Volatility Governor
# CRITICAL: This PRICES variance, it doesn't ELIMINATE it.

SDG_ENABLED = True
SDG_MODE = "soft"  # "soft" = penalty, "hard" = block

# Z-Score Thresholds (Stricter than NBA by ~50%)
SDG_Z_THRESHOLDS = {
    "PTS": 0.60,      # NBA: 0.40
    "REB": 0.55,      # NBA: 0.35
    "AST": 0.55,      # NBA: 0.35
    "3PM": 0.45,      # NBA: 0.35
    "BLK": 0.50,
    "STL": 0.50,
    "TOV": 0.45,
    "PTS+REB": 0.60,  # Only allowed composite
    "DEFAULT": 0.55,
}

# Blowout-adjusted z-thresholds (spread >12)
SDG_Z_THRESHOLDS_BLOWOUT = {
    "PTS": 0.75,
    "REB": 0.70,
    "AST": 0.70,
    "3PM": 0.60,
    "PTS+REB": 0.75,
    "DEFAULT": 0.70,
}

# CV Thresholds by Role (NOT blanket 0.65)
SDG_CV_THRESHOLDS = {
    "STAR": 0.50,        # Usage >25%, should be consistent
    "ROLE_PLAYER": 0.65, # Usage 15-25%
    "SPECIALIST": 0.85,  # 3PT shooters, binary stats
    "BENCH": 0.70,       # Rotation players
    "DEFAULT": 0.65,
}

# Stat-Specific CV Thresholds (2026-02-14 RECALIBRATION)
# Binary/event stats are INHERENTLY volatile — a flat cap kills them unfairly.
# This dict sets per-stat CV ceilings. The SDG uses max(role_threshold, stat_threshold)
# so that neither axis penalizes unjustly.
STAT_CV_THRESHOLDS = {
    "points": 0.50,       # Core volume, should be stable
    "rebounds": 0.65,     # Game-flow dependent
    "assists": 0.60,      # Scheme dependent
    "3pm": 0.85,          # Binary events — high CV EXPECTED
    "blocks": 0.90,       # Rare events — high CV EXPECTED
    "steals": 0.85,       # Rare events
    "turnovers": 0.80,    # Highly contextual
    "pra": 0.45,          # Composite — tight CV required
    "pts_ast": 0.50,      # Composite
    "pts_reb": 0.50,      # Composite
    "reb_ast": 0.60,      # Composite
    "DEFAULT": 0.55,
}
STAT_CV_DEFAULT = 0.55

# SDG Penalty Brackets (soft compression)
SDG_PENALTY_BRACKETS = [
    (0.50, 1.00),  # CV <= 0.50: no penalty
    (0.75, 0.90),  # CV <= 0.75: -10%
    (1.00, 0.80),  # CV <= 1.00: -20%
    (999, 0.65),   # CV > 1.00: -35%
]

# Multi-window validation
SDG_MULTI_WINDOW_REQUIRED = True
SDG_MAX_WINDOW_DRIFT = 0.25  # Block if L10 vs Season differ >25%

# =============================================================================
# CONFERENCE PHASE GATES (2026-02-01 UPGRADE)
# =============================================================================
CONFERENCE_PHASE_GATES = {
    "EARLY_NONCONF": {
        "months": [11, 12],
        "min_z": 0.80,
        "volatility_multiplier": 1.4,
    },
    "EARLY_CONF": {
        "months": [11, 12],
        "min_z": 0.65,
        "volatility_multiplier": 1.2,
    },
    "CONFERENCE": {
        "months": [1, 2],
        "min_z": 0.50,
        "volatility_multiplier": 1.0,
    },
    "CONF_TOURNAMENT": {
        "months": [3],
        "min_z": 0.70,
        "volatility_multiplier": 1.3,
    },
    "MARCH_MADNESS": {
        "min_z": 0.85,
        "volatility_multiplier": 1.5,
    },
}

# =============================================================================
# BLOWOUT PROTECTION (2026-02-01 UPGRADE)
# =============================================================================
# CRITICAL: CBB has ~40% blowout rate. This is NOT optional.
BLOWOUT_ENABLED = True
BLOWOUT_MODE = "penalty"  # "penalty" = multiply, "block" = hard reject

BLOWOUT_TIERS = {
    "COMPETITIVE": {"max_spread": 7, "penalty": 1.00, "block_stars": False},
    "MINOR": {"max_spread": 11, "penalty": 0.92, "block_stars": False},
    "MODERATE": {"max_spread": 14, "penalty": 0.85, "block_stars": False},
    "HIGH": {"max_spread": 17, "penalty": 0.75, "block_stars": False},
    "EXTREME": {"max_spread": 999, "penalty": 0.70, "block_stars": True},
}

# =============================================================================
# SHRINKAGE (REPLACES "MIN 5 GAMES" HARD BLOCK)
# =============================================================================
SHRINKAGE_ENABLED = True
SHRINKAGE_MAX_GAMES = 10  # Full weight at 10 games

# Formula: shrunk_μ = w × observed_μ + (1-w) × baseline_μ
# where w = min(games_played, 10) / 10

# =============================================================================
# MULTI-WINDOW PROJECTION (REPLACES SINGLE L10)
# =============================================================================
WINDOW_WEIGHTS = {
    "CONFERENCE": {  # Jan-Feb (stable)
        "L5": 0.40,
        "L10": 0.40,
        "SEASON": 0.20,
    },
    "NONCONF": {  # Nov-Dec (baseline-heavy)
        "L10": 0.60,
        "SEASON": 0.40,
    },
    "POST_INJURY": {  # Very recent focus
        "L3": 0.50,
        "L5": 0.30,
        "L10": 0.20,
    },
    "DEFAULT": {
        "L5": 0.25,
        "L10": 0.40,
        "L15": 0.20,
        "SEASON": 0.15,
    },
}

# =============================================================================
# COMPOSITE STATS (RE-ENABLED v2.2)
# =============================================================================
# All standard composites allowed — NegBin model handles variance correctly now
ALLOWED_COMPOSITES = ["PTS+REB", "PTS+AST", "REB+AST", "PRA", "PTS+REB+AST", "BLKS+STLS"]
COMPOSITE_MAX_CONFIDENCE = 0.75  # Cap composites at 75% (aligns with stat_caps)
COMPOSITE_MIN_Z = 0.60
COMPOSITE_MAX_CV = 0.50

# =============================================================================
# UPDATED TIER THRESHOLDS (Post-SDG)
# =============================================================================
# SLAM: DISABLED (kept disabled)
# STRONG: 70% (restored from 68% — the 68% was artificially low)
# LEAN: 60% (unchanged)
CBB_TIER_THRESHOLDS_V2 = {
    "SLAM": None,    # Disabled
    "STRONG": 0.70,  # Restored to 70% (was 68% — caused flat cap bug)
    "LEAN": 0.60,    # Unchanged
    "NO_PLAY": 0.00,
}

# =============================================================================
# CALIBRATION MODE (v3.0 — Fix 8)
# =============================================================================
# During the calibration period, cap all STRONG → LEAN.
# This prevents premature high-confidence picks while new distribution
# and game-script fixes are being validated against real outcomes.
#
# Set CALIBRATION_MODE = False after 14 days if hit rates look correct.
CALIBRATION_MODE = True
CALIBRATION_START_DATE = "2026-02-15"  # When v3.0 fixes went live
CALIBRATION_DAYS = 14                  # Days to run calibration before allowing STRONG
