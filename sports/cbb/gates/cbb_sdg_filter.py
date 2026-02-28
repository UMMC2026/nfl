"""
CBB Stat Deviation Gate (SDG) — Soft Volatility Governor

CRITICAL: This is NOT a hard block. It's a probability compressor that PRICES
variance instead of eliminating it.

Key Differences from NBA SDG:
- Stricter z-score thresholds (0.60 PTS vs 0.40 NBA)
- Tiered CV thresholds by player role (star/role/specialist/bench)
- Multi-window validation (must pass L10 AND Season)
- Blowout-aware thresholds (spread >12 → stricter z)
- SOS calibration (opponent defense rank adjustment)

Implementation Date: 2026-02-01
Author: Risk-First Pipeline Team
"""

from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum
import math


# =============================================================================
# CONFIGURATION
# =============================================================================

class PlayerRole(Enum):
    """Player role classification for tiered CV thresholds."""
    STAR = "STAR"               # Usage >25%
    ROLE_PLAYER = "ROLE_PLAYER" # Usage 15-25%
    SPECIALIST = "SPECIALIST"   # 3PT shooters, rim protectors
    BENCH = "BENCH"             # <15% usage, rotation player


@dataclass
class CBBSDGConfig:
    """
    CBB SDG Configuration — Stricter than NBA.
    
    GOVERNANCE: These are calibration-derived values. Do NOT hardcode elsewhere.
    """
    
    # Z-Score Thresholds (50% stricter than NBA)
    z_thresholds: Dict[str, float] = None
    
    # Blowout-Adjusted Z-Thresholds
    z_thresholds_blowout: Dict[str, float] = None
    
    # CV Thresholds by Role (tiered, not blanket)
    cv_thresholds: Dict[str, float] = None
    
    # SDG Penalty Brackets (soft compression, not hard block)
    sdg_penalty_brackets: Dict[str, float] = None
    
    # SOS Adjustments (opponent defense rank → μ modifier)
    sos_adjustments: Dict[str, float] = None
    
    # Multi-window drift threshold
    max_window_drift: float = 0.25  # Block if L10 vs Season differ >25%
    
    # Minimum z required for different contexts
    min_z_conference: float = 0.50
    min_z_nonconf_early: float = 0.80
    min_z_tournament: float = 0.85
    
    def __post_init__(self):
        # Default z-thresholds (stricter than NBA)
        if self.z_thresholds is None:
            self.z_thresholds = {
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
        if self.z_thresholds_blowout is None:
            self.z_thresholds_blowout = {
                "PTS": 0.75,
                "REB": 0.70,
                "AST": 0.70,
                "3PM": 0.60,
                "PTS+REB": 0.75,
                "DEFAULT": 0.70,
            }
        
        # CV thresholds by role (not blanket 0.65)
        if self.cv_thresholds is None:
            self.cv_thresholds = {
                PlayerRole.STAR.value: 0.50,        # High usage → should be consistent
                PlayerRole.ROLE_PLAYER.value: 0.65, # Standard
                PlayerRole.SPECIALIST.value: 0.85,  # 3PM is binary, higher CV ok
                PlayerRole.BENCH.value: 0.70,       # Rotation players
                "DEFAULT": 0.65,
            }
        
        # SDG penalty brackets (soft compression)
        if self.sdg_penalty_brackets is None:
            self.sdg_penalty_brackets = {
                "LOW": {"max_cv_ratio": 0.50, "penalty": 1.00},    # No penalty
                "MEDIUM": {"max_cv_ratio": 0.75, "penalty": 0.90}, # -10%
                "HIGH": {"max_cv_ratio": 1.00, "penalty": 0.80},   # -20%
                "EXTREME": {"max_cv_ratio": float('inf'), "penalty": 0.65},  # -35%
            }
        
        # SOS adjustments (opponent defense rank)
        if self.sos_adjustments is None:
            self.sos_adjustments = {
                "ELITE": {"max_rank": 50, "mu_modifier": 0.85},    # -15%
                "GOOD": {"max_rank": 100, "mu_modifier": 0.92},    # -8%
                "AVERAGE": {"max_rank": 150, "mu_modifier": 0.95}, # -5%
                "WEAK": {"max_rank": 250, "mu_modifier": 1.00},    # Neutral
                "BAD": {"max_rank": 362, "mu_modifier": 1.08},     # +8%
            }


# Global config instance
CBB_SDG_CONFIG = CBBSDGConfig()


# =============================================================================
# CORE SDG FUNCTIONS
# =============================================================================

def calculate_z_score(line: float, mu: float, sigma: float) -> float:
    """
    Calculate z-score for line deviation from mean.
    
    z = |line - μ| / σ
    
    Higher z = more deviation = better edge (if direction is correct)
    Lower z = coin flip territory = penalize
    """
    if sigma <= 0:
        return 0.0
    
    return abs(line - mu) / sigma


def get_sdg_penalty(cv_ratio: float) -> float:
    """
    Get SDG penalty based on coefficient of variation ratio.
    
    This is SOFT compression, not hard block.
    """
    config = CBB_SDG_CONFIG.sdg_penalty_brackets
    
    if cv_ratio <= config["LOW"]["max_cv_ratio"]:
        return config["LOW"]["penalty"]
    elif cv_ratio <= config["MEDIUM"]["max_cv_ratio"]:
        return config["MEDIUM"]["penalty"]
    elif cv_ratio <= config["HIGH"]["max_cv_ratio"]:
        return config["HIGH"]["penalty"]
    else:
        return config["EXTREME"]["penalty"]


def classify_player_role(
    usage_rate: Optional[float] = None,
    is_3pt_specialist: bool = False,
    minutes_avg: Optional[float] = None
) -> PlayerRole:
    """
    Classify player role for tiered CV thresholds.
    """
    if is_3pt_specialist:
        return PlayerRole.SPECIALIST
    
    if usage_rate is not None:
        if usage_rate > 25:
            return PlayerRole.STAR
        elif usage_rate > 15:
            return PlayerRole.ROLE_PLAYER
    
    if minutes_avg is not None:
        if minutes_avg < 20:
            return PlayerRole.BENCH
    
    return PlayerRole.ROLE_PLAYER  # Default


def get_cv_threshold(role: PlayerRole, stat_type: str = "") -> float:
    """Get CV threshold — max of role-based and stat-specific.
    
    Binary/event stats (3PM, BLK, STL) are inherently volatile.
    Using max() ensures neither axis penalises unjustly.
    """
    role_threshold = CBB_SDG_CONFIG.cv_thresholds.get(
        role.value, 
        CBB_SDG_CONFIG.cv_thresholds["DEFAULT"]
    )
    
    # Import stat-specific thresholds
    try:
        from sports.cbb.config import STAT_CV_THRESHOLDS, STAT_CV_DEFAULT
        stat_key = stat_type.lower().replace("+", "_").replace(" ", "_")
        stat_threshold = STAT_CV_THRESHOLDS.get(stat_key, STAT_CV_DEFAULT)
    except ImportError:
        stat_threshold = role_threshold  # Fallback: role only
    
    return max(role_threshold, stat_threshold)


def get_z_threshold(stat_type: str, is_blowout_risk: bool = False) -> float:
    """Get z-score threshold for stat type."""
    thresholds = (
        CBB_SDG_CONFIG.z_thresholds_blowout 
        if is_blowout_risk 
        else CBB_SDG_CONFIG.z_thresholds
    )
    
    # Normalize stat type
    stat_upper = stat_type.upper().replace(" ", "").replace("-", "")
    
    return thresholds.get(stat_upper, thresholds["DEFAULT"])


# =============================================================================
# SOS CALIBRATION
# =============================================================================

def apply_sos_adjustment(
    player_mu: float,
    opponent_def_rank: Optional[int] = None
) -> Tuple[float, str]:
    """
    Adjust player mean based on opponent defense quality.
    
    Returns: (adjusted_mu, adjustment_reason)
    """
    if opponent_def_rank is None:
        return player_mu, "NO_SOS_DATA"
    
    sos_config = CBB_SDG_CONFIG.sos_adjustments
    
    for tier, settings in sos_config.items():
        if opponent_def_rank <= settings["max_rank"]:
            modifier = settings["mu_modifier"]
            adjusted_mu = player_mu * modifier
            
            pct_change = (modifier - 1.0) * 100
            sign = "+" if pct_change >= 0 else ""
            reason = f"SOS_{tier}:{sign}{pct_change:.0f}%"
            
            return adjusted_mu, reason
    
    return player_mu, "SOS_NEUTRAL"


# =============================================================================
# MULTI-WINDOW VALIDATION
# =============================================================================

def check_multi_window_sdg(
    line: float,
    l10_mu: float,
    l10_sigma: float,
    season_mu: float,
    season_sigma: float,
    stat_type: str,
    is_blowout_risk: bool = False
) -> Tuple[bool, str, Dict]:
    """
    Player must pass SDG on BOTH L10 and Season windows.
    
    Also checks for excessive drift between windows (hot/cold streak).
    
    Returns: (passed, reason, details)
    """
    z_threshold = get_z_threshold(stat_type, is_blowout_risk)
    
    # Calculate z-scores for both windows
    z_l10 = calculate_z_score(line, l10_mu, l10_sigma)
    z_season = calculate_z_score(line, season_mu, season_sigma)
    
    details = {
        "z_l10": round(z_l10, 3),
        "z_season": round(z_season, 3),
        "z_threshold": z_threshold,
        "l10_mu": round(l10_mu, 2),
        "season_mu": round(season_mu, 2),
    }
    
    # Must pass BOTH windows
    if z_l10 < z_threshold:
        return False, f"FAIL_L10_Z:{z_l10:.2f}<{z_threshold}", details
    
    if z_season < z_threshold:
        return False, f"FAIL_SEASON_Z:{z_season:.2f}<{z_threshold}", details
    
    # Check for excessive drift (hot/cold streak detection)
    if season_mu > 0:
        drift = abs(l10_mu - season_mu) / season_mu
        details["window_drift"] = round(drift, 3)
        
        if drift > CBB_SDG_CONFIG.max_window_drift:
            return False, f"FAIL_DRIFT:{drift:.1%}>{CBB_SDG_CONFIG.max_window_drift:.0%}", details
    
    return True, "PASS_MULTI_WINDOW", details


# =============================================================================
# BLOWOUT PROTECTION
# =============================================================================

def get_blowout_z_adjustment(spread: float) -> Tuple[float, str]:
    """
    Get minimum z-score required based on game spread.
    
    CBB has 40% blowout rate — this is critical protection.
    
    Returns: (min_z_required, reason)
    """
    abs_spread = abs(spread)
    
    if abs_spread >= 18:
        # Extreme mismatch — stars sit final 8-12 minutes
        return 0.90, "BLOWOUT_EXTREME"
    elif abs_spread >= 12:
        # Moderate mismatch — some garbage time
        return 0.70, "BLOWOUT_MODERATE"
    elif abs_spread >= 8:
        # Slight mismatch — minor concern
        return 0.60, "BLOWOUT_MINOR"
    else:
        # Competitive game — standard threshold
        return 0.50, "COMPETITIVE"


def calculate_blowout_penalty(spread: float, is_over: bool) -> float:
    """
    Calculate probability penalty based on blowout risk.
    
    CRITICAL: This is PENALTY, not BLOCK. We price the risk, not eliminate it.
    
    - Overs get penalized more (stars sit)
    - Unders can benefit (bench inflation for rebounds)
    """
    abs_spread = abs(spread)
    
    if abs_spread < 8:
        return 1.0  # No penalty
    
    # Base penalty from spread
    if abs_spread >= 18:
        base_penalty = 0.75  # -25%
    elif abs_spread >= 12:
        base_penalty = 0.85  # -15%
    else:
        base_penalty = 0.92  # -8%
    
    # Overs hurt more than unders in blowouts
    if is_over:
        return base_penalty
    else:
        # Unders get smaller penalty (bench inflation can help)
        return min(1.0, base_penalty + 0.10)


# =============================================================================
# CONFERENCE PHASE GATES
# =============================================================================

def get_conference_phase_threshold(
    game_date_month: int,
    is_conference_game: bool,
    is_tournament: bool = False
) -> Tuple[float, str]:
    """
    Different phases of CBB season have different reliability.
    
    Returns: (min_z_required, phase_name)
    """
    if is_tournament:
        return CBB_SDG_CONFIG.min_z_tournament, "TOURNAMENT_CHAOS"
    
    if game_date_month in [11, 12]:
        if not is_conference_game:
            return CBB_SDG_CONFIG.min_z_nonconf_early, "EARLY_NONCONF"
        return 0.65, "EARLY_CONF"
    
    elif game_date_month in [1, 2]:
        return CBB_SDG_CONFIG.min_z_conference, "CONFERENCE_PLAY"
    
    elif game_date_month == 3:
        if is_tournament:
            return CBB_SDG_CONFIG.min_z_tournament, "MARCH_MADNESS"
        return 0.65, "CONF_TOURNAMENT"
    
    return CBB_SDG_CONFIG.min_z_conference, "DEFAULT"


# =============================================================================
# ROAD PENALTY (CONTEXT-AWARE)
# =============================================================================

def calculate_road_penalty(
    is_away: bool,
    travel_distance_miles: Optional[int] = None,
    is_rivalry: bool = False,
    altitude_change_ft: Optional[int] = None,
    team_avg_age: Optional[float] = None,
    player_usage: Optional[float] = None
) -> float:
    """
    Smart road penalty — context-aware, not flat.
    
    Returns: Probability multiplier (1.0 = no penalty)
    """
    if not is_away:
        return 1.0
    
    base_penalty = 0.10  # 10% baseline for road games
    
    # Travel distance
    if travel_distance_miles is not None and travel_distance_miles > 1000:
        base_penalty += 0.05
    
    # Rivalry/hostile crowd
    if is_rivalry:
        base_penalty += 0.05
    
    # Altitude (Denver, Salt Lake, etc.)
    if altitude_change_ft is not None and altitude_change_ft > 3000:
        base_penalty += 0.05
    
    # Senior-heavy teams handle road better
    if team_avg_age is not None and team_avg_age > 22:
        base_penalty *= 0.70
    
    # Role players hurt more on road
    if player_usage is not None and player_usage < 20:
        base_penalty *= 1.20
    
    # Cap at 25% penalty
    final_penalty = min(base_penalty, 0.25)
    
    return 1.0 - final_penalty


# =============================================================================
# SHRINKAGE (REPLACES HARD "MIN 5 GAMES" BLOCK)
# =============================================================================

def apply_shrinkage(
    observed_mu: float,
    team_baseline_mu: Optional[float],
    games_played: int,
    max_effective_games: int = 10
) -> Tuple[float, float, str]:
    """
    Apply shrinkage to observed mean based on sample size.
    
    This REPLACES the hard "min 5 games" block. Now we:
    - Accept all players
    - Shrink unreliable means toward team baseline
    - Learn safely without blind spots
    
    Returns: (shrunk_mu, shrinkage_weight, reason)
    """
    effective_games = min(games_played, max_effective_games)
    weight = effective_games / max_effective_games
    
    # If no team baseline, use observed mean (no shrinkage)
    if team_baseline_mu is None:
        return observed_mu, 1.0, "NO_BASELINE"
    
    shrunk_mu = weight * observed_mu + (1 - weight) * team_baseline_mu
    
    if games_played < 5:
        reason = f"HEAVY_SHRINKAGE:{weight:.0%}"
    elif games_played < 10:
        reason = f"MODERATE_SHRINKAGE:{weight:.0%}"
    else:
        reason = "FULL_WEIGHT"
    
    return shrunk_mu, weight, reason


# =============================================================================
# MAIN SDG FILTER FUNCTION
# =============================================================================

def apply_cbb_sdg_filter(
    prop: Dict,
    player_stats: Dict,
    game_context: Optional[Dict] = None
) -> Dict:
    """
    Apply full CBB SDG filter to a prop.
    
    This is the main entry point. It:
    1. Applies SOS adjustment to μ
    2. Applies shrinkage if sample size is low
    3. Checks multi-window SDG (L10 AND Season)
    4. Applies CV-based penalty (soft, not hard)
    5. Applies blowout penalty
    6. Applies road penalty
    7. Checks conference phase threshold
    
    Returns: Updated prop dict with SDG fields
    """
    line = prop.get("line", 0)
    stat_type = prop.get("stat", "").upper()
    direction = prop.get("direction", "higher")
    is_over = direction.lower() in ["higher", "over"]
    
    # Extract player stats
    l10_mu = player_stats.get("l10_mu", player_stats.get("mu", 0))
    l10_sigma = player_stats.get("l10_sigma", player_stats.get("sigma", 1))
    season_mu = player_stats.get("season_mu", l10_mu)
    season_sigma = player_stats.get("season_sigma", l10_sigma)
    games_played = player_stats.get("games_played", player_stats.get("n", 10))
    team_baseline = player_stats.get("team_baseline_mu", season_mu * 0.85)
    usage_rate = player_stats.get("usage_rate")
    minutes_avg = player_stats.get("minutes_avg")
    
    # Extract game context
    opponent_def_rank = game_context.get("opponent_def_rank") if game_context else None
    spread = game_context.get("spread", 0) if game_context else 0
    is_away = game_context.get("is_away", False) if game_context else False
    game_month = game_context.get("game_month", 1) if game_context else 1
    is_conference = game_context.get("is_conference_game", True) if game_context else True
    is_tournament = game_context.get("is_tournament", False) if game_context else False
    
    # Initialize SDG result
    sdg_result = {
        "sdg_passed": True,
        "sdg_penalty": 1.0,
        "sdg_reasons": [],
        "sdg_details": {},
    }
    
    # 1. Apply shrinkage if low sample size
    if games_played < 10:
        shrunk_mu, weight, shrink_reason = apply_shrinkage(
            l10_mu, team_baseline, games_played
        )
        sdg_result["sdg_details"]["shrinkage"] = {
            "original_mu": round(l10_mu, 2),
            "shrunk_mu": round(shrunk_mu, 2),
            "weight": round(weight, 2),
        }
        sdg_result["sdg_reasons"].append(shrink_reason)
        l10_mu = shrunk_mu
    
    # 2. Apply SOS adjustment
    adjusted_mu, sos_reason = apply_sos_adjustment(l10_mu, opponent_def_rank)
    if adjusted_mu != l10_mu:
        sdg_result["sdg_details"]["sos"] = {
            "original_mu": round(l10_mu, 2),
            "adjusted_mu": round(adjusted_mu, 2),
            "opponent_rank": opponent_def_rank,
        }
        sdg_result["sdg_reasons"].append(sos_reason)
        l10_mu = adjusted_mu
    
    # 3. Check blowout risk (handle None spread)
    spread = spread or 0  # Default to 0 if None
    is_blowout_risk = abs(spread) >= 12
    blowout_min_z, blowout_reason = get_blowout_z_adjustment(spread)
    sdg_result["sdg_details"]["blowout"] = {
        "spread": spread,
        "min_z_required": blowout_min_z,
        "reason": blowout_reason,
    }
    
    # 4. Multi-window SDG check
    mw_passed, mw_reason, mw_details = check_multi_window_sdg(
        line, l10_mu, l10_sigma, season_mu, season_sigma,
        stat_type, is_blowout_risk
    )
    sdg_result["sdg_details"]["multi_window"] = mw_details
    
    if not mw_passed:
        sdg_result["sdg_passed"] = False
        sdg_result["sdg_reasons"].append(mw_reason)
    
    # 5. CV-based penalty (soft compression)
    cv_ratio = l10_sigma / l10_mu if l10_mu > 0 else 1.0
    role = classify_player_role(usage_rate, stat_type == "3PM", minutes_avg)
    cv_threshold = get_cv_threshold(role, stat_type)
    
    sdg_result["sdg_details"]["cv"] = {
        "cv_ratio": round(cv_ratio, 3),
        "cv_threshold": cv_threshold,
        "player_role": role.value,
    }
    
    if cv_ratio > cv_threshold:
        sdg_penalty = get_sdg_penalty(cv_ratio)
        sdg_result["sdg_penalty"] *= sdg_penalty
        sdg_result["sdg_reasons"].append(f"CV_PENALTY:{sdg_penalty:.0%}")
    
    # 6. Blowout penalty
    if abs(spread) >= 8:
        blowout_penalty = calculate_blowout_penalty(spread, is_over)
        sdg_result["sdg_penalty"] *= blowout_penalty
        sdg_result["sdg_reasons"].append(f"BLOWOUT_PENALTY:{blowout_penalty:.0%}")
    
    # 7. Road penalty
    if is_away:
        road_penalty = calculate_road_penalty(is_away)
        sdg_result["sdg_penalty"] *= road_penalty
        sdg_result["sdg_reasons"].append(f"ROAD_PENALTY:{road_penalty:.0%}")
    
    # 8. Conference phase check
    phase_min_z, phase_name = get_conference_phase_threshold(
        game_month, is_conference, is_tournament
    )
    sdg_result["sdg_details"]["phase"] = {
        "name": phase_name,
        "min_z_required": phase_min_z,
    }
    
    # Get effective z-score
    z_l10 = mw_details.get("z_l10", 0)
    if z_l10 < phase_min_z:
        sdg_result["sdg_passed"] = False
        sdg_result["sdg_reasons"].append(f"PHASE_FAIL:{phase_name}")
    
    # Attach to prop
    prop["sdg_passed"] = sdg_result["sdg_passed"]
    prop["sdg_penalty"] = round(sdg_result["sdg_penalty"], 3)
    prop["sdg_reasons"] = sdg_result["sdg_reasons"]
    prop["sdg_details"] = sdg_result["sdg_details"]
    
    # Apply penalty to probability
    if "probability" in prop:
        prop["raw_probability"] = prop["probability"]
        raw_prob = prop["probability"]
        adjusted_prob = raw_prob * sdg_result["sdg_penalty"]
        
        # FLOOR PROTECTION: Don't let SDG penalty kill direction-aligned edges
        # If projection supports the direction and raw_prob >= LEAN, cap penalty
        from sports.cbb.config import CBB_TIER_THRESHOLDS_V2
        LEAN_FLOOR = CBB_TIER_THRESHOLDS_V2.get("LEAN", 0.60)
        
        direction_aligned = False
        if is_over and l10_mu > line:
            direction_aligned = True
        elif not is_over and l10_mu < line:
            direction_aligned = True
        
        if direction_aligned and raw_prob >= LEAN_FLOOR and adjusted_prob < LEAN_FLOOR:
            # Cap the penalty so the edge stays at LEAN minimum
            adjusted_prob = LEAN_FLOOR
            sdg_result["sdg_reasons"].append(
                f"FLOOR_APPLIED:{raw_prob:.0%}→{LEAN_FLOOR:.0%} "
                f"(uncapped would be {raw_prob * sdg_result['sdg_penalty']:.0%})"
            )
            prop["sdg_floor_applied"] = True
            prop["sdg_reasons"] = sdg_result["sdg_reasons"]
        
        prop["probability"] = round(adjusted_prob, 4)
    
    return prop


# =============================================================================
# BINARY PROP HANDLER (3PM O0.5 SPECIAL CASE)
# =============================================================================

def check_binary_prop_eligibility(
    prop: Dict,
    player_stats: Dict,
    min_hit_rate: float = 0.75,
    min_games: int = 5
) -> Tuple[bool, str]:
    """
    Check if a binary prop (e.g., 3PM O0.5) is eligible.
    
    Binary props have cleaner probability distributions but need
    strict hit-rate requirements.
    
    Returns: (eligible, reason)
    """
    stat_type = prop.get("stat", "").upper()
    line = prop.get("line", 0)
    direction = prop.get("direction", "higher")
    
    # Only for binary lines (0.5, 1.5)
    if line not in [0.5, 1.5]:
        return True, "NOT_BINARY"
    
    # Get hit rate from player stats
    games_played = player_stats.get("games_played", player_stats.get("n", 0))
    
    if games_played < min_games:
        return False, f"INSUFFICIENT_GAMES:{games_played}<{min_games}"
    
    # For Over 0.5, we need hit rate (how often they hit 1+)
    if line == 0.5 and direction.lower() in ["higher", "over"]:
        hit_rate = player_stats.get("hit_rate_1plus")
        if hit_rate is not None and hit_rate < min_hit_rate:
            return False, f"LOW_HIT_RATE:{hit_rate:.0%}<{min_hit_rate:.0%}"
    
    return True, "BINARY_ELIGIBLE"


# =============================================================================
# COMPOSITE STAT HANDLER (PTS+REB ONLY)
# =============================================================================

def check_composite_eligibility(
    prop: Dict,
    player_stats: Dict
) -> Tuple[bool, str]:
    """
    Check if composite stat is allowed.
    
    ONLY PTS+REB is allowed in CBB (per governance).
    
    Requirements:
    - SDG must pass with z >= 0.60
    - Confidence cap at 68%
    - Never SLAM tier
    """
    stat_type = prop.get("stat", "").upper().replace(" ", "")
    
    allowed_composites = ["PTS+REB", "PTSREB"]
    
    if stat_type not in allowed_composites:
        return False, f"BLOCKED_COMPOSITE:{stat_type}"
    
    # Check z-score requirement
    z_score = prop.get("sdg_details", {}).get("multi_window", {}).get("z_l10", 0)
    if z_score < 0.60:
        return False, f"COMPOSITE_LOW_Z:{z_score:.2f}<0.60"
    
    # Check CV requirement
    cv_ratio = prop.get("sdg_details", {}).get("cv", {}).get("cv_ratio", 1.0)
    if cv_ratio > 0.50:
        return False, f"COMPOSITE_HIGH_CV:{cv_ratio:.2f}>0.50"
    
    return True, "COMPOSITE_ALLOWED"
