"""
CBB Context Gates — Situational Filters

These gates handle CBB-specific chaos factors:
1. Conference Phase (Nov-Dec vs Jan-Feb vs March)
2. Blowout Protection (spread-based)
3. Multi-Window Projection (L5/L10/Season blend)
4. SOS Calibration (opponent defense rank)
5. Road Adjustments (context-aware)

Implementation Date: 2026-02-01
Author: Risk-First Pipeline Team
"""

from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime
import math


# =============================================================================
# MULTI-WINDOW PROJECTION (CBB-SAFE)
# =============================================================================

@dataclass
class CBBWindowConfig:
    """
    CBB multi-window projection configuration.
    
    This REPLACES the single L10 with 40% blend.
    Now we have context-aware weighting.
    """
    
    # Conference play weights (Jan-Feb, stable)
    conference_weights: Dict[str, float] = None
    
    # Non-conference weights (Nov-Dec, rely on baseline)
    nonconf_weights: Dict[str, float] = None
    
    # Post-injury weights (recent focus)
    injury_weights: Dict[str, float] = None
    
    # Default weights
    default_weights: Dict[str, float] = None
    
    def __post_init__(self):
        if self.conference_weights is None:
            self.conference_weights = {
                "L5": 0.40,     # Recent conference form
                "L10": 0.40,   # Medium-term trend
                "SEASON": 0.20 # Baseline
            }
        
        if self.nonconf_weights is None:
            self.nonconf_weights = {
                "L10": 0.60,    # Recent games
                "SEASON": 0.40  # More baseline weight
            }
        
        if self.injury_weights is None:
            self.injury_weights = {
                "L3": 0.50,     # Very recent
                "L5": 0.30,     # Recent
                "L10": 0.20    # Some history
            }
        
        if self.default_weights is None:
            self.default_weights = {
                "L5": 0.25,
                "L10": 0.40,
                "L15": 0.20,
                "SEASON": 0.15
            }


CBB_WINDOW_CONFIG = CBBWindowConfig()


def calculate_multi_window_projection(
    player_stats: Dict,
    game_context: Optional[Dict] = None
) -> Tuple[float, float, Dict]:
    """
    Calculate CBB projection using multi-window blend.
    
    Returns: (projected_mu, projected_sigma, details)
    """
    # Determine which weights to use
    is_conference = game_context.get("is_conference_game", True) if game_context else True
    games_since_injury = player_stats.get("games_since_injury")
    game_month = game_context.get("game_month", 1) if game_context else 1
    
    if games_since_injury is not None and games_since_injury < 5:
        weights = CBB_WINDOW_CONFIG.injury_weights
        mode = "POST_INJURY"
    elif game_month in [11, 12] and not is_conference:
        weights = CBB_WINDOW_CONFIG.nonconf_weights
        mode = "NONCONF_EARLY"
    elif game_month in [1, 2]:
        weights = CBB_WINDOW_CONFIG.conference_weights
        mode = "CONFERENCE"
    else:
        weights = CBB_WINDOW_CONFIG.default_weights
        mode = "DEFAULT"
    
    # Calculate weighted projection
    total_weight = 0.0
    weighted_mu = 0.0
    weighted_var = 0.0
    
    details = {"mode": mode, "windows_used": [], "weights": weights.copy()}
    
    for window, weight in weights.items():
        mu_key = f"{window.lower()}_mu"
        sigma_key = f"{window.lower()}_sigma"
        
        mu = player_stats.get(mu_key)
        sigma = player_stats.get(sigma_key)
        
        if mu is not None:
            weighted_mu += weight * mu
            total_weight += weight
            details["windows_used"].append(window)
            
            if sigma is not None:
                weighted_var += weight * (sigma ** 2)
    
    # Fallback if no windows available
    if total_weight == 0:
        fallback_mu = player_stats.get("mu", player_stats.get("season_mu", 0))
        fallback_sigma = player_stats.get("sigma", player_stats.get("season_sigma", 1))
        return fallback_mu, fallback_sigma, {"mode": "FALLBACK", "windows_used": []}
    
    projected_mu = weighted_mu / total_weight
    projected_sigma = math.sqrt(weighted_var / total_weight) if weighted_var > 0 else 1.0
    
    details["projected_mu"] = round(projected_mu, 2)
    details["projected_sigma"] = round(projected_sigma, 2)
    
    return projected_mu, projected_sigma, details


# =============================================================================
# CONFERENCE PHASE DETECTION
# =============================================================================

def detect_conference_phase(
    game_date: datetime,
    team1_conference: Optional[str] = None,
    team2_conference: Optional[str] = None,
    is_tournament: bool = False
) -> Dict:
    """
    Detect which phase of CBB season we're in.
    
    Phases:
    - EARLY_NONCONF: Nov 1 - Dec 31, different conferences
    - EARLY_CONF: Nov 1 - Dec 31, same conference
    - CONFERENCE: Jan 1 - Feb 28
    - CONF_TOURNAMENT: Early March
    - MARCH_MADNESS: NCAA Tournament
    
    Returns: Phase info dict
    """
    month = game_date.month
    day = game_date.day
    
    same_conference = (
        team1_conference and team2_conference and 
        team1_conference == team2_conference
    )
    
    result = {
        "month": month,
        "is_same_conference": same_conference,
        "is_tournament": is_tournament,
    }
    
    if is_tournament:
        result["phase"] = "MARCH_MADNESS"
        result["reliability"] = "LOW"
        result["min_z_required"] = 0.85
        result["volatility_multiplier"] = 1.5
        
    elif month in [11, 12]:
        if same_conference:
            result["phase"] = "EARLY_CONF"
            result["reliability"] = "MEDIUM"
            result["min_z_required"] = 0.65
            result["volatility_multiplier"] = 1.2
        else:
            result["phase"] = "EARLY_NONCONF"
            result["reliability"] = "LOW"
            result["min_z_required"] = 0.80
            result["volatility_multiplier"] = 1.4
            
    elif month in [1, 2]:
        result["phase"] = "CONFERENCE"
        result["reliability"] = "HIGH"
        result["min_z_required"] = 0.50
        result["volatility_multiplier"] = 1.0
        
    elif month == 3:
        if day <= 15 and not is_tournament:
            result["phase"] = "CONF_TOURNAMENT"
            result["reliability"] = "MEDIUM"
            result["min_z_required"] = 0.70
            result["volatility_multiplier"] = 1.3
        else:
            result["phase"] = "MARCH_MADNESS"
            result["reliability"] = "LOW"
            result["min_z_required"] = 0.85
            result["volatility_multiplier"] = 1.5
    else:
        result["phase"] = "OFFSEASON"
        result["reliability"] = "NONE"
        result["min_z_required"] = 1.0
        result["volatility_multiplier"] = 2.0
    
    return result


# =============================================================================
# BLOWOUT DETECTION & PROTECTION
# =============================================================================

def analyze_blowout_risk(
    spread: float,
    player_role: str = "ROLE_PLAYER",
    stat_type: str = "PTS",
    direction: str = "higher"
) -> Dict:
    """
    Comprehensive blowout risk analysis.
    
    CBB has ~40% blowout rate. This is CRITICAL protection.
    
    Returns: Blowout risk assessment dict
    """
    # Handle None spread
    if spread is None:
        spread = 0
    
    abs_spread = abs(spread)
    is_over = direction.lower() in ["higher", "over"]
    
    result = {
        "spread": spread,
        "abs_spread": abs_spread,
        "player_role": player_role,
        "stat_type": stat_type.upper(),
        "direction": direction,
    }
    
    # Classify blowout tier
    if abs_spread >= 20:
        result["tier"] = "EXTREME"
        result["blowout_probability"] = 0.70
        result["star_sits_minutes"] = "10-15"
    elif abs_spread >= 15:
        result["tier"] = "HIGH"
        result["blowout_probability"] = 0.55
        result["star_sits_minutes"] = "6-10"
    elif abs_spread >= 12:
        result["tier"] = "MODERATE"
        result["blowout_probability"] = 0.40
        result["star_sits_minutes"] = "4-6"
    elif abs_spread >= 8:
        result["tier"] = "LOW"
        result["blowout_probability"] = 0.25
        result["star_sits_minutes"] = "0-4"
    else:
        result["tier"] = "COMPETITIVE"
        result["blowout_probability"] = 0.10
        result["star_sits_minutes"] = "0"
    
    # Calculate recommendation
    if result["tier"] == "EXTREME":
        if player_role == "STAR" and is_over:
            result["recommendation"] = "BLOCK"
            result["reason"] = "Star will sit final 10-15 minutes"
        else:
            result["recommendation"] = "HEAVY_PENALTY"
            result["penalty"] = 0.70
            
    elif result["tier"] == "HIGH":
        if player_role == "STAR" and is_over:
            result["recommendation"] = "HEAVY_PENALTY"
            result["penalty"] = 0.75
        else:
            result["recommendation"] = "MODERATE_PENALTY"
            result["penalty"] = 0.85
            
    elif result["tier"] == "MODERATE":
        result["recommendation"] = "LIGHT_PENALTY"
        result["penalty"] = 0.92
        
    else:
        result["recommendation"] = "NO_PENALTY"
        result["penalty"] = 1.00
    
    # Stat-specific adjustments
    stat_upper = stat_type.upper()
    
    # Rebounds often survive blowouts (garbage time chaos)
    if stat_upper == "REB" and not is_over:
        result["penalty"] = min(1.0, result.get("penalty", 1.0) + 0.05)
        result["stat_note"] = "Rebounds survive blowouts better"
    
    # 3PM overs hurt badly in blowouts
    if stat_upper == "3PM" and is_over and result["tier"] in ["HIGH", "EXTREME"]:
        result["penalty"] = result.get("penalty", 1.0) * 0.90
        result["stat_note"] = "3PM overs collapse in blowouts"
    
    return result


# =============================================================================
# SOS (STRENGTH OF SCHEDULE) CALIBRATION
# =============================================================================

# Defense rankings tiers (based on KenPom/etc.)
SOS_TIERS = {
    "ELITE": {"min_rank": 1, "max_rank": 25, "pts_modifier": 0.82, "reb_modifier": 0.90, "ast_modifier": 0.88},
    "EXCELLENT": {"min_rank": 26, "max_rank": 50, "pts_modifier": 0.88, "reb_modifier": 0.93, "ast_modifier": 0.90},
    "GOOD": {"min_rank": 51, "max_rank": 100, "pts_modifier": 0.93, "reb_modifier": 0.96, "ast_modifier": 0.94},
    "AVERAGE": {"min_rank": 101, "max_rank": 175, "pts_modifier": 0.97, "reb_modifier": 0.98, "ast_modifier": 0.97},
    "BELOW_AVG": {"min_rank": 176, "max_rank": 250, "pts_modifier": 1.00, "reb_modifier": 1.00, "ast_modifier": 1.00},
    "WEAK": {"min_rank": 251, "max_rank": 300, "pts_modifier": 1.05, "reb_modifier": 1.03, "ast_modifier": 1.05},
    "BAD": {"min_rank": 301, "max_rank": 362, "pts_modifier": 1.10, "reb_modifier": 1.06, "ast_modifier": 1.08},
}


def get_sos_tier(defense_rank: int) -> Dict:
    """Get SOS tier info for a defense ranking."""
    for tier_name, tier_info in SOS_TIERS.items():
        if tier_info["min_rank"] <= defense_rank <= tier_info["max_rank"]:
            return {"tier": tier_name, **tier_info}
    
    return {"tier": "UNKNOWN", "pts_modifier": 1.0, "reb_modifier": 1.0, "ast_modifier": 1.0}


def apply_sos_calibration(
    player_mu: float,
    stat_type: str,
    opponent_def_rank: int
) -> Tuple[float, Dict]:
    """
    Apply SOS calibration to player projection.
    
    Returns: (adjusted_mu, details)
    """
    tier_info = get_sos_tier(opponent_def_rank)
    
    stat_upper = stat_type.upper()
    
    # Get appropriate modifier
    if stat_upper in ["PTS", "POINTS", "PTS+REB"]:
        modifier = tier_info.get("pts_modifier", 1.0)
    elif stat_upper in ["REB", "REBOUNDS"]:
        modifier = tier_info.get("reb_modifier", 1.0)
    elif stat_upper in ["AST", "ASSISTS"]:
        modifier = tier_info.get("ast_modifier", 1.0)
    else:
        modifier = (tier_info.get("pts_modifier", 1.0) + tier_info.get("reb_modifier", 1.0)) / 2
    
    adjusted_mu = player_mu * modifier
    
    details = {
        "original_mu": round(player_mu, 2),
        "adjusted_mu": round(adjusted_mu, 2),
        "modifier": modifier,
        "opponent_rank": opponent_def_rank,
        "tier": tier_info["tier"],
        "stat_type": stat_upper,
    }
    
    return adjusted_mu, details


# =============================================================================
# ROAD CONTEXT ANALYSIS
# =============================================================================

# Conference rivalries (hostile environments)
MAJOR_RIVALRIES = {
    # ACC
    ("DUKE", "UNC"): "EXTREME",
    ("UNC", "NCST"): "HIGH",
    ("LOUISVILLE", "KENTUCKY"): "EXTREME",
    
    # Big Ten
    ("MICHIGAN", "OHST"): "EXTREME",
    ("MICHIGAN", "MSU"): "HIGH",
    ("INDIANA", "PURDUE"): "HIGH",
    
    # SEC
    ("KENTUCKY", "TENNESSEE"): "HIGH",
    ("AUBURN", "ALABAMA"): "HIGH",
    
    # Big 12
    ("KANSAS", "KSTATE"): "HIGH",
    ("KANSAS", "MISSOURI"): "EXTREME",
    
    # Pac-12/Big 10
    ("UCLA", "USC"): "HIGH",
    ("ARIZONA", "ASU"): "HIGH",
}


def analyze_road_context(
    home_team: str,
    away_team: str,
    player_stats: Optional[Dict] = None,
    game_context: Optional[Dict] = None
) -> Dict:
    """
    Analyze road game context for penalty calculation.
    
    Returns: Road context assessment
    """
    result = {
        "is_away": True,
        "home_team": home_team,
        "away_team": away_team,
        "base_penalty": 0.10,  # 10% baseline
    }
    
    # Check for rivalry
    pair1 = (home_team.upper(), away_team.upper())
    pair2 = (away_team.upper(), home_team.upper())
    
    rivalry_level = MAJOR_RIVALRIES.get(pair1) or MAJOR_RIVALRIES.get(pair2)
    if rivalry_level:
        result["is_rivalry"] = True
        result["rivalry_level"] = rivalry_level
        if rivalry_level == "EXTREME":
            result["base_penalty"] += 0.08
        else:
            result["base_penalty"] += 0.05
    else:
        result["is_rivalry"] = False
    
    # Travel distance (if provided)
    travel_miles = game_context.get("travel_distance_miles") if game_context else None
    if travel_miles:
        result["travel_miles"] = travel_miles
        if travel_miles > 1500:
            result["base_penalty"] += 0.06
            result["travel_note"] = "Cross-country travel"
        elif travel_miles > 1000:
            result["base_penalty"] += 0.04
            result["travel_note"] = "Long distance"
        elif travel_miles > 500:
            result["base_penalty"] += 0.02
            result["travel_note"] = "Moderate distance"
    
    # Altitude (for mountain teams)
    altitude_change = game_context.get("altitude_change_ft") if game_context else None
    if altitude_change and altitude_change > 3000:
        result["altitude_change"] = altitude_change
        result["base_penalty"] += 0.05
        result["altitude_note"] = "High altitude adjustment"
    
    # Experience factor (seniors handle road better)
    if player_stats:
        team_avg_age = player_stats.get("team_avg_age")
        if team_avg_age and team_avg_age > 22.5:
            result["base_penalty"] *= 0.75
            result["experience_note"] = "Experienced team handles road better"
    
    # Cap total penalty
    result["final_penalty"] = min(result["base_penalty"], 0.25)
    result["probability_multiplier"] = 1.0 - result["final_penalty"]
    
    return result


# =============================================================================
# COMBINED CONTEXT GATE
# =============================================================================

def apply_all_context_gates(
    prop: Dict,
    player_stats: Dict,
    game_context: Dict
) -> Dict:
    """
    Apply all CBB context gates to a prop.
    
    This is the main entry point for context-based filtering.
    
    Returns: Updated prop with all context adjustments
    """
    context_result = {
        "context_adjustments": [],
        "context_penalty": 1.0,
        "context_flags": [],
    }
    
    # 1. Multi-window projection
    projected_mu, projected_sigma, window_details = calculate_multi_window_projection(
        player_stats, game_context
    )
    context_result["projected_mu"] = projected_mu
    context_result["projected_sigma"] = projected_sigma
    context_result["window_details"] = window_details
    
    # 2. Conference phase
    game_date = game_context.get("game_date")
    if game_date:
        if isinstance(game_date, str):
            game_date = datetime.fromisoformat(game_date)
        
        phase_info = detect_conference_phase(
            game_date,
            game_context.get("team1_conference"),
            game_context.get("team2_conference"),
            game_context.get("is_tournament", False)
        )
        context_result["phase_info"] = phase_info
        context_result["context_flags"].append(f"PHASE:{phase_info['phase']}")
        
        # Apply volatility multiplier to sigma
        projected_sigma *= phase_info.get("volatility_multiplier", 1.0)
    
    # 3. Blowout analysis
    spread = game_context.get("spread", 0)
    direction = prop.get("direction", "higher")
    player_role = player_stats.get("role", "ROLE_PLAYER")
    stat_type = prop.get("stat", "PTS")
    
    blowout_info = analyze_blowout_risk(spread, player_role, stat_type, direction)
    context_result["blowout_info"] = blowout_info
    
    if blowout_info.get("recommendation") == "BLOCK":
        context_result["context_flags"].append("BLOWOUT_BLOCK")
        prop["blocked"] = True
        prop["block_reason"] = blowout_info.get("reason", "Blowout risk")
    elif blowout_info.get("penalty", 1.0) < 1.0:
        context_result["context_penalty"] *= blowout_info["penalty"]
        context_result["context_adjustments"].append(
            f"BLOWOUT:{blowout_info['tier']}:{blowout_info['penalty']:.0%}"
        )
    
    # 4. SOS calibration
    opponent_def_rank = game_context.get("opponent_def_rank")
    if opponent_def_rank:
        adjusted_mu, sos_details = apply_sos_calibration(
            projected_mu, stat_type, opponent_def_rank
        )
        context_result["sos_details"] = sos_details
        context_result["projected_mu"] = adjusted_mu
        
        if sos_details["modifier"] != 1.0:
            pct = (sos_details["modifier"] - 1.0) * 100
            sign = "+" if pct >= 0 else ""
            context_result["context_adjustments"].append(
                f"SOS:{sos_details['tier']}:{sign}{pct:.0f}%"
            )
    
    # 5. Road penalty
    is_away = game_context.get("is_away", False)
    if is_away:
        road_info = analyze_road_context(
            game_context.get("home_team", ""),
            game_context.get("away_team", ""),
            player_stats,
            game_context
        )
        context_result["road_info"] = road_info
        context_result["context_penalty"] *= road_info["probability_multiplier"]
        context_result["context_adjustments"].append(
            f"ROAD:{road_info['final_penalty']:.0%}"
        )
        
        if road_info.get("is_rivalry"):
            context_result["context_flags"].append(
                f"RIVALRY:{road_info['rivalry_level']}"
            )
    
    # Attach to prop
    prop["context_penalty"] = round(context_result["context_penalty"], 3)
    prop["context_adjustments"] = context_result["context_adjustments"]
    prop["context_flags"] = context_result["context_flags"]
    prop["projected_mu"] = round(context_result["projected_mu"], 2)
    prop["projected_sigma"] = round(projected_sigma, 2)
    
    # Apply penalty to probability
    if "probability" in prop:
        current_prob = prop.get("raw_probability", prop["probability"])
        prop["probability"] = round(current_prob * context_result["context_penalty"], 4)
    
    return prop
