#!/usr/bin/env python3
"""
Fetch per-game player stats (from SportsData.io) and compute 5-game rolling averages
for the specified season. Writes CSV with one row per player containing the
most-recent 5-game averages for all numeric stat fields.

Usage:
  python scripts/fetch_5game_averages.py --season 2025 --league NFL --output outputs/players_5game_averages_2025_2026.csv

If you don't have a SportsData API key, provide a local per-game CSV via
--local-file that contains one row per player-game (same schema as SportsData).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv


def fetch_sportsdata_player_game_stats(season: int, league: str, key: str) -> pd.DataFrame:
    league = league.lower()
    if league == "nfl":
        url = f"https://api.sportsdata.io/v3/nfl/stats/json/PlayerGameStatsBySeason/{season}"
    else:
        raise ValueError(f"Unsupported league: {league}. Currently only NFL is supported via SportsData.io endpoint in this script.")

    headers = {"Ocp-Apim-Subscription-Key": key}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    df = pd.DataFrame(data)
    return df


def load_local_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def compute_last_5game_averages(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    # Normalize common column names
    name_col = None
    for cand in ("Name", "Player", "PlayerName"):
        if cand in df.columns:
            name_col = cand
            break

    player_id_col = None
    for cand in ("PlayerID", "PlayerId", "PlayerID"):
        if cand in df.columns:
            player_id_col = cand
            break

    team_col = None
    for cand in ("Team", "TeamName"):
        if cand in df.columns:
            team_col = cand
            break

    # Determine sorting column: prefer GameDate, then Week
    sort_col = None
    if "GameDate" in df.columns:
        df["GameDate"] = pd.to_datetime(df["GameDate"], errors="coerce")
        sort_col = "GameDate"
    elif "Week" in df.columns:
        sort_col = "Week"
    else:
        # fallback to existing index order
        df = df.reset_index(drop=True)
        sort_col = None

    # Select numeric stat columns to average
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    # Remove identifying numeric columns that aren't stats if obvious
    for id_col in (player_id_col, "Season", "GameKey", "GameID", "GameId", "Week"):
        if id_col in numeric_cols:
            numeric_cols.remove(id_col)

    results = []

    group_key = player_id_col if player_id_col is not None else name_col
    if group_key is None:
        raise RuntimeError("Cannot find a player identifier column (PlayerID or Name) in the input data.")

    for player, group in df.groupby(group_key):
        if sort_col is not None:
            group = group.sort_values(by=sort_col)
        else:
            group = group
        group = group.reset_index(drop=True)

        # compute rolling mean over numeric columns with window=5
        if len(group) == 0:
            continue
        if numeric_cols:
            rolling = group[numeric_cols].rolling(window=5, min_periods=1).mean()
            last_rolling = rolling.iloc[-1].to_dict()
        else:
            last_rolling = {}

        # metadata
        name = group[name_col].iloc[-1] if name_col and name_col in group.columns else player
        team = group[team_col].iloc[-1] if team_col and team_col in group.columns else None
        games_count = len(group)

        row = {"player_key": player, "player_name": name, "team": team, "games_count": games_count}
        row.update(last_rolling)
        results.append(row)

    out_df = pd.DataFrame(results)
    # sort by games_count desc then player_name
    out_df = out_df.sort_values(by=["games_count", "player_name"], ascending=[False, True]).reset_index(drop=True)
    return out_df


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch per-game stats and compute 5-game averages for players.")
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g., 2025)")
    parser.add_argument("--league", type=str, default="NFL", help="League (default: NFL)")
    parser.add_argument("--output", type=str, default="outputs/players_5game_averages.csv", help="CSV output path")
    parser.add_argument("--local-file", type=str, help="Optional local per-game CSV file to use instead of SportsData API")
    args = parser.parse_args(argv)

    load_dotenv()
    sd_key = os.getenv("SPORTSDATA_API_KEY")

    if args.local_file:
        print(f"Loading local file: {args.local_file}")
        df = load_local_csv(args.local_file)
    else:
        if not sd_key:
            print("Error: No SPORTSDATA_API_KEY set in environment and no --local-file provided.", file=sys.stderr)
            return 2
        print(f"Fetching season {args.season} {args.league} player game stats from SportsData.io...")
        df = fetch_sportsdata_player_game_stats(args.season, args.league, sd_key)

    if df.empty:
        print("No game-level data available.")
        return 1

    out_df = compute_last_5game_averages(df)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    out_df.to_csv(args.output, index=False)
    print(f"Wrote {len(out_df)} player 5-game averages to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
