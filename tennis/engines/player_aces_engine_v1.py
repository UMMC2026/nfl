"""PLAYER_ACES_ENGINE_v1

Market: Player Aces
Principle: High-variance, must be aggressively gated.

HARD RULES
- EDGE identity: unique(player, opponent, aces_line, surface)
- Mandatory AUTO-BLOCK gates:
  - Player avg aces < 60% of line
  - Surface = CLAY AND line > 6.5 (WTA)
  - Opponent return rank top 15
  - Indoor/Outdoor unknown (HARD requires explicit env)
  - Player retired in last 2 matches
  - Line >= 15.5 => BLOCK unless top-5 server

Tiers:
- STRONG >= 0.67
- LEAN   0.59–0.66
- NO PLAY < 0.59

Deterministic: no Monte Carlo.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tennis_props_parser import TennisProp

TENNIS_DIR = Path(__file__).resolve().parents[1]
VALID_SURFACES = {"HARD", "CLAY", "GRASS", "INDOOR"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _normal_cdf(z: float) -> float:
    # Standard normal CDF via erf
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def load_player_stats() -> Dict:
    stats_file = TENNIS_DIR / "player_stats.json"
    if stats_file.exists():
        try:
            return json.loads(stats_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def detect_surface(raw_text: str, surface_override: Optional[str]) -> Optional[str]:
    if surface_override:
        s = surface_override.strip().upper()
        return s if s in VALID_SURFACES else None

    text = raw_text.upper()
    for surf in VALID_SURFACES:
        if f"SURFACE: {surf}" in text or f"SURFACE={surf}" in text:
            return surf
    for surf in VALID_SURFACES:
        if surf in text:
            return surf
    return None


def detect_environment(raw_text: str, surface: Optional[str], env_override: Optional[str]) -> Optional[str]:
    """Return INDOOR / OUTDOOR / None (unknown). Gate requires known."""

    if env_override:
        e = env_override.strip().upper()
        if e in {"INDOOR", "OUTDOOR"}:
            return e
        return None

    # Surface implies environment except HARD (ambiguous)
    if surface == "INDOOR":
        return "INDOOR"
    if surface in {"CLAY", "GRASS"}:
        return "OUTDOOR"

    text = raw_text.upper()
    if "ENV: INDOOR" in text or "ENV=INDOOR" in text:
        return "INDOOR"
    if "ENV: OUTDOOR" in text or "ENV=OUTDOOR" in text:
        return "OUTDOOR"

    # HARD without explicit env is unknown
    return None


def _retired_in_last_2(player_stats: Dict) -> bool:
    for k in (
        "retired_in_last_2",
        "retired_last_2",
        "retired_last_2_matches",
        "retired_in_last_2_matches",
    ):
        if bool(player_stats.get(k, False)):
            return True
    if bool(player_stats.get("retired_last_match", False)):
        return True
    return False


def _tour(player_stats: Dict) -> Optional[str]:
    t = player_stats.get("tour")
    if isinstance(t, str) and t.strip():
        return t.strip().upper()
    # Infer from keys
    if player_stats.get("wta_rank") is not None:
        return "WTA"
    if player_stats.get("atp_rank") is not None:
        return "ATP"
    return None


def _opponent_return_rank(opponent_stats: Dict) -> Optional[int]:
    for k in (
        "return_rank",
        "return_rank_overall",
        "return_rank_atp",
        "return_rank_wta",
    ):
        if k in opponent_stats and opponent_stats[k] is not None:
            try:
                return int(opponent_stats[k])
            except Exception:
                return None
    return None


def _opponent_return_pts_won(opponent_stats: Dict, default: float = 0.35) -> float:
    for k in ("return_pts_won", "return_points_won", "return_win", "return_win_pct"):
        if k in opponent_stats and opponent_stats[k] is not None:
            try:
                v = float(opponent_stats[k])
                return v / 100.0 if v > 1.0 else v
            except Exception:
                pass
    return float(default)


def _stat_surface(player_stats: Dict, base_key: str, surface: str, default: float) -> float:
    k = f"{base_key}_{surface.lower()}"
    if k in player_stats and player_stats[k] is not None:
        try:
            return float(player_stats[k])
        except Exception:
            pass
    if base_key in player_stats and player_stats[base_key] is not None:
        try:
            return float(player_stats[base_key])
        except Exception:
            pass
    return float(default)


def _is_top5_server(player_stats: Dict) -> bool:
    for k in ("aces_rank", "ace_rank", "serve_aces_rank"):
        if k in player_stats and player_stats[k] is not None:
            try:
                return int(player_stats[k]) <= 5
            except Exception:
                pass

    # Fallback proxy: extremely high aces per service game.
    apsg = player_stats.get("aces_per_service_game")
    if apsg is not None:
        try:
            return float(apsg) >= 0.75
        except Exception:
            pass

    return False


def surface_ace_multiplier(surface: str) -> float:
    return {
        "GRASS": 1.15,
        "INDOOR": 1.10,
        "HARD": 1.00,
        "CLAY": 0.75,
    }.get(surface, 1.0)


def estimate_expected_service_games(
    player_stats: Dict,
    opponent_stats: Dict,
    surface: str,
) -> Tuple[float, Dict]:
    """Expected service games for the player (not per set), derived from a minimal parity proxy."""

    # Minimal: use hold rates to infer match length. (No sets/games engine reuse.)
    hold_p = _stat_surface(player_stats, "serve_hold", surface, 0.80)
    hold_o = _stat_surface(opponent_stats, "serve_hold", surface, 0.80)

    hold_avg = (hold_p + hold_o) / 2.0

    # Baseline service games for a typical Bo3 match
    base = 11.5

    # Higher hold => more games => more service games
    base += (hold_avg - 0.80) * 10.0

    # Clamp for sanity
    exp_sg = _clamp(base, 8.5, 16.5)

    return exp_sg, {
        "hold_player": round(hold_p, 4),
        "hold_opp": round(hold_o, 4),
        "expected_service_games": round(exp_sg, 3),
    }


def estimate_prob_over_aces(
    player: str,
    opponent: str,
    surface: str,
    env: str,
    aces_line: float,
    stats: Dict,
) -> Tuple[float, Dict]:
    ps = stats.get(player, {})
    os = stats.get(opponent, {})

    apsg = ps.get("aces_per_service_game")
    if apsg is None:
        # No modeling if missing the only normalization feature.
        return 0.50, {"missing": "aces_per_service_game"}

    try:
        apsg = float(apsg)
    except Exception:
        return 0.50, {"missing": "aces_per_service_game"}

    exp_sg, sg_details = estimate_expected_service_games(ps, os, surface)

    opp_rpw = _opponent_return_pts_won(os, default=0.35)
    # Suppression increases as opponent return improves.
    suppress = _clamp((opp_rpw - 0.35) * 1.2, 0.0, 0.25)

    env_mult = 1.05 if env == "INDOOR" else 1.00
    surf_mult = surface_ace_multiplier(surface) * env_mult

    mean = apsg * exp_sg * surf_mult * (1.0 - suppress)

    # Dispersion: higher variance than Poisson, but bounded.
    sd = max(2.5, math.sqrt(max(mean, 0.1)) * 1.15)

    # Continuity correction
    z = (aces_line + 0.5 - mean) / sd
    prob_over = 1.0 - _normal_cdf(z)

    # Conservative bounds (do not overstate)
    prob_over = _clamp(prob_over, 0.50, 0.76)

    details = {
        "aces_per_service_game": round(apsg, 4),
        "expected_service_games": round(exp_sg, 3),
        "surface_mult": round(surf_mult, 3),
        "opp_return_pts_won": round(opp_rpw, 4),
        "suppress": round(suppress, 4),
        "mean_aces": round(mean, 3),
        "sd": round(sd, 3),
        "z": round(z, 3),
        "prob_over": round(prob_over, 4),
        **sg_details,
    }

    return prob_over, details


def assign_tier(p: float) -> str:
    if p >= 0.67:
        return "STRONG"
    if p >= 0.59:
        return "LEAN"
    return "NO_PLAY"


def make_edge_id(player: str, opponent: str, surface: str, aces_line: float) -> str:
    p = player.replace(" ", "_")
    o = opponent.replace(" ", "_")
    return f"TENNIS_PLAYER_ACES::{p}::{o}::{surface}::{aces_line:.1f}"


def make_match_id(player: str, opponent: str, surface: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    p3 = player[:3].upper().replace(" ", "")
    o3 = opponent[:3].upper().replace(" ", "")
    return f"ACES_{surface}_{p3}_{o3}_{date_str}"


def run_aces_gates(
    player: str,
    opponent: str,
    surface: Optional[str],
    env: Optional[str],
    aces_line: float,
    stats: Dict,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if not surface or surface not in VALID_SURFACES:
        reasons.append("UNKNOWN_SURFACE")
        return False, reasons

    if env not in {"INDOOR", "OUTDOOR"}:
        reasons.append("UNKNOWN_ENVIRONMENT")

    ps = stats.get(player, {})
    os = stats.get(opponent, {})

    if _retired_in_last_2(ps):
        reasons.append("RETIRED_LAST_2")

    # Opponent return rank top 15
    rr = _opponent_return_rank(os)
    if rr is not None and rr <= 15:
        reasons.append(f"OPP_RETURN_RANK_TOP15 ({rr})")

    # Clay + high line for WTA
    tour = _tour(ps)
    if surface == "CLAY" and aces_line > 6.5:
        if tour == "WTA":
            reasons.append("WTA_CLAY_LINE_GT_6_5")
        elif tour is None:
            # If tour unknown, be conservative.
            reasons.append("UNKNOWN_TOUR_CLAY_LINE_GT_6_5")

    # Very high lines require elite servers
    if aces_line >= 15.5 and not _is_top5_server(ps):
        reasons.append("LINE_GE_15_5_NOT_TOP5_SERVER")

    # Player avg aces must be >= 60% of line
    avg = ps.get("aces_per_match_avg")
    if avg is not None:
        try:
            avg = float(avg)
            if avg < 0.60 * aces_line:
                reasons.append(f"AVG_ACES_LT_60PCT_LINE ({avg:.1f} < {0.60*aces_line:.1f})")
        except Exception:
            pass
    else:
        # Fallback derived mean using the engine's features.
        if env in {"INDOOR", "OUTDOOR"}:
            prob_over, det = estimate_prob_over_aces(player, opponent, surface, env, aces_line, stats)
            derived_mean = float(det.get("mean_aces", 0.0) or 0.0)
            if derived_mean and derived_mean < 0.60 * aces_line:
                reasons.append(f"DERIVED_MEAN_ACES_LT_60PCT_LINE ({derived_mean:.1f} < {0.60*aces_line:.1f})")
        else:
            reasons.append("MISSING_ACES_AVG_AND_ENV_UNKNOWN")

    return len(reasons) == 0, reasons


def build_aces_edge(
    player: str,
    opponent: str,
    surface: Optional[str],
    env: Optional[str],
    aces_line: float,
    stats: Dict,
) -> Dict:
    match_id = make_match_id(player, opponent, surface or "UNKNOWN")

    passed, reasons = run_aces_gates(player, opponent, surface, env, aces_line, stats)
    if not passed:
        return {
            "edge_id": make_edge_id(player, opponent, (surface or "UNKNOWN"), float(aces_line)),
            "sport": "TENNIS",
            "match_id": match_id,
            "player": player,
            "opponent": opponent,
            "entity": player,
            "market": "PLAYER_ACES",
            "surface": surface,
            "environment": env,
            "line": float(aces_line),
            "direction": None,
            "probability": None,
            "tier": "BLOCKED",
            "edge": None,
            "risk_tag": "PLAYER_ACES_ONLY",
            "blocked": True,
            "block_reason": reasons,
            "generated_at": _now_iso(),
        }

    assert surface is not None and env is not None

    prob_over, details = estimate_prob_over_aces(player, opponent, surface, env, float(aces_line), stats)

    if prob_over >= 0.5:
        direction = "OVER"
        prob_dir = prob_over
    else:
        direction = "UNDER"
        prob_dir = 1.0 - prob_over

    tier = assign_tier(prob_dir)
    edge = prob_dir - 0.50

    return {
        "edge_id": make_edge_id(player, opponent, surface, float(aces_line)),
        "sport": "TENNIS",
        "match_id": match_id,
        "player": player,
        "opponent": opponent,
        "entity": player,
        "market": "PLAYER_ACES",
        "surface": surface,
        "environment": env,
        "line": float(aces_line),
        "direction": direction,
        "probability": round(prob_dir, 4),
        "tier": tier,
        "edge": round(edge, 4),
        "risk_tag": "PLAYER_ACES_ONLY",
        "blocked": False,
        "block_reason": None,
        "features": details,
        "generated_at": _now_iso(),
    }


def extract_candidates(props: Iterable[TennisProp]) -> List[Tuple[str, str, float]]:
    out: List[Tuple[str, str, float]] = []
    for p in props:
        if (p.stat or "").strip().lower() == "aces":
            player = (p.player or "").strip()
            opponent = (p.opponent or "").strip() or "TBD"
            if player:
                out.append((player, opponent, float(p.line)))
    return out


def generate_from_props(
    props: List[TennisProp],
    raw_text: str,
    surface_override: Optional[str] = None,
    env_override: Optional[str] = None,
    max_plays: int = 2,
) -> Dict:
    surface = detect_surface(raw_text, surface_override)
    env = detect_environment(raw_text, surface, env_override)

    stats = load_player_stats()

    candidates = extract_candidates(props)

    seen = set()
    edges_all: List[Dict] = []

    for player, opponent, line in candidates:
        key = (player, opponent, surface, float(line))
        if key in seen:
            continue
        seen.add(key)

        edges_all.append(build_aces_edge(player, opponent, surface, env, float(line), stats))

    blocked = [e for e in edges_all if e.get("blocked")]
    playable = [e for e in edges_all if not e.get("blocked") and e.get("tier") in ("STRONG", "LEAN")]

    playable.sort(key=lambda e: (e.get("probability") or 0.0), reverse=True)
    plays = playable[:max_plays]

    return {
        "engine": "PLAYER_ACES_ENGINE_v1",
        "sport": "TENNIS",
        "market": "PLAYER_ACES",
        "surface": surface,
        "environment": env,
        "generated_at": _now_iso(),
        "total_candidates": len(candidates),
        "unique_edges": len(seen),
        "blocked_count": len(blocked),
        "playable_count": len(playable),
        "plays": plays,
        "edges": edges_all,
    }
