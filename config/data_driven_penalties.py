"""
DATA-DRIVEN PENALTY CONFIG
===========================
Updated: 2026-02-09 (595 picks calibration)
Previous: 114 picks (2026-02-04)

This replaces arbitrary penalties with empirically-validated adjustments.

KEY FINDINGS FROM CALIBRATION (Feb 9 update):
- PRA UNDER: 70% win rate (BEST edge!)
- PRA OVER: 25% win rate → NOW 0/4 (0%) → HARD AVOID
- 3PM UNDER: 100% hit rate (4/4) on low-volume shooters
- ASSISTS OVER (LEAN): 1/6 (16.7%) → CATASTROPHIC → severe penalty added
- NBA LEAN higher: 50% (19/38) → below 55% target → OVER penalty tightened
- NBA LEAN lower: 53.6% (15/28) → close but needs boost
- NHL Binary (Points ≥0.5, Blocks, SOG): 100% hit rate (4/4)
- Tennis UNDER: 100% hit rate (2/2)
- CBB Points OVER: 0% (0/1) - HIGH CHAOS

STRUCTURAL INSIGHT:
"Your math is right. Your ticket construction is the problem."
"Assists OVER on LEAN is poison — 5/6 missed. Direction matters more than base."
"""

# === PENALTY CAPS (FIX #2: 2026-01-30) ===
# Prevents over-aggressive gate penalties from zeroing out valid picks
MAX_PENALTY_PERCENT = 25.0   # Maximum total penalty (percentage points)
MIN_CONFIDENCE_FLOOR = 50.0  # Never go below 50% (prevents 0.0% blocking)

# === NBA STAT-SPECIFIC MULTIPLIERS ===
# Based on actual win rates from historical data
# Formula: multiplier = observed_win_rate / 0.50 (break-even)
# Updated 2026-02-04 with Feb 1-3 calibration

STAT_MULTIPLIERS_DATA_DRIVEN = {
    # ASSISTS: Overall 16.7% on LEAN overs → base NEUTRAL, direction matters
    "ast": 1.00,         # Was 1.20 but 1/6 LEAN misses → direction-specific now
    "assists": 1.00,
    
    # STRONG STATS (3PM unders crushing it)
    "3pm": 1.10,         # 4/4 hits on unders → boost base
    "threes": 1.10,
    
    # BREAK-EVEN STATS (no penalty)
    "pts": 1.00,         # 50% win rate → neutral
    "points": 1.00,
    "reb": 1.00,         # 50% win rate → neutral
    "rebounds": 1.00,
    "pra": 1.00,         # 50% win rate overall → neutral (BUT SEE DIRECTION)
    "pts+reb+ast": 1.00,
    
    # LOSING STATS (PENALIZE heavily)
    "pts+ast": 0.75,     # 37.5% win rate → reduce by 25%
    "reb+ast": 0.75,     # Similar combo stat
    "ast+reb": 0.75,
}

# === STAT + DIRECTION COMBO MULTIPLIERS (UPDATED 2026-02-04) ===
# These override base multipliers when direction matters significantly
# Key insight: PRA direction is CRITICAL - 0/4 misses on PRA OVER
STAT_DIRECTION_COMBOS = {
    # PRA direction makes HUGE difference
    ("pra", "lower"): 1.40,      # 70% win rate → BIG BOOST
    ("pra", "under"): 1.40,
    ("pts+reb+ast", "lower"): 1.40,
    ("pts+reb+ast", "under"): 1.40,
    
    ("pra", "higher"): 0.40,     # 0/4 misses Feb 1-3 → SEVERE PENALTY (was 0.50)
    ("pra", "over"): 0.40,
    ("pts+reb+ast", "higher"): 0.40,
    ("pts+reb+ast", "over"): 0.40,
    
    # 3PM direction - UNDERS CRUSHING IT (4/4 Feb 1-3)
    ("3pm", "lower"): 1.30,      # 100% hit rate on low-volume shooters
    ("3pm", "under"): 1.30,
    ("threes", "lower"): 1.30,
    ("threes", "under"): 1.30,
    
    ("3pm", "higher"): 1.00,     # Neutral (Ayo hit, context-dependent)
    ("3pm", "over"): 1.00,
    ("threes", "higher"): 1.00,
    ("threes", "over"): 1.00,
    
    # PTS direction - OVERS risky on volatile usage players
    # UPDATED 2026-02-09: Valid LEAN pts higher = 1/3 (33%) → severe penalty
    ("pts", "higher"): 0.80,     # 33% hit rate on valid LEAN → heavy penalty
    ("pts", "over"): 0.80,
    ("points", "higher"): 0.80,
    ("points", "over"): 0.80,
    
    ("pts", "lower"): 0.90,      # 1/3 (33%) on valid LEAN → penalty
    ("pts", "under"): 0.90,
    ("points", "lower"): 0.90,
    ("points", "under"): 0.90,
    
    # REB - Big man unders DANGEROUS (Jarrett Allen 8.5 → 17)
    # UPDATED 2026-02-09: Valid LEAN reb higher = 0/1 → penalty
    ("reb", "higher"): 0.90,     # Reb overs underperform
    ("reb", "over"): 0.90,
    ("rebounds", "higher"): 0.90,
    ("rebounds", "over"): 0.90,
    ("reb", "lower"): 0.85,      # Big man unders need pace filter
    ("rebounds", "lower"): 0.85,
    ("rebounds", "under"): 0.85,
    
    # PTS+AST - AVOID both directions
    ("pts+ast", "higher"): 0.50,  # 25% win rate
    ("pts+ast", "over"): 0.50,
    ("pts+ast", "lower"): 1.00,   # 50% (small sample)
    
    # REB+AST - NEUTRAL (insufficient calibration data)
    ("reb+ast", "higher"): 1.00,
    ("reb+ast", "over"): 1.00,
    ("reb+ast", "lower"): 1.00,
    ("reb+ast", "under"): 1.00,
    ("ast+reb", "higher"): 1.00,
    ("ast+reb", "over"): 1.00,
    ("ast+reb", "lower"): 1.00,
    ("ast+reb", "under"): 1.00,
    
    # ASSISTS DIRECTION — CRITICAL FIX 2026-02-09
    # LEAN assists OVER: 1/6 (16.7%) → catastrophic miss rate
    # Only Marcus Smart hit; Draymond, Podziemski, Melton, Brooks, Williams all missed
    ("ast", "higher"): 0.55,      # 16.7% hit rate → severe penalty
    ("ast", "over"): 0.55,
    ("assists", "higher"): 0.55,
    ("assists", "over"): 0.55,
    
    # Assists UNDER: insufficient data, keep neutral
    ("ast", "lower"): 1.10,
    ("ast", "under"): 1.10,
    ("assists", "lower"): 1.10,
    ("assists", "under"): 1.10,
}

# === NFL STAT-SPECIFIC MULTIPLIERS (SEPARATE - DO NOT MIX WITH NBA) ===
# These are NFL-only stats from calibration data
NFL_STAT_MULTIPLIERS = {
    "recs": 0.50,            # 25% win rate → cut by 50%
    "receptions": 0.50,
    "rec yards": 0.67,       # 33.3% win rate → cut by 33%
    "receiving yards": 0.67,
    "rush yards": 1.00,      # 50% win rate → neutral
    "rushing yards": 1.00,
}

# === NHL STAT-SPECIFIC MULTIPLIERS (NEW 2026-02-04) ===
# Based on Feb 1-3 calibration: 4/4 hits on binary stats
# NHL Binary props = low variance, high reliability
NHL_STAT_MULTIPLIERS = {
    # BINARY STATS - ELITE (100% hit rate)
    "points": 1.25,          # Points ≥0.5 → reliable
    "goals": 1.20,           # Goals ≥0.5 → reliable
    "assists": 1.20,         # Assists ≥0.5 → reliable
    "blocks": 1.20,          # Blocks ≥1.5 → reliable
    "sog": 1.15,             # SOG ≥2.5 → reliable
    "shots": 1.15,
    
    # HIGHER VARIANCE
    "saves": 1.00,           # Goalie variance
}

# Binary stat flag for NHL (can stack safely)
NHL_BINARY_STATS = {"points", "goals", "assists", "blocks", "sog", "shots"}

# === TENNIS STAT-SPECIFIC MULTIPLIERS (NEW 2026-02-04) ===
# Based on Feb 1-3 calibration: 2/2 hits on unders
# Tennis unders = exceptional signal clarity
TENNIS_STAT_MULTIPLIERS = {
    "games_won": 1.00,       # Neutral base
    "aces": 1.00,
    "double_faults": 1.00,
    "total_games": 1.00,
}

TENNIS_DIRECTION_COMBOS = {
    # UNDERS CRUSHING IT
    ("games_won", "lower"): 1.30,
    ("games_won", "under"): 1.30,
    ("aces", "lower"): 1.25,
    ("aces", "under"): 1.25,
    ("total_games", "lower"): 1.20,
    ("total_games", "under"): 1.20,
    
    # Overs neutral
    ("games_won", "higher"): 1.00,
    ("aces", "higher"): 1.00,
}

# === CBB STAT-SPECIFIC MULTIPLIERS (UPDATED 2026-02-10) ===
# Earlier calibration treated CBB points overs as "high chaos" and applied
# a blanket penalty. New policy (user directive):
#   - "Don't clip my overs too much" → let raw truth shine unless other
#     contextual gates (defense, pace, minutes) veto the play.
#   - Keep a modest boost on UNDERS where they remain more stable.
CBB_STAT_MULTIPLIERS = {
    "points": 1.00,          # Remove global penalty on CBB points
    "rebounds": 1.00,
    "assists": 1.00,
    "3pm": 1.00,
}

CBB_DIRECTION_COMBOS = {
    # Points OVERS: no extra data-driven penalty — governance + SDG handle chaos.
    ("points", "higher"): 1.00,
    ("points", "over"): 1.00,
	
    # PRA in CBB: stabilize by making it clearly under-first.
    #   - Overs remain penalized (historically weak).
    #   - Unders get a modest boost when the Poisson gap is real.
    ("pra", "higher"): 0.70,
    ("pra", "over"): 0.70,
    ("pra", "lower"): 1.15,
    ("pra", "under"): 1.15,
	
    # Unders more predictable on points → keep a small boost
    ("points", "lower"): 1.10,
    ("points", "under"): 1.10,
}

# === DIRECTION BIAS (overall, when no stat-specific combo) ===
# UNDERS hit 51.5%, OVERS hit 46.9%
# Difference: ~5 percentage points

# Updated 2026-02-09: LEAN higher only 50% (19/38), lower 53.6% (15/28)
# Tightening OVER penalty to reflect continued underperformance
DIRECTION_ADJUSTMENT = {
    "higher": 0.92,      # OVERS underperform — 50% hit rate on LEAN
    "over": 0.92,
    "lower": 1.05,       # UNDERS outperform — boost slightly
    "under": 1.05,
}

# === EDGE THRESHOLDS ===
# With 97 picks all showing negative edge (no probabilities recorded),
# we can't calibrate the optimal threshold from data yet.
# Using theoretical minimum: implied_prob - break_even = 52.38% - 50% = 2.38%

EDGE_THRESHOLDS = {
    "minimum_edge": 2.0,     # Below this, NO_PLAY
    "lean_edge": 2.0,        # LEAN tier
    "strong_edge": 7.0,      # STRONG tier  
    "slam_edge": 15.0,       # SLAM tier
}

# === SAMPLE SIZE REQUIREMENTS ===
# Standard statistical confidence
# n=10 gives ~95% CI width of ±0.62σ

SAMPLE_SIZE_RULES = {
    "minimum_games": 5,      # Below this, VETO
    "confidence_scaling": {
        5: 0.80,             # 5 games → 80% confidence
        10: 0.90,            # 10 games → 90% confidence
        15: 0.95,            # 15 games → 95% confidence
        20: 1.00,            # 20+ games → full confidence
    }
}

# === VARIANCE PENALTY ===
# CV > 0.35 is high volatility, but we have no data on if this matters
# Default: light penalty until proven harmful

VARIANCE_RULES = {
    "cv_threshold": 0.35,
    "high_cv_penalty": 0.95,  # Only 5% penalty for high CV
}

# === PLAYER VARIANCE LABELS (NEW 2026-02-04) ===
# Labels for ticket construction rules
# These identify picks that should NOT be stacked together

VARIANCE_LABELS = {
    "VARIANCE_EXPOSED": {
        "description": "High-variance props (PRA overs, points overs on volatile players)",
        "max_per_ticket": 2,  # RULE 1: Max 2 volatility props per ticket
        "stats": ["pra", "pts+reb+ast"],
        "directions": ["higher", "over"],
    },
    "ROLE_UNSTABLE": {
        "description": "Players with inconsistent roles (rookies, bench scorers)",
        "confidence_penalty": 0.90,  # RULE 4: -10% confidence
        "conditions": ["rookie", "bench", "minutes_variance > 0.25"],
    },
    "BINARY_STAT": {
        "description": "Low-variance binary stats (NHL points ≥0.5, blocks ≥1.5)",
        "safe_to_stack": True,  # RULE 5: Binary stats can stack safely
        "boost": 1.05,
    },
    "SAFE_STACK": {
        "description": "Props that work well together in parlays",
        "types": ["3pm_under", "nhl_binary", "tennis_under"],
    },
}

# === ROOKIE / BENCH PENALTY (NEW 2026-02-04) ===
# Matas Buzelis 3PM under miss (5 on 2.5 line) = young player variance
ROOKIE_PENALTY = 0.90        # -10% confidence for rookies/bench scorers
BENCH_MINUTES_THRESHOLD = 22  # Minutes threshold for bench classification

# === PRA OVER CAP (NEW 2026-02-04) ===
# "Cap PRA overs at ≤28 unless elite usage"
PRA_OVER_LINE_CAP = 28.0     # Don't play PRA overs above this line
PRA_USAGE_STABILITY_MIN = 0.75  # RULE 2: Usage stability score required

# === MASTER SWITCH ===
# When True, bypasses ALL penalties (demon_mode)

USE_DATA_DRIVEN_PENALTIES = True
BYPASS_ALL_PENALTIES = False  # Set True for demon_mode


# === TICKET CONSTRUCTION RULES (NEW 2026-02-04) ===
# "Your edge collapses when more than 2 volatility-exposed props exist in the same ticket"

TICKET_RULES = {
    "max_variance_props": 2,           # RULE 1: Max 2 volatility props per ticket
    "max_pra_overs": 1,                # Max 1 PRA over per ticket
    "max_points_overs": 2,             # Max 2 points overs per ticket
    "max_same_game": 2,                # Max 2 props from same game
    "max_rookie_props": 1,             # Max 1 rookie prop per ticket
    
    # Safe stacking (no limits)
    "safe_stack_types": [
        "3pm_under",
        "nhl_binary",
        "tennis_under",
        "nba_ast",
    ],
}

# Variance prop identifiers
VARIANCE_PROP_PATTERNS = {
    ("pra", "higher"),
    ("pra", "over"),
    ("pts+reb+ast", "higher"),
    ("pts+reb+ast", "over"),
    ("points", "higher"),  # When player has high usage volatility
    ("points", "over"),
}


def get_data_driven_multiplier(stat: str, direction: str = "higher", league: str = "nba") -> float:
    """
    Get the data-driven multiplier for a stat/direction combo.
    
    PRIORITY:
    1. Check sport-specific direction combos (most specific)
    2. Check STAT_DIRECTION_COMBOS (NBA default)
    3. Fall back to sport-specific stat multipliers
    4. Fall back to STAT_MULTIPLIERS + DIRECTION_ADJUSTMENT
    
    Returns: multiplier to apply to raw confidence
    """
    if BYPASS_ALL_PENALTIES:
        return 1.0
    
    stat_lower = stat.lower().strip()
    dir_lower = direction.lower().strip()
    league_lower = league.lower().strip()
    
    # Sport-specific lookups
    if league_lower == "nhl":
        # NHL binary stats get boost
        if stat_lower in NHL_BINARY_STATS:
            return NHL_STAT_MULTIPLIERS.get(stat_lower, 1.0) * 1.05
        return NHL_STAT_MULTIPLIERS.get(stat_lower, 1.0)
    
    if league_lower == "tennis":
        combo_key = (stat_lower, dir_lower)
        if combo_key in TENNIS_DIRECTION_COMBOS:
            return TENNIS_DIRECTION_COMBOS[combo_key]
        return TENNIS_STAT_MULTIPLIERS.get(stat_lower, 1.0)
    
    if league_lower == "cbb":
        combo_key = (stat_lower, dir_lower)
        if combo_key in CBB_DIRECTION_COMBOS:
            return CBB_DIRECTION_COMBOS[combo_key]
        return CBB_STAT_MULTIPLIERS.get(stat_lower, 1.0)
    
    if league_lower == "nfl":
        return NFL_STAT_MULTIPLIERS.get(stat_lower, 1.0)
    
    # NBA default (most comprehensive)
    combo_key = (stat_lower, dir_lower)
    if combo_key in STAT_DIRECTION_COMBOS:
        return STAT_DIRECTION_COMBOS[combo_key]
    
    # Fallback: generic stat * direction
    stat_mult = STAT_MULTIPLIERS_DATA_DRIVEN.get(stat_lower, 1.0)
    dir_mult = DIRECTION_ADJUSTMENT.get(dir_lower, 1.0)
    
    return stat_mult * dir_mult


def get_minimum_edge() -> float:
    """Get minimum edge threshold for a play."""
    if BYPASS_ALL_PENALTIES:
        return 0.0  # Any positive edge is a play
    return EDGE_THRESHOLDS["minimum_edge"]


def get_sample_size_factor(n_games: int) -> float:
    """Get confidence scaling based on sample size."""
    if BYPASS_ALL_PENALTIES:
        return 1.0
    
    if n_games < SAMPLE_SIZE_RULES["minimum_games"]:
        return 0.0  # VETO
    
    scaling = SAMPLE_SIZE_RULES["confidence_scaling"]
    for min_games, factor in sorted(scaling.items(), reverse=True):
        if n_games >= min_games:
            return factor
    
    return 0.80  # Default conservative


def should_veto_stat(stat: str) -> bool:
    """Check if stat type should be vetoed entirely."""
    stat_lower = stat.lower().strip()
    return STAT_MULTIPLIERS_DATA_DRIVEN.get(stat_lower, 1.0) <= 0.50


def is_variance_exposed(stat: str, direction: str) -> bool:
    """Check if a pick is variance-exposed (should limit stacking)."""
    combo = (stat.lower().strip(), direction.lower().strip())
    return combo in VARIANCE_PROP_PATTERNS


def is_safe_to_stack(stat: str, direction: str, league: str = "nba") -> bool:
    """Check if a pick is safe to stack (binary stats, unders)."""
    stat_lower = stat.lower().strip()
    dir_lower = direction.lower().strip()
    league_lower = league.lower().strip()
    
    # NHL binary stats are always safe
    if league_lower == "nhl" and stat_lower in NHL_BINARY_STATS:
        return True
    
    # Tennis unders are safe
    if league_lower == "tennis" and dir_lower in ("lower", "under"):
        return True
    
    # 3PM unders are safe
    if stat_lower in ("3pm", "threes") and dir_lower in ("lower", "under"):
        return True
    
    return False


def validate_ticket(picks: list) -> dict:
    """
    Validate a ticket against construction rules.
    
    Args:
        picks: List of dicts with keys: stat, direction, player, league, is_rookie (optional)
    
    Returns:
        {
            "valid": bool,
            "warnings": list[str],
            "violations": list[str],
            "variance_count": int
        }
    """
    result = {
        "valid": True,
        "warnings": [],
        "violations": [],
        "variance_count": 0,
    }
    
    variance_count = 0
    pra_overs = 0
    points_overs = 0
    rookie_count = 0
    
    for pick in picks:
        stat = pick.get("stat", "").lower()
        direction = pick.get("direction", "").lower()
        is_rookie = pick.get("is_rookie", False)
        
        # Count variance props
        if is_variance_exposed(stat, direction):
            variance_count += 1
        
        # Count PRA overs
        if stat in ("pra", "pts+reb+ast") and direction in ("higher", "over"):
            pra_overs += 1
        
        # Count points overs
        if stat in ("pts", "points") and direction in ("higher", "over"):
            points_overs += 1
        
        # Count rookies
        if is_rookie:
            rookie_count += 1
    
    result["variance_count"] = variance_count
    
    # Check violations
    if variance_count > TICKET_RULES["max_variance_props"]:
        result["violations"].append(
            f"Too many variance props: {variance_count} (max {TICKET_RULES['max_variance_props']})"
        )
        result["valid"] = False
    
    if pra_overs > TICKET_RULES["max_pra_overs"]:
        result["violations"].append(
            f"Too many PRA overs: {pra_overs} (max {TICKET_RULES['max_pra_overs']})"
        )
        result["valid"] = False
    
    if rookie_count > TICKET_RULES["max_rookie_props"]:
        result["warnings"].append(
            f"High rookie exposure: {rookie_count} (recommended max {TICKET_RULES['max_rookie_props']})"
        )
    
    # Warnings for borderline tickets
    if variance_count == TICKET_RULES["max_variance_props"]:
        result["warnings"].append("At variance limit - consider removing one volatile prop")
    
    return result


# Export for use in analyzers
__all__ = [
    'STAT_MULTIPLIERS_DATA_DRIVEN',
    'DIRECTION_ADJUSTMENT', 
    'EDGE_THRESHOLDS',
    'SAMPLE_SIZE_RULES',
    'VARIANCE_RULES',
    'VARIANCE_LABELS',
    'TICKET_RULES',
    'NHL_STAT_MULTIPLIERS',
    'NHL_BINARY_STATS',
    'TENNIS_STAT_MULTIPLIERS',
    'TENNIS_DIRECTION_COMBOS',
    'CBB_STAT_MULTIPLIERS',
    'CBB_DIRECTION_COMBOS',
    'ROOKIE_PENALTY',
    'PRA_OVER_LINE_CAP',
    'get_data_driven_multiplier',
    'get_minimum_edge',
    'get_sample_size_factor',
    'should_veto_stat',
    'is_variance_exposed',
    'is_safe_to_stack',
    'validate_ticket',
    'BYPASS_ALL_PENALTIES',
]
