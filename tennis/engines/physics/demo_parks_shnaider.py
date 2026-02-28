"""Demo: opponent-aware physics props simulation.

This is a *smoke script* meant for local execution.

It uses the existing CalibratedTennisPropsEngine but forces physics mode for the
Monte Carlo backend (TENNIS_PROP_MC_MODE=physics).

Example:
  .venv\Scripts\python.exe tennis/engines/physics/demo_parks_shnaider.py --surface Hard

If player profiles aren't present in tennis_stats.db, the script will report
"Player not found".
"""

from __future__ import annotations

import argparse
import os

from tennis.calibrated_props_engine import CalibratedTennisPropsEngine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surface", default="Hard")
    args = parser.parse_args()

    os.environ.setdefault("TENNIS_PROP_MC_MODE", "physics")

    player = "Alycia Parks"
    opponent = "Diana Shnaider"

    engine = CalibratedTennisPropsEngine()
    try:
        props = [
            {"player": player, "opponent": opponent, "stat": "games_won", "line": 9.5, "direction": "HIGHER"},
            {"player": player, "opponent": opponent, "stat": "games_played", "line": 20.5, "direction": "HIGHER"},
            {"player": player, "opponent": opponent, "stat": "sets_won", "line": 1.5, "direction": "HIGHER"},
            {"player": player, "opponent": opponent, "stat": "aces", "line": 5.5, "direction": "HIGHER"},
            {"player": player, "opponent": opponent, "stat": "double_faults", "line": 3.5, "direction": "LOWER"},
            {"player": player, "opponent": opponent, "stat": "1st_set_games", "line": 9.5, "direction": "HIGHER"},
        ]

        results = engine.analyze_slate(props, surface=args.surface)
        print("\n--- TOP RESULTS (physics_mode first) ---")
        for r in results.get("results", [])[:10]:
            print(
                f"{r.get('player')} | {r.get('stat')} {r.get('line')} {r.get('direction')} -> "
                f"p={r.get('probability'):.3f} conf={r.get('confidence'):.1f} tier={r.get('tier')} "
                f"physics={r.get('physics_mode')}"
            )
    finally:
        engine.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
