"""RISK-FIRST GATING SYSTEM

Machine-enforceable structural safety checks.

Important: We now distinguish between:
- HARD blocks: immediately return BLOCKED
- SOFT warnings: allow the math to run, but apply a confidence penalty
"""

import json
from pathlib import Path
from typing import Optional

import unicodedata

# Market alignment gate (Tier 1 fix - 2026-01-24)
try:
    from market_alignment_gate import check_market_alignment
    HAS_MARKET_GATE = True
except ImportError:
    HAS_MARKET_GATE = False

# =============================================================================
# PENALTY MODE CONFIGURATION (2026-01-29)
# =============================================================================
def load_penalty_mode() -> dict:
    """Load penalty mode configuration."""
    config_path = Path(__file__).parent / "config" / "penalty_mode.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("active_mode_settings", {})
    except Exception:
        return {"stat_penalty": True, "gate_penalties": True}

PENALTY_MODE = load_penalty_mode()

# Load configuration files
CONFIG_DIR = Path(__file__).parent

with open(CONFIG_DIR / "role_mapping.json", encoding="utf-8") as f:
    ROLE_CONFIG = json.load(f)

with open(CONFIG_DIR / "player_stat_memory.json", encoding="utf-8") as f:
    MEMORY_DB = json.load(f)

with open(CONFIG_DIR / "confidence_rules.json", encoding="utf-8") as f:
    CONFIDENCE_CONFIG = json.load(f)

ROLE_DEFINITIONS = ROLE_CONFIG["role_definitions"]
PLAYER_CLASSIFICATIONS = ROLE_CONFIG["player_classifications"]
STAT_CAPS = CONFIDENCE_CONFIG["stat_confidence_caps"]
THRESHOLDS = CONFIDENCE_CONFIG["probability_thresholds"]
MEMORY_PENALTY = CONFIDENCE_CONFIG["memory_penalty_per_fail"]

# NEW: Stat-specific penalties from Bayesian calibration
STAT_PENALTIES = CONFIDENCE_CONFIG.get("stat_penalties", {})


def _strip_diacritics(name: str) -> str:
    """Best-effort diacritic removal for player-name key matching.

    Underdog pastes sometimes include diacritics (e.g., Dončić, Nurkić) while
    our role mapping config may store ASCII equivalents (Doncic, Nurkic).
    """
    try:
        s = str(name or "")
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return s
    except Exception:
        return str(name or "")


def _normalize_player_key_for_lookup(player: str) -> str:
    try:
        return str(player or "").strip()
    except Exception:
        return str(player or "")


def _player_lookup_keys(player: str) -> list[str]:
    """Generate ordered candidate keys for player mapping lookups.

    Goal: avoid false "not classified" blocks due to minor name formatting
    differences (diacritics, suffix punctuation).
    """
    base = _normalize_player_key_for_lookup(player)
    keys: list[str] = []

    def _add(k: str):
        k = str(k or "").strip()
        if k and k not in keys:
            keys.append(k)

    _add(base)

    alt = _strip_diacritics(base)
    if alt and alt != base:
        _add(alt)

    # Suffix normalization (common in NBA names)
    suffixes = [" Jr.", " Jr", " Sr.", " Sr", " II", " III", " IV"]
    stripped = base
    for sfx in suffixes:
        if stripped.endswith(sfx):
            stripped = stripped[: -len(sfx)].strip()
            break

    if stripped and stripped != base:
        _add(stripped)
        # Also try diacritic-stripped version of the stripped name.
        stripped_alt = _strip_diacritics(stripped)
        if stripped_alt and stripped_alt != stripped:
            _add(stripped_alt)

    # If the paste omits a suffix that our mapping has, try a couple common adds.
    # (Only as fallbacks; we never prefer these over exact matches.)
    if base and not any(base.endswith(sfx) for sfx in suffixes):
        _add(base + " Jr")
        _add(base + " Jr.")

    return keys


# ========================================
# SOFT-WARNING POLICY (penalties)
# ========================================
# Penalties are applied to model_confidence (percent) before caps/memory.
# They must NEVER increase confidence.
PENALTY_BIG_FORBIDS_ASSISTS = 0.12
PENALTY_BIG_FORBIDS_3PM = 0.12
PENALTY_BIG_FORBIDS_STEALS = 0.10

PENALTY_STAR_GUARD_VS_ELITE_DEF = 0.15  # ranks 1-3
PENALTY_STAR_GUARD_VS_STRONG_DEF = 0.10  # ranks 4-10

PENALTY_ELITE_DEF_SOFT = 0.08  # e.g., assists/3pm vs top-5


def _gate_tuple(passed: bool, reason: str, *, severity: str | None = None, penalty: float | None = None) -> tuple:
    """Return a compact gate result.

    Back-compat: callers can treat the return as (passed, reason). If severity/penalty
    are provided, the tuple will be length 3.
    """
    meta = {}
    if severity:
        meta["severity"] = severity
    if penalty is not None:
        meta["penalty"] = float(penalty)
    if meta:
        return passed, reason, meta
    return passed, reason


def _parse_gate_result(ret) -> tuple[bool, str, dict]:
    """Normalize gate returns into (passed, reason, meta)."""
    if isinstance(ret, tuple):
        if len(ret) == 2:
            return bool(ret[0]), str(ret[1]), {}
        if len(ret) >= 3 and isinstance(ret[2], dict):
            return bool(ret[0]), str(ret[1]), dict(ret[2])
    # Fallback: treat as pass
    return True, "PASS", {}


def _apply_warning_penalties(model_confidence: float, gate_results: list[dict]) -> float:
    """Apply WARNING penalties without ever increasing confidence."""
    mc = float(model_confidence)
    for g in gate_results:
        if g.get("severity") != "WARNING":
            continue
        try:
            p = float(g.get("penalty", 0.0) or 0.0)
        except Exception:
            p = 0.0
        if p <= 0.0:
            continue

        # Never increase confidence.
        if mc >= 50.0:
            mc = 50.0 + (mc - 50.0) * (1.0 - p)
        else:
            mc = mc * (1.0 - p)

        mc = max(0.0, min(100.0, mc))

    return mc


# ========================================
# RISK GATE 1: COMPOSITE STAT FRAGILITY
# ========================================
def gate_composite_stat(stat: str, soft_gates: bool = False) -> tuple[bool, str]:
    """
    R1 - Composite stats have multi-category fragility risk.
    
    When soft_gates=False: HARD BLOCK all composite stats
    When soft_gates=True: ALLOW with warning (confidence will be capped downstream)
    """
    composite_stats = ["pra", "pr", "pa", "ra", "pts+reb+ast", "pts+reb", "pts+ast", "reb+ast"]
    
    if stat.lower() in composite_stats:
        if soft_gates:
            return True, f"WARNING: Composite stat '{stat}' - multi-category fragility (soft gate)"
        return False, f"BLOCKED: Composite stat '{stat}' - multi-category fragility"
    
    return True, "PASS"


# ========================================
# RISK GATE 2: ELITE DEFENSE SUPPRESSION
# ========================================
def gate_elite_defense(stat: str, opponent_def_rank: int, soft_gates: bool = False) -> tuple:
    """
    R2 - Elite defenses (top 5) suppress certain stats
    
    When soft_gates=True: Composite stats get WARNING + penalty instead of BLOCK
    """
    if opponent_def_rank > 5:
        return _gate_tuple(True, "PASS")

    stat_lower = str(stat).lower()

    # Composite stats that are vulnerable to elite defense
    composite_suppressed = {"pra", "pa", "ra", "pts+reb+ast", "pts+reb", "pts+ast", "reb+ast"}
    soft_suppressed = {"assists", "3pm"}

    if stat_lower in composite_suppressed:
        if soft_gates:
            return _gate_tuple(
                True,
                f"WARNING: Elite defense (#{opponent_def_rank}) suppresses '{stat}' (soft gate)",
                severity="WARNING",
                penalty=PENALTY_ELITE_DEF_SOFT + 0.03,  # Extra penalty for combo vs elite D
            )
        return _gate_tuple(False, f"BLOCKED: Elite defense (#{opponent_def_rank}) suppresses '{stat}'")

    if stat_lower in soft_suppressed:
        return _gate_tuple(
            True,
            f"WARNING: Elite defense (#{opponent_def_rank}) may suppress '{stat}'",
            severity="WARNING",
            penalty=PENALTY_ELITE_DEF_SOFT,
        )
    
    return _gate_tuple(True, "PASS")


# ========================================
# RISK GATE 3: STAR GUARD VS ELITE DEFENSE (POINTS TRAP)
# ========================================
def gate_star_guard_points(player_role: str, stat: str, opponent_def_rank: int) -> tuple:
    """
    R3 - Star guards vs elite defenses (top 10) on points props
    """
    stat_lower = str(stat).lower()

    # Soft-warning policy:
    # - STAR_GUARD points vs strong defenses is elevated risk but not impossible.
    # - Apply a confidence penalty (stronger for top-3).
    if player_role == "STAR_GUARD" and stat_lower == "points":
        if opponent_def_rank <= 3:
            return _gate_tuple(
                True,
                f"WARNING: Star guard points vs elite defense (#{opponent_def_rank})",
                severity="WARNING",
                penalty=PENALTY_STAR_GUARD_VS_ELITE_DEF,
            )
        if opponent_def_rank <= 10:
            return _gate_tuple(
                True,
                f"WARNING: Star guard points vs strong defense (#{opponent_def_rank})",
                severity="WARNING",
                penalty=PENALTY_STAR_GUARD_VS_STRONG_DEF,
            )

    return _gate_tuple(True, "PASS")


# ========================================
# RISK GATE 4: BLOWOUT RISK
# ========================================
def gate_blowout(spread: float) -> tuple[bool, str]:
    """
    R4 - Block if spread >= 9.0 (blowout risk)
    """
    if abs(spread) >= 9.0:
        return False, f"BLOCKED: Blowout risk (spread: {spread})"
    
    return True, "PASS"


# ========================================
# RISK GATE 5: BENCH PLAYER GARBAGE TIME TRAP
# ========================================
def gate_bench_garbage_time(player: str, spread: float) -> tuple[bool, str]:
    """
    R5 - Block bench players in ALL games (unreliable opportunity)
    
    Rationale: Bench players have inconsistent minutes regardless of spread.
    Their stats depend on:
    - Starter foul trouble
    - Garbage time (if blowout happens)
    - Coach's rotation decisions
    
    This is structural fragility - opportunity is not guaranteed.
    Block unless starter role is confirmed.
    """
    bench_players = ROLE_CONFIG.get("bench_players", [])

    # Bench list is a blunt instrument; accept common name variants.
    for k in _player_lookup_keys(player):
        if k in bench_players:
            return False, f"BLOCKED: Bench player with unreliable opportunity"
    
    return True, "PASS"


# ========================================
# ROLE MAPPING: STAT PERMISSION MATRIX
# ========================================
def gate_role_mapping(player: str, stat: str, soft_gates: bool = False) -> tuple[bool, str]:
    """
    Check if stat is allowed for player's role
    If not explicitly allowed → BLOCK (unless soft_gates for combos)
    """
    # Get player role (robust lookup)
    player_role = None
    for k in _player_lookup_keys(player):
        player_role = PLAYER_CLASSIFICATIONS.get(k)
        if player_role:
            break
    if not player_role:
        return False, f"BLOCKED: Player '{player}' not classified"
    
    # Get role definition
    role_def = ROLE_DEFINITIONS.get(player_role)
    if not role_def:
        return False, f"BLOCKED: Role '{player_role}' not defined"
    
    stat_lower = stat.lower()
    
    # Check forbidden stats first
    if stat_lower in role_def.get("forbidden_stats", []):
        # Convert certain formerly-hard role forbids into soft warnings.
        # This allows the probability math to run, but applies a penalty.
        if player_role == "BIG" and stat_lower == "assists":
            return _gate_tuple(
                True,
                f"WARNING: BIG role risk on '{stat}' (low-volume/high-variance)",
                severity="WARNING",
                penalty=PENALTY_BIG_FORBIDS_ASSISTS,
            )
            
        if player_role == "BIG" and stat_lower == "3pm":
            return _gate_tuple(
                True,
                f"WARNING: BIG role risk on '{stat}' (stretch-variance)",
                severity="WARNING",
                penalty=PENALTY_BIG_FORBIDS_3PM,
            )

        if player_role == "BIG" and stat_lower == "steals":
            return _gate_tuple(
                True,
                f"WARNING: BIG role risk on '{stat}' (event-variance)",
                severity="WARNING",
                penalty=PENALTY_BIG_FORBIDS_STEALS,
            )

        # Soft gate: Allow combo stats with heavy penalty when SOFTGATES=1
        combo_stats = {"pra", "pts+reb+ast", "pr", "pts+reb", "pa", "pts+ast", "ra", "reb+ast"}
        if soft_gates and stat_lower in combo_stats:
            return _gate_tuple(
                True,
                f"WARNING: {player_role} role forbids '{stat}' but soft gate allows (high-risk)",
                severity="WARNING",
                penalty=0.08,  # Heavy penalty for role mismatch
            )

        return False, f"BLOCKED: {player_role} role forbids '{stat}'"
    
    # Check allowed stats
    if stat_lower not in role_def.get("allowed_stats", []):
        # Soft gate: Allow combo stats not in allowed list
        combo_stats = {"pra", "pts+reb+ast", "pr", "pts+reb", "pa", "pts+ast", "ra", "reb+ast"}
        if soft_gates and stat_lower in combo_stats:
            return _gate_tuple(
                True,
                f"WARNING: {player_role} role doesn't explicitly allow '{stat}' (soft gate)",
                severity="WARNING",
                penalty=0.05,
            )
        return False, f"BLOCKED: {player_role} role doesn't allow '{stat}'"
    
    return True, f"PASS: {player_role} → '{stat}' allowed"


# ========================================
# MEMORY SYSTEM: BAN LIST
# ========================================
def gate_ban_list(player: str, stat: str) -> tuple[bool, str]:
    """
    M3 - Check if player+stat is banned
    """
    key = f"{player}|{stat.lower()}"
    
    # Check permanent bans
    if key in MEMORY_DB.get("bans", {}):
        ban_data = MEMORY_DB["bans"][key]
        if ban_data.get("banned", False):
            reason = ban_data.get("reason", "Unknown")
            fails = ban_data.get("fails_10", 0)
            return False, f"BANNED: {player} {stat} ({fails} recent fails) - {reason}"
    
    return True, "PASS"


def get_memory_penalty(player: str, stat: str) -> int:
    """
    Calculate confidence penalty from past failures (non-ban)
    """
    key = f"{player}|{stat.lower()}"
    
    # Check warnings (non-ban failures)
    if key in MEMORY_DB.get("warnings", {}):
        fails = MEMORY_DB["warnings"][key].get("fails_10", 0)
        return fails * MEMORY_PENALTY
    
    return 0


# ========================================
# CONFIDENCE ADJUSTMENT
# ========================================
def apply_confidence_cap(stat: str, model_confidence: float) -> float:
    """
    Apply stat-type confidence caps
    """
    stat_lower = stat.lower()
    cap = STAT_CAPS.get(stat_lower, 85)
    
    return min(model_confidence, cap)


def calculate_effective_confidence(player: str, stat: str, model_confidence: float) -> float:
    """
    Apply caps + memory penalties
    CONTROLLED BY: config/penalty_mode.json → gate_penalties
    """
    # If penalties are off, return raw confidence
    if not PENALTY_MODE.get("gate_penalties", True):
        return model_confidence
    
    # Apply stat cap
    capped = apply_confidence_cap(stat, model_confidence)
    
    # Apply memory penalty
    penalty = get_memory_penalty(player, stat)
    effective = capped - penalty
    
    return max(effective, 0.0)


# ========================================
# FINAL DECISION
# ========================================
def get_play_decision(effective_confidence: float) -> str:
    """
    Determine tier based on canonical thresholds.
    
    Returns:
        PLAY (SLAM): ≥80%
        STRONG: ≥65% and <80%
        LEAN: ≥55% and <65%
        NO_PLAY: <55%
    """
    slam_thresh = THRESHOLDS.get("SLAM", THRESHOLDS.get("PLAY", 80))
    strong_thresh = THRESHOLDS.get("STRONG", 65)
    lean_thresh = THRESHOLDS.get("LEAN", 55)
    
    if effective_confidence >= slam_thresh:
        return "PLAY"
    elif effective_confidence >= strong_thresh:
        return "STRONG"
    elif effective_confidence >= lean_thresh:
        return "LEAN"
    else:
        return "NO_PLAY"


# ========================================
# MASTER GATE FUNCTION
# ========================================
def run_all_gates(
    player: str,
    stat: str,
    opponent_def_rank: int,
    spread: float,
    model_confidence: float,
    soft_gates: bool = False,
    multiplier_higher: Optional[float] = None,
    multiplier_lower: Optional[float] = None,
    direction: str = "OVER"
) -> dict:
    """
    Run all gates in order (execution order per spec)
    
    Args:
        soft_gates: If True, composite stats get WARNING instead of BLOCK
        multiplier_higher: Underdog HIGHER multiplier (for market alignment)
        multiplier_lower: Underdog LOWER multiplier (for market alignment)
        direction: "OVER" or "UNDER" (for market alignment)
    
    Returns:
        {
            'passed': bool,
            'decision': 'PLAY' | 'LEAN' | 'NO_PLAY' | 'BLOCKED',
            'effective_confidence': float,
            'gate_results': [list of gate results],
            'block_reason': str or None
        }
    """
    gate_results = []
    composite_warning = False
    
    # GATE 1: Composite Stat
    passed, reason, meta = _parse_gate_result(gate_composite_stat(stat, soft_gates=soft_gates))
    gate_results.append({"gate": "R1_COMPOSITE", "passed": passed, "reason": reason, **meta})
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    # Track if composite stat warning (for confidence cap later)
    if "WARNING" in reason:
        composite_warning = True
    
    # GATE 2: Elite Defense
    passed, reason, meta = _parse_gate_result(gate_elite_defense(stat, opponent_def_rank, soft_gates=soft_gates))
    gate_results.append({"gate": "R2_ELITE_DEF", "passed": passed, "reason": reason, **meta})
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    # Track elite defense warning on combos
    if "WARNING" in reason and "suppresses" in reason:
        composite_warning = True
    
    # GATE 3: Star Guard Points Trap
    player_role = None
    for k in _player_lookup_keys(player):
        player_role = PLAYER_CLASSIFICATIONS.get(k)
        if player_role:
            break
    if not player_role:
        player_role = "UNKNOWN"
    passed, reason, meta = _parse_gate_result(gate_star_guard_points(player_role, stat, opponent_def_rank))
    gate_results.append({"gate": "R3_STAR_GUARD", "passed": passed, "reason": reason, **meta})
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    
    # GATE 4: Blowout Risk
    passed, reason, meta = _parse_gate_result(gate_blowout(spread))
    gate_results.append({"gate": "R4_BLOWOUT", "passed": passed, "reason": reason, **meta})
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    
    # GATE 5: Bench Garbage Time Trap
    passed, reason, meta = _parse_gate_result(gate_bench_garbage_time(player, spread))
    gate_results.append({"gate": "R5_BENCH_TRAP", "passed": passed, "reason": reason, **meta})
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    
    # GATE 6: Market Alignment (Tier 1 Fix - MIT Quant Review)
    # Block if model diverges >10% from market-implied probability
    if HAS_MARKET_GATE and multiplier_higher is not None and multiplier_lower is not None:
        market_passes, market_msg, market_details = check_market_alignment(
            model_prob=model_confidence,
            direction=direction,
            multiplier_higher=multiplier_higher,
            multiplier_lower=multiplier_lower,
            threshold_pct=10.0  # Conservative threshold: 10% divergence
        )
        gate_results.append({
            "gate": "R6_MARKET_ALIGN",
            "passed": market_passes,
            "reason": market_msg,
            "market_prob": market_details.get("market_prob"),
            "divergence": market_details.get("divergence"),
            "threshold": 10.0  # Conservative 10% threshold
        })
        if not market_passes:
            return {
                "passed": False,
                "decision": "BLOCKED",
                "effective_confidence": 0.0,
                "gate_results": gate_results,
                "block_reason": market_msg
            }
    
    # ROLE MAPPING
    passed, reason, meta = _parse_gate_result(gate_role_mapping(player, stat, soft_gates=soft_gates))
    # If we returned a WARNING via role mapping, attach the configured penalty.
    if meta.get("severity") == "WARNING" and "penalty" not in meta:
        stat_lower = str(stat).lower()
        if player_role == "BIG" and stat_lower == "assists":
            meta["penalty"] = PENALTY_BIG_FORBIDS_ASSISTS
        elif player_role == "BIG" and stat_lower == "3pm":
            meta["penalty"] = PENALTY_BIG_FORBIDS_3PM
        elif player_role == "BIG" and stat_lower == "steals":
            meta["penalty"] = PENALTY_BIG_FORBIDS_STEALS

    gate_results.append({"gate": "ROLE_MAP", "passed": passed, "reason": reason, **meta})
    # Track combo stat warnings for confidence cap
    if "WARNING" in reason and ("forbids" in reason or "doesn't explicitly allow" in reason):
        composite_warning = True
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    
    # BAN LIST
    passed, reason, meta = _parse_gate_result(gate_ban_list(player, stat))
    gate_results.append({"gate": "BAN_LIST", "passed": passed, "reason": reason, **meta})
    if not passed:
        return {
            "passed": False,
            "decision": "BLOCKED",
            "effective_confidence": 0.0,
            "gate_results": gate_results,
            "block_reason": reason
        }
    
    # CONFIDENCE ADJUSTMENT
    warned_model_confidence = _apply_warning_penalties(float(model_confidence), gate_results)
    
    # NEW: Apply stat-specific Bayesian calibration penalties
    # CONTROLLED BY: config/penalty_mode.json → stat_penalty
    stat_lower = str(stat).lower()
    stat_penalty = STAT_PENALTIES.get(stat_lower, 0.0)
    if stat_penalty > 0 and PENALTY_MODE.get("stat_penalty", True):
        # Apply penalty as percentage reduction
        warned_model_confidence = warned_model_confidence * (1.0 - stat_penalty / 100.0)
        gate_results.append({
            "gate": "STAT_CALIBRATION",
            "passed": True,
            "reason": f"Bayesian penalty -{stat_penalty}% for '{stat}' (underperforming vs prediction)",
            "severity": "WARNING",
            "penalty": stat_penalty / 100.0
        })
    
    effective_confidence = calculate_effective_confidence(player, stat, warned_model_confidence)
    
    # Cap composite stats at 68% max (multi-category fragility risk)
    if composite_warning and effective_confidence > 68.0:
        effective_confidence = 68.0
        gate_results.append({
            "gate": "COMPOSITE_CAP",
            "passed": True,
            "reason": f"Capped at 68% (composite stat fragility)"
        })
    
    if abs(warned_model_confidence - float(model_confidence)) > 1e-9:
        warn_note = f"warnings adjusted {float(model_confidence):.1f}%→{warned_model_confidence:.1f}%"
    else:
        warn_note = None
    gate_results.append({
        "gate": "CONFIDENCE_ADJ",
        "passed": True,
        "reason": (
            f"Adjusted to {effective_confidence:.1f}% (cap + memory penalty)"
            + (f"; {warn_note}" if warn_note else "")
        )
    })
    
    # FINAL DECISION
    decision = get_play_decision(effective_confidence)
    
    return {
        "passed": True,
        "decision": decision,
        "effective_confidence": effective_confidence,
        "gate_results": gate_results,
        "block_reason": None
    }


# ========================================
# UTILITY: Print Gate Results
# ========================================
def print_gate_results(player: str, stat: str, result: dict):
    """Pretty print gate results for debugging"""
    print(f"\n{'='*60}")
    print(f"PLAYER: {player} | STAT: {stat}")
    print(f"{'='*60}")
    
    for gate in result["gate_results"]:
        status = "✅ PASS" if gate["passed"] else "🚫 BLOCK"
        print(f"{status} | {gate['gate']}: {gate['reason']}")
    
    print(f"\nFINAL DECISION: {result['decision']}")
    if result['decision'] != "BLOCKED":
        print(f"Effective Confidence: {result['effective_confidence']:.1f}%")
    print(f"{'='*60}\n")
