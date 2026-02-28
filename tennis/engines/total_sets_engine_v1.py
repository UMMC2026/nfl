"""TOTAL_SETS_ENGINE_v1

Market: Total Sets (2.5 / 3.5 / 4.5)
Principle: Measures parity, not raw skill.

HARD RULES
- EDGE identity: unique(playerA, playerB, sets_line, surface)
- Mandatory AUTO-BLOCK gates:
  - Elo gap > 220
  - Qualifier vs top-20 player
  - Either player straight-set win rate last 12 > 65%
  - Injury return <= 14 days (either)
  - Best-of-5 AND line < 4.5

Tiers:
- STRONG >= 0.66
- LEAN   0.58–0.65
- NO PLAY < 0.58
(No SLAM tier.)

Deterministic: no Monte Carlo.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tennis_elo import get_player_elo, load_elo_ratings
from tennis_props_parser import TennisProp

TENNIS_DIR = Path(__file__).resolve().parents[1]
VALID_SURFACES = {"HARD", "CLAY", "GRASS", "INDOOR"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(z: float) -> float:
    # stable-ish sigmoid
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


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


def detect_best_of(raw_text: str, best_of_override: Optional[int]) -> int:
    if best_of_override in (3, 5):
        return int(best_of_override)
    text = raw_text.upper()
    if "BO5" in text or "BEST OF 5" in text or "BEST-OF-5" in text:
        return 5
    return 3


def _days_since(date_iso: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(date_iso)
    except Exception:
        return None
    delta = datetime.now() - dt
    return max(0, int(delta.total_seconds() // 86400))


def _injury_return_days_ago(player_stats: Dict) -> Optional[int]:
    for k in (
        "days_since_injury_return",
        "injury_return_days_ago",
        "days_since_return",
    ):
        if k in player_stats and player_stats[k] is not None:
            try:
                return int(player_stats[k])
            except Exception:
                pass

    if player_stats.get("injury_return_date"):
        return _days_since(str(player_stats["injury_return_date"]))

    return None


def _is_qualifier(player: str, player_stats: Dict) -> bool:
    if bool(player_stats.get("is_qualifier", False)):
        return True
    return "QUALIFIER" in player.upper() or player.strip().upper() in {"Q", "QUAL"}


def _rank(player_stats: Dict) -> Optional[int]:
    for k in ("rank", "atp_rank", "wta_rank"):
        if k in player_stats and player_stats[k] is not None:
            try:
                return int(player_stats[k])
            except Exception:
                return None
    return None


def _straight_set_rate_last12(player_stats: Dict) -> Optional[float]:
    for k in ("straight_set_win_rate_last12", "straight_set_win_pct_last12", "straight_set_rate_last12"):
        if k in player_stats and player_stats[k] is not None:
            try:
                v = float(player_stats[k])
                return v / 100.0 if v > 1.0 else v
            except Exception:
                return None

    # fallback to generic straight_set_rate
    if player_stats.get("straight_set_rate") is not None:
        try:
            v = float(player_stats["straight_set_rate"])
            return v / 100.0 if v > 1.0 else v
        except Exception:
            return None

    return None


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


def assign_tier(p: float) -> str:
    if p >= 0.66:
        return "STRONG"
    if p >= 0.58:
        return "LEAN"
    return "NO_PLAY"


def make_edge_id(player_a: str, player_b: str, surface: str, sets_line: float) -> str:
    a = player_a.replace(" ", "_")
    b = player_b.replace(" ", "_")
    return f"TENNIS_TOTAL_SETS::{a}::{b}::{surface}::{sets_line:.1f}"


def make_match_id(player_a: str, player_b: str, surface: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    a3 = player_a[:3].upper().replace(" ", "")
    b3 = player_b[:3].upper().replace(" ", "")
    return f"SETS_{surface}_{a3}_{b3}_{date_str}"


def run_total_sets_gates(
    player_a: str,
    player_b: str,
    surface: Optional[str],
    sets_line: float,
    best_of: int,
    stats: Dict,
    elo_data: Dict,
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if not surface or surface not in VALID_SURFACES:
        reasons.append("UNKNOWN_SURFACE")
        return False, reasons

    # Best-of-5 sanity
    if best_of == 5 and sets_line < 4.5:
        reasons.append("BO5_LINE_LT_4_5")

    # Line sanity for Bo3 (2.5 only in practice)
    if best_of == 3 and sets_line > 2.5:
        reasons.append("INVALID_LINE_FOR_BO3")

    elo_a = get_player_elo(player_a, surface, elo_data)
    elo_b = get_player_elo(player_b, surface, elo_data)
    elo_gap = abs(elo_a - elo_b)

    if elo_gap > 220:
        reasons.append(f"ELO_GAP_GT_220 ({elo_gap:.1f})")

    a_stats = stats.get(player_a, {})
    b_stats = stats.get(player_b, {})

    # Qualifier vs top-20
    a_qual = _is_qualifier(player_a, a_stats)
    b_qual = _is_qualifier(player_b, b_stats)
    if a_qual != b_qual:
        if a_qual:
            r = _rank(b_stats)
            if r is not None and r <= 20:
                reasons.append("QUALIFIER_VS_TOP20")
        if b_qual:
            r = _rank(a_stats)
            if r is not None and r <= 20:
                reasons.append("QUALIFIER_VS_TOP20")

    # Straight-set dominance gate
    for p, ps in ((player_a, a_stats), (player_b, b_stats)):
        ss = _straight_set_rate_last12(ps)
        if ss is not None and ss > 0.65:
            reasons.append(f"STRAIGHT_SET_RATE_GT_65::{p} ({ss:.2f})")

    # Injury return <= 14d
    for p, ps in ((player_a, a_stats), (player_b, b_stats)):
        days = _injury_return_days_ago(ps)
        if days is not None and days <= 14:
            reasons.append(f"INJURY_RETURN_LE_14D::{p} ({days}d)")

    return len(reasons) == 0, reasons


def estimate_prob_over_sets(
    player_a: str,
    player_b: str,
    surface: str,
    sets_line: float,
    stats: Dict,
    elo_data: Dict,
) -> Tuple[float, Dict]:
    """Deterministic parity-based model for P(over sets_line)."""

    elo_a = get_player_elo(player_a, surface, elo_data)
    elo_b = get_player_elo(player_b, surface, elo_data)

    favorite = player_a if elo_a >= elo_b else player_b
    underdog = player_b if favorite == player_a else player_a

    fav_elo = max(elo_a, elo_b)
    dog_elo = min(elo_a, elo_b)
    elo_gap = abs(elo_a - elo_b)

    # Scale to 0..1 where 1 = very close matchup.
    parity = 1.0 - _clamp(elo_gap / 220.0, 0.0, 1.0)

    fav_stats = stats.get(favorite, {})
    dog_stats = stats.get(underdog, {})

    # Core features (no extras)
    dog_set_win_vs_top50 = float(dog_stats.get("set_win_pct_vs_top50", 0.38) or 0.38)
    if dog_set_win_vs_top50 > 1.0:
        dog_set_win_vs_top50 /= 100.0

    tb_fav = _stat_surface(fav_stats, "tiebreak_freq", surface, 0.18)
    tb_dog = _stat_surface(dog_stats, "tiebreak_freq", surface, 0.18)
    tiebreak_freq = (tb_fav + tb_dog) / 2.0

    bps_fav = _stat_surface(fav_stats, "breaks_per_set", surface, 1.05)
    bps_dog = _stat_surface(dog_stats, "breaks_per_set", surface, 1.05)
    breaks_per_set = (bps_fav + bps_dog) / 2.0

    hold_fav = _stat_surface(fav_stats, "surface_hold_rate", surface, 0.80)
    hold_dog = _stat_surface(dog_stats, "surface_hold_rate", surface, 0.80)
    surface_hold_rate = (hold_fav + hold_dog) / 2.0

    # Logistic score (hand-tuned, deterministic)
    # Interpretation: higher parity + higher dog resistance + more tiebreaks + more breaks (volatility)
    # => higher chance of extra sets.
    score = 0.0
    score += (parity - 0.45) * 2.2
    score += (dog_set_win_vs_top50 - 0.35) * 2.0
    score += (tiebreak_freq - 0.18) * 1.5
    score += (breaks_per_set - 1.05) * 0.9
    score += (surface_hold_rate - 0.80) * 0.8

    # Line-specific shift: higher lines require more parity.
    line_shift = {2.5: 0.00, 3.5: 0.35, 4.5: 0.55}.get(round(sets_line, 1), 0.25)
    score -= line_shift

    prob_over = _sigmoid(score)

    # Conservative bounding (keeps tiers honest)
    prob_over = _clamp(prob_over, 0.50, 0.75)

    details = {
        "favorite": favorite,
        "underdog": underdog,
        "fav_elo": round(fav_elo, 1),
        "dog_elo": round(dog_elo, 1),
        "elo_gap": round(elo_gap, 1),
        "parity": round(parity, 4),
        "dog_set_win_pct_vs_top50": round(dog_set_win_vs_top50, 4),
        "tiebreak_freq": round(tiebreak_freq, 4),
        "breaks_per_set": round(breaks_per_set, 4),
        "surface_hold_rate": round(surface_hold_rate, 4),
        "line_shift": line_shift,
        "score": round(score, 4),
        "prob_over": round(prob_over, 4),
    }

    return prob_over, details


def build_total_sets_edge(
    player_a: str,
    player_b: str,
    surface: Optional[str],
    sets_line: float,
    best_of: int,
    stats: Dict,
    elo_data: Dict,
) -> Dict:
    pa, pb = sorted([player_a, player_b])
    match_id = make_match_id(pa, pb, surface or "UNKNOWN")

    passed, reasons = run_total_sets_gates(pa, pb, surface, sets_line, best_of, stats, elo_data)
    if not passed:
        return {
            "edge_id": make_edge_id(pa, pb, (surface or "UNKNOWN"), float(sets_line)),
            "sport": "TENNIS",
            "match_id": match_id,
            "player_a": pa,
            "player_b": pb,
            "entity": f"{pa} vs {pb}",
            "market": "TOTAL_SETS",
            "surface": surface,
            "line": float(sets_line),
            "direction": None,
            "probability": None,
            "tier": "BLOCKED",
            "edge": None,
            "risk_tag": "TOTAL_SETS_ONLY",
            "blocked": True,
            "block_reason": reasons,
            "generated_at": _now_iso(),
        }

    assert surface is not None
    prob_over, details = estimate_prob_over_sets(pa, pb, surface, sets_line, stats, elo_data)

    if prob_over >= 0.5:
        direction = "OVER"
        prob_dir = prob_over
    else:
        direction = "UNDER"
        prob_dir = 1.0 - prob_over

    tier = assign_tier(prob_dir)
    edge = prob_dir - 0.50

    return {
        "edge_id": make_edge_id(pa, pb, surface, float(sets_line)),
        "sport": "TENNIS",
        "match_id": match_id,
        "player_a": pa,
        "player_b": pb,
        "entity": f"{pa} vs {pb}",
        "market": "TOTAL_SETS",
        "surface": surface,
        "line": float(sets_line),
        "direction": direction,
        "probability": round(prob_dir, 4),
        "tier": tier,
        "edge": round(edge, 4),
        "risk_tag": "TOTAL_SETS_ONLY",
        "blocked": False,
        "block_reason": None,
        "features": details,
        "generated_at": _now_iso(),
    }


def extract_candidates(props: Iterable[TennisProp]) -> List[Tuple[str, float]]:
    out: List[Tuple[str, float]] = []
    for p in props:
        if (p.stat or "").strip().lower() == "sets played":
            out.append(((p.match_info or "").strip(), float(p.line)))
    return out


def group_match_players(props: List[TennisProp]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for p in props:
        key = (p.match_info or "").strip()
        if not key:
            continue
        groups.setdefault(key, [])
        if p.player and p.player not in groups[key]:
            groups[key].append(p.player)
    return groups


def generate_from_props(
    props: List[TennisProp],
    raw_text: str,
    surface_override: Optional[str] = None,
    best_of_override: Optional[int] = None,
    max_plays: int = 3,
) -> Dict:
    surface = detect_surface(raw_text, surface_override)
    best_of = detect_best_of(raw_text, best_of_override)

    stats = load_player_stats()
    elo_data = load_elo_ratings()

    candidates = extract_candidates(props)
    players_by_match = group_match_players(props)

    seen = set()
    edges_all: List[Dict] = []

    for match_info, sets_line in candidates:
        players = players_by_match.get(match_info, [])
        if len(players) < 2:
            continue
        pa, pb = players[0], players[1]

        a, b = sorted([pa, pb])
        key = (a, b, surface, float(sets_line))
        if key in seen:
            continue
        seen.add(key)

        edges_all.append(build_total_sets_edge(a, b, surface, float(sets_line), best_of, stats, elo_data))

    blocked = [e for e in edges_all if e.get("blocked")]
    playable = [e for e in edges_all if not e.get("blocked") and e.get("tier") in ("STRONG", "LEAN")]

    playable.sort(key=lambda e: (e.get("probability") or 0.0), reverse=True)
    plays = playable[:max_plays]

    return {
        "engine": "TOTAL_SETS_ENGINE_v1",
        "sport": "TENNIS",
        "market": "TOTAL_SETS",
        "surface": surface,
        "best_of": best_of,
        "generated_at": _now_iso(),
        "total_candidates": len(candidates),
        "unique_edges": len(seen),
        "blocked_count": len(blocked),
        "playable_count": len(playable),
        "plays": plays,
        "edges": edges_all,
    }
