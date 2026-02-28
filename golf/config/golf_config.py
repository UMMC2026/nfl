"""
Golf Configuration — Single Source of Truth
============================================
Tier thresholds, market definitions, course database.
"""

from typing import Dict, Optional

# =============================================================================
# REGISTRY (mirrors sport_registry.json structure)
# =============================================================================

GOLF_REGISTRY = {
    "enabled": True,
    "status": "DEVELOPMENT",  # DEVELOPMENT → PRODUCTION when validated
    "version": "0.1.0",
    "frozen": False,
    "data_sources": ["datagolf", "manual"],
    "pipeline": "golf/run_daily.py",
    "notes": "SG-based modeling. Course fit critical. Weather significant for wind events."
}

# =============================================================================
# TIER THRESHOLDS (Golf-Specific Overrides)
# =============================================================================
# Golf has higher variance than team sports — conservative tiers

GOLF_THRESHOLDS = {
    "SLAM": None,           # DISABLED — golf too volatile for 80%+ confidence
    "STRONG": 0.72,         # Top finish props with SG edge ≥+1.5
    "LEAN": 0.60,           # Standard edges with course fit confirmation
    "SPEC": 0.52,           # Speculative (longshots, weather plays)
    "AVOID": 0.0,
}

# Confidence caps by market type
GOLF_CONFIDENCE_CAPS = {
    "outright_winner": 0.45,    # Even elite players rarely >15% to win
    "top_5": 0.60,
    "top_10": 0.68,
    "top_20": 0.72,
    "make_cut": 0.85,           # Highest confidence market
    "miss_cut": 0.65,
    "h2h_matchup": 0.72,        # Head-to-head weekend/tournament
    "h2h_round": 0.68,          # Single round H2H
    "first_round_leader": 0.40, # High variance
    "nationality": 0.55,        # Top American, European, etc.
}

# =============================================================================
# MARKET DEFINITIONS
# =============================================================================

GOLF_MARKETS = {
    # Finish position markets
    "outright": {"stat": "finish_position", "line": 1, "direction": "equal"},
    "top_5": {"stat": "finish_position", "line": 5, "direction": "lower"},
    "top_10": {"stat": "finish_position", "line": 10, "direction": "lower"},
    "top_20": {"stat": "finish_position", "line": 20, "direction": "lower"},
    
    # Cut markets
    "make_cut": {"stat": "made_cut", "line": 0.5, "direction": "higher"},
    "miss_cut": {"stat": "made_cut", "line": 0.5, "direction": "lower"},
    
    # Head-to-head markets
    "h2h_tournament": {"stat": "finish_position", "direction": "h2h"},
    "h2h_round": {"stat": "round_score", "direction": "h2h"},
    
    # Scoring markets
    "round_score_over": {"stat": "round_score", "direction": "higher"},
    "round_score_under": {"stat": "round_score", "direction": "lower"},
    "tournament_total_over": {"stat": "total_score", "direction": "higher"},
    "tournament_total_under": {"stat": "total_score", "direction": "lower"},
    
    # First round leader
    "frl": {"stat": "round_1_score", "line": 1, "direction": "equal"},
}

# =============================================================================
# STROKES GAINED WEIGHTS BY COURSE TYPE
# =============================================================================
# Different courses emphasize different skills

SG_WEIGHTS_BY_COURSE_TYPE = {
    "balanced": {
        "sg_ott": 0.25,   # Off the tee (driving)
        "sg_app": 0.30,   # Approach shots
        "sg_arg": 0.20,   # Around the green
        "sg_putt": 0.25,  # Putting
    },
    "ball_strikers": {
        # Links, tight fairways, premium on accuracy
        "sg_ott": 0.35,
        "sg_app": 0.35,
        "sg_arg": 0.15,
        "sg_putt": 0.15,
    },
    "bombers": {
        # Long courses, wide fairways, par 5 reachability
        "sg_ott": 0.40,
        "sg_app": 0.25,
        "sg_arg": 0.15,
        "sg_putt": 0.20,
    },
    "putting_premium": {
        # Undulating greens, Augusta-style
        "sg_ott": 0.20,
        "sg_app": 0.25,
        "sg_arg": 0.20,
        "sg_putt": 0.35,
    },
    "short_game": {
        # US Open setups, thick rough
        "sg_ott": 0.20,
        "sg_app": 0.25,
        "sg_arg": 0.35,
        "sg_putt": 0.20,
    },
}

# =============================================================================
# COURSE DATABASE
# =============================================================================
# Key PGA Tour venues with characteristics

COURSE_DATABASE = {
    # Major Championships
    "augusta_national": {
        "name": "Augusta National Golf Club",
        "tournament": "The Masters",
        "par": 72,
        "yardage": 7545,
        "type": "putting_premium",
        "grass": "bentgrass_overseeded",
        "elevation_change": "significant",
        "avg_winning_score": -12,
        "cut_rule": "top_50_ties",
        "sg_correlation": {"sg_app": 0.35, "sg_putt": 0.32, "sg_ott": 0.20},
    },
    "southern_hills": {
        "name": "Southern Hills Country Club",
        "tournament": "PGA Championship",
        "par": 70,
        "yardage": 7556,
        "type": "ball_strikers",
        "grass": "bentgrass",
        "elevation_change": "moderate",
        "avg_winning_score": -6,
        "cut_rule": "top_70_ties",
    },
    "pinehurst_no2": {
        "name": "Pinehurst No. 2",
        "tournament": "US Open",
        "par": 70,
        "yardage": 7588,
        "type": "short_game",
        "grass": "bermuda",
        "elevation_change": "moderate",
        "avg_winning_score": -2,
        "cut_rule": "top_60_ties",
    },
    "royal_troon": {
        "name": "Royal Troon",
        "tournament": "The Open Championship",
        "par": 71,
        "yardage": 7385,
        "type": "ball_strikers",
        "grass": "fescue_links",
        "elevation_change": "minimal",
        "avg_winning_score": -8,
        "cut_rule": "top_70_ties",
        "wind_factor": 1.5,  # Amplified weather impact
    },
    
    # Signature Events
    "tpc_sawgrass": {
        "name": "TPC Sawgrass",
        "tournament": "The Players Championship",
        "par": 72,
        "yardage": 7256,
        "type": "balanced",
        "grass": "bermuda_overseeded",
        "avg_winning_score": -14,
        "cut_rule": "top_65_ties",
    },
    "bay_hill": {
        "name": "Bay Hill Club & Lodge",
        "tournament": "Arnold Palmer Invitational",
        "par": 72,
        "yardage": 7466,
        "type": "ball_strikers",
        "grass": "bermuda",
        "avg_winning_score": -10,
    },
    "riviera": {
        "name": "Riviera Country Club",
        "tournament": "Genesis Invitational",
        "par": 71,
        "yardage": 7322,
        "type": "ball_strikers",
        "grass": "kikuyu_poa",
        "avg_winning_score": -12,
    },
    "muirfield_village": {
        "name": "Muirfield Village Golf Club",
        "tournament": "The Memorial Tournament",
        "par": 72,
        "yardage": 7571,
        "type": "balanced",
        "grass": "bentgrass",
        "avg_winning_score": -13,
    },
    
    # Fall/Winter Events
    "torrey_pines_south": {
        "name": "Torrey Pines (South)",
        "tournament": "Farmers Insurance Open",
        "par": 72,
        "yardage": 7765,
        "type": "bombers",
        "grass": "kikuyu_poa",
        "avg_winning_score": -14,
    },
    "pebble_beach": {
        "name": "Pebble Beach Golf Links",
        "tournament": "AT&T Pebble Beach Pro-Am",
        "par": 72,
        "yardage": 7075,
        "type": "short_game",
        "grass": "poa_annua",
        "avg_winning_score": -16,
        "wind_factor": 1.3,
    },
}

# =============================================================================
# WEATHER ADJUSTMENTS
# =============================================================================

WIND_ADJUSTMENT_FACTORS = {
    "calm": 0.0,           # 0-5 mph
    "light": -0.2,         # 5-10 mph
    "moderate": -0.5,      # 10-15 mph
    "strong": -1.0,        # 15-20 mph
    "very_strong": -1.8,   # 20-25 mph
    "extreme": -3.0,       # 25+ mph
}

# Bogey rate increase per wind category
WIND_BOGEY_MULTIPLIER = {
    "calm": 1.0,
    "light": 1.05,
    "moderate": 1.12,
    "strong": 1.25,
    "very_strong": 1.40,
    "extreme": 1.60,
}

# =============================================================================
# DATA SOURCE CONFIG
# =============================================================================

DATAGOLF_CONFIG = {
    "base_url": "https://feeds.datagolf.com",
    "endpoints": {
        "rankings": "/preds/get-dg-rankings",
        "skill_decompositions": "/preds/skill-decompositions",
        "pre_tournament": "/preds/pre-tournament-preds",
        "live_tournament": "/preds/in-play-tournament-preds",
        "approach": "/preds/approach-skill",
        "course_fit": "/historical-raw-data/event-list",
    },
    "rate_limit_per_minute": 10,
}
