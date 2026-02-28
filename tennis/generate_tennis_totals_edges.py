"""
Tennis Totals Edge Generator — TENNIS_TOTALS_ENGINE_v1
======================================================
Generates edges for match total games market (TOTAL_GAMES).

Design goals (per spec):
- Isolated from match-winner logic.
- Deterministic scoring (no Monte Carlo).
- Canonical EDGE identity: (playerA, playerB, surface, total_games_line).
- Mandatory AUTO-BLOCK rules enforced before math.
- Output only top N overs + top N unders.

Input format:
- Intended to work from Underdog copy/paste via `tennis_props_parser.parse_tennis_props`.
- Uses the "Games Played" stat as match total games line.

Notes:
- If surface is unknown, all matches are blocked (per spec).
- Probability is computed as sigmoid(base_games - line), then per-direction clamped to [0.55, 0.72].
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tennis_elo import get_player_elo, load_elo_ratings
from tennis_props_parser import TennisProp, parse_tennis_props
from underdog_total_games_parser import parse_underdog_total_games_paste

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

VALID_SURFACES = {"HARD", "CLAY", "GRASS", "INDOOR"}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _sigmoid(z: float) -> float:
    # Numerically stable-ish for our range.
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _now_iso() -> str:
    return datetime.now().isoformat()


def load_player_stats() -> Dict:
    """Load player statistics used by totals model/risk gates."""
    stats_file = TENNIS_DIR / "player_stats.json"
    if stats_file.exists():
        try:
            return json.loads(stats_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def detect_surface(raw_text: str, surface_override: Optional[str]) -> Optional[str]:
    """Detect surface from override or from the pasted text."""
    if surface_override:
        s = surface_override.strip().upper()
        return s if s in VALID_SURFACES else None

    text = raw_text.upper()

    # Allow simple headers like: "SURFACE: HARD" or "Surface=Clay"
    for surf in VALID_SURFACES:
        if f"SURFACE: {surf}" in text or f"SURFACE={surf}" in text:
            return surf

    # Fallback: if the raw text contains the surface keyword, accept.
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
    """Support a few likely keys without forcing a schema migration."""
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

    # ISO date key
    if player_stats.get("injury_return_date"):
        return _days_since(str(player_stats["injury_return_date"]))

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

    # If only last match is tracked, treat that as within last 2.
    if bool(player_stats.get("retired_last_match", False)):
        return True

    return False


def _is_qualifier(player: str, player_stats: Dict) -> bool:
    if bool(player_stats.get("is_qualifier", False)):
        return True
    return "QUALIFIER" in player.upper() or player.strip().upper() in {"Q", "QUAL"}


def _is_top10(player: str, player_stats: Dict, surface: str, elo_data: Dict) -> bool:
    # Prefer explicit ranking if available.
    for k in ("rank", "atp_rank", "wta_rank"):
        if k in player_stats and player_stats[k] is not None:
            try:
                return int(player_stats[k]) <= 10
            except Exception:
                pass

    # Fallback: treat very high Elo as proxy for top-10.
    elo = get_player_elo(player, surface, elo_data)
    return elo >= 2000


def run_totals_risk_gates(
    player_a: str,
    player_b: str,
    surface: Optional[str],
    total_line: float,
    best_of: int,
    stats: Dict,
    elo_data: Dict,
) -> Tuple[bool, List[str]]:
    """Return (passed, reasons). Reasons non-empty means blocked."""

    reasons: List[str] = []

    # Gate 1: Unknown surface
    if not surface or surface not in VALID_SURFACES:
        reasons.append("UNKNOWN_SURFACE")
        return False, reasons

    # Gate 2: Bo5 block unless line >= 36.5
    if best_of == 5 and total_line < 36.5:
        reasons.append("BO5_LOW_TOTAL_LINE")

    # Gate 3: Retired in last 2 matches
    for p in (player_a, player_b):
        if _retired_in_last_2(stats.get(p, {})):
            reasons.append(f"RETIRED_LAST_2::{p}")

    # Gate 4: Injury return <= 14 days
    for p in (player_a, player_b):
        days = _injury_return_days_ago(stats.get(p, {}))
        if days is not None and days <= 14:
            reasons.append(f"INJURY_RETURN_LE_14D::{p} ({days}d)")

    # Gate 5: Qualifier vs top-10 mismatch
    a_stats = stats.get(player_a, {})
    b_stats = stats.get(player_b, {})
    a_qual = _is_qualifier(player_a, a_stats)
    b_qual = _is_qualifier(player_b, b_stats)
    if a_qual != b_qual:
        # If exactly one is qualifier, block if the other is top-10.
        if a_qual and _is_top10(player_b, b_stats, surface, elo_data):
            reasons.append("QUALIFIER_VS_TOP10")
        if b_qual and _is_top10(player_a, a_stats, surface, elo_data):
            reasons.append("QUALIFIER_VS_TOP10")

    return len(reasons) == 0, reasons


def _stat_with_surface_fallback(player_stats: Dict, base_key: str, surface: str, default: float) -> float:
    # Try surface-specific keys like: serve_hold_hard
    key_surface = f"{base_key}_{surface.lower()}"
    if key_surface in player_stats and player_stats[key_surface] is not None:
        try:
            return float(player_stats[key_surface])
        except Exception:
            pass
    if base_key in player_stats and player_stats[base_key] is not None:
        try:
            return float(player_stats[base_key])
        except Exception:
            pass
    return float(default)


def estimate_base_games(
    player_a: str,
    player_b: str,
    surface: str,
    stats: Dict,
    elo_data: Dict,
) -> Tuple[float, Dict]:
    """Estimate base expected total games (best-of-3 baseline)."""

    a = stats.get(player_a, {})
    b = stats.get(player_b, {})

    hold_a = _stat_with_surface_fallback(a, "serve_hold", surface, 0.80)
    hold_b = _stat_with_surface_fallback(b, "serve_hold", surface, 0.80)

    # "break% allowed" is a bit ambiguous. We support either explicit value or derive from hold%.
    break_allowed_a = _stat_with_surface_fallback(a, "break_allowed", surface, 1.0 - hold_a)
    break_allowed_b = _stat_with_surface_fallback(b, "break_allowed", surface, 1.0 - hold_b)

    tiebreak_a = _stat_with_surface_fallback(a, "tiebreak_rate", surface, 0.22)
    tiebreak_b = _stat_with_surface_fallback(b, "tiebreak_rate", surface, 0.22)

    straight_a = _stat_with_surface_fallback(a, "straight_set_rate", surface, 0.62)
    straight_b = _stat_with_surface_fallback(b, "straight_set_rate", surface, 0.62)

    matches_5d_a = int(a.get("matches_last_5_days", 0) or 0)
    matches_5d_b = int(b.get("matches_last_5_days", 0) or 0)

    elo_a = get_player_elo(player_a, surface, elo_data)
    elo_b = get_player_elo(player_b, surface, elo_data)
    elo_gap = abs(elo_a - elo_b)

    # Scaled 0..1: closer matchup => longer match.
    closeness = 1.0 - _clamp(elo_gap / 600.0, 0.0, 1.0)

    hold_avg = (hold_a + hold_b) / 2.0
    tiebreak_avg = (tiebreak_a + tiebreak_b) / 2.0
    straight_avg = (straight_a + straight_b) / 2.0
    fatigue_total = matches_5d_a + matches_5d_b

    surface_adj = {
        "GRASS": 0.8,
        "HARD": 0.2,
        "INDOOR": 0.4,
        "CLAY": -0.4,
    }.get(surface, 0.0)

    base = 22.0
    base += surface_adj

    # Heuristics: higher holds + more tiebreaks => more games.
    base += (hold_avg - 0.80) * 12.0
    base += (tiebreak_avg - 0.20) * 14.0

    # Closer matchup => longer sets / three-set likelihood.
    base += (closeness - 0.50) * 6.0

    # Straight-set tendencies shorten matches.
    base -= (straight_avg - 0.60) * 8.0

    # Fatigue increases variance/breaks; treat as slightly shortening total.
    base -= _clamp(fatigue_total, 0.0, 6.0) * 0.4

    details = {
        "hold_a": round(hold_a, 4),
        "hold_b": round(hold_b, 4),
        "break_allowed_a": round(break_allowed_a, 4),
        "break_allowed_b": round(break_allowed_b, 4),
        "tiebreak_rate_a": round(tiebreak_a, 4),
        "tiebreak_rate_b": round(tiebreak_b, 4),
        "straight_set_rate_a": round(straight_a, 4),
        "straight_set_rate_b": round(straight_b, 4),
        "matches_last_5_days_a": matches_5d_a,
        "matches_last_5_days_b": matches_5d_b,
        "elo_a": round(elo_a, 1),
        "elo_b": round(elo_b, 1),
        "elo_gap": round(elo_gap, 1),
        "closeness": round(closeness, 4),
        "surface_adj": surface_adj,
        "base_games": round(base, 3),
    }

    return base, details


def assign_tier(probability: float) -> str:
    if probability >= 0.66:
        return "STRONG"
    if probability >= 0.58:
        return "LEAN"
    return "NO_PLAY"


def make_edge_id(player_a: str, player_b: str, surface: str, total_line: float) -> str:
    a = player_a.replace(" ", "_")
    b = player_b.replace(" ", "_")
    return f"TENNIS_TOTALS::{a}::{b}::{surface}::{total_line:.1f}"


def make_match_id(player_a: str, player_b: str, surface: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    a3 = player_a[:3].upper().replace(" ", "")
    b3 = player_b[:3].upper().replace(" ", "")
    return f"TOT_{surface}_{a3}_{b3}_{date_str}"


def build_totals_edge(
    player_a: str,
    player_b: str,
    surface: Optional[str],
    total_line: float,
    best_of: int,
    stats: Dict,
    elo_data: Dict,
    allowed_directions: Optional[set] = None,
) -> Dict:
    """Create a totals edge dict for the matchup and total line."""

    # Canonical ordering for uniqueness
    pa, pb = sorted([player_a, player_b])

    match_id = make_match_id(pa, pb, surface or "UNKNOWN")

    passed, reasons = run_totals_risk_gates(pa, pb, surface, total_line, best_of, stats, elo_data)
    if not passed:
        return {
            "edge_id": make_edge_id(pa, pb, (surface or "UNKNOWN"), float(total_line)),
            "sport": "TENNIS",
            "match_id": match_id,
            "player_a": pa,
            "player_b": pb,
            "entity": f"{pa} vs {pb}",
            "market": "TOTAL_GAMES",
            "surface": surface,
            "line": float(total_line),
            "direction": None,
            "probability": None,
            "tier": "BLOCKED",
            "edge": None,
            "risk_tag": "TOTALS_ONLY",
            "blocked": True,
            "block_reason": reasons,
            "generated_at": _now_iso(),
        }

    # If risk gates passed, surface must be known and valid.
    assert surface is not None
    surf = surface

    base_games, feat = estimate_base_games(pa, pb, surf, stats, elo_data)
    diff = base_games - float(total_line)

    # Sigmoid of delta between modeled base games and market line.
    k = 0.35
    prob_over_raw = _sigmoid(k * diff)

    # Compute both directions; then select an allowed direction if availability is known.
    prob_over_dir_raw = prob_over_raw
    prob_under_dir_raw = 1.0 - prob_over_raw

    if allowed_directions:
        allowed = {str(x).upper() for x in allowed_directions}
        candidates = []
        if "OVER" in allowed:
            candidates.append(("OVER", prob_over_dir_raw))
        if "UNDER" in allowed:
            candidates.append(("UNDER", prob_under_dir_raw))

        if not candidates:
            return {
                "edge_id": make_edge_id(pa, pb, surf, float(total_line)),
                "sport": "TENNIS",
                "match_id": match_id,
                "player_a": pa,
                "player_b": pb,
                "entity": f"{pa} vs {pb}",
                "market": "TOTAL_GAMES",
                "surface": surf,
                "line": float(total_line),
                "direction": None,
                "probability": None,
                "tier": "BLOCKED",
                "edge": None,
                "risk_tag": "TOTALS_ONLY",
                "blocked": True,
                "block_reason": ["DIRECTION_NOT_AVAILABLE"],
                "generated_at": _now_iso(),
            }

        direction, prob_dir_raw = max(candidates, key=lambda t: t[1])
    else:
        if prob_over_raw >= 0.5:
            direction = "OVER"
            prob_dir_raw = prob_over_dir_raw
        else:
            direction = "UNDER"
            prob_dir_raw = prob_under_dir_raw

    probability = _clamp(prob_dir_raw, 0.55, 0.72)
    tier = assign_tier(probability)

    # Even-odds implied baseline.
    implied = 0.50
    edge = probability - implied

    return {
        "edge_id": make_edge_id(pa, pb, surf, float(total_line)),
        "sport": "TENNIS",
        "match_id": match_id,
        "player_a": pa,
        "player_b": pb,
        "entity": f"{pa} vs {pb}",
        "market": "TOTAL_GAMES",
        "surface": surf,
        "line": float(total_line),
        "direction": direction,
        "probability": round(probability, 4),
        "tier": tier,
        "edge": round(edge, 4),
        "risk_tag": "TOTALS_ONLY",
        "blocked": False,
        "block_reason": None,
        "features": feat,
        "prob_details": {
            "base_games": round(base_games, 3),
            "diff_base_minus_line": round(diff, 3),
            "sigmoid_k": k,
            "prob_over_raw": round(prob_over_raw, 4),
            "prob_direction_raw": round(prob_dir_raw, 4),
            "probability_clamped": round(probability, 4),
        },
        "generated_at": _now_iso(),
    }


def _extract_total_game_candidates(props: Iterable[TennisProp]) -> List[Tuple[str, float]]:
    """Return list of (match_info, line) candidates from Games Played props."""
    out: List[Tuple[str, float]] = []
    for p in props:
        if (p.stat or "").strip().lower() == "games played":
            out.append((p.match_info or "", float(p.line)))
    return out


def _group_match_players(props: List[TennisProp]) -> Dict[str, List[str]]:
    """Group full player names by match_info."""
    groups: Dict[str, List[str]] = {}
    for p in props:
        key = (p.match_info or "").strip()
        if not key:
            continue
        groups.setdefault(key, [])
        if p.player and p.player not in groups[key]:
            groups[key].append(p.player)
    return groups


def generate_totals_edges_from_paste(
    raw_paste: str,
    surface_override: Optional[str] = None,
    best_of_override: Optional[int] = None,
    max_per_side: int = 5,
) -> Dict:
    """Generate totals edges and return the output document."""

    surface = detect_surface(raw_paste, surface_override)
    best_of = detect_best_of(raw_paste, best_of_override)

    props = parse_tennis_props(raw_paste)
    candidates = _extract_total_game_candidates(props)
    players_by_match = _group_match_players(props)

    # If the props parser didn't find match totals, try the alternate Underdog Total Games paste.
    alt_candidates = []
    if not candidates:
        try:
            alt_candidates = parse_underdog_total_games_paste(raw_paste)
        except Exception:
            alt_candidates = []

    stats = load_player_stats()
    elo_data = load_elo_ratings()

    edges_all: List[Dict] = []

    # Match-level uniqueness: (playerA, playerB, surface, line)
    seen = set()

    if candidates:
        for match_info, line in candidates:
            players = players_by_match.get(match_info, [])
            if len(players) >= 2:
                p1, p2 = players[0], players[1]
            else:
                # Fallback: try to pick from any prop that has that match_info.
                related = [p for p in props if (p.match_info or "").strip() == match_info]
                if related:
                    p1 = related[0].player
                    p2 = related[0].opponent or "TBD"
                else:
                    continue

            pa, pb = sorted([p1, p2])
            key = (pa, pb, surface, float(line))
            if key in seen:
                continue
            seen.add(key)

            edge = build_totals_edge(pa, pb, surface, float(line), best_of, stats, elo_data)
            edges_all.append(edge)
    else:
        # Alternate Total Games paste candidates include direction availability.
        for c in alt_candidates:
            pa, pb = sorted([c.player_a, c.player_b])
            key = (pa, pb, surface, float(c.line))
            if key in seen:
                continue
            seen.add(key)

            edge = build_totals_edge(
                pa,
                pb,
                surface,
                float(c.line),
                best_of,
                stats,
                elo_data,
                allowed_directions=set(c.allowed_directions),
            )
            edges_all.append(edge)

    blocked = [e for e in edges_all if e.get("blocked")]
    playable = [e for e in edges_all if not e.get("blocked") and e.get("tier") in ("STRONG", "LEAN")]

    overs = [e for e in playable if e.get("direction") == "OVER"]
    unders = [e for e in playable if e.get("direction") == "UNDER"]

    overs.sort(key=lambda e: (e.get("probability") or 0.0), reverse=True)
    unders.sort(key=lambda e: (e.get("probability") or 0.0), reverse=True)

    overs = overs[:max_per_side]
    unders = unders[:max_per_side]

    output = {
        "sport": "TENNIS",
        "engine": "TENNIS_TOTALS_ENGINE_v1",
        "generated_at": _now_iso(),
        "surface": surface,
        "best_of": best_of,
        "market": "TOTAL_GAMES",
        "total_candidates": len(candidates) if candidates else len(alt_candidates),
        "unique_matches": len(seen),
        "total_edges": len(edges_all),
        "blocked_count": len(blocked),
        "overs": overs,
        "unders": unders,
        "edges": overs + unders,
    }

    return output


def save_output(doc: Dict) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = OUTPUTS_DIR / f"tennis_totals_edges_{timestamp}.json"
    output_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    latest_file = OUTPUTS_DIR / "tennis_totals_edges_latest.json"
    latest_file.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    return output_file


def _interactive_paste() -> str:
    print("\nPaste Underdog tennis props (Enter twice when done):")
    lines: List[str] = []
    empty = 0
    while empty < 2:
        line = input()
        if not line.strip():
            empty += 1
        else:
            empty = 0
            lines.append(line)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate tennis total games edges (totals-only).")
    parser.add_argument("--paste-file", type=str, default=None, help="Path to a text file with copied Underdog props")
    parser.add_argument("--surface", type=str, default=None, help="Override surface (HARD/CLAY/GRASS/INDOOR)")
    parser.add_argument("--best-of", type=int, default=None, help="Override match format (3 or 5)")
    parser.add_argument("--max-per-side", type=int, default=5, help="Top N overs and top N unders to output")

    args = parser.parse_args()

    if args.paste_file:
        raw = Path(args.paste_file).read_text(encoding="utf-8")
    else:
        raw = _interactive_paste()

    doc = generate_totals_edges_from_paste(
        raw_paste=raw,
        surface_override=args.surface,
        best_of_override=args.best_of,
        max_per_side=int(args.max_per_side),
    )

    out_path = save_output(doc)

    playable_count = len(doc.get("edges", []))
    print("\n" + "=" * 65)
    print("TENNIS TOTALS — TOP EDGES")
    print("=" * 65)
    print(f"Engine: {doc.get('engine')} | Surface: {doc.get('surface')} | Best-of: {doc.get('best_of')}")
    print(f"Candidates: {doc.get('total_candidates')} | Unique matches: {doc.get('unique_matches')} | Blocked: {doc.get('blocked_count')}")
    print(f"Output: {out_path}")

    if playable_count == 0:
        print("\n(No playable edges after gates/tiers.)")
        return 0

    def _print_edge(e: Dict):
        print(f"  [{e.get('tier')}] {e.get('entity')} | {e.get('surface')} | {e.get('direction')} {e.get('line')} | P={e.get('probability'):.1%} | edge={e.get('edge'):+.1%}")

    if doc.get("overs"):
        print("\nTop OVERS")
        for e in doc["overs"]:
            _print_edge(e)

    if doc.get("unders"):
        print("\nTop UNDERS")
        for e in doc["unders"]:
            _print_edge(e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
