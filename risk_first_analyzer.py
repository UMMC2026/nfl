"""
RISK-FIRST ANALYSIS PIPELINE
Integrates risk gates into NBA prop analysis
Execution order: Gates → Probability → Decision
"""

import hashlib
import json
import numpy as np
from scipy.stats import norm, nbinom
from pathlib import Path
from typing import Optional
import os
from risk_gates import run_all_gates, print_gate_results
from context_gates import run_context_gates
from extended_stats_dict import PLAYER_STATS

from stats_last10_cache import refresh_daily_last10_mu_sigma
from signals_export import build_signals_from_risk_first
from telegram_push import can_send as telegram_can_send, push_signals as telegram_push_signals

from nba_team_resolver import normalize_team_code, resolve_current_team_abbr
from nba_team_context import (
    get_team_context, get_pace_adjustment, get_defensive_matchup_factor,
    get_matchup_summary, apply_context_to_projection, is_elite_defense, is_weak_defense
)

# =============================================================================
# HYBRID CONFIDENCE SYSTEM (Data-Driven, 2026-01-29)
# =============================================================================
try:
    from core.hybrid_confidence import calculate_hybrid_confidence
    from integration.hybrid_adapter import RiskFirstHybridAdapter
    HAS_HYBRID_CONFIDENCE = True
except ImportError:
    HAS_HYBRID_CONFIDENCE = False

# DATA-DRIVEN PENALTIES (from 97-pick calibration analysis)
try:
    from config.data_driven_penalties import (
        STAT_MULTIPLIERS_DATA_DRIVEN,
        DIRECTION_ADJUSTMENT,
        SAMPLE_SIZE_RULES,
        get_data_driven_multiplier,
    )
    HAS_DATA_DRIVEN_PENALTIES = True
except ImportError:
    HAS_DATA_DRIVEN_PENALTIES = False

# NBA specialist/type governance (2nd-axis archetype system)
try:
    from nba.stat_specialists import (
        StatSpecialistClassifier,
        StatSpecialistType,
        apply_specialist_confidence_governance,
    )
    HAS_STAT_SPECIALISTS = True
except ImportError:
    HAS_STAT_SPECIALISTS = False

# NEW: Pure stat specialist engine (production lock-in v1.0)
try:
    from core.stat_specialist_engine import (
        StatSpecialist,
        classify_stat_specialist,
        apply_specialist_confidence_cap,
        should_reject_pick,
        SPECIALIST_CONFIDENCE_CAP_PCT,
    )
    HAS_STAT_SPECIALIST_ENGINE = True
except ImportError:
    HAS_STAT_SPECIALIST_ENGINE = False

# 3PM shot-profile governor (enforces 3PM confidence ceilings)
try:
    from core.shot_profile_archetypes import ThreePointGovernor
    HAS_3PM_SHOT_PROFILE_GOVERNOR = True
except ImportError:
    HAS_3PM_SHOT_PROFILE_GOVERNOR = False

# =============================================================================
# STAT DEVIATION GATE (SDG) - Coin Flip Detection (2026-02-01)
# Penalizes picks where line ≈ player's mean (star-tax traps)
# =============================================================================
try:
    from core.stat_deviation_gate import stat_deviation_gate, SDG_CONFIG
    HAS_STAT_DEVIATION_GATE = True
except ImportError:
    HAS_STAT_DEVIATION_GATE = False

# Import Kelly and Compression from thresholds (SOP v2.1)
try:
    from config.thresholds import (
        compute_kelly_bet_size, apply_confidence_compression,
        COMPRESSION_THRESHOLD_STDDEV, COMPRESSED_MAX_CONFIDENCE
    )
    HAS_KELLY = True
except ImportError:
    HAS_KELLY = False

# Game situation context (B2B, Home/Away, Rest Days)
try:
    from nba_game_situation import (
        get_game_situation, get_default_situation, get_situation_adjustment,
        apply_situation_to_projection, set_game_situation
    )
    HAS_SITUATION_CONTEXT = True
except ImportError:
    HAS_SITUATION_CONTEXT = False

from hq_options import HQOptions, PlayerOverride, load_hq_options_from_env

# =============================================================================
# PENALTY MODE CONFIGURATION (2026-01-29)
# =============================================================================
# Load penalty mode to control which penalties are active
def load_penalty_mode() -> dict:
    """Load penalty mode configuration."""
    config_path = Path(__file__).parent / "config" / "penalty_mode.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("active_mode_settings", {})
    except Exception:
        # Default: all penalties ON (legacy behavior)
        return {
            "variance_penalty": True,
            "sample_penalty": True,
            "stat_penalty": True,
            "gate_penalties": True,
            "bootstrap_guard": True,
            "edge_gate": True
        }

PENALTY_MODE = load_penalty_mode()

# Analysis configuration (advanced settings)
try:
    from analysis_config import get_active_config, AnalysisConfig
    HAS_ANALYSIS_CONFIG = True
except ImportError:
    HAS_ANALYSIS_CONFIG = False

# Probability blender (hybrid model)
try:
    from probability_blender import blend_probabilities, apply_graduated_penalty, calculate_kelly_edge
    HAS_PROBABILITY_BLENDER = True
except ImportError:
    HAS_PROBABILITY_BLENDER = False

# Edge diagnostics (σ-distance, penalty attribution, tier labeling)
try:
    from edge_diagnostics import (
        generate_edge_diagnostic, 
        get_tier_label,
        format_diagnostic_block,
        EdgeDiagnostic
    )
    HAS_EDGE_DIAGNOSTICS = True
except ImportError:
    HAS_EDGE_DIAGNOSTICS = False

# =============================================================================
# CALIBRATION FIXER (Confidence Compression to Fix 28% Error)
# =============================================================================
try:
    from config.calibration_fixer import apply_calibration_fix
    HAS_CALIBRATION_FIXER = True
except ImportError:
    HAS_CALIBRATION_FIXER = False

# =============================================================================
# SOP v2.1: Professional Quant Framework Integration
# =============================================================================
# These modules implement the MISSING quant features:
# - Multi-window projection (L3/L5/L10/L20/Season weighted)
# - Variance penalty (CV-based confidence reduction)
# - Edge threshold gate (3% minimum edge requirement)

try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "betting_system" / "quant"))
    from multi_window_projection import MultiWindowProjectionEngine, WINDOW_WEIGHTS
    from variance_penalty import apply_variance_penalty, calculate_cv
    from edge_threshold_gate import check_edge_gate, EDGE_THRESHOLDS
    HAS_QUANT_FRAMEWORK = True
except ImportError as e:
    HAS_QUANT_FRAMEWORK = False
    print(f"[WARNING] Quant framework not available: {e}")


def _cap_percent_no_increase(value_percent: float, *, cap_percent: float) -> float:
    """Cap a percent value without ever increasing it."""
    try:
        v = float(value_percent)
        c = float(cap_percent)
        return float(min(v, c))
    except Exception:
        return float(value_percent)


def _player_override_for(player: str, opts: HQOptions) -> Optional[PlayerOverride]:
    try:
        if not player or not isinstance(player, str):
            return None
        return opts.player_overrides.get(player.strip())
    except Exception:
        return None

# Create STATS_DICT in new format (player -> {stat: (mu, sigma)})
STATS_DICT = {}
for (player, stat), (mu, sigma) in PLAYER_STATS.items():
    if player not in STATS_DICT:
        STATS_DICT[player] = {}
    STATS_DICT[player][stat] = (mu, sigma)

# In-memory tracking to ensure we refresh NBA API stats once per day.
_LAST_REFRESH_ISO = None

# Best-effort player->team map derived from NBA API game logs (populated during daily refresh).
_LAST_TEAM_MAP = {}

# Best-effort recent value series (player, stat) -> [values] (most recent first)
_LAST_SERIES_MAP = {}

# Best-effort minutes volatility proxy: player -> minutes_cv (std/mean)
_LAST_MINUTES_CV = {}

# Optional roster truth map (player -> team) sourced from ESPN via engine/roster_gate.
# NOTE: This can be slow if it tries to fetch all teams. Disabled by default.
_ACTIVE_ROSTER_MAP = None

# Team defensive rankings - now populated from nba_team_context.py
# This provides fallback for any code still using TEAM_DEF_RANK directly
def _build_team_def_rank():
    """Build TEAM_DEF_RANK from nba_team_context."""
    from nba_team_context import NBA_TEAM_CONTEXT
    return {team: ctx.def_rank for team, ctx in NBA_TEAM_CONTEXT.items()}

TEAM_DEF_RANK = _build_team_def_rank()

# Discrete/count stat keys eligible for count-process modeling.
# Keep this conservative; we can expand later if we have consistent keying.
COUNT_STATS = {
    "points",
    "pts",
    "rebounds",
    "reb",
    "assists",
    "ast",
    "steals",
    "stl",
    "blocks",
    "blk",
    "turnovers",
    "tov",
    "3pm",
    "3ptm",
    "threes",
}


def _should_use_negbin_for_stat(
    *,
    stat_lower: str,
    has_series: bool,
    sample_n: int,
    series_mean: float | None,
    series_var: float | None,
    mu_adj: float,
    sigma_eff: float,
) -> bool:
    """Decide if negative-binomial modeling is appropriate for a given stat.

    Rationale:
    - Use negbin only for true count processes (REB, AST, STL, BLK, TOV, 3PM),
      and only when overdispersion is evident (var > mean) with decent sample.
    - Be conservative with PTS: default to normal CDF due to aggregation and
      CLT-like behavior. Allow negbin for PTS only when mean is small and
      overdispersion is strong.
    - PRA and composite stats should never route to negbin.
    """
    try:
        s = str(stat_lower).lower().strip()

        # Stats that are eligible for negbin when overdispersed
        canonical_negbin_stats = {
            "rebounds", "reb",
            "assists", "ast",
            "steals", "stl",
            "blocks", "blk",
            "turnovers", "tov",
            "3pm", "3ptm", "threes",
        }

        # Points: prefer normal; only allow negbin in narrow, overdispersed regimes
        if s in {"points", "pts"}:
            if has_series and sample_n >= 15 and isinstance(series_mean, (int, float)) and isinstance(series_var, (int, float)):
                return (series_mean <= 15.0) and (series_var >= series_mean * 1.5)
            # Without series, avoid negbin for points
            return False

        # Canonical count stats: require overdispersion signals
        if s in canonical_negbin_stats:
            if has_series and sample_n >= 12 and isinstance(series_mean, (int, float)) and isinstance(series_var, (int, float)):
                return (series_var > series_mean) and (series_mean > 0.0)
            # No series: fallback only when variance proxy from sigma indicates overdispersion
            vv = float(sigma_eff) ** 2
            return (vv > float(mu_adj)) and (float(mu_adj) > 0.0)

        # All other stats (including PRA/composites): do not use negbin
        return False
    except Exception:
        return False


def _maybe_apply_oracle_probability(
    prop: dict,
    base_confidence: float,
    prob_details: dict,
) -> float:
    """Optionally override model_confidence with an Oracle-provided probability.

    This is a *soft wiring* hook: when the environment variable USE_ORACLE_PROB
    is set to "1" and the prop contains an "oracle_prob" field, that value is
    interpreted as a probability and used as the new model_confidence.

    - oracle_prob in [0, 1] is treated as decimal and scaled to percent.
    - oracle_prob > 1 is assumed to already be in percent.

    If anything is missing or invalid, the base_confidence is returned.
    """
    try:
        if os.getenv("USE_ORACLE_PROB", "0").strip() != "1":
            return float(base_confidence)

        if not isinstance(prop, dict) or "oracle_prob" not in prop:
            return float(base_confidence)

        raw = prop.get("oracle_prob")
        if raw is None:
            return float(base_confidence)

        p = float(raw)
        # Accept both decimal and percentage formats
        if p <= 1.0:
            p_pct = p * 100.0
        else:
            p_pct = p

        # Sanity clamp
        p_pct = max(1.0, min(99.0, p_pct))

        prob_details["oracle_prob"] = round(p_pct, 3)
        prob_details["oracle_used"] = True
        return float(p_pct)
    except Exception:
        return float(base_confidence)


def _clip(v: float, lo: float, hi: float) -> float:
    try:
        x = float(v)
        return float(max(lo, min(hi, x)))
    except Exception:
        return float(lo)

# Game spreads (placeholder - update with real data)
GAME_SPREADS = {
    "ORL": -2.5,  # ORL -2.5 vs MEM
    "MEM": 2.5,
    "CLE": -8.0,  # CLE -8 vs PHI
    "PHI": 8.0,
    "TOR": 5.5,
    "NYK": -5.5,
    "SAC": 3.0,
    "LAC": -3.0,
    "BKN": 7.0,
    "IND": -7.0
}

# Combo stat definitions: stat_name -> list of component stats
COMBO_STAT_MAP = {
    "pra": ["points", "rebounds", "assists"],
    "pts+reb+ast": ["points", "rebounds", "assists"],
    "pr": ["points", "rebounds"],
    "pts+reb": ["points", "rebounds"],
    "points+rebounds": ["points", "rebounds"],
    "pa": ["points", "assists"],
    "pts+ast": ["points", "assists"],
    "points+assists": ["points", "assists"],
    "ra": ["rebounds", "assists"],
    "reb+ast": ["rebounds", "assists"],
    "rebounds+assists": ["rebounds", "assists"],
    "stocks": ["steals", "blocks"],
    "stl+blk": ["steals", "blocks"],
    "blocks+steals": ["steals", "blocks"],
}


def get_stat_params(player: str, stat: str) -> tuple:
    """Get mu, sigma for player+stat from STATS_DICT.
    
    For combo stats (pra, pts+reb+ast, etc.), computes from base stats:
    - mu_combo = sum of component mus
    - sigma_combo = sqrt(sum of component variances)
    """
    player_stats = STATS_DICT.get(player)
    if not player_stats:
        return None, None
    
    stat_lower = stat.lower()
    
    # Direct lookup first
    stat_data = player_stats.get(stat_lower)
    if stat_data:
        return stat_data
    
    # Check if it's a combo stat we can compute
    components = COMBO_STAT_MAP.get(stat_lower)
    if components:
        mu_total = 0.0
        var_total = 0.0
        for comp in components:
            comp_data = player_stats.get(comp)
            if comp_data is None:
                return None, None  # Missing a component
            mu, sigma = comp_data
            mu_total += mu
            var_total += sigma ** 2
        sigma_total = var_total ** 0.5
        return (mu_total, sigma_total)
    
    return None, None


def _apply_stats_overlay(overlay: dict) -> int:
    """Apply {(player, stat): (mu, sigma)} overlay into STATS_DICT. Returns count applied."""
    applied = 0
    for (player, stat), (mu, sigma) in overlay.items():
        if player not in STATS_DICT:
            STATS_DICT[player] = {}
        STATS_DICT[player][stat] = (mu, sigma)
        applied += 1
    return applied


def preflight_stats_check(props: list = None, verbose: bool = True) -> dict:
    """
    Pre-flight check to validate stats pipeline is working before analysis.
    
    Checks:
    1. STATS_DICT has data (not empty)
    2. Today's cache file exists
    3. Sample players have valid mu/sigma values
    4. Stat averages are non-zero for key stats
    
    Returns dict with: passed (bool), issues (list), stats (dict of counts)
    """
    from datetime import date
    import glob
    
    issues = []
    stats = {
        "stats_dict_players": len(STATS_DICT),
        "cache_exists": False,
        "cache_date": None,
        "sample_checks_passed": 0,
        "sample_checks_failed": 0,
    }
    
    today_iso = date.today().isoformat()
    
    # Check 1: STATS_DICT has data (should have 100+ after API refresh)
    if len(STATS_DICT) < 100:
        issues.append(f"STATS_DICT only has {len(STATS_DICT)} players (expected 100+ after API refresh). Stats may be stale.")
    
    # Check 2: Today's cache file exists
    cache_pattern = f"outputs/stats_cache/nba_mu_sigma_*{today_iso}*.json"
    cache_files = glob.glob(cache_pattern)
    if cache_files:
        stats["cache_exists"] = True
        stats["cache_date"] = today_iso
        # Also check cache size to ensure it has good data
        try:
            import json
            with open(cache_files[0], 'r') as f:
                cache_data = json.load(f)
            cache_entries = len(cache_data.get("stats", []))
            stats["cache_entries"] = cache_entries
            if cache_entries < 400:
                issues.append(f"Cache only has {cache_entries} stat entries (expected 500+). API fetch may have been incomplete.")
        except Exception:
            pass
    else:
        issues.append(f"No cache file found for today ({today_iso}). Run will use stale/fallback data.")
    
    # Check 3: Sample players have valid data
    sample_players = []
    if props:
        # Use players from the slate
        seen = set()
        for p in props:
            if isinstance(p, dict) and p.get("player") and p.get("player") not in seen:
                sample_players.append(p.get("player"))
                seen.add(p.get("player"))
                if len(sample_players) >= 10:
                    break
    else:
        # Use first 10 from STATS_DICT
        sample_players = list(STATS_DICT.keys())[:10]
    
    # Check 4: Validate mu/sigma values
    key_stats = ["points", "rebounds", "assists", "3pm", "steals", "blocks"]
    zero_stat_players = []
    
    for player in sample_players:
        player_data = STATS_DICT.get(player, {})
        if not player_data:
            stats["sample_checks_failed"] += 1
            continue
        
        has_valid_stat = False
        for stat in key_stats:
            stat_data = player_data.get(stat)
            if isinstance(stat_data, (tuple, list)) and len(stat_data) >= 2:
                mu, sigma = stat_data[0], stat_data[1]
                if mu > 0 or sigma > 0:
                    has_valid_stat = True
                    break
        
        if has_valid_stat:
            stats["sample_checks_passed"] += 1
        else:
            stats["sample_checks_failed"] += 1
            zero_stat_players.append(player)
    
    if zero_stat_players:
        issues.append(f"Players with zero stats: {', '.join(zero_stat_players[:5])}")
    
    # Determine pass/fail
    passed = len(issues) == 0
    
    # Print results if verbose
    if verbose:
        print()
        print("=" * 60)
        print("PRE-FLIGHT STATS CHECK")
        print("=" * 60)
        print(f"  STATS_DICT players: {stats['stats_dict_players']}")
        print(f"  Cache file exists:  {stats['cache_exists']} ({stats['cache_date'] or 'N/A'})")
        print(f"  Sample checks:      {stats['sample_checks_passed']} passed, {stats['sample_checks_failed']} failed")
        
        if issues:
            print()
            # NOTE: Keep output ASCII-only for Windows terminals that default to cp1252.
            print("WARN: ISSUES FOUND:")
            for issue in issues:
                print(f"    - {issue}")
            print()
            print("  RECOMMENDATION: Set FORCE_STATS_REFRESH=1 and re-run to refresh cache")
        else:
            print()
            print("OK: All checks passed - stats pipeline is healthy")
        print("=" * 60)
        print()
    
    return {
        "passed": passed,
        "issues": issues,
        "stats": stats,
    }


def _refresh_daily_api_stats(
    props: list,
    *,
    season: str = "2025-26",
    last_n_games: int = 10,
    short_n_games: int = 5,
    blend_weight: float = 0.65,
) -> None:
    """Refresh API-enabled stats once per day for players in this slate.

    Never raises (report runs must not crash). Falls back to existing stats if API fails.
    """
    global _LAST_REFRESH_ISO
    global _LAST_TEAM_MAP
    global _LAST_SERIES_MAP
    global _LAST_MINUTES_CV

    from datetime import date

    today_iso = date.today().isoformat()
    force_refresh = os.getenv("FORCE_STATS_REFRESH", "").strip() == "1"

    # Optional window override (menu-driven). Defaults preserve existing behavior.
    try:
        env_last = os.getenv("STATS_LAST_N", "").strip()
        env_short = os.getenv("STATS_SHORT_N", "").strip()
        env_blend = os.getenv("STATS_BLEND_WEIGHT", "").strip()
        if env_last:
            last_n_games = int(env_last)
        if env_short:
            short_n_games = int(env_short)
        if env_blend:
            blend_weight = float(env_blend)
    except Exception:
        pass

    if _LAST_REFRESH_ISO == today_iso and not force_refresh:
        return

    try:
        players: list[str] = []
        for p in props:
            if not isinstance(p, dict):
                continue
            name = p.get("player")
            if isinstance(name, str) and name:
                players.append(name)
        rr = refresh_daily_last10_mu_sigma(
            players,
            season=season,
            last_n_games=last_n_games,
            short_n_games=short_n_games,
            mode="blend",
            blend_weight=blend_weight,
            force=force_refresh,
        )
        applied = _apply_stats_overlay(rr.overlay)

        # Keep best-effort team map for team sanity checks on later runs.
        try:
            if isinstance(rr.team_map, dict) and rr.team_map:
                _LAST_TEAM_MAP = dict(rr.team_map)
        except Exception:
            pass

        # Keep best-effort series + minutes vol for empirical probability + uncertainty adjustments.
        try:
            if hasattr(rr, "series") and isinstance(rr.series, dict) and rr.series:
                _LAST_SERIES_MAP = dict(rr.series)
        except Exception:
            pass
        try:
            if hasattr(rr, "minutes_cv") and isinstance(rr.minutes_cv, dict) and rr.minutes_cv:
                _LAST_MINUTES_CV = dict(rr.minutes_cv)
        except Exception:
            pass

        # ASCII-safe informational logging (no emojis)
        if rr.warnings:
            print("[STATS] Warnings during NBA API refresh:")
            for w in rr.warnings[:10]:
                print(f"  - {w}")

        print(
            f"[STATS] Daily refresh: mode=L{last_n_games}/L{short_n_games} blend({blend_weight:.2f}) "
            f"refreshed={rr.refreshed} applied={applied} source={rr.source}"
        )
        _LAST_REFRESH_ISO = today_iso
    except Exception as e:
        # No exceptions allowed in report run
        print(f"[STATS] Daily refresh skipped due to error: {e}")
        _LAST_REFRESH_ISO = today_iso


def _team_truth_for_player(player: str) -> Optional[str]:
    """Return best-effort authoritative team code for player (3-letter), or None."""
    if not player:
        return None
    try:
        t = _LAST_TEAM_MAP.get(player)
        if isinstance(t, str) and t.strip():
            return normalize_team_code(t)
    except Exception:
        pass

    # Fallback: ask nba_api CommonPlayerInfo (best-effort; cached per process)
    team = resolve_current_team_abbr(player)
    if team:
        return normalize_team_code(team)

    # Optional last-resort: ESPN roster map (can be slow). Off by default.
    try:
        import os

        if os.getenv("USE_ESPN_ROSTER_TRUTH", "").strip() != "1":
            return None

        global _ACTIVE_ROSTER_MAP
        if _ACTIVE_ROSTER_MAP is None:
            from engine.roster_gate import build_active_roster_map
            import io
            from contextlib import redirect_stdout, redirect_stderr

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                _ACTIVE_ROSTER_MAP = build_active_roster_map("NBA") or {}

        if isinstance(_ACTIVE_ROSTER_MAP, dict) and player in _ACTIVE_ROSTER_MAP:
            return normalize_team_code(_ACTIVE_ROSTER_MAP.get(player) or None)
    except Exception:
        return None

    return None


def _sanitize_props_team_truth(props: list) -> tuple[list, list, list]:
    """Sanitize props against matchup teams + best-effort roster truth.

    Returns:
      kept_props: list[dict]          - props to analyze
      skipped_results: list[dict]     - SKIP results for dropped props (transparent)
      warnings: list[str]            - human-readable warnings
    """
    kept: list = []
    skipped_results: list = []
    warnings: list[str] = []

    for prop in props:
        if not isinstance(prop, dict):
            continue

        player = prop.get("player")
        stat = prop.get("stat")
        line = prop.get("line")
        direction = prop.get("direction")
        team = normalize_team_code(prop.get("team") or None) or "UNK"
        away = normalize_team_code(prop.get("matchup_away") or None)
        home = normalize_team_code(prop.get("matchup_home") or None)

        # If we don't have matchup info, keep as-is (backward compatibility).
        if not away or not home:
            kept.append(prop)
            continue

        matchup_set = {away, home}
        truth_team = _team_truth_for_player(player) if isinstance(player, str) else None

        # If we can confidently tell the player is not in this matchup, drop the prop.
        if truth_team and truth_team not in matchup_set:
            skipped_results.append(
                {
                    "player": player,
                    "team": team,
                    "stat": stat,
                    "line": line,
                    "direction": direction,
                    "decision": "SKIP",
                    "reason": f"Team mismatch: {player} is {truth_team}, slate matchup is {away}@{home}",
                    "gates_passed": False,
                }
            )
            if len(warnings) < 10:
                warnings.append(f"[TEAM] Dropped prop due to mismatch: {player}={truth_team} not in {away}/{home}")
            continue

        # Otherwise, normalize team/opponent fields when possible.
        new_prop = dict(prop)
        if truth_team and truth_team in matchup_set:
            new_prop["team"] = truth_team
            new_prop["opponent"] = home if truth_team == away else away
        else:
            # No truth; at least ensure opponent is consistent if the parsed team is one of the matchup teams.
            if team in matchup_set:
                new_prop["team"] = team
                new_prop["opponent"] = home if team == away else away

        kept.append(new_prop)

    return kept, skipped_results, warnings


def monte_carlo_sim(mu: float, sigma: float, line: float, direction: str, trials: int = 10000) -> float:
    """Monte Carlo simulation for probability"""
    samples = np.random.normal(mu, sigma, trials)
    
    if direction.lower() == "higher":
        hits = np.sum(samples > line)
    else:
        hits = np.sum(samples < line)
    
    return float((hits / trials) * 100)


def bayesian_prob(mu: float, sigma: float, line: float, direction: str) -> float:
    """Bayesian probability using Normal CDF"""
    z_score = (line - mu) / sigma
    
    if direction.lower() == "higher":
        prob = 1 - norm.cdf(z_score)
    else:
        prob = norm.cdf(z_score)
    
    return float(prob * 100)


def _empirical_prob_from_series(series: list, line: float, direction: str) -> Optional[float]:
    """Deterministic empirical hit probability from observed values.

    Tie handling: counts exact-equals as half-hit (conservative for integer lines).
    Returns percent in [0, 100].
    """
    try:
        if not series:
            return None
        vals = [float(x) for x in series if isinstance(x, (int, float))]
        n = len(vals)
        if n <= 0:
            return None

        hits = 0.0
        if str(direction).lower() == "higher":
            for v in vals:
                if v > line:
                    hits += 1.0
                elif v == line:
                    hits += 0.5
        else:
            for v in vals:
                if v < line:
                    hits += 1.0
                elif v == line:
                    hits += 0.5
        return float((hits / n) * 100.0)
    except Exception:
        return None


def _wilson_lower_bound(phat: float, n: int, z: float = 1.28) -> Optional[float]:
    """Wilson lower bound for a Bernoulli proportion.

    - phat in [0,1]
    - n >= 1
    - z=1.28 ~ 80% two-sided interval

    Returns a conservative estimate in [0,1].
    """
    try:
        n_i = int(n)
        if n_i <= 0:
            return None
        p = float(phat)
        p = max(0.0, min(1.0, p))
        zf = float(z)

        denom = 1.0 + (zf * zf) / n_i
        center = p + (zf * zf) / (2.0 * n_i)
        margin = zf * float(np.sqrt((p * (1.0 - p) + (zf * zf) / (4.0 * n_i)) / n_i))
        out = (center - margin) / denom
        return float(max(0.0, min(1.0, out)))
    except Exception:
        return None


def _empirical_hybrid_percent(
    p_emp_percent: float,
    *,
    avg_margin_dir: float,
    scale_sigma: float,
    max_adjustment: float = 0.10,
) -> float:
    """Blend empirical hit-rate with directional average margin.

    Conservative by construction:
    - Adjustment bounded to +/- max_adjustment probability mass.
    - Output clipped to [1%, 99%].
    """
    try:
        p_emp = float(p_emp_percent)
        scale = float(max(1.0, scale_sigma))
        adj = _clip(float(avg_margin_dir) / (3.0 * scale), -float(max_adjustment), float(max_adjustment))
        p_adj = p_emp + (adj * 100.0)
        return float(_clip(p_adj, 1.0, 99.0))
    except Exception:
        return float(_clip(p_emp_percent, 1.0, 99.0))


def _deterministic_seed(*parts: object) -> int:
    """Deterministic 32-bit seed from stable string parts."""
    try:
        s = "|".join(str(p) for p in parts)
        h = hashlib.md5(s.encode("utf-8")).hexdigest()
        return int(h[:8], 16)
    except Exception:
        return 1337


def _bootstrap_bands_percent(
    series: list,
    line: float,
    direction: str,
    *,
    seed: int,
    boots: int = 250,
    low_q: float = 10.0,
    high_q: float = 90.0,
) -> Optional[dict]:
    """Deterministic bootstrap confidence bands for empirical hit probability.

    Returns dict with p_median/p_low/p_high/width in percent points.
    """
    try:
        vals = [float(x) for x in series if isinstance(x, (int, float))]
        n = len(vals)
        if n < 4:
            return None

        rng = np.random.RandomState(int(seed) & 0xFFFFFFFF)
        probs: list[float] = []
        for _ in range(int(max(10, boots))):
            idx = rng.randint(0, n, size=n)
            sample = [vals[i] for i in idx]
            p = _empirical_prob_from_series(sample, float(line), direction)
            if isinstance(p, (int, float)):
                probs.append(float(p))

        if len(probs) < 10:
            return None

        arr = np.array(probs, dtype=float)
        p_med = float(np.percentile(arr, 50.0))
        p_lo = float(np.percentile(arr, float(low_q)))
        p_hi = float(np.percentile(arr, float(high_q)))
        width = float(max(0.0, p_hi - p_lo))
        return {
            "p_median": round(p_med, 3),
            "p_low": round(p_lo, 3),
            "p_high": round(p_hi, 3),
            "width": round(width, 3),
            "boots": int(len(probs)),
            "quantiles": [float(low_q), float(high_q)],
        }
    except Exception:
        return None


def _negbin_probability_percent(
    *,
    mean: float,
    var: float,
    line: float,
    direction: str,
) -> Optional[float]:
    """Negative binomial P(hit) for count processes.

    Uses mean/var method-of-moments:
      r = mean^2 / (var - mean)
      p = r / (r + mean)

    Returns percent in [0, 100].
    """
    try:
        mu = float(mean)
        vv = float(var)
        if not np.isfinite(mu) or not np.isfinite(vv) or mu <= 0.0:
            return None
        if vv <= mu:
            return None

        r = (mu * mu) / (vv - mu)
        if not np.isfinite(r) or r <= 0.0:
            return None
        # Cap r to keep scipy stable in extreme near-Poisson cases.
        r = float(min(r, 1_000_000.0))
        p = r / (r + mu)
        p = float(max(1e-9, min(1.0 - 1e-9, p)))

        # Convert fractional line to an integer threshold.
        line_f = float(line)
        if str(direction).lower() == "higher":
            # P(X > line) = 1 - CDF(floor(line))
            k = int(np.floor(line_f))
            cdf = float(nbinom.cdf(k, r, p))
            out = 1.0 - cdf
        else:
            # P(X < line) = P(X <= ceil(line)-1)
            k = int(np.ceil(line_f) - 1)
            cdf = float(nbinom.cdf(k, r, p))
            out = cdf

        out = float(max(0.0, min(1.0, out)))
        return float(out * 100.0)
    except Exception:
        return None


def _minutes_shrink(prob_percent: float, minutes_cv: float) -> float:
    """Shrink probability toward 50% when minutes volatility is high.

    This is the empirical analogue of sigma inflation: it reduces overconfidence
    without inventing signal.
    """
    try:
        p = float(prob_percent)
        cv = float(minutes_cv)
        if not np.isfinite(p) or not np.isfinite(cv) or cv <= 0.0:
            return p
        # Multiplier >= 1, capped to avoid extreme damping.
        mult = 1.0 + min(cv, 1.0)
        return float(50.0 + (p - 50.0) / mult)
    except Exception:
        return float(prob_percent)


def analyze_prop_with_gates(
    prop: dict,
    verbose: bool = False,
    game_context: Optional[dict] = None,
    hq_options: Optional[HQOptions] = None,
) -> dict:
    """
    Analyze single prop through risk-first pipeline
    
    Expected prop format:
    {
        "player": str,
        "team": str,
        "stat": str,
        "line": float,
        "direction": str
    }
    """
    # Options are clamps only (HQ Quant): never bypass gates.
    opts = hq_options if isinstance(hq_options, HQOptions) else load_hq_options_from_env()

    player = prop["player"]
    team = prop.get("team", "UNK")
    stat = prop["stat"]
    line = prop["line"]
    direction = prop["direction"]

    player_override = _player_override_for(player, opts) or PlayerOverride()
    
    # ===============================================================
    # SOP v2.1: Initialize Quant Framework Variables
    # ===============================================================
    quant_projection_used = False
    multi_window_data = None
    variance_penalty_applied = False
    variance_penalty_data = None
    edge_gate_data = None
    edge_gate_passed = True  # Default to True, will be set by edge gate
    
    # Get opponent (placeholder logic - improve with real matchup data)
    opponent = prop.get("opponent", "UNK")
    opponent_def_rank = TEAM_DEF_RANK.get(opponent, 15)
    spread = abs(GAME_SPREADS.get(team, 0.0))
    
    # Get stat parameters
    mu, sigma = get_stat_params(player, stat)
    if mu is None:
        return {
            "player": player,
            "stat": stat,
            "line": line,
            "decision": "SKIP",
            "reason": f"No data for {player} {stat}",
            "gates_passed": False
        }
    
    stat_lower = str(stat).lower()

    # ========== CONTEXT-AWARE ADJUSTMENTS ==========
    # Apply pace and defensive matchup context from nba_team_context.py
    # CONTROLLED BY: config/penalty_mode.json → context_adjustment
    pace_factor = 1.0
    matchup_factor = 1.0
    context_notes = []
    
    if PENALTY_MODE.get("context_adjustment", True):
        try:
            if opponent and opponent != "UNK":
                # Pace adjustment (fast matchup = higher counting stats)
                pace_factor = get_pace_adjustment(team, opponent)
                if abs(pace_factor - 1.0) > 0.02:
                    pct = (pace_factor - 1.0) * 100
                    context_notes.append(f"Pace: {'+' if pct > 0 else ''}{pct:.1f}%")
                
                # Defensive matchup adjustment (weak D = higher stats)
                matchup_factor = get_defensive_matchup_factor(opponent, stat_lower)
                if abs(matchup_factor - 1.0) > 0.02:
                    pct = (matchup_factor - 1.0) * 100
                    context_notes.append(f"Matchup: {'+' if pct > 0 else ''}{pct:.1f}%")
                
                # Check for elite/weak defense flags
                if is_elite_defense(opponent):
                    context_notes.append(f"WARN vs Elite D (#{TEAM_DEF_RANK.get(opponent, 15)})")
                elif is_weak_defense(opponent):
                    context_notes.append(f"OK vs Weak D (#{TEAM_DEF_RANK.get(opponent, 15)})")
        except Exception:
            pace_factor = 1.0
            matchup_factor = 1.0
    
    # Combined context factor (pace × matchup)
    context_factor = pace_factor * matchup_factor
    # Cap total context adjustment to ±12%
    context_factor = max(0.88, min(1.12, context_factor))

    # Optional opponent defensive scalar hook (default no-op).
    defense_factor = 1.0
    try:
        ctx = game_context or {}
        df_map = ctx.get("defense_factors") if isinstance(ctx, dict) else None
        if isinstance(df_map, dict):
            opp_map = df_map.get(opponent)
            if isinstance(opp_map, dict):
                raw = opp_map.get(stat_lower)
                if isinstance(raw, (int, float)) and float(raw) > 0.0:
                    defense_factor = float(raw)
    except Exception:
        defense_factor = 1.0

    # Cap defense factor to avoid overfitting/overshooting.
    defense_factor = float(max(0.93, min(1.07, defense_factor)))

    mu_raw = float(mu)
    sigma_raw = float(sigma)
    # Apply both defense_factor (from game_context) and context_factor (from team context)
    combined_factor = defense_factor * context_factor
    combined_factor = float(max(0.85, min(1.15, combined_factor)))  # Cap combined at ±15%
    
    # ========== GAME SITUATION ADJUSTMENTS ==========
    # Apply back-to-back, home/away, rest day factors
    situation_factor = 1.0
    situation_notes = []
    
    if HAS_SITUATION_CONTEXT:
        try:
            situation = get_game_situation(team)
            if situation:
                situation_factor, situation_notes = get_situation_adjustment(stat, situation)
                # Add situation notes to context notes
                context_notes.extend(situation_notes)
        except Exception:
            pass  # Silently skip if situation data unavailable
    
    # Apply all factors: defense × context × situation
    total_factor = combined_factor * situation_factor
    total_factor = float(max(0.82, min(1.18, total_factor)))  # Cap total at ±18%
    
    mu_adj = float(mu_raw * total_factor)

    # ==========================================================================
    # GAME MARKET CONTEXT (Spread / Total / Implied Team Total)
    # ==========================================================================
    # Uses core/game_context.py for cross-sport blowout, pace, game script signals.
    game_impact_data = {}
    try:
        from core.game_context import GameContext, analyze_game_impact

        _gc_spread = None
        _gc_total = None
        _gc_is_home = True

        # Get spread/total from game_context dict if passed in
        _gc_ctx = game_context or {}
        if isinstance(_gc_ctx, dict):
            _gc_spread = _gc_ctx.get("spread")
            _gc_total = _gc_ctx.get("total")
            _gc_is_home = _gc_ctx.get("is_home", True)

        # Fallback to stale GAME_SPREADS if no live data
        if _gc_spread is None:
            _stale = GAME_SPREADS.get(team)
            if _stale is not None:
                _gc_spread = _stale
                _gc_is_home = True  # stale dict doesn't track H/A

        if _gc_spread is not None or _gc_total is not None:
            _gc = GameContext(
                spread=_gc_spread,
                total=_gc_total,
                player_team=team,
                opponent=opponent,
                is_home=_gc_is_home,
                sport="NBA",
            )
            _gi = analyze_game_impact(
                _gc,
                stat=stat_lower,
                direction=direction,
                player_role="STAR" if prop.get("usage_rate", 0) >= 0.22 else "STARTER",
            )

            # Apply lambda multiplier if meaningful
            if _gi.lambda_mult != 1.0:
                mu_adj *= _gi.lambda_mult
                context_notes.append(f"GameMkt: x{_gi.lambda_mult:.2f}")

            # Store for report rendering
            game_impact_data = {
                "lambda_mult": _gi.lambda_mult,
                "confidence_adj": _gi.confidence_adj,
                "flags": _gi.flags,
                "report_line": _gi.report_line,
                "blowout_tier": _gi.blowout_tier,
                "pace_tier": _gi.pace_tier,
                "implied_team_total": _gi.implied_team_total,
                "should_block": _gi.should_block,
                "block_reason": _gi.block_reason,
            }
    except Exception:
        pass  # Fail open — never crash pipeline for game context

    # ==========================================================================
    # CONTEXTUAL ADJUSTMENTS (LAYER 2: AI EVIDENCE)
    # ==========================================================================
    # Check for lineup changes, injuries → adjust projections
    contextual_reasoning = "no_context"
    try:
        from core.contextual_adjustments import ContextualAdjuster, apply_contextual_adjustment
        
        adjuster = ContextualAdjuster()
        evidence = adjuster.check_and_adjust(
            player=player,
            team=team_abbrev,
            opponent=opponent_abbrev,
            stat=stat_lower,
            mu=mu_adj,
            sigma=sigma_raw
        )
        
        if evidence:
            mu_adj, sigma_raw, contextual_reasoning = apply_contextual_adjustment(
                mu=mu_adj,
                sigma=sigma_raw,
                evidence=evidence
            )
            context_notes.append(f"🔄 Context: {contextual_reasoning}")
            
    except Exception as e:
        # Fail gracefully if contextual adjustments unavailable
        pass

    # ==========================================================================
    # SOP v2.1: MULTI-WINDOW WEIGHTED PROJECTION
    # ==========================================================================
    # If we have game log data, use weighted multi-window projection instead
    # of single L10 average. Weights: L3=10%, L5=25%, L10=30%, L20=20%, Season=15%
    quant_projection_used = False
    multi_window_data = {}
    
    if HAS_QUANT_FRAMEWORK:
        try:
            # Get game log from series cache
            game_log = _LAST_SERIES_MAP.get((player, stat_lower))
            if isinstance(game_log, list) and len(game_log) >= 5:
                engine = MultiWindowProjectionEngine()
                mw_result = engine.calculate_projection(
                    player_id=player,
                    player_name=player,
                    stat_type=stat_lower,
                    game_log=game_log,
                    line=float(line)
                )
                
                # Use multi-window projection if we have enough data
                if mw_result.total_weight >= 0.5:  # At least 50% of windows valid
                    # Apply context factors to multi-window projection
                    mu_adj = float(mw_result.weighted_projection * total_factor)
                    sigma_raw = float(mw_result.combined_std_dev)
                    quant_projection_used = True
                    
                    # Store multi-window data for output
                    multi_window_data = {
                        "L3": round(mw_result.windows.get("L3").average, 1) if mw_result.windows.get("L3") and mw_result.windows.get("L3").is_valid else None,
                        "L5": round(mw_result.windows.get("L5").average, 1) if mw_result.windows.get("L5") and mw_result.windows.get("L5").is_valid else None,
                        "L10": round(mw_result.windows.get("L10").average, 1) if mw_result.windows.get("L10") and mw_result.windows.get("L10").is_valid else None,
                        "L20": round(mw_result.windows.get("L20").average, 1) if mw_result.windows.get("L20") and mw_result.windows.get("L20").is_valid else None,
                        "season": round(mw_result.windows.get("season").average, 1) if mw_result.windows.get("season") and mw_result.windows.get("season").is_valid else None,
                        "weighted_projection": round(mw_result.weighted_projection, 2),
                        "weights_used": {k: round(v, 2) for k, v in mw_result.weights_used.items()},
                        "z_score_vs_line": round(mw_result.z_score, 2),
                    }
                    context_notes.append(f"📊 Multi-window projection: {mw_result.weighted_projection:.1f}")
        except Exception as e:
            # Fall back to single-window if multi-window fails
            pass

    # Minutes uncertainty -> sigma inflation (normal) / shrink (empirical)
    minutes_cv = 0.0
    try:
        cv = _LAST_MINUTES_CV.get(player)
        if isinstance(cv, (int, float)):
            minutes_cv = float(max(0.0, cv))
    except Exception:
        minutes_cv = 0.0

    # Base sigma before any policy adjustments.
    sigma_eff_base = float(max(0.75, sigma_raw))

    # Probability method selection (deterministic by default)
    prob_method = os.getenv("RISK_PROB_METHOD", "auto").strip().lower()

    # Try empirical from cached recent values first (if available)
    series = None
    try:
        s = _LAST_SERIES_MAP.get((player, stat_lower))
        if isinstance(s, list) and s:
            # Apply opponent factor by scaling the observed values (small capped scalar).
            series = [float(x) * defense_factor for x in s if isinstance(x, (int, float))]
    except Exception:
        series = None

    # OPTION: Injury return clamp (HQ Quant). Clamp only; same engine.
    inj = opts.injury_return
    injury_return = False
    injury_return_stat_policy = False
    stat_window_n = None

    try:
        if inj.enabled and isinstance(player, str) and player.strip() in {p.strip() for p in (inj.players or [])}:
            injury_return = True
    except Exception:
        injury_return = False

    if injury_return:
        try:
            if isinstance(series, list) and series and str(inj.stat_window).lower() == "last_5":
                series = series[:5]
                stat_window_n = len(series)
                if stat_window_n and stat_window_n >= 1:
                    mu_adj = float(np.mean(series)) * float(inj.projection_multiplier)
                    # ddof=1 for n>1 to avoid sigma=0 from singleton
                    ddof = 1 if stat_window_n > 1 else 0
                    s_std = float(np.std(series, ddof=ddof))
                    sigma_eff_base = float(max(0.75, s_std * 1.10))
                    injury_return_stat_policy = True
            else:
                # No series: still apply conservative penalties to existing params.
                mu_adj = float(mu_adj) * float(inj.projection_multiplier)
                sigma_eff_base = float(max(0.75, sigma_eff_base * 1.10))
                injury_return_stat_policy = True
        except Exception:
            injury_return_stat_policy = False

    # Minutes uncertainty -> sigma inflation (normal) / shrink (empirical)
    # NOTE: Cap minutes-driven sigma inflation to +25% to avoid over-penalizing volatility.
    sigma_eff = float(max(0.75, sigma_eff_base * (1.0 + min(minutes_cv, 0.25))))

    model_confidence = None
    used_method = ""
    sample_n = 0

    prob_details: dict = {
        "requested": prob_method,
    }

    has_series = isinstance(series, list) and bool(series)
    series_mean = None
    series_var = None
    if has_series:
        try:
            sample_n = len(series)
            series_mean = float(np.mean(series))
            ddof = 1 if sample_n > 1 else 0
            series_var = float(np.var(series, ddof=ddof))
        except Exception:
            series_mean = None
            series_var = None

    stat_is_count = str(stat_lower) in COUNT_STATS

    def _set_empirical_base() -> tuple[Optional[float], Optional[float]]:
        """Returns (p_emp_percent, avg_margin_dir)."""
        if not has_series:
            return None, None
        p_emp = _empirical_prob_from_series(series, float(line), direction)
        if not isinstance(p_emp, (int, float)):
            return None, None
        try:
            if str(direction).lower() == "higher":
                avg_margin = float(series_mean) - float(line)
            else:
                avg_margin = float(line) - float(series_mean)
        except Exception:
            avg_margin = 0.0
        return float(p_emp), float(avg_margin)

    # -------------------------------
    # Probability method selection
    # -------------------------------
    req = str(prob_method).lower().strip()

    # Auto router (disciplined, deterministic, fail-soft)
    if req == "auto":
        if has_series and sample_n > 0:
            p_emp, avg_margin_dir = _set_empirical_base()
            if p_emp is not None:
                prob_details["empirical_hit_rate"] = round(float(p_emp), 3)
                prob_details["sample_n"] = int(sample_n)
                prob_details["avg_margin_dir"] = round(float(avg_margin_dir), 3)
                prob_details["series_mean"] = round(float(series_mean), 3) if isinstance(series_mean, (int, float)) else None
                prob_details["series_var"] = round(float(series_var), 3) if isinstance(series_var, (int, float)) else None

                # Count-stat specialist (only when dispersion is clearly present and sample is decent)
                if _should_use_negbin_for_stat(
                    stat_lower=stat_lower,
                    has_series=has_series,
                    sample_n=sample_n,
                    series_mean=series_mean,
                    series_var=series_var,
                    mu_adj=mu_adj,
                    sigma_eff=sigma_eff,
                ):
                    p_nb = _negbin_probability_percent(mean=float(series_mean), var=float(series_var), line=float(line), direction=direction)
                    if isinstance(p_nb, (int, float)):
                        model_confidence = _minutes_shrink(float(p_nb), minutes_cv)
                        used_method = "negbin"
                        prob_details["negbin_mean"] = round(float(series_mean), 3)
                        prob_details["negbin_var"] = round(float(series_var), 3)

                # Default empirical stack
                if model_confidence is None:
                    if sample_n >= 10:
                        p_h = _empirical_hybrid_percent(
                            float(p_emp),
                            avg_margin_dir=float(avg_margin_dir),
                            scale_sigma=float(max(1.0, sigma_eff)),
                        )
                        model_confidence = _minutes_shrink(float(p_h), minutes_cv)
                        used_method = "empirical_hybrid"
                        prob_details["hybrid_used"] = True
                    else:
                        ph = float(p_emp) / 100.0
                        p_w = _wilson_lower_bound(ph, int(sample_n), z=1.28)
                        if p_w is not None:
                            model_confidence = _minutes_shrink(float(p_w * 100.0), minutes_cv)
                            used_method = "wilson_empirical"
                            prob_details["wilson_z"] = 1.28
        else:
            # No series: allow count-stat specialist from (mu, sigma) only when variance meaningfully exceeds mean.
            if _should_use_negbin_for_stat(
                stat_lower=stat_lower,
                has_series=False,
                sample_n=0,
                series_mean=None,
                series_var=None,
                mu_adj=mu_adj,
                sigma_eff=sigma_eff,
            ):
                p_nb = _negbin_probability_percent(mean=float(mu_adj), var=float(sigma_eff) ** 2, line=float(line), direction=direction)
                if isinstance(p_nb, (int, float)):
                    model_confidence = float(p_nb)
                    used_method = "negbin"
                    prob_details["negbin_mean"] = round(float(mu_adj), 3)
                    prob_details["negbin_var"] = round(float(sigma_eff) ** 2, 3)

    elif req == "empirical":
        if has_series and sample_n > 0:
            p_emp, _ = _set_empirical_base()
            if p_emp is not None:
                model_confidence = _minutes_shrink(float(p_emp), minutes_cv)
                used_method = "empirical"
                prob_details["empirical_hit_rate"] = round(float(p_emp), 3)
                prob_details["sample_n"] = int(sample_n)

    elif req == "empirical_hybrid":
        if has_series and sample_n > 0:
            p_emp, avg_margin_dir = _set_empirical_base()
            if p_emp is not None:
                p_h = _empirical_hybrid_percent(
                    float(p_emp),
                    avg_margin_dir=float(avg_margin_dir),
                    scale_sigma=float(max(1.0, sigma_eff)),
                )
                model_confidence = _minutes_shrink(float(p_h), minutes_cv)
                used_method = "empirical_hybrid"
                prob_details["empirical_hit_rate"] = round(float(p_emp), 3)
                prob_details["avg_margin_dir"] = round(float(avg_margin_dir), 3)
                prob_details["sample_n"] = int(sample_n)

    elif req == "wilson_empirical":
        if has_series and sample_n > 0:
            p_emp, _ = _set_empirical_base()
            if p_emp is not None:
                p_w = _wilson_lower_bound(float(p_emp) / 100.0, int(sample_n), z=1.28)
                if p_w is not None:
                    model_confidence = _minutes_shrink(float(p_w * 100.0), minutes_cv)
                    used_method = "wilson_empirical"
                    prob_details["empirical_hit_rate"] = round(float(p_emp), 3)
                    prob_details["wilson_z"] = 1.28
                    prob_details["sample_n"] = int(sample_n)

    elif req == "negbin":
        # If we have a series, prefer series moments; else fall back to (mu, sigma).
        if _should_use_negbin_for_stat(
            stat_lower=stat_lower,
            has_series=has_series,
            sample_n=sample_n,
            series_mean=series_mean,
            series_var=series_var,
            mu_adj=mu_adj,
            sigma_eff=sigma_eff,
        ):
            if has_series and sample_n >= 10 and isinstance(series_mean, (int, float)) and isinstance(series_var, (int, float)):
                p_nb = _negbin_probability_percent(mean=float(series_mean), var=float(series_var), line=float(line), direction=direction)
                if isinstance(p_nb, (int, float)):
                    model_confidence = _minutes_shrink(float(p_nb), minutes_cv)
                    used_method = "negbin"
                    prob_details["negbin_mean"] = round(float(series_mean), 3)
                    prob_details["negbin_var"] = round(float(series_var), 3)
                    prob_details["sample_n"] = int(sample_n)
            if model_confidence is None:
                p_nb = _negbin_probability_percent(mean=float(mu_adj), var=float(sigma_eff) ** 2, line=float(line), direction=direction)
                if isinstance(p_nb, (int, float)):
                    model_confidence = float(p_nb)
                    used_method = "negbin"
                    prob_details["negbin_mean"] = round(float(mu_adj), 3)
                    prob_details["negbin_var"] = round(float(sigma_eff) ** 2, 3)

    if model_confidence is None:
        # Deterministic fallback: Normal CDF with sigma inflation
        model_confidence = bayesian_prob(mu_adj, sigma_eff, float(line), direction)
        used_method = "normal_cdf"

    # Optional Oracle integration: allow external ensemble to supply probability.
    # This only activates when USE_ORACLE_PROB=1 and the prop carries an
    # oracle_prob field, and never fails hard.
    try:
        model_confidence = _maybe_apply_oracle_probability(prop, model_confidence, prob_details)
    except Exception:
        pass

    # Bootstrap confidence bands (deterministic) as a conservative guardrail.
    # This is NOT a new probability model; it just caps overconfidence when the empirical band is wide.
    # CONTROLLED BY: config/penalty_mode.json → bootstrap_guard
    bootstrap_band = None
    bootstrap_guard_factor = 1.0
    if has_series and sample_n >= 6 and PENALTY_MODE.get("bootstrap_guard", True):
        try:
            seed = _deterministic_seed(player, stat_lower, line, direction, round(defense_factor, 4))
            bootstrap_band = _bootstrap_bands_percent(series, float(line), direction, seed=seed)
            if isinstance(bootstrap_band, dict):
                w = float(bootstrap_band.get("width", 0.0) or 0.0)
                if w >= 35.0:
                    bootstrap_guard_factor = 0.60
                elif w >= 25.0:
                    bootstrap_guard_factor = 0.75

                if bootstrap_guard_factor < 1.0:
                    p0 = float(model_confidence)
                    model_confidence = float(50.0 + (p0 - 50.0) * bootstrap_guard_factor)
        except Exception:
            bootstrap_band = None
            bootstrap_guard_factor = 1.0

    if isinstance(bootstrap_band, dict):
        prob_details["bootstrap_band"] = bootstrap_band
        if bootstrap_guard_factor < 1.0:
            prob_details["bootstrap_guard_factor"] = round(float(bootstrap_guard_factor), 3)

    # HQ Quant clamps: never increase confidence.
    if injury_return:
        try:
            model_confidence = _cap_percent_no_increase(float(model_confidence), cap_percent=float(inj.max_probability) * 100.0)
        except Exception:
            pass

    if player_override.max_probability is not None:
        try:
            model_confidence = _cap_percent_no_increase(
                float(model_confidence),
                cap_percent=float(player_override.max_probability) * 100.0,
            )
        except Exception:
            pass
    
    # ==========================================================================
    # SOP v2.1: VARIANCE PENALTY (CV-based confidence reduction)
    # ==========================================================================
    # High variance players get penalized: CV > 0.35 = -10%, CV > 0.25 = -5%
    # CONTROLLED BY: config/penalty_mode.json → variance_penalty
    variance_penalty_data = {}
    variance_penalty_applied = False
    
    if HAS_QUANT_FRAMEWORK and sigma_eff > 0 and mu_adj > 0 and PENALTY_MODE.get("variance_penalty", True):
        try:
            cv = calculate_cv(sigma_eff, mu_adj)
            variance_result = apply_variance_penalty(
                confidence=model_confidence / 100.0,  # Convert to 0-1
                std_dev=sigma_eff,
                mean=mu_adj,
                sample_size=sample_n
            )
            
            if variance_result.total_penalty < 1.0:
                # Apply the penalty
                old_confidence = float(model_confidence)
                # Clamp total confidence drop from variance penalty to a maximum of 20%
                adjusted_confidence = float(variance_result.adjusted_confidence * 100.0)
                min_allowed = float(max(0.0, old_confidence * 0.80))
                model_confidence = float(max(min_allowed, adjusted_confidence))
                variance_penalty_applied = True
                
                variance_penalty_data = {
                    "cv": round(cv, 3),
                    "cv_category": variance_result.cv_category,
                    "cv_penalty": round(variance_result.cv_penalty, 3),
                    "sample_penalty": round(variance_result.sample_penalty, 3),
                    "total_penalty": round(variance_result.total_penalty, 3),
                    "confidence_before": round(old_confidence, 1),
                    "confidence_after": round(model_confidence, 1),
                }
                
                if variance_result.is_high_variance:
                    context_notes.append(f"WARN High variance (CV={cv:.2f}): -{(1-variance_result.cv_penalty)*100:.0f}% penalty")
        except Exception as e:
            pass  # Silently skip if variance penalty fails
    
    # CALCULATE EDGE (value indicator)
    if direction.lower() == "higher":
        edge = mu_adj - line  # Positive = good (avg above line)
    else:
        edge = line - mu_adj  # Positive = good (avg below line)
    
    z_score = edge / sigma_eff  # Standard deviations of edge (minutes uncertainty-aware)
    
    # Edge quality categories
    if abs(z_score) >= 1.0:
        edge_quality = "ELITE"  # 1+ SD edge
    elif abs(z_score) >= 0.5:
        edge_quality = "STRONG"  # 0.5-1 SD edge
    elif abs(z_score) >= 0.25:
        edge_quality = "MODERATE"  # 0.25-0.5 SD edge
    else:
        edge_quality = "THIN"  # <0.25 SD edge
    
    # ==========================================================================
    # SOP v2.1: EDGE THRESHOLD GATE (3% minimum edge requirement)
    # ==========================================================================
    # No matter how high confidence, if edge < 3%, reject the play
    # CONTROLLED BY: config/penalty_mode.json → edge_gate
    edge_gate_data = {}
    edge_gate_passed = True
    
    if HAS_QUANT_FRAMEWORK and PENALTY_MODE.get("edge_gate", True):
        try:
            edge_gate_result = check_edge_gate(
                confidence=model_confidence / 100.0,  # Convert to 0-1
                odds=-110  # Standard assumption
            )
            
            edge_gate_data = {
                "edge_percent": round(edge_gate_result.edge_percent, 2),
                "required_edge": round(edge_gate_result.required_edge * 100, 1),
                "passes_gate": edge_gate_result.passes_gate,
                "tier_recommendation": edge_gate_result.tier_recommendation,
                "ev_percent": round(edge_gate_result.ev_percent, 2),
            }
            
            if not edge_gate_result.passes_gate:
                edge_gate_passed = False
                context_notes.append(f"BLOCK Edge gate FAIL: {edge_gate_result.edge_percent:.1f}% < 3% min")
        except Exception as e:
            pass  # Silently skip if edge gate fails
    
    # ==========================================================================
    # HYBRID CONFIDENCE SYSTEM (Data-Driven) 2026-01-29
    # ==========================================================================
    # This uses empirically-validated adjustments from 97 historical picks
    # CONTROLLED BY: config/penalty_mode.json → use_hybrid_confidence
    hybrid_data = {}
    hybrid_tier = None
    
    if HAS_HYBRID_CONFIDENCE and PENALTY_MODE.get("use_hybrid_confidence", True):
        try:
            # Normalize stat for hybrid system
            stat_normalized = stat.lower().replace(" ", "_")
            
            hybrid_result = calculate_hybrid_confidence(
                mu=mu_adj,
                sigma=sigma_eff if sigma_eff > 0 else mu_adj * 0.25,
                line=float(line),
                n_games=sample_n,
                stat=stat_normalized,
                direction=direction.lower(),
                verbose=False
            )
            
            hybrid_data = {
                "raw_probability": hybrid_result.get("raw_probability"),
                "effective_probability": hybrid_result.get("effective_probability"),
                "raw_edge": hybrid_result.get("raw_edge"),
                "effective_edge": hybrid_result.get("effective_edge"),
                "stat_direction_multiplier": hybrid_result.get("stat_direction_multiplier"),
                "sample_size_multiplier": hybrid_result.get("sample_size_multiplier"),
                "tier": hybrid_result.get("tier"),
                "decision": hybrid_result.get("decision"),
            }
            
            hybrid_tier = hybrid_result.get("tier")
            
            # If hybrid says VETO, respect it
            if hybrid_tier == "VETO":
                reason = hybrid_result.get("reason", "Data-driven VETO")
                context_notes.append(f"🚫 Hybrid VETO: {reason}")
            # If hybrid has a tier recommendation, log it
            elif hybrid_tier in ["SLAM", "STRONG", "LEAN"]:
                eff_edge = hybrid_result.get("effective_edge", 0)
                context_notes.append(f"📊 Hybrid: {hybrid_tier} (edge: {eff_edge:.1f}%)")
        except Exception as e:
            pass  # Silently skip if hybrid fails

    # ========== CONFIG-BASED KELLY EDGE ==========
    kelly_metrics = {}
    if HAS_PROBABILITY_BLENDER:
        try:
            kelly_metrics = calculate_kelly_edge(model_confidence / 100.0)
        except Exception:
            pass
    
    # ==========================================================================
    # STAT DEVIATION GATE (SDG) — GATE_0: Coin Flip Detection
    # Penalizes picks where line ≈ player's mean (star-tax traps)
    # MUST run BEFORE other gates to identify market-priced-at-expectation bets
    # ==========================================================================
    sdg_result = None
    sdg_multiplier = 1.0
    sdg_penalty_applied = False
    
    if HAS_STAT_DEVIATION_GATE and mu_adj is not None and sigma_eff is not None and sigma_eff > 0:
        try:
            sdg_mult, sdg_desc, sdg_details = stat_deviation_gate(
                mu_context=float(mu_adj),
                sigma=float(sigma_eff),
                expected=float(line),  # Use line as the expected value
                stat=stat,
                mode="soft"  # Use soft mode for analysis (penalties, not rejection)
            )
            sdg_result = {
                "z_stat": sdg_details.get("z_stat", 0.0),
                "multiplier": sdg_mult,
                "description": sdg_desc,
                "penalty_level": sdg_details.get("penalty", "PASS"),  # Get actual penalty level
                "mu": float(mu_adj),
                "sigma": float(sigma_eff),
                "line": float(line),
            }
            
            # Apply SDG penalty to model_confidence
            if sdg_mult < 1.0:
                original_conf = model_confidence
                model_confidence = model_confidence * sdg_mult
                sdg_multiplier = sdg_mult
                sdg_penalty_applied = True
                sdg_result["original_confidence"] = original_conf
                sdg_result["adjusted_confidence"] = model_confidence
                
                if verbose:
                    print(f"\n[SDG] {player} {stat}: z={sdg_result['z_stat']:.2f}, mult={sdg_mult:.2f} -> {original_conf:.1f}% -> {model_confidence:.1f}%")
        except Exception as e:
            if verbose:
                print(f"[SDG] Warning: SDG failed for {player} {stat}: {e}")
    
    # ========== CONFIG-BASED GATE SYSTEM ==========
    # Load analysis config for gate system and penalty severity
    soft_gates_enabled = os.getenv("SOFTGATES", "0").strip() == "1"
    penalty_severity = "medium"
    
    if HAS_ANALYSIS_CONFIG:
        try:
            analysis_config = get_active_config()
            # Override soft gates from config
            soft_gates_enabled = analysis_config.is_soft_gates()
            penalty_severity = analysis_config.penalty_severity
            # Apply config-based environment for downstream compatibility
            os.environ["GATE_SYSTEM"] = analysis_config.gate_system
            os.environ["PENALTY_SEVERITY"] = penalty_severity
        except Exception:
            pass
    
    gate_result = run_all_gates(
        player=player,
        stat=stat,
        opponent_def_rank=opponent_def_rank,
        spread=spread,
        model_confidence=model_confidence,
        soft_gates=soft_gates_enabled
    )
    
    # RUN CONTEXT GATES (coaching, rest, injuries)
    context_result = run_context_gates(
        player=player,
        team=team,
        opponent=opponent,
        stat=stat,
        game_context=game_context or {},
    )
    
    # HARD BLOCK if context gates fail
    if not context_result["all_clear"]:
        if verbose:
            print(f"\nCONTEXT BLOCK: {player}")
            for block in context_result["hard_blocks"]:
                print(f"   {block}")
        
        return {
            "player": player,
            "stat": stat,
            "line": line,
            "decision": "BLOCKED",
            "block_reason": context_result["hard_blocks"][0] if context_result["hard_blocks"] else "Context gate failure",
            "gates_passed": False,
            "context_warnings": context_result["warnings"],
            # Keep model_confidence visibility even when context blocks.
            "model_confidence": model_confidence,
            "effective_confidence": 0.0,
        }
    
    if verbose:
        print_gate_results(player, stat, gate_result)
        if context_result["warnings"]:
            print("CONTEXT WARNINGS:")
            for warning in context_result["warnings"]:
                print(f"   {warning}")
    
    # Build result
    result = {
        "player": player,
        "team": team,
        "opponent": opponent,
        "stat": stat,
        "line": line,
        "direction": direction,
        "mu": mu_adj,
        "sigma": sigma_eff,
        "mu_raw": mu_raw,
        "sigma_raw": sigma_raw,
        "defense_factor": defense_factor,
        "context_factor": context_factor,
        "pace_factor": pace_factor,
        "matchup_factor": matchup_factor,
        "situation_factor": situation_factor,
        "situation_notes": situation_notes,
        "context_notes": context_notes,
        "minutes_cv": minutes_cv,
        "sample_n": sample_n,
        "stat_window_n": stat_window_n,
        "injury_return": injury_return,
        "injury_return_stat_policy": injury_return_stat_policy,
        # Backward-compatible alias (older reports/readers may look for this key).
        "early_return_stat_policy": injury_return_stat_policy,
        "prob_method": used_method,
        "prob_method_details": prob_details,
        "edge": edge,
        "z_score": z_score,
        "edge_quality": edge_quality,
        "kelly_metrics": kelly_metrics,  # Kelly criterion edge data
        "model_confidence": model_confidence,
        "effective_confidence": gate_result["effective_confidence"],
        "decision": gate_result["decision"],
        "gates_passed": gate_result["passed"],
        "gate_details": gate_result["gate_results"],
        "context_warnings": context_result["warnings"],
        # ===============================================================
        # SOP v2.1: Professional Quant Framework Data
        # ===============================================================
        "quant_framework": {
            "enabled": HAS_QUANT_FRAMEWORK,
            "multi_window_projection": multi_window_data if quant_projection_used else None,
            "variance_penalty": variance_penalty_data if variance_penalty_applied else None,
            "edge_gate": edge_gate_data if edge_gate_data else None,
            "edge_gate_passed": edge_gate_passed,
        },
        # ===============================================================
        # HYBRID CONFIDENCE SYSTEM (Data-Driven) 2026-01-29
        # ===============================================================
        "hybrid_confidence": hybrid_data if hybrid_data else None,
        "hybrid_tier": hybrid_tier,
        # ===============================================================
        # STAT DEVIATION GATE (SDG) — Coin Flip Detection 2026-02-01
        # ===============================================================
        "sdg_result": sdg_result,
        "sdg_multiplier": sdg_multiplier,
        "sdg_penalty_applied": sdg_penalty_applied,
        # ===============================================================
        # GAME MARKET CONTEXT (Spread / Total / Blowout / Pace)
        # ===============================================================
        "game_impact": game_impact_data,
    }

    # Preserve upstream slate metadata when present (OddsAPI + validated parquet passthrough).
    # This enables reporting and telegram diversity checks even when team/opponent is unknown.
    for k in (
        "sport",
        "platform",
        "event_id",
        "commence_time",
        "home_team",
        "away_team",
        "matchup_home",
        "matchup_away",
        "bookmaker_key",
        "market_key",
        "source",
    ):
        try:
            if isinstance(prop, dict) and prop.get(k) is not None and k not in result:
                result[k] = prop.get(k)
        except Exception:
            pass
    
    # Add NBA Role Layer fields if present in prop
    if prop.get("nba_role_archetype"):
        result["nba_role_archetype"] = prop["nba_role_archetype"]
        result["nba_confidence_cap_adjustment"] = prop["nba_confidence_cap_adjustment"]
        result["nba_role_flags"] = prop["nba_role_flags"]
        result["nba_role_metadata"] = prop["nba_role_metadata"]
    if prop.get("nba_specialist_flags"):
        result["nba_specialist_flags"] = prop["nba_specialist_flags"]
    if prop.get("nba_stat_averages"):
        result["nba_stat_averages"] = prop["nba_stat_averages"]
    
    # Add SDG context warning if penalty was applied
    if sdg_penalty_applied and sdg_result:
        z_val = sdg_result.get("z_stat", 0)
        penalty_level = sdg_result.get("penalty_level", "UNKNOWN")
        result["context_warnings"].append(f"WARN SDG: {penalty_level} penalty (z={z_val:.2f}, line~=mu)")
    
    analysis_config = get_active_config()
    adj_conf, meets_edge, stat_info = analysis_config.apply_stat_adjustment(
        stat=stat,
        confidence=gate_result["effective_confidence"],
        z_score=z_score
    )
    
    # Store adjustment info
    result["stat_adjustment"] = stat_info
    result["effective_confidence"] = adj_conf
    
    # =================================================================
    # DATA-DRIVEN PENALTIES (from 97-pick calibration analysis)
    # CONTROLLED BY: config/penalty_mode.json → use_data_driven_penalties
    # =================================================================
    if HAS_DATA_DRIVEN_PENALTIES and PENALTY_MODE.get("use_data_driven_penalties", False):
        data_driven_adjustments = {}
        
        # Use unified multiplier (stat+direction combo > base+direction fallback)
        stat_lower = stat.lower().replace(" ", "_").replace("-", "_")
        dir_lower = direction.lower()
        unified_mult = get_data_driven_multiplier(stat_lower, dir_lower, "nba")
        if unified_mult != 1.0:
            adj_conf_before = adj_conf
            adj_conf = adj_conf * unified_mult
            data_driven_adjustments["stat_direction_multiplier"] = {
                "stat": stat_lower,
                "direction": dir_lower,
                "multiplier": unified_mult,
                "before": adj_conf_before,
                "after": adj_conf
            }
        
        # Apply sample size scaling
        if sample_n and sample_n > 0:
            for threshold, scale in sorted(SAMPLE_SIZE_RULES["confidence_scaling"].items(), reverse=True):
                if sample_n >= threshold:
                    if scale < 1.0:
                        adj_conf_before = adj_conf
                        adj_conf = adj_conf * scale
                        data_driven_adjustments["sample_size_scaling"] = {
                            "n_games": sample_n,
                            "threshold": threshold,
                            "scale": scale,
                            "before": adj_conf_before,
                            "after": adj_conf
                        }
                    break
        
        if data_driven_adjustments:
            result["data_driven_adjustments"] = data_driven_adjustments
            result["effective_confidence"] = adj_conf
            result["context_warnings"].append(f"📊 Data-driven: {', '.join(data_driven_adjustments.keys())}")

    # =================================================================
    # SOP v2.1: Apply Confidence Compression (Rule C1)
    # CONTROLLED BY: config/penalty_mode.json → confidence_compression
    # =================================================================
    if HAS_KELLY and not PENALTY_MODE.get("master_penalties_off", False):
        compressed_conf, was_compressed, compression_reason = apply_confidence_compression(
            confidence=adj_conf / 100.0,  # Convert to 0-1
            projection=float(mu_adj),
            line=float(line),
            std_dev=float(sigma_eff)
        )
        if was_compressed:
            adj_conf = compressed_conf * 100.0  # Convert back to percentage
            result["effective_confidence"] = adj_conf
            result["compression_applied"] = True
            result["compression_reason"] = compression_reason
            result["context_warnings"].append("WARN Confidence compressed: outlier projection")
    
    # =================================================================
    # SOP v2.1: Add Kelly Bet Sizing
    # =================================================================
    if HAS_KELLY:
        tier = result.get("tier_label", result.get("decision", "AVOID"))
        kelly_info = compute_kelly_bet_size(
            confidence=adj_conf / 100.0,  # Convert to 0-1
            tier=tier
        )
        result["kelly_sizing"] = kelly_info
        result["recommended_units"] = kelly_info["recommended_units"]
        result["edge_percent"] = kelly_info["edge_percent"]
    
    # Apply NBA Role Layer confidence cap adjustments
    if prop.get("nba_confidence_cap_adjustment") is not None:
        nba_cap_adjustment = float(prop.get("nba_confidence_cap_adjustment", 0.0))
        if nba_cap_adjustment != 0.0:
            adj_conf += (nba_cap_adjustment / 100.0) * 100.0  # Convert to percentage points
            result["effective_confidence"] = adj_conf
            result["nba_cap_adjustment_applied"] = nba_cap_adjustment

    # =================================================================
    # STAT ROUTING + SPECIALIST GOVERNANCE (SECOND AXIS)
    # CONTROLLED BY: config/penalty_mode.json → specialist_governance
    # =================================================================
    # 3PM routing: weight shot profile, ignore usage/minutes bias.
    # PTS routing: require role + specialist alignment; cap overconfidence.
    # REB/AST routing: do NOT apply scoring-role ceilings.
    if not PENALTY_MODE.get("master_penalties_off", False):
        try:
            # 3PM shot-profile ceiling application (only for 3PM-like stats)
            if HAS_3PM_SHOT_PROFILE_GOVERNOR:
                stat_u = str(stat).upper()
                if stat_u in {"3PM", "3PT", "3PTS", "THREES", "THREE_POINTERS"}:
                    gov = ThreePointGovernor()
                    tmp = {"player": player, "stat": stat_u, "probability": float(adj_conf)}
                    tmp = gov.govern(tmp)
                    if tmp.get("3pm_governed"):
                        result["3pm_governed"] = True
                        result["shot_profile_archetype"] = tmp.get("shot_profile_archetype")
                        result["3pm_confidence_ceiling"] = tmp.get("3pm_confidence_ceiling")
                        result["3pm_original_confidence"] = tmp.get("3pm_original_confidence")
                        result["3pm_governed_confidence"] = tmp.get("3pm_governed_confidence")
                        if isinstance(tmp.get("governed_final_probability"), (int, float)):
                            adj_conf = float(tmp["governed_final_probability"])
                            result["effective_confidence"] = adj_conf

            # Specialist ceiling application (mainly PTS + hard avoids)
            if HAS_STAT_SPECIALISTS:
                specialist_raw = prop.get("nba_stat_specialist_type")
                specialist: StatSpecialistType
                try:
                    specialist = StatSpecialistType(str(specialist_raw))
                except Exception:
                    specialist = StatSpecialistType.GENERIC

                role_u = prop.get("nba_role_archetype")
                new_conf, meta = apply_specialist_confidence_governance(
                    stat=stat,
                    line=line,
                    confidence_percent=float(adj_conf),
                    specialist=specialist,
                    role_archetype=str(role_u) if role_u is not None else None,
                )

                result["nba_stat_specialist_type"] = specialist.value
                result["nba_stat_specialist_governance"] = meta
                # Canonical alias (used by governance/optimizer enforcement).
                result["stat_specialist_type"] = specialist.value

                if isinstance(new_conf, (int, float)) and float(new_conf) < float(adj_conf):
                    adj_conf = float(new_conf)
                    result["effective_confidence"] = adj_conf
                    result["nba_stat_specialist_ceiling_applied"] = True

                # Hard avoid should override any remaining decision.
                if meta.get("hard_avoid"):
                    result["nba_stat_specialist_hard_avoid"] = True
                    reason = meta.get("hard_avoid_reason") or "STAT_SPECIALIST_HARD_AVOID"
                    result["context_warnings"].append(f"BLOCK Specialist rule: {reason}")
                    # Use NO_PLAY rather than BLOCKED to preserve transparency.
                    if result.get("decision") in ("PLAY", "STRONG", "LEAN"):
                        result["decision"] = "NO_PLAY"

                if meta.get("role_alignment_flag"):
                    result["context_warnings"].append(f"WARN Specialist alignment: {meta['role_alignment_flag']}")

            # NEW: Apply stat_specialist_engine cap as a final governance pass (production lock-in)
            if HAS_STAT_SPECIALIST_ENGINE:
                # Build player features dict from prop for classification
                player_features = dict(prop)
                specialist_v2 = classify_stat_specialist(player_features, stat)
                capped_conf, cap_meta = apply_specialist_confidence_cap(
                    float(adj_conf), specialist_v2, use_percent_scale=True
                )
                
                result["stat_specialist_engine"] = specialist_v2.value
                result["stat_specialist_engine_meta"] = cap_meta
                
                if capped_conf < float(adj_conf):
                    adj_conf = capped_conf
                    result["effective_confidence"] = adj_conf
                    result["stat_specialist_engine_capped"] = True
                
                # Check rejection rules
                reject, reject_reason = should_reject_pick(
                    specialist_v2, stat, float(line), capped_conf, use_percent_scale=True
                )
                if reject:
                    result["stat_specialist_rejected"] = True
                    result["stat_specialist_rejection_reason"] = reject_reason
                    result["context_warnings"].append(f"BLOCK Specialist engine: {reject_reason}")
                    if result.get("decision") in ("PLAY", "STRONG", "LEAN"):
                        result["decision"] = "NO_PLAY"
        except Exception:
            pass
    # END OF SPECIALIST GOVERNANCE BLOCK (controlled by master_penalties_off)
    
    # ========== EDGE DIAGNOSTICS (σ-distance, penalty attribution, tier label) ==========
    # Generate comprehensive diagnostic bundle for transparency
    if HAS_EDGE_DIAGNOSTICS:
        try:
            edge_diag = generate_edge_diagnostic(
                line=float(line),
                mu=float(mu_adj),
                sigma=float(sigma_eff),
                direction=direction,
                raw_probability=float(model_confidence),
                final_probability=float(adj_conf),
                stat=stat,
                sport="nba",  # TODO: Make sport-aware
                context_flags={
                    "b2b": situation_factor != 1.0,
                    "injury": injury_return,
                    "context_applied": context_factor != 1.0
                }
            )
            result["edge_diagnostics"] = edge_diag.to_dict()
            result["tier_label"] = edge_diag.tier_label.tier
            result["diagnostic_summary"] = edge_diag.diagnostic_summary
        except Exception:
            pass
    
    # Downgrade decision if doesn't meet stat-specific minimum edge
    if not meets_edge:
        # Stat failed minimum edge threshold - downgrade to LEAN or PASS
        result["stat_edge_block"] = True
        result["context_warnings"].append(
            f"WARN {stat.upper()} requires >={stat_info['min_edge_required']:.1f} sigma edge (got {z_score:.2f} sigma)"
        )
        # Downgrade decision
        if result["decision"] == "PLAY":
            result["decision"] = "LEAN"
        elif result["decision"] == "LEAN":
            result["decision"] = "PASS"
    
    # =================================================================
    # SOP v2.1: Edge Gate Enforcement (3% Minimum Edge)
    # =================================================================
    # If edge gate failed, downgrade decision regardless of other factors
    if not edge_gate_passed and HAS_QUANT_FRAMEWORK:
        result["edge_gate_block"] = True
        if result["decision"] in ("PLAY", "LEAN"):
            result["decision"] = "PASS"
            result["context_warnings"].append(
                f"BLOCK EDGE GATE BLOCK: {edge_gate_data.get('edge_percent', 0):.1f}% edge < 3% minimum required"
            )
    
    if not gate_result["passed"]:
        result["block_reason"] = gate_result["block_reason"]
    
    # =================================================================
    # CALIBRATION FIXER (Final Step - Apply Confidence Compression)
    # CONTROLLED BY: config/penalty_mode.json → use_calibration_fixer
    # =================================================================
    # This is the LAST adjustment to address the 28% calibration error.
    # Applies sigmoid compression + archetype caps + direction bias.
    if HAS_CALIBRATION_FIXER and PENALTY_MODE.get("use_calibration_fixer", True):
        try:
            # Get archetype if available
            archetype = result.get("nba_role_archetype") or prop.get("nba_role_archetype")
            
            # Apply the calibration fix
            calibrated = apply_calibration_fix(
                raw_probability=adj_conf / 100.0,  # Convert to 0-1
                archetype=archetype,
                direction=direction,
                sample_n=sample_n
            )
            
            calibrated_conf = calibrated.adjusted_probability * 100.0  # Convert back to percent
            
            # Only apply if it's a meaningful reduction (avoid noise)
            if abs(calibrated_conf - adj_conf) > 0.5:
                result["calibration_fix"] = {
                    "raw_conf": round(adj_conf, 2),
                    "calibrated_conf": round(calibrated_conf, 2),
                    "archetype": archetype,
                    "direction": direction,
                    "sample_n": sample_n,
                    "sigmoid_pull": round((calibrated.raw_probability - calibrated.sigmoid_compressed) * 100, 2),
                    "archetype_cap_applied": calibrated.archetype_cap is not None,
                    "details": calibrated.details
                }
                adj_conf = calibrated_conf
                result["effective_confidence"] = adj_conf
                result["context_warnings"].append(
                    f"Calibration fix: {result['calibration_fix']['raw_conf']:.1f}%->{calibrated_conf:.1f}%"
                )
        except Exception as e:
            # Silently skip calibration fix on error
            pass

    # =================================================================
    # FINAL DECISION NORMALIZATION (Post-adjustment)
    # =================================================================
    # At this point, adj_conf represents the FINAL effective confidence after:
    # - stat adjustments
    # - data-driven penalties
    # - compression
    # - calibration fix
    # Therefore, ensure:
    #   1) hybrid VETO can never remain actionable
    #   2) decision is consistent with the FINAL effective confidence
    try:
        final_conf = float(adj_conf)
    except Exception:
        final_conf = float(result.get("effective_confidence") or 0.0)

    # 1) Enforce hybrid veto: do not allow PLAY/STRONG/LEAN when hybrid says VETO.
    try:
        if str(result.get("hybrid_tier") or "").upper() == "VETO":
            if result.get("decision") in ("PLAY", "STRONG", "LEAN"):
                result["hybrid_veto_enforced"] = True
                result["decision"] = "NO_PLAY"
                # Keep as a BLOCK-style warning without converting to BLOCKED so analytics remain transparent.
                try:
                    result.setdefault("context_warnings", []).append("BLOCK Hybrid VETO enforced")
                except Exception:
                    pass
    except Exception:
        pass

    # 2) Align decision with final confidence (never upgrade blocked/skip).
    #    HYBRID RECONCILIATION (2026-02-09): When hybrid_confidence identifies
    #    a prop as actionable (LEAN/STRONG/SLAM) but the model_confidence path
    #    crushes it below threshold (due to SDG + compounding penalties), trust
    #    the hybrid system. The hybrid system was calibrated against 97 picks
    #    and applies adjustments to the EDGE (not probability directly).
    try:
        from config.thresholds import implied_tier

        def _tier_to_decision(t: str) -> str:
            tt = str(t or "").upper()
            if tt == "SLAM":
                return "PLAY"
            if tt == "STRONG":
                return "STRONG"
            if tt == "LEAN":
                return "LEAN"
            return "NO_PLAY"

        if result.get("decision") not in ("BLOCKED", "SKIP"):
            tier_final = implied_tier(max(0.0, min(1.0, final_conf / 100.0)), sport="NBA")
            result["tier_label_final"] = tier_final

            # --- HYBRID RECONCILIATION ---
            # If model path says NO_PLAY but hybrid says actionable, use hybrid.
            hybrid_info = result.get("hybrid_confidence") or {}
            hybrid_eff_prob = hybrid_info.get("effective_probability", 0) or 0
            hybrid_tier_val = str(hybrid_info.get("tier") or "").upper()

            if (tier_final in ("AVOID", "NO_PLAY")
                    and hybrid_tier_val in ("LEAN", "STRONG", "SLAM")
                    and hybrid_eff_prob >= 55
                    and not result.get("hybrid_veto_enforced")):
                # Hybrid system overrides — use hybrid effective probability
                hybrid_tier_mapped = implied_tier(
                    max(0.0, min(1.0, hybrid_eff_prob / 100.0)), sport="NBA"
                )
                result["decision"] = _tier_to_decision(hybrid_tier_mapped)
                result["tier_label_final"] = hybrid_tier_mapped
                result["hybrid_override"] = True
                result["hybrid_override_detail"] = (
                    f"model={final_conf:.1f}%→{tier_final} | "
                    f"hybrid={hybrid_eff_prob:.1f}%→{hybrid_tier_mapped} (USED)"
                )
                # Update effective_confidence to reflect hybrid value
                final_conf = hybrid_eff_prob
                result["effective_confidence"] = final_conf
                result["status_confidence"] = final_conf
            elif not result.get("hybrid_veto_enforced"):
                # Normal path — model confidence determines decision
                result["decision"] = _tier_to_decision(tier_final)
    except Exception:
        pass

    # 3) Recompute edge diagnostics using FINAL confidence so tier_label/summary are consistent.
    if HAS_EDGE_DIAGNOSTICS:
        try:
            edge_diag = generate_edge_diagnostic(
                line=float(line),
                mu=float(mu_adj),
                sigma=float(sigma_eff),
                direction=direction,
                raw_probability=float(result.get("model_confidence") or model_confidence),
                final_probability=float(final_conf),
                stat=stat,
                sport="nba",
                context_flags={
                    "b2b": situation_factor != 1.0,
                    "injury": injury_return,
                    "context_applied": context_factor != 1.0,
                },
            )
            result["edge_diagnostics"] = edge_diag.to_dict()
            result["tier_label"] = edge_diag.tier_label.tier
            result["diagnostic_summary"] = edge_diag.diagnostic_summary
        except Exception:
            pass
    
    # Optional detailed breakdown for debugging
    if verbose:
        try:
            print("\n===== PROBABILITY BREAKDOWN =====")
            print(f"Player: {player} | Stat: {stat} | Line: {line} | Dir: {direction}")
            print(f"Raw mu: {mu_raw:.2f}  Raw sigma: {sigma_raw:.2f}")
            print(f"Context×Defense×Situation factor: {total_factor:.3f}  (pace={pace_factor:.3f}, matchup={matchup_factor:.3f}, situation={situation_factor:.3f})")
            print(f"Adj mu: {mu_adj:.2f}  Eff sigma: {sigma_eff:.2f}  (minutes_cv={minutes_cv:.3f})")
            print(f"Method: {used_method}  Model conf (raw): {model_confidence:.1f}%  Effective conf (final): {result['effective_confidence']:.1f}%")
            if variance_penalty_applied and isinstance(variance_penalty_data, dict):
                print(f"Variance penalty: CV={variance_penalty_data.get('cv')}  total_penalty={variance_penalty_data.get('total_penalty')}  before={variance_penalty_data.get('confidence_before')}%  after={variance_penalty_data.get('confidence_after')}%")
            if result.get('edge_diagnostics'):
                ed = result['edge_diagnostics']
                print(f"Edge: {edge:.2f}  z={z_score:.2f} sigma  Tier={result.get('tier_label', 'N/A')}")
            print("==================================\n")
        except Exception:
            pass

    # =========================================================================
    # CALIBRATION TRACKING: Save prediction with lambda for later diagnosis
    # =========================================================================
    try:
        if os.getenv("ENABLE_CALIBRATION_TRACKING", "").strip() == "1":
            from calibration.unified_tracker import UnifiedCalibration, CalibrationPick
            from datetime import datetime
            import uuid
            
            # Only track PLAY decisions that passed gates
            if result.get("decision") in ("PLAY", "STRONG", "LEAN") and result.get("gates_passed"):
                cal = UnifiedCalibration()
                
                # Extract probability chain data
                prob_details = result.get("prob_method_details", {})
                
                pick = CalibrationPick(
                    pick_id=str(uuid.uuid4()),
                    date=datetime.now().isoformat(),
                    sport="NBA",
                    player=player,
                    team=team,
                    opponent=opponent or prop.get("opponent", "UNK"),
                    stat=stat,
                    line=line,
                    direction=direction,
                    probability=result.get("effective_confidence", model_confidence),
                    tier=result.get("tier_label", result.get("decision", "UNKNOWN")),
                    
                    # CRITICAL: Lambda anchor for diagnosis
                    lambda_player=mu_adj,
                    lambda_calculation=f"mu_raw={mu_raw:.2f} * factors={total_factor:.3f} = {mu_adj:.2f}",
                    gap=((line - mu_adj) / mu_adj * 100) if mu_adj > 0 else 0,
                    z_score=(line - mu_adj) / sigma_eff if sigma_eff > 0 else 0,
                    
                    # Probability chain (for calibration diagnosis)
                    prob_raw=prob_details.get("base_probability", model_confidence),
                    prob_stat_capped=prob_details.get("stat_capped", model_confidence),
                    prob_global_capped=prob_details.get("global_capped", model_confidence),
                    cap_applied=prob_details.get("cap_applied", "none"),
                    
                    model_version="nba_props_v2.1.4",
                    edge=mu_adj - line,
                    edge_type="PRIMARY"
                )
                
                cal.add_pick(pick)
    except Exception as e:
        # Never crash on calibration tracking failures
        if verbose:
            print(f"[CALIBRATION] Warning: Failed to save prediction: {e}")

    return result

def analyze_slate(props: list, verbose: bool = False, game_context: Optional[dict] = None) -> dict:
    """
    Analyze full slate of props
    
    Returns:
        {
            "total_props": int,
            "blocked": int,
            "no_play": int,
            "lean": int,
            "play": int,
            "results": [list of prop results]
        }
    """
    # =================================================================
    # OBSERVABILITY: Track metrics for this analysis run
    # =================================================================
    try:
        from observability import metrics, tracer
        _has_observability = True
        tracer.start_trace()
        _analysis_span = tracer.span("analyze_slate", sport="NBA", prop_count=len(props))
        _analysis_span.__enter__()
    except ImportError:
        _has_observability = False
    
    # =================================================================
    # FIX #1: DEDUPLICATION (2026-01-30)
    # Remove duplicate props BEFORE analysis to prevent triple-counting
    # =================================================================
    original_count = len(props)
    seen_keys = {}
    deduped_props = []
    duplicates_removed = 0
    
    for prop in props:
        if not isinstance(prop, dict):
            deduped_props.append(prop)
            continue
        
        player = str(prop.get("player", "")).strip().lower()
        stat = str(prop.get("stat", "")).strip().lower()
        line = round(float(prop.get("line", 0)), 1)
        direction = str(prop.get("direction", "")).strip().lower()
        
        key = (player, stat, line, direction)
        
        if key not in seen_keys:
            seen_keys[key] = prop
            deduped_props.append(prop)
        else:
            duplicates_removed += 1
    
    if duplicates_removed > 0:
        # ASCII-only (Windows terminals may default to cp1252 and crash on emoji)
        print(f"WARN: DEDUP removed {duplicates_removed} duplicate props ({original_count} -> {len(deduped_props)})")
    
    props = deduped_props  # Use deduplicated list
    # =================================================================
    
    # HQ Quant options (clamps only). Same engine paths for live + backtests.
    hq_options = load_hq_options_from_env()

    # STANDARD: On the first run each day, refresh all API-enabled stats for the players in this slate.
    # This makes mu/sigma realistic without requiring manual hydration edits.
    _refresh_daily_api_stats(props)

    # PRE-FLIGHT CHECK: Validate stats pipeline before analysis
    preflight = preflight_stats_check(props, verbose=True)
    if not preflight["passed"]:
        print("[WARNING] Pre-flight check found issues. Results may be unreliable.")
        print("[TIP] To force refresh: set environment variable FORCE_STATS_REFRESH=1")

    # Detect league from props
    league = "NBA"  # Default assumption for menu-based analysis
    for prop in props:
        if isinstance(prop, dict) and prop.get("league"):
            league = prop["league"].upper()
            break

    # Enrich usage/minutes for NBA (required for Role Layer)
    if league == "NBA":
        from engine.enrich_nba_simple import enrich_nba_usage_minutes_simple
        props = enrich_nba_usage_minutes_simple(props)
        print(f"Enriched {len(props)} NBA props with usage/minutes estimates")

    # NBA ROLE & SCHEME NORMALIZATION LAYER (NBA-only)
    
    if league == "NBA":
        try:
            from nba.role_scheme_normalizer import RoleSchemeNormalizer
            print("NBA ROLE & SCHEME NORMALIZATION")
            normalizer = RoleSchemeNormalizer()
            specialist_classifier = StatSpecialistClassifier() if HAS_STAT_SPECIALISTS else None
            normalized_count = 0
            
            for prop in props:
                if not isinstance(prop, dict):
                    continue
                
                # Extract player info
                player_name = prop.get("player", "")
                team = prop.get("team", "")
                opponent = prop.get("opponent", "")
                
                # Skip if no player
                if not player_name:
                    continue
                
                # Get usage/minutes from enriched props
                # enrich_usage_minutes adds: usage_rate, minutes_projected
                usage_rate_l10 = prop.get("usage_rate", 0.0)
                minutes_l10_avg = prop.get("minutes_projected", 0.0)
                # Estimate std as 15% of avg (typical variance)
                minutes_l10_std = minutes_l10_avg * 0.15
                
                # Skip if missing critical data
                if minutes_l10_avg == 0.0:
                    continue
                
                # Build game context
                game_context_local = {}
                if "spread" in prop:
                    game_context_local["spread"] = prop["spread"]
                if "is_back_to_back" in prop:
                    game_context_local["is_back_to_back"] = prop["is_back_to_back"]
                
                # Run normalization
                norm_result = normalizer.normalize(
                    player_name=player_name,
                    team=team,
                    opponent=opponent,
                    minutes_l10_avg=minutes_l10_avg,
                    minutes_l10_std=minutes_l10_std,
                    usage_rate_l10=usage_rate_l10,
                    game_context=game_context_local if game_context_local else None
                )
                
                # Store normalization metadata for audit trail (attach to prop for later use)
                prop["nba_role_archetype"] = norm_result.archetype.value
                prop["nba_confidence_cap_adjustment"] = norm_result.confidence_cap_adjustment
                prop["nba_role_flags"] = norm_result.flags
                prop["nba_role_metadata"] = norm_result.metadata
                
                # Transfer specialist flags from enrichment
                if "specialist_flags" in prop:
                    prop["nba_specialist_flags"] = prop["specialist_flags"]
                # Always attach nba_stat_averages, and compute if missing
                stat_keys = ["points", "rebounds", "3pm", "steals", "blocks", "assists"]
                if "stat_averages" in prop:
                    prop["nba_stat_averages"] = prop["stat_averages"]
                else:
                    # Read from STATS_DICT (live mu/sigma from NBA API cache)
                    player_name = prop.get("player", "")
                    player_stats = STATS_DICT.get(player_name, {})
                    nba_stat_averages = {}
                    for k in stat_keys:
                        val = None
                        # Try to get from prop first
                        if k in prop and isinstance(prop[k], (int, float)):
                            val = prop[k]
                        # Then from STATS_DICT (mu, sigma) tuple - extract mu
                        elif player_stats and k in player_stats:
                            stat_data = player_stats[k]
                            if isinstance(stat_data, (tuple, list)) and len(stat_data) >= 1:
                                val = stat_data[0]  # mu is first element
                            elif isinstance(stat_data, (int, float)):
                                val = stat_data
                        # Fallback to 0
                        if val is None:
                            val = 0
                        nba_stat_averages[k] = round(val, 1) if isinstance(val, float) else val
                    prop["nba_stat_averages"] = nba_stat_averages
                    # Only debug print if we got real data
                    if any(v > 0 for v in nba_stat_averages.values()):
                        pass  # suppress debug spam
                    # print(f"[DEBUG] Attached nba_stat_averages for {player_name}: {nba_stat_averages}")
                
                normalized_count += 1
            
            print(f"   Normalized {normalized_count} NBA picks with role/scheme adjustments")
            print()

            # --- Specialist flag generation ---
            # Collect stat averages for all props
            stat_types = {
                "rebounds": "REB_SPECIALIST",
                "3pm": "3PM_SPECIALIST",
                "steals": "STL_SPECIALIST",
                "blocks": "BLK_SPECIALIST",
                "assists": "AST_SPECIALIST"
            }
            stat_avgs = {k: [] for k in stat_types}
            for prop in props:
                avgs = prop.get("nba_stat_averages", {})
                for stat, flag in stat_types.items():
                    val = avgs.get(stat)
                    if isinstance(val, (int, float)):
                        stat_avgs[stat].append(val)
            # Compute top 20% threshold for each stat
            stat_thresholds = {}
            for stat, values in stat_avgs.items():
                if values:
                    values_sorted = sorted(values, reverse=True)
                    idx = max(1, int(0.2 * len(values_sorted)))
                    stat_thresholds[stat] = values_sorted[idx-1]
            # Assign specialist flags to each prop
            for prop in props:
                avgs = prop.get("nba_stat_averages", {})
                specialist_flags = []
                for stat, flag in stat_types.items():
                    val = avgs.get(stat)
                    threshold = stat_thresholds.get(stat)
                    if isinstance(val, (int, float)) and threshold is not None and val >= threshold:
                        specialist_flags.append(flag)
                if specialist_flags:
                    prop["nba_specialist_flags"] = specialist_flags

                # --- STAT SPECIALIST TYPE (2nd-axis) ---
                if specialist_classifier is not None:
                    try:
                        player_name = prop.get("player", "")
                        if player_name:
                            # NOTE: specialist type is per-stat. Prefer the prop's stat field when present.
                            stat_hint = prop.get("stat") or prop.get("prop_type") or prop.get("market")
                            cls = specialist_classifier.classify(player_name, stat=stat_hint, prop=prop)
                            prop["nba_stat_specialist_type"] = cls.specialist.value
                            prop["nba_stat_specialist_source"] = cls.source
                            prop["nba_stat_specialist_metadata"] = cls.metadata
                            # Canonical aliases for downstream enforcement.
                            prop["stat_specialist_type"] = cls.specialist.value
                            prop["stat_specialist_source"] = cls.source
                            prop["stat_specialist_metadata"] = cls.metadata
                    except Exception:
                        pass
        except ImportError:
            print("   WARNING: NBA Role Layer not available (nba.role_scheme_normalizer not found)")
            print()
        except Exception as e:
            print(f"   WARNING: NBA Role Layer failed: {e}")
            print()

    # SANITY: drop obvious slate/team artifacts (e.g., player not on either matchup team).
    kept_props, skipped_results, sanitize_warnings = _sanitize_props_team_truth(props)
    if sanitize_warnings:
        for w in sanitize_warnings:
            print(w)

    results = []
    stats = {
        "total_props": len(props),
        "blocked": 0,
        "no_play": 0,
        "lean": 0,
        "strong": 0,
        "play": 0,
        "skip": 0
    }

    # Count and include skips from sanitation so totals remain transparent.
    if skipped_results:
        results.extend(skipped_results)
        stats["skip"] += len(skipped_results)
    
    for prop in kept_props:
        result = analyze_prop_with_gates(prop, verbose=verbose, game_context=game_context, hq_options=hq_options)

        # -------------------------------------------------------
        # INJURY PENALTY (from nba_injury_gate)
        # If the incoming prop was flagged by the injury gate in
        # menu.py, apply the penalty to the final confidence.
        # -------------------------------------------------------
        inj_penalty = prop.get("injury_penalty", 0.0)
        inj_flag = prop.get("injury_flag", False)
        if inj_flag and inj_penalty > 0:
            eff = float(result.get("effective_confidence") or result.get("model_confidence") or 0)
            penalty_pts = eff * inj_penalty
            eff_new = max(0.0, eff - penalty_pts)
            result["injury_penalty_applied"] = round(penalty_pts, 2)
            result["injury_status"] = prop.get("injury_status", "")
            result["effective_confidence"] = round(eff_new, 2)
            result.setdefault("context_warnings", []).append(
                f"INJURY: {prop.get('injury_status','?')} penalty -{penalty_pts:.1f}% ({eff:.1f}->{eff_new:.1f}%)"
            )
            # Re-classify decision after penalty
            try:
                from config.thresholds import implied_tier
                tier = implied_tier(max(0.0, min(1.0, eff_new / 100.0)), sport="NBA")
                tier_map = {"SLAM": "PLAY", "STRONG": "STRONG", "LEAN": "LEAN"}
                result["decision"] = tier_map.get(tier, "NO_PLAY")
            except Exception:
                pass

        results.append(result)
        
        decision = result["decision"]
        if decision == "BLOCKED":
            stats["blocked"] += 1
        elif decision == "NO_PLAY":
            stats["no_play"] += 1
        elif decision == "LEAN":
            stats["lean"] += 1
        elif decision == "STRONG":
            stats["strong"] += 1
        elif decision == "PLAY":
            stats["play"] += 1
        elif decision == "SKIP":
            stats["skip"] += 1
    
    # Attach options metadata (auditable, backtestable).
    analysis = {
        **stats,
        "results": results,
        "hq_options": {
            "source": getattr(hq_options, "source", "default"),
            "source_path": getattr(hq_options, "source_path", ""),
            "reporting": {
                "top_n_per_team": getattr(getattr(hq_options, "reporting", None), "top_n_per_team", 5),
                "include_status": getattr(getattr(hq_options, "reporting", None), "include_status", ["PLAY", "LEAN", "ANALYSIS_ONLY"]),
            },
        },
    }

    # View-layer status fields (do NOT alter engine decisions).
    # - decision: engine decision (PLAY/LEAN/NO_PLAY/BLOCKED/SKIP)
    # - status: reporting visibility (includes ANALYSIS_ONLY)
    # - status_confidence: reporting confidence (used for sorting)
    analysis_only = 0
    out_results: list = []
    for r in analysis.get("results", []) or []:
        if not isinstance(r, dict):
            continue

        rr = dict(r)
        status = rr.get("decision")
        status_conf = rr.get("effective_confidence", 0.0)

        try:
            ov = _player_override_for(str(rr.get("player", "")), hq_options)
            if rr.get("decision") == "BLOCKED" and ov and ov.allow_analysis:
                status = "ANALYSIS_ONLY"
                base = rr.get("model_confidence", 0.0)
                status_conf = float(base) if isinstance(base, (int, float)) else 0.0
                if ov.max_probability is not None:
                    status_conf = _cap_percent_no_increase(status_conf, cap_percent=float(ov.max_probability) * 100.0)
                analysis_only += 1
        except Exception:
            pass

        rr["status"] = status
        rr["status_confidence"] = float(status_conf) if isinstance(status_conf, (int, float)) else 0.0
        out_results.append(rr)

    analysis["results"] = out_results
    analysis["analysis_only"] = analysis_only

    # Signals export + Telegram push are best-effort. Never crash report runs.
    try:
        export_result = build_signals_from_risk_first(analysis)
        if telegram_can_send() and export_result.signals:
            try:
                telegram_push_signals(export_result.signals, mode=export_result.mode)
            except Exception:
                pass
    except Exception as e:
        print(f"[SIGNALS] Export skipped due to error: {e}")

    # =================================================================
    # OBSERVABILITY: Record final metrics
    # =================================================================
    try:
        if _has_observability:
            # Record edges by tier
            for result in analysis["results"]:
                tier = result.get("decision", "UNKNOWN")
                stat = result.get("stat", "unknown").lower()
                if tier in ("PLAY", "STRONG", "LEAN"):
                    metrics.record_edge_generated("NBA", stat, tier)
                elif tier == "BLOCKED":
                    reason = result.get("block_reason", "unknown")[:30]
                    metrics.record_edge_rejected("NBA", stat, reason)
            
            # Record gate passes
            metrics.record_gate_pass("NBA", "analyze_slate")
            
            # End trace
            _analysis_span.set_attribute("total_props", analysis["total_props"])
            _analysis_span.set_attribute("play_count", analysis["play"])
            _analysis_span.set_attribute("blocked_count", analysis["blocked"])
            _analysis_span.__exit__(None, None, None)
            tracer.end_trace()
            
            # Save metrics snapshot
            metrics.save_snapshot()
    except Exception:
        pass  # Never crash on observability

    # =================================================================
    # UGO EXPORT: Convert edges to Universal Governance Object format
    # =================================================================
    try:
        from core.universal_governance_object import adapt_edge, Sport
        ugo_edges = []
        for result in analysis["results"]:
            # Only export OPTIMIZABLE/VETTED edges (not BLOCKED/NO_PLAY)
            if result.get("decision") in ["PLAY", "STRONG", "LEAN"]:
                try:
                    ugo = adapt_edge(Sport.NBA, result)
                    ugo_edges.append(ugo.to_dict())
                except Exception as e:
                    # Silently skip edges that fail conversion
                    if verbose:
                        print(f"[UGO] Failed to convert {result.get('player')} {result.get('stat')}: {e}")
        
        # Attach UGO edges to analysis
        if ugo_edges:
            analysis["ugo_edges"] = ugo_edges
            analysis["ugo_count"] = len(ugo_edges)
            if verbose:
                print(f"\nUGO Export: {len(ugo_edges)} edges converted to Universal Governance Object format")
    except ImportError:
        pass  # UGO not available, skip silently
    except Exception as e:
        if verbose:
            print(f"\nWARN: UGO export failed: {e}")

    # =================================================================
    # CROSS-SPORT DATABASE: Save top picks for unified parlay building
    # =================================================================
    try:
        from engine.daily_picks_db import save_top_picks
        # Convert results to edge format for cross-sport DB
        nba_edges = []
        for result in analysis["results"]:
            if result.get("decision") in ["PLAY", "STRONG", "LEAN"]:
                nba_edges.append({
                    "player": result.get("player"),
                    "stat": result.get("stat"),
                    "line": result.get("line"),
                    "direction": result.get("direction"),
                    "probability": result.get("effective_confidence", 50) / 100,
                    "tier": "SLAM" if result.get("decision") == "PLAY" else result.get("decision")
                })
        if nba_edges:
            save_top_picks(nba_edges, "NBA", top_n=5)
            if verbose:
                print(f"\nINFO: Cross-Sport DB saved top 5 NBA picks")
    except ImportError:
        pass
    except Exception as e:
        if verbose:
            print(f"\nWARN: Cross-Sport DB save failed: {e}")

    return analysis


def print_summary(analysis: dict, bankroll: float = 1000.0):
    """Print analysis summary with Slate Quality and Kelly sizing"""

    def _console_safe(text) -> str:
        """Best-effort sanitization for Windows consoles (cp1252) to avoid UnicodeEncodeError."""
        import sys
        if text is None:
            return ""
        s = str(text)
        # Replace common unicode symbols/emoji that frequently appear in warnings/drivers.
        s = (
            s.replace("✅", "OK")
            .replace("⚠️", "WARN")
            .replace("⚠", "WARN")
            .replace("⛔", "BLOCK")
            .replace("🟢", "[GREEN]")
            .replace("🟡", "[YELLOW]")
            .replace("🟠", "[ORANGE]")
            .replace("🔴", "[RED]")
            .replace("⛔", "[BLOCK]")
            .replace("⚪", "[NEUTRAL]")
            .replace("≥", ">=")
            .replace("≤", "<=")
            .replace("σ", "sigma")
            .replace("μ", "mu")
            .replace("→", "->")
            .replace("≈", "~=")
            .replace("—", "-")
            .replace("–", "-")
        )

        # Final guarantee: make sure the string can be encoded by the active stdout encoding.
        # This avoids hard crashes on Windows terminals with cp1252.
        enc = getattr(sys.stdout, "encoding", None) or "cp1252"
        try:
            s.encode(enc)
            return s
        except Exception:
            return s.encode(enc, errors="replace").decode(enc, errors="replace")
    
    # Calculate Slate Quality
    slate_grade = "N/A"
    slate_score = 0
    slate_drivers = []
    try:
        from core.slate_quality import compute_slate_quality
        results = analysis.get("results", [])
        playable = [r for r in results if r.get("decision") in ["PLAY", "STRONG", "LEAN"]]
        pct_above_55 = len(playable) / max(len(results), 1)
        avg_sigma = sum(r.get("sigma", 5.0) for r in results) / max(len(results), 1)
        context = {
            "api_health": 1.0,
            "injury_density": 0.0,
            "avg_sigma": avg_sigma,
            "sigma_threshold": 7.0,
            "pct_above_55": pct_above_55
        }
        sq = compute_slate_quality(context)
        slate_grade = sq.grade
        slate_score = sq.score
        slate_drivers = sq.drivers
    except Exception:
        pass
    
    print("\n" + "="*70)
    print("RISK-FIRST ANALYSIS SUMMARY")
    print("="*70)
    
    # Show Slate Quality prominently
    # ASCII-only slate quality marker (avoid emoji to prevent cp1252 crashes).
    grade_marker = {"A": "[A]", "B": "[B]", "C": "[C]", "D": "[D]", "F": "[F]"}.get(slate_grade, "[N/A]")
    print(f"Slate Quality: {grade_marker} {slate_grade} ({slate_score}/100)")
    if slate_drivers:
        safe_drivers = [_console_safe(d) for d in slate_drivers[:3]]
        print(f"   Drivers: {', '.join(safe_drivers)}")
    print("-"*70)
    
    print(f"Total Props Analyzed: {analysis['total_props']}")
    print(f"Skipped (No Data):    {analysis['skip']}")
    print(f"BLOCKED:              {analysis['blocked']}")
    if isinstance(analysis.get("analysis_only"), int) and analysis.get("analysis_only", 0) > 0:
        print(f"ANALYSIS_ONLY (view): {analysis.get('analysis_only', 0)}")
    print(f"NO PLAY:              {analysis['no_play']}")
    print(f"LEAN (55-64%):        {analysis['lean']}")
    print(f"STRONG (65-79%):      {analysis.get('strong', 0)}")
    print(f"PLAY/SLAM (>=80%):    {analysis['play']}")
    print("="*70)
    
    # Helper function for Kelly stake calculation
    def _get_kelly_stake(confidence: float, bankroll: float) -> str:
        """Calculate Kelly stake from confidence"""
        try:
            from core.kelly import kelly_fraction
            p = confidence / 100.0
            odds = 1.91  # Standard Underdog odds
            kelly = kelly_fraction(p, odds)
            fractional_kelly = kelly * 0.25  # 25% Kelly
            stake = bankroll * min(fractional_kelly, 0.25)  # Capped at 25%
            if stake < 1:
                return "$0"
            return f"${stake:.0f}"
        except Exception:
            return "N/A"
    
    # Show PLAY (SLAM) picks - >= 80%
    play_picks = [r for r in analysis["results"] if r["decision"] == "PLAY"]
    if play_picks:
        # Sort by edge quality (z_score descending)
        play_picks.sort(key=lambda x: abs(x.get("z_score", 0)), reverse=True)
        
        print(f"\n[SLAM] PLAY PICKS (>=80% Effective Confidence) | Bankroll: ${bankroll:.0f}:\n")
        for i, pick in enumerate(play_picks, 1):
            edge_str = f"{pick['edge']:+.1f}" if pick['edge'] >= 0 else f"{pick['edge']:.1f}"
            z_str = f"{pick['z_score']:+.2f}sigma"
            kelly_stake = _get_kelly_stake(pick['effective_confidence'], bankroll)
            
            # Edge quality marker (ASCII-safe)
            edge_emoji = {
                "ELITE": "[ELITE]",
                "STRONG": "[STRONG]", 
                "MODERATE": "[MODERATE]",
                "THIN": "[THIN]"
            }.get(pick['edge_quality'], "")
            
            print(f"{i}. {pick['player']} - {pick['stat'].upper()} {pick['direction'].upper()} {pick['line']}")
            print(f"   Confidence: {pick['effective_confidence']:.1f}% | Edge: {edge_str} ({z_str}) {edge_emoji} {pick['edge_quality']}")
            print(f"   Stats: mu={pick['mu']:.1f}, sigma={pick['sigma']:.1f} | Kelly: {kelly_stake}")
            
            # Show context warnings if any
            if pick.get("context_warnings"):
                for warning in pick["context_warnings"]:
                    print(f"   WARNING: {_console_safe(warning)}")
            
            print()
    
    # Show STRONG picks - 65-79%
    strong_picks = [r for r in analysis["results"] if r["decision"] == "STRONG"]
    if strong_picks:
        strong_picks.sort(key=lambda x: abs(x.get("z_score", 0)), reverse=True)
        
        print("\n[STRONG] PICKS (65-79% Effective Confidence):\n")
        for i, pick in enumerate(strong_picks, 1):
            edge_str = f"{pick['edge']:+.1f}" if pick['edge'] >= 0 else f"{pick['edge']:.1f}"
            z_str = f"{pick['z_score']:+.2f}sigma"
            kelly_stake = _get_kelly_stake(pick['effective_confidence'], bankroll)
            
            # Edge quality marker (ASCII-safe)
            edge_emoji = {
                "ELITE": "[ELITE]",
                "STRONG": "[STRONG]", 
                "MODERATE": "[MODERATE]",
                "THIN": "[THIN]"
            }.get(pick['edge_quality'], "")
            
            print(f"{i}. {pick['player']} - {pick['stat'].upper()} {pick['direction'].upper()} {pick['line']}")
            print(f"   Confidence: {pick['effective_confidence']:.1f}% | Edge: {edge_str} ({z_str}) {edge_emoji} {pick['edge_quality']}")
            print(f"   Stats: mu={pick['mu']:.1f}, sigma={pick['sigma']:.1f} | Kelly: {kelly_stake}")
            
            # Show context warnings if any
            if pick.get("context_warnings"):
                for warning in pick["context_warnings"]:
                    print(f"   WARNING: {_console_safe(warning)}")
            
            print()
    
    # Show LEAN picks - 55-64%
    lean_picks = [r for r in analysis["results"] if r["decision"] == "LEAN"]
    if lean_picks:
        lean_picks.sort(key=lambda x: abs(x.get("z_score", 0)), reverse=True)
        
        print("\n[LEAN] PICKS (55-64% Effective Confidence):\n")
        for i, pick in enumerate(lean_picks, 1):
            edge_str = f"{pick['edge']:+.1f}" if pick['edge'] >= 0 else f"{pick['edge']:.1f}"
            z_str = f"{pick['z_score']:+.2f}sigma"
            kelly_stake = _get_kelly_stake(pick['effective_confidence'], bankroll)
            
            print(f"{i}. {pick['player']} - {pick['stat'].upper()} {pick['direction'].upper()} {pick['line']}")
            print(f"   Confidence: {pick['effective_confidence']:.1f}% | Edge: {edge_str} ({z_str}) {pick['edge_quality']} | Kelly: {kelly_stake}\n")
    
    # Show top blocked reasons
    blocked = [r for r in analysis["results"] if r["decision"] == "BLOCKED"]
    if blocked:
        print("\nTOP BLOCK REASONS:\n")
        reasons = {}
        for b in blocked:
            reason = b.get("block_reason", "Unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
        
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   {count}x - {reason}")
    
    # Kelly Legend
    print("\n" + "-"*70)
    print("KELLY SIZING GUIDE (25% Fractional Kelly @ 1.91 odds)")
    print("-"*70)
    print("• Kelly = optimal bet size based on edge vs odds")
    print("• Amounts shown assume ${:.0f} bankroll (adjustable)".format(bankroll))
    print("• SLAM picks: Higher Kelly | LEAN picks: Lower Kelly")
    print("• Cap: Max 25% of bankroll per bet")
    print("="*70 + "\n")


if __name__ == "__main__":
    # Test with sample props
    test_props = [
        # Should BLOCK - composite stat
        {"player": "Franz Wagner", "team": "ORL", "opponent": "MEM", "stat": "pra", "line": 23.5, "direction": "higher"},
        
        # Should BLOCK - big + assists
        {"player": "Joel Embiid", "team": "PHI", "opponent": "CLE", "stat": "assists", "line": 3.5, "direction": "higher"},
        
        # Should BLOCK - banned
        {"player": "Tyrese Maxey", "team": "PHI", "opponent": "CLE", "stat": "pra", "line": 31.5, "direction": "higher"},
        
        # Should PASS - Franz Wagner points (SECONDARY_WING allowed)
        {"player": "Franz Wagner", "team": "ORL", "opponent": "MEM", "stat": "points", "line": 15.5, "direction": "higher"},
        
        # Should PASS - Jaren Jackson Jr rebounds (BIG allowed)
        {"player": "Jaren Jackson Jr", "team": "MEM", "opponent": "ORL", "stat": "rebounds", "line": 5.5, "direction": "higher"},
        
        # Should BLOCK - STAR_GUARD points vs elite defense
        {"player": "Darius Garland", "team": "CLE", "opponent": "PHI", "stat": "points", "line": 18.5, "direction": "higher"},
    ]
    
    print("\nTESTING RISK-FIRST SYSTEM WITH 6 PROPS\n")
    analysis = analyze_slate(test_props, verbose=True)
    print_summary(analysis)
