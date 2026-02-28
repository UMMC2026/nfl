"""
Game Script Gate — Prevents UNDER on losing team stars

CRITICAL GATE: Prevents structurally -EV UNDER picks.

Key insight from calibration failures:
  When a team is trailing, their star players:
    - Play more minutes (no rest / garbage time)
    - Take more shots (team needs scoring)
    - Get more counting stats (assists, rebounds from desperate possessions)
  This makes UNDERs on underdog stars structurally -EV.

All thresholds loaded from:
  - config/gate_thresholds.yaml (game_script_gate section)
  - config/cbb_runtime.json (runtime toggles)

Examples blocked:
  KJ Lewis PRA UNDER 19.5 (Memphis +17) → actual 36 (LOSS)
  MJ Collins PTS UNDER 15.5 (Auburn +14) → actual 22 (LOSS)
  M. Millender AST UNDER 4.5 (Georgia +16) → actual 8 (LOSS)

Implementation Date: 2026-02-14
"""

from typing import Dict, Tuple, Optional, List, Set
from pathlib import Path
import json
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIG LOADING
# ============================================================================

_CONFIG_DIR = Path(__file__).parent.parent / "config"


def _load_yaml_config() -> Dict:
    """Load game_script_gate section from gate_thresholds.yaml."""
    path = _CONFIG_DIR / "gate_thresholds.yaml"
    if not path.exists() or not HAS_YAML:
        return {}
    try:
        with open(path) as f:
            full = yaml.safe_load(f) or {}
        return full.get("game_script_gate", {})
    except Exception as e:
        logger.warning(f"Failed to load gate_thresholds.yaml: {e}")
        return {}


def _load_runtime_config() -> Dict:
    """Load game_script_gate section from cbb_runtime.json."""
    path = _CONFIG_DIR / "cbb_runtime.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            full = json.load(f) or {}
        return full.get("game_script_gate", {})
    except Exception as e:
        logger.warning(f"Failed to load cbb_runtime.json: {e}")
        return {}


def _load_spread_lambda_config() -> Dict:
    """Load spread_lambda_adjustment from either config source."""
    # Try YAML first
    path_yaml = _CONFIG_DIR / "gate_thresholds.yaml"
    if path_yaml.exists() and HAS_YAML:
        try:
            with open(path_yaml) as f:
                full = yaml.safe_load(f) or {}
            sla = full.get("spread_lambda_adjustment", {})
            if sla:
                return sla
        except Exception:
            pass

    # Fall back to JSON
    path_json = _CONFIG_DIR / "cbb_runtime.json"
    if path_json.exists():
        try:
            with open(path_json) as f:
                full = json.load(f) or {}
            return full.get("spread_lambda_adjustment", {})
        except Exception:
            pass

    return {}


# ============================================================================
# DEFAULT THRESHOLDS (fallback if config missing)
# ============================================================================

_DEFAULTS = {
    "enabled": True,
    "high_impact_stats": [
        "pra", "pts_rebs_asts", "pts+reb+ast",
        "pa", "pts_ast", "pts+ast",
        "pr", "pts_reb", "pts+reb",
        "reb+ast", "reb_ast",
        "points+assists", "points+rebounds",
        "points+rebounds+assists", "rebounds+assists",
    ],
    "block_under_on_underdog_spread": 6,
    "block_under_combo_spread": 4,
    "high_usage_threshold": 0.22,
    "block_high_usage_under_if_spread_gte": 5,
    "soft_penalty": {
        "min_spread": 3,
        "max_spread": 6,
        "per_point_inflation": 0.03,
        "close_game_high_usage_penalty": 1.03,
    },
}

_SPREAD_LAMBDA_DEFAULTS = {
    "enabled": True,
    "underdog_boost": {
        "spread_5_to_8": 1.08,
        "spread_8_to_12": 1.12,
        "spread_12_plus": 1.15,
    },
    "favorite_reduction": {
        "spread_10_to_14": 0.95,
        "spread_14_plus": 0.90,
    },
}


def _merge_config() -> Dict:
    """Merge YAML + JSON + defaults into final config."""
    config = dict(_DEFAULTS)
    yaml_cfg = _load_yaml_config()
    json_cfg = _load_runtime_config()

    # JSON overrides YAML, both override defaults
    for key in _DEFAULTS:
        if key in yaml_cfg:
            config[key] = yaml_cfg[key]
        if key in json_cfg:
            config[key] = json_cfg[key]

    return config


def _get_high_impact_stats(config: Dict) -> Set[str]:
    """Get the set of high-impact stat names (normalized to lowercase)."""
    stats = config.get("high_impact_stats", _DEFAULTS["high_impact_stats"])
    return {s.lower() for s in stats}


# ============================================================================
# GAME SCRIPT GATE  (MAIN FUNCTION)
# ============================================================================

def game_script_gate(
    edge: Dict,
    game_context: Dict,
    player_data: Optional[Dict] = None,
) -> Tuple[bool, str]:
    """
    Block UNDER picks that will get killed by game script.

    When a team is losing, their star players:
    - Play more minutes (no rest)
    - Take more shots (team needs scoring)
    - Get more counting stats

    This makes UNDERs on underdog stars structurally -EV.

    Parameters
    ----------
    edge : dict
        The edge being evaluated. Expected keys:
        direction, stat (or stat_type), player (or player_name), line
    game_context : dict
        Game-level context. Expected keys:
        spread (float), is_home (bool) or is_favorite (bool)
    player_data : dict, optional
        Player-level data. Expected key: usage_rate (float)

    Returns
    -------
    (passed, reason) :
        passed: False = hard-block this pick
        reason: Human-readable gate result
    """
    config = _merge_config()

    if not config.get("enabled", True):
        return True, "Game script gate: DISABLED"

    player_data = player_data or {}

    # ---- Extract edge fields ----
    direction = (edge.get("direction") or "").upper()
    stat_type = (edge.get("stat") or edge.get("stat_type") or "").lower()
    player_name = edge.get("player") or edge.get("player_name") or "?"

    # Only affects UNDER/LOWER picks
    if direction not in ("UNDER", "LOWER"):
        return True, "Game script gate: OVER not affected"

    # ---- Determine team's spread position ----
    spread = game_context.get("spread", 0)
    is_favorite = game_context.get("is_favorite")

    # If is_favorite not pre-computed, derive from is_home + spread sign
    if is_favorite is None:
        is_home = game_context.get("is_home", True)
        raw_spread = game_context.get("raw_spread", spread)
        if raw_spread is not None:
            # Convention: negative raw_spread = home favored
            is_favorite = (is_home and raw_spread <= 0) or (not is_home and raw_spread > 0)
        else:
            is_favorite = True

    # How big an underdog is this team?
    is_underdog = not is_favorite
    underdog_points = abs(spread) if is_underdog else 0

    if not is_underdog:
        return True, "Game script gate: PASSED (team is favorite)"

    # ---- Player usage ----
    usage = player_data.get("usage_rate", edge.get("player_usage", 0.20))
    high_usage_threshold = config.get("high_usage_threshold", 0.22)
    is_high_usage = usage >= high_usage_threshold

    # ---- Build high-impact stat set ----
    high_impact = _get_high_impact_stats(config)

    # ============================================================
    # RULE 1: Block all UNDER on heavy underdog stars (high-usage)
    # ============================================================
    block_spread = config.get("block_under_on_underdog_spread", 6)
    if underdog_points >= block_spread and is_high_usage:
        edge["game_script_warning"] = True
        return False, (
            f"GAME_SCRIPT_BLOCK: Team is +{underdog_points:.1f} underdog, "
            f"high-usage player ({usage:.0%}) will inflate stats. UNDER blocked."
        )

    # ============================================================
    # RULE 2: Block combo stat UNDER on moderate underdog
    # ============================================================
    block_combo_spread = config.get("block_under_combo_spread", 4)
    if underdog_points >= block_combo_spread and stat_type in high_impact:
        edge["game_script_warning"] = True
        return False, (
            f"GAME_SCRIPT_BLOCK: Combo stat ({stat_type}) UNDER blocked. "
            f"Team is +{underdog_points:.1f} underdog — trailing teams inflate PRA."
        )

    # ============================================================
    # RULE 3: Block high-usage UNDER on moderate underdog (points)
    # ============================================================
    block_hu_spread = config.get("block_high_usage_under_if_spread_gte", 5)
    if underdog_points >= block_hu_spread and is_high_usage:
        if stat_type in ("points", "pts"):
            edge["game_script_warning"] = True
            return False, (
                f"GAME_SCRIPT_BLOCK: Points UNDER on high-usage "
                f"(+{underdog_points:.1f} underdog). Star will chase."
            )

    # ============================================================
    # RULE 4: Warn on moderate underdog + points (do not block)
    # ============================================================
    soft = config.get("soft_penalty", _DEFAULTS["soft_penalty"])
    warn_min = soft.get("min_spread", 3)

    if underdog_points >= warn_min:
        if stat_type in ("points", "pts") and is_high_usage:
            logger.warning(
                f"GAME_SCRIPT_WARN: {player_name} points UNDER "
                f"on +{underdog_points:.1f} underdog. Consider skipping."
            )
            edge["game_script_warning"] = True
            # Don't block, just flag

    return True, "Game script gate: PASSED"


# ============================================================================
# SPREAD-BASED LAMBDA ADJUSTMENT
# ============================================================================

def apply_spread_lambda_adjustment(
    raw_lambda: float,
    game_context: Dict,
    direction: str,
) -> Tuple[float, float]:
    """
    Adjust lambda based on expected game script.

    Trailing teams → inflated stats (lambda goes up).
    Leading teams in blowouts → stars rest (lambda goes down).

    Parameters
    ----------
    raw_lambda : float
        The raw projected lambda (mean) for the player+stat.
    game_context : dict
        Must contain: spread (float), is_favorite (bool) or is_home (bool)
    direction : str
        "HIGHER"/"OVER" or "LOWER"/"UNDER"

    Returns
    -------
    (adjusted_lambda, adjustment_factor) :
        adjustment_factor: multiplier applied (>1 = inflation, <1 = reduction)
    """
    sla_config = _load_spread_lambda_config()
    if not sla_config:
        sla_config = _SPREAD_LAMBDA_DEFAULTS

    if not sla_config.get("enabled", True):
        return raw_lambda, 1.0

    spread = game_context.get("spread", 0)
    is_favorite = game_context.get("is_favorite")

    if is_favorite is None:
        is_home = game_context.get("is_home", True)
        raw_spread = game_context.get("raw_spread", spread)
        if raw_spread is not None:
            is_favorite = (is_home and raw_spread <= 0) or (not is_home and raw_spread > 0)
        else:
            is_favorite = True

    is_underdog = not is_favorite
    abs_spread = abs(spread)

    adjustment = 1.0

    if is_underdog:
        boosts = sla_config.get("underdog_boost", _SPREAD_LAMBDA_DEFAULTS["underdog_boost"])
        if abs_spread >= 12:
            adjustment = boosts.get("spread_12_plus", 1.15)
        elif abs_spread >= 8:
            adjustment = boosts.get("spread_8_to_12", 1.12)
        elif abs_spread >= 5:
            adjustment = boosts.get("spread_5_to_8", 1.08)
        elif abs_spread >= 3:
            adjustment = 1.04  # Minor inflation for close-ish underdog
    else:
        reductions = sla_config.get("favorite_reduction", _SPREAD_LAMBDA_DEFAULTS["favorite_reduction"])
        if abs_spread >= 14:
            adjustment = reductions.get("spread_14_plus", 0.90)
        elif abs_spread >= 10:
            adjustment = reductions.get("spread_10_to_14", 0.95)

    adjusted_lambda = raw_lambda * adjustment

    return adjusted_lambda, adjustment


# ============================================================================
# SOFT PENALTY CALCULATOR (for moderate underdogs)
# ============================================================================

def calculate_game_script_penalty(
    spread: float,
    is_favorite: bool,
    stat_type: str,
    player_usage: float = 0.20,
) -> float:
    """
    Calculate soft lambda inflation penalty for moderate underdog situations.

    Returns a multiplier (>1 = inflate lambda = UNDER less likely).
    """
    config = _merge_config()
    soft = config.get("soft_penalty", _DEFAULTS["soft_penalty"])

    if is_favorite:
        return 1.0

    abs_spread = abs(spread)
    min_spread = soft.get("min_spread", 3)
    max_spread = soft.get("max_spread", 6)
    per_point = soft.get("per_point_inflation", 0.03)
    close_game_penalty = soft.get("close_game_high_usage_penalty", 1.03)

    high_impact = _get_high_impact_stats(config)
    high_usage_threshold = config.get("high_usage_threshold", 0.22)

    # Combo stat on moderate underdog → inflation
    if min_spread <= abs_spread < max_spread and stat_type.lower() in high_impact:
        penalty = 1.0 + (abs_spread - min_spread) * per_point
        return round(penalty, 4)

    # Points on moderate underdog
    if min_spread <= abs_spread < max_spread and stat_type.lower() in ("points", "pts"):
        penalty = 1.0 + (abs_spread - min_spread) * (per_point * 0.67)
        return round(penalty, 4)

    # Close game + high-usage star
    if abs_spread <= min_spread and player_usage >= 0.25:
        return close_game_penalty

    return 1.0
