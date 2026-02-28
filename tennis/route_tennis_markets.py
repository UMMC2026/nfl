"""Tennis Market Router (engine-level separation)

This script prevents the critical failure mode: mixing markets.

Flow:
1) Parse raw Underdog paste
2) Classify by MARKET TYPE (TOTAL_GAMES / TOTAL_SETS / PLAYER_ACES)
3) Route to market-specific engines
4) Enforce correlation control (no duplicate players across selected plays)
5) Output capped plays:
   - Top 3 TOTAL_SETS plays
   - Top 2 PLAYER_ACES plays

This does NOT produce human gambling advice; it produces machine-readable edges
under strict gates.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from tennis_props_parser import parse_tennis_props

# IMPORTANT: These are intentionally local imports (not package-qualified) so the
# script works when executed directly (e.g., `python tennis/route_tennis_markets.py`).
from engines.total_sets_engine_v1 import generate_from_props as gen_total_sets
from engines.player_aces_engine_v1 import generate_from_props as gen_player_aces

# Total games engine stays isolated in its own script (already implemented)
from generate_tennis_totals_edges import generate_totals_edges_from_paste

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _players_in_sets_edge(edge: Dict) -> Set[str]:
    return {str(edge.get("player_a", "")), str(edge.get("player_b", ""))}


def _players_in_aces_edge(edge: Dict) -> Set[str]:
    return {str(edge.get("player", "")), str(edge.get("opponent", ""))}


def apply_correlation_control(sets_doc: Dict, aces_doc: Dict, max_sets: int = 3, max_aces: int = 2) -> Dict:
    """Ensure no player appears across selected plays (hidden correlation control)."""

    selected_sets: List[Dict] = []
    selected_aces: List[Dict] = []

    used_players: Set[str] = set()

    # Sets first (as per spec)
    for e in (sets_doc.get("plays") or [])[:max_sets]:
        ps = {p for p in _players_in_sets_edge(e) if p}
        if ps & used_players:
            continue
        selected_sets.append(e)
        used_players |= ps

    # Then aces, but only if players are clean
    for e in (aces_doc.get("plays") or [])[: max_aces * 3]:  # allow a few extra candidates
        ps = {p for p in _players_in_aces_edge(e) if p}
        if ps & used_players:
            continue
        selected_aces.append(e)
        used_players |= ps
        if len(selected_aces) >= max_aces:
            break

    return {
        "total_sets": selected_sets,
        "player_aces": selected_aces,
        "used_players": sorted(used_players),
    }


def route(
    raw_text: str,
    surface: Optional[str] = None,
    best_of: Optional[int] = None,
    env: Optional[str] = None,
) -> Dict:
    props = parse_tennis_props(raw_text)

    # Engines run independently
    sets_doc = gen_total_sets(props, raw_text, surface_override=surface, best_of_override=best_of, max_plays=3)
    aces_doc = gen_player_aces(props, raw_text, surface_override=surface, env_override=env, max_plays=2)

    # Total games engine remains separate (and optional); we don't select plays from it here
    # because spec says this paste includes sets + aces, and we cap output to those markets.
    games_doc = generate_totals_edges_from_paste(raw_text, surface_override=surface, best_of_override=best_of, max_per_side=5)

    selection = apply_correlation_control(sets_doc, aces_doc, max_sets=3, max_aces=2)

    out = {
        "sport": "TENNIS",
        "router": "TENNIS_MARKET_ROUTER_v1",
        "generated_at": _now_iso(),
        "inputs": {
            "surface_override": surface,
            "best_of_override": best_of,
            "env_override": env,
        },
        "markets_detected": {
            "TOTAL_SETS_candidates": sets_doc.get("total_candidates", 0),
            "PLAYER_ACES_candidates": aces_doc.get("total_candidates", 0),
            "TOTAL_GAMES_candidates": games_doc.get("total_candidates", 0),
        },
        "engines": {
            "TOTAL_SETS_ENGINE_v1": {
                "blocked_count": sets_doc.get("blocked_count", 0),
                "playable_count": sets_doc.get("playable_count", 0),
            },
            "PLAYER_ACES_ENGINE_v1": {
                "blocked_count": aces_doc.get("blocked_count", 0),
                "playable_count": aces_doc.get("playable_count", 0),
                "environment": aces_doc.get("environment"),
            },
            "TENNIS_TOTALS_ENGINE_v1": {
                "blocked_count": games_doc.get("blocked_count", 0),
            },
        },
        "selection": {
            "total_sets": selection["total_sets"],
            "player_aces": selection["player_aces"],
            "max_total_sets": 3,
            "max_player_aces": 2,
            "used_players": selection["used_players"],
        },
        "raw": {
            "total_sets_engine": sets_doc,
            "player_aces_engine": aces_doc,
        },
    }

    return out


def save(doc: Dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    fp = OUTPUTS_DIR / f"tennis_routed_{ts}.json"
    fp.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    latest = OUTPUTS_DIR / "tennis_routed_latest.json"
    latest.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    return fp


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
    ap = argparse.ArgumentParser(description="Route tennis props by market and run isolated engines")
    ap.add_argument("--paste-file", type=str, default=None)
    ap.add_argument("--surface", type=str, default=None, help="HARD/CLAY/GRASS/INDOOR")
    ap.add_argument("--best-of", type=int, default=None, help="3 or 5")
    ap.add_argument("--env", type=str, default=None, help="INDOOR or OUTDOOR (required for HARD aces market)")
    args = ap.parse_args()

    raw = Path(args.paste_file).read_text(encoding="utf-8") if args.paste_file else _interactive_paste()

    doc = route(raw_text=raw, surface=args.surface, best_of=args.best_of, env=args.env)
    out_path = save(doc)

    sets_n = len(doc["selection"]["total_sets"])
    aces_n = len(doc["selection"]["player_aces"])

    print("\n" + "=" * 70)
    print("TENNIS ROUTER — CAPPED OUTPUT")
    print("=" * 70)
    print(f"Saved: {out_path}")
    print(f"Selected TOTAL_SETS: {sets_n} (cap 3)")
    print(f"Selected PLAYER_ACES: {aces_n} (cap 2)")
    print(f"Used players: {', '.join(doc['selection']['used_players'])}")

    # We print only structural summaries (not betting advice)
    def _summ(e: Dict) -> str:
        return f"{e.get('market')} | {e.get('entity')} | {e.get('direction')} {e.get('line')} | tier={e.get('tier')} | p={e.get('probability')}"

    if sets_n:
        print("\nTOTAL_SETS (selected)")
        for e in doc["selection"]["total_sets"]:
            print("  - " + _summ(e))

    if aces_n:
        print("\nPLAYER_ACES (selected)")
        for e in doc["selection"]["player_aces"]:
            print("  - " + _summ(e))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
