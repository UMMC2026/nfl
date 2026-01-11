#!/usr/bin/env python3
"""
Use the repository's hydration wrapper to fetch recent NFL game values and compute
5-game averages for players mentioned in `picks_hydrated.json`.

Usage:
  python scripts/fetch_5game_averages_from_hydrate.py --season 2025 --output outputs/players_5game_averages_2025_2026.csv

This does not require SportsData.io; it uses `ufa.ingest.hydrate.hydrate_recent_values` (nflreadpy/ESPN)
and will skip players that cannot be hydrated.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
import sys
import pathlib

# Ensure repo root is on sys.path so we can import `ufa` package
repo_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))


def load_picks(path: str = "picks_hydrated.json") -> list[dict]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Hydrate NFL picks and compute 5-game averages via repo hydrator")
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g., 2025)")
    parser.add_argument("--output", type=str, default="outputs/players_5game_averages_2025_2026.csv")
    parser.add_argument("--picks", type=str, default="picks_hydrated.json")
    args = parser.parse_args(argv)

    load_dotenv()
    from ufa.ingest.hydrate import hydrate_recent_values

    picks = load_picks(args.picks)
    # collect unique (player, stat, team)
    keys = {}
    for p in picks:
        if p.get("league", "NFL").upper() != "NFL":
            continue
        player = p.get("player")
        stat = p.get("stat")
        team = p.get("team")
        if not player or not stat:
            continue
        keys[(player, stat)] = team

    rows = []
    for (player, stat), team in keys.items():
        try:
            recent = hydrate_recent_values("NFL", player, stat, nfl_seasons=[args.season], last_n=5)
        except Exception as e:
            # Fallback: if pick contains recent_values, use last 5 from there
            print(f"Hydration error for {player} {stat}: {e}. Trying fallback to picks_hydrated.json recent_values...")
            # search for pick entry
            fallback_vals = None
            for p in picks:
                if p.get("player") == player and p.get("stat") == stat and p.get("recent_values"):
                    fallback_vals = p.get("recent_values")
                    break
            if fallback_vals:
                recent = list(fallback_vals)[-5:]
            else:
                print(f"Skipping {player} {stat}: no fallback recent_values available")
                continue
        if not recent:
            print(f"No recent values for {player} {stat}")
            continue
        import math

        mean5 = float(sum(recent) / len(recent)) if recent else float("nan")
        std5 = float(pd.Series(recent).std(ddof=0)) if recent else float("nan")
        rows.append({"player": player, "team": team, "stat": stat, "mean_5": mean5, "std_5": std5, "n": len(recent), "recent_values": json.dumps(recent)})

    out_df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    out_df.to_csv(args.output, index=False)
    print(f"Wrote {len(out_df)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
