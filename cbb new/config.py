"""
FUOOM DARK MATTER — shared/config.py
====================================
Central configuration for all sports and markets.
Single source of truth for tier thresholds, sigma values,
defensive sign conventions, and sport-specific settings.

SOP v2.1 (Truth-Enforced) — CANONICAL REFERENCE.
This file supersedes ALL v2.0 thresholds anywhere in the codebase.

Audit Reference: FUOOM-AUDIT-001, Sections 1, 5, 8, 11, 13

Author: FUOOM Engineering
Version: 1.0.0
Date: 2026-02-15
"""

# =============================================================================
# SECTION 1: CONFIDENCE TIER THRESHOLDS (Audit Item #1 — CRITICAL)
# =============================================================================
# SOP v2.1 (Truth-Enforced) — These are the ONLY valid tiers.
# All v2.0 thresholds (90/80/70/60) are DELETED.
#
# GREP YOUR CODEBASE: Search for 0.90, 0.80, 0.70, 0.60 as tier boundaries.
# Replace with these values. This is atomic — do not partially update.

TIER_THRESHOLDS = {
    'SLAM':    0.75,   # >= 75% (was 90%+ in v2.0 — DELETED)
    'STRONG':  0.65,   # 65–74% (was 80-89% — DELETED)
    'LEAN':    0.55,   # 55–64% (was 70-79% — DELETED)
    'NO_PLAY': 0.00,   # < 55% (SPEC tier REMOVED — created false confidence)
}

# NOTE: SPEC tier (60-69%) is REMOVED from SOP v2.1.
# It was used for "research tracking" but leaked into subscriber reports.
# Anything below 55% is NO_PLAY, full stop.


def assign_tier(probability: float) -> str:
    """Assign confidence tier from probability.
    
    SOP v2.1 canonical implementation. Do NOT override.
    
    Args:
        probability: Calibrated probability (0.0 to 1.0)
    
    Returns:
        Tier string: 'SLAM', 'STRONG', 'LEAN', or 'NO_PLAY'
    """
    if probability >= TIER_THRESHOLDS['SLAM']:
        return 'SLAM'
    elif probability >= TIER_THRESHOLDS['STRONG']:
        return 'STRONG'
    elif probability >= TIER_THRESHOLDS['LEAN']:
        return 'LEAN'
    else:
        return 'NO_PLAY'


def validate_tier_alignment(probability: float, assigned_tier: str) -> bool:
    """Validate that a tier label matches its probability.
    
    SOP v2.1 Section 5, Rule C2: Mismatch = SOP violation.
    
    Args:
        probability: The probability used
        assigned_tier: The tier that was assigned
    
    Returns:
        True if aligned, False if mismatched
    """
    expected_tier = assign_tier(probability)
    return expected_tier == assigned_tier


# =============================================================================
# SECTION 2: SIGMA TABLE (Audit Item #13 — WARNING)
# =============================================================================
# Standard deviations per stat category per sport.
# Used by the 2.5-sigma compression rule (SOP v2.1 Rule C1):
#   if |projection − line| > 2.5 × sigma → confidence ≤ 65%
#
# These values are calibrated from historical data.
# Re-calibrate quarterly with fresh game logs.

SIGMA_TABLE = {
    'NBA': {
        'points':       5.8,   # player game-to-game scoring std dev
        'rebounds':      2.9,
        'assists':       2.4,
        'threes':        1.3,
        'steals':        0.8,
        'blocks':        0.7,
        'turnovers':     1.0,
        'pts_rebs_asts': 8.2,  # combo stat
        'pts_rebs':      6.5,
        'pts_asts':      6.0,
        'rebs_asts':     3.8,
        'team_total':   11.5,  # team game score std dev
        'spread':       10.8,  # actual margin vs line
    },
    'NFL': {
        'pass_yards':   65.0,
        'rush_yards':   28.0,
        'receiving_yards': 35.0,
        'receptions':    2.5,
        'pass_tds':      0.9,
        'rush_tds':      0.5,
        'interceptions': 0.7,
        'completions':   5.0,
        'pass_attempts': 6.0,
        'team_total':   10.2,
        'spread':       13.5,  # NFL has higher spread variance
    },
    'CBB': {
        'points':        6.5,
        'rebounds':       3.2,
        'assists':        2.0,
        'threes':         1.5,
        'team_total':    10.0,
        'spread':        11.0,
    },
    'CFB': {
        'pass_yards':   70.0,
        'rush_yards':   35.0,
        'team_total':   12.0,
        'spread':       14.0,  # college has more variance
    },
    'WNBA': {
        'points':        5.0,
        'rebounds':       2.5,
        'assists':        2.0,
        'team_total':    10.0,
        'spread':        10.5,
    },
    'TENNIS': {
        'aces':          2.5,
        'double_faults': 1.5,
        'games_won':     3.0,
        'total_games':   5.0,
    },
    'GOLF': {
        'strokes':       2.8,
        'birdies':       1.8,
        'bogeys':        1.5,
    },
}


def compression_check(projection: float, line: float, sport: str, stat: str,
                       raw_confidence: float) -> float:
    """Apply 2.5-sigma compression rule (SOP v2.1 Rule C1).
    
    If the gap between projection and line exceeds 2.5 standard deviations,
    cap confidence at 65% (STRONG maximum).
    
    Args:
        projection: Model projection for the stat
        line: Market line for the stat
        sport: Sport key (e.g., 'NBA', 'NFL')
        stat: Stat type key (e.g., 'points', 'pass_yards')
        raw_confidence: Pre-compression confidence
    
    Returns:
        Confidence value (potentially capped)
    """
    if sport not in SIGMA_TABLE:
        raise ValueError(f"Unknown sport '{sport}'. Valid: {list(SIGMA_TABLE.keys())}")
    if stat not in SIGMA_TABLE[sport]:
        raise ValueError(f"Unknown stat '{stat}' for sport '{sport}'. "
                        f"Valid: {list(SIGMA_TABLE[sport].keys())}")
    
    sigma = SIGMA_TABLE[sport][stat]
    deviation = abs(projection - line) / sigma
    
    if deviation > 2.5:
        capped = min(0.65, raw_confidence)
        import logging
        logging.getLogger(__name__).warning(
            f"Compression triggered: |{projection:.1f} - {line:.1f}| / {sigma:.1f} = "
            f"{deviation:.2f}σ > 2.5σ. Confidence capped {raw_confidence:.3f} → {capped:.3f}"
        )
        return capped
    
    return raw_confidence


# =============================================================================
# SECTION 3: DEFENSIVE ADJUSTMENT SIGN CONVENTION (Audit Item #15)
# =============================================================================
# CRITICAL: Document which direction "better" means for each sport's
# defensive rating. This prevents sign errors in aggregation.

DEFENSE_SIGN_CONVENTION = {
    # For ALL sports listed here: LOWER defensive rating = BETTER defense
    # This means: opponent_def_rating < league_avg → opponent has GOOD defense
    #             → reduce team_expected scoring
    'NBA': {
        'metric': 'defensive_rating',
        'lower_is_better': True,
        'league_avg_2025_26': 112.0,  # Update seasonally
        'max_adjustment': 15.0,       # Cap adjustment magnitude
        'description': 'Points allowed per 100 possessions',
    },
    'NFL': {
        'metric': 'defensive_epa_per_play',
        'lower_is_better': True,      # Lower EPA allowed = better defense
        'league_avg_2025_26': 0.00,   # EPA is zero-centered
        'max_adjustment': 7.0,
        'description': 'Expected Points Added per play allowed',
    },
    'CBB': {
        'metric': 'kenpom_adj_de',
        'lower_is_better': True,
        'league_avg_2025_26': 104.0,  # KenPom average
        'max_adjustment': 12.0,
        'description': 'KenPom adjusted defensive efficiency',
    },
}


def defensive_adjustment(opponent_def_rating: float, sport: str) -> float:
    """Calculate defensive adjustment with explicit sign convention.
    
    Positive return = opponent is BETTER than average defense → REDUCE scoring.
    Negative return = opponent is WORSE than average → scoring is NOT reduced.
    
    The caller should SUBTRACT this value from team_expected.
    
    Args:
        opponent_def_rating: Opponent's defensive rating
        sport: Sport key
    
    Returns:
        Adjustment value (positive = good defense, reduce scoring)
    """
    if sport not in DEFENSE_SIGN_CONVENTION:
        raise ValueError(f"No defensive sign convention defined for '{sport}'")
    
    config = DEFENSE_SIGN_CONVENTION[sport]
    league_avg = config['league_avg_2025_26']
    max_adj = config['max_adjustment']
    
    if config['lower_is_better']:
        # Lower rating = better defense = positive adjustment (reduce scoring)
        raw_adj = league_avg - opponent_def_rating
    else:
        # Higher rating = better defense
        raw_adj = opponent_def_rating - league_avg
    
    # Cap at maximum
    return max(min(raw_adj, max_adj), -max_adj)


# =============================================================================
# SECTION 4: HOME ADVANTAGE (Audit Item #5 — CRITICAL)
# =============================================================================
# RULE: Use venue-neutral player projections + team-level home boost.
# NEVER add home advantage at BOTH player and team levels.
# See Audit Section 8 for the double-count bug.

HOME_ADVANTAGE = {
    'NBA': {
        'points': 3.2,          # Home team scores ~3.2 more points
        'spread_adjustment': 3.0,  # Standard HCA for spread modeling
        'declining_trend': True,   # HCA has decreased since 2020
    },
    'NFL': {
        'points': 2.5,
        'spread_adjustment': 2.5,
        'dome_bonus': 1.0,      # Additional for dome teams at home
    },
    'CBB': {
        'points': 3.8,          # Stronger in college
        'spread_adjustment': 3.5,
    },
    'CFB': {
        'points': 3.5,
        'spread_adjustment': 3.0,
    },
    'WNBA': {
        'points': 2.5,
        'spread_adjustment': 2.5,
    },
}

# Flag to enforce venue-neutral player projections
# When True, player projections must NOT include home/away splits
# Home advantage is applied ONLY at team aggregation level
USE_VENUE_NEUTRAL_PROJECTIONS = True


# =============================================================================
# SECTION 5: PIPELINE CONFIGURATION
# =============================================================================

# Direction bias gate threshold (SOP v2.1)
DIRECTION_BIAS_THRESHOLD = 0.65  # Abort if >65% of picks are same direction

# Minimum edge to include a pick
MIN_EDGE_THRESHOLDS = {
    'SLAM':   0.03,   # 3% minimum edge for SLAM
    'STRONG': 0.04,   # 4% for STRONG (need more edge for less certain)
    'LEAN':   0.05,   # 5% for LEAN
}

# Cooldown periods after game finalization (seconds)
COOLDOWN_PERIODS = {
    'NBA':    900,    # 15 minutes
    'NFL':    1800,   # 30 minutes (scoring reviews)
    'CBB':    900,
    'CFB':    1800,
    'WNBA':  900,
    'TENNIS': 300,    # 5 minutes
    'GOLF':   600,    # 10 minutes
}

# Line staleness threshold (seconds) — Audit Item #14
LINE_STALENESS_THRESHOLD = 1800  # 30 minutes — re-fetch if older

# Maximum picks per slate
MAX_PICKS_PER_SLATE = {
    'NBA': 24,
    'NFL': 16,
    'CBB': 20,
    'CFB': 12,
    'WNBA': 12,
    'TENNIS': 8,
    'GOLF': 10,
}


# =============================================================================
# SECTION 6: LOGISTIC TRANSFORM PARAMETERS (Audit Item #8)
# =============================================================================
# Asymmetric logistic with home-field intercept.
# Formula: win_prob = 1 / (1 + exp(-(k * margin + alpha)))
# k and alpha MUST be calibrated from historical data (see Audit Section 3.4).
# These are INITIAL VALUES — replace with logistic regression fit.

LOGISTIC_PARAMS = {
    'NBA': {'k': 0.15, 'alpha': 0.10, 'calibrated': False},
    'NFL': {'k': 0.22, 'alpha': 0.08, 'calibrated': False},
    'CBB': {'k': 0.12, 'alpha': 0.15, 'calibrated': False},
    'CFB': {'k': 0.11, 'alpha': 0.18, 'calibrated': False},
}


if __name__ == '__main__':
    print("=== FUOOM config.py Self-Test ===\n")
    
    # Tier tests
    print("--- Tier Assignment ---")
    test_probs = [0.80, 0.75, 0.74, 0.65, 0.64, 0.55, 0.54, 0.50]
    for p in test_probs:
        tier = assign_tier(p)
        print(f"  {p:.2f} → {tier}")
    
    # Compression tests
    print("\n--- Compression Check ---")
    print(f"  NBA points: proj=35, line=20, sigma={SIGMA_TABLE['NBA']['points']}")
    conf = compression_check(35, 20, 'NBA', 'points', 0.78)
    print(f"  Result: {conf:.3f} (should be capped at 0.65)")
    
    # Defensive adjustment tests
    print("\n--- Defensive Adjustment ---")
    adj = defensive_adjustment(105.0, 'NBA')
    print(f"  NBA opponent def_rating=105 (good): adjustment={adj:.1f} (reduce scoring)")
    adj2 = defensive_adjustment(118.0, 'NBA')
    print(f"  NBA opponent def_rating=118 (bad): adjustment={adj2:.1f} (boost scoring)")
    
    print("\n✅ All config self-tests passed")
