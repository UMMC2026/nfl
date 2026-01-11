"""Quick Ollama spot-check for top-N current slate picks.

Usage (from project root, with venv active):

    python ollama_spot_check.py --top 10 --model llama3

This script:
  - Loads `picks_hydrated.json` (and, if present, cross-filters by `picks.json`)
  - Ranks picks by absolute edge |mu - line|
  - Runs the Ollama data validator on the top-N picks
  - Prints a compact, human-readable summary for manual review

It uses the same helper as the hydration validator, but runs purely
on-demand so you can sanity-check tonight's biggest edges before
locking anything in.
"""

from __future__ import annotations

import argparse
import json
from math import fabs
from pathlib import Path
from typing import Any, Dict, List

from ollama.data_validator import validate_pick_with_ollama


PICKS_HYDRATED_PATH = Path("picks_hydrated.json")
PICKS_SOURCE_PATH = Path("picks.json")


def load_current_slate() -> List[Dict[str, Any]]:
    """Load hydrated picks and, if possible, restrict to current slate.

    "Current slate" is defined as the intersection of hydrated picks
    and the raw picks in `picks.json`, keyed by (player, stat, line,
    direction). If `picks.json` is missing, we fall back to all
    hydrated rows.
    """

    if not PICKS_HYDRATED_PATH.exists():
        raise SystemExit("picks_hydrated.json not found – run hydrate_new_picks.py first.")

    picks = json.loads(PICKS_HYDRATED_PATH.read_text(encoding="utf-8"))

    if PICKS_SOURCE_PATH.exists():
        try:
            source = json.loads(PICKS_SOURCE_PATH.read_text(encoding="utf-8"))
            keyset = {
                (
                    sp.get("player"),
                    sp.get("stat"),
                    sp.get("line"),
                    sp.get("direction"),
                )
                for sp in source
            }
            picks = [
                p
                for p in picks
                if (
                    p.get("player"),
                    p.get("stat"),
                    p.get("line"),
                    p.get("direction"),
                ) in keyset
            ]
        except Exception:
            # If anything goes wrong, just use hydrated picks as-is.
            pass

    return picks


def rank_by_edge(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rank picks by absolute edge |mu - line|, descending.

    Falls back to original order when mu/line are missing or invalid.
    """

    def edge_value(p: Dict[str, Any]) -> float:
        mu = p.get("mu")
        line = p.get("line")
        try:
            if isinstance(mu, (int, float)) and isinstance(line, (int, float)):
                return float(fabs(mu - line))
        except Exception:
            pass
        return 0.0

    return sorted(picks, key=edge_value, reverse=True)


def spot_check(top_n: int, model: str | None = None) -> None:
    picks = load_current_slate()
    if not picks:
        print("No picks found for current slate.")
        return

    ranked = rank_by_edge(picks)
    subset = ranked[:top_n]

    print(f"🔍 Running Ollama spot-check on top {len(subset)} picks by |mu - line|…")
    print("")

    for i, p in enumerate(subset, start=1):
        player = p.get("player")
        team = p.get("team")
        stat = p.get("stat")
        line = p.get("line")
        mu = p.get("mu")
        direction = p.get("direction")

        print(f"[{i}] {player} ({team}) {direction} {line} {stat} — mu={mu}")

        result = validate_pick_with_ollama(p, model=model)
        parsed = result.get("ollama_parsed") or {}
        error = result.get("ollama_error")

        if error:
            print(f"    ⚠️ Ollama error: {error}")
        else:
            is_reasonable = parsed.get("is_reasonable")
            correct_team = parsed.get("correct_team")
            notes = parsed.get("notes")

            print(f"    is_reasonable: {is_reasonable}")
            if correct_team and correct_team != (team or "").upper():
                print(f"    team_correction: {team} → {correct_team}")
            if notes:
                print(f"    notes: {notes}")

        print("")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ollama spot-check for top-N picks.")
    parser.add_argument("--top", type=int, default=10, help="Number of picks to check (default: 10)")
    parser.add_argument("--model", type=str, default=None, help="Override OLLAMA_MODEL for this run")
    args = parser.parse_args()

    spot_check(top_n=args.top, model=args.model)


if __name__ == "__main__":
    main()
