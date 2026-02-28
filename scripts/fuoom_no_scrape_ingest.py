#!/usr/bin/env python3
"""FUOOM No-Scrape Ingest (Odds API -> validate -> set slate)

This is the non-interactive equivalent of the menu option:
  [1A] Auto-Scrape Props 0 [9] FUOOM No-Scrape Ingest

Why this exists:
- Calling the menu function from automation can be fragile due to interactive prompts.
- This script runs the same workflow end-to-end without requiring user input.

Usage (PowerShell):
    .venv\\Scripts\\python.exe scripts\\fuoom_no_scrape_ingest.py --sport NBA

Requires:
- ODDS_API_KEY in repo root .env
- pandas installed (to read the validated parquet)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

# Make repo modules importable when this script is run via a relative path.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path=str((PROJECT_ROOT / ".env").resolve()), override=False)
        # Also do a refresh load in case the current process already had empty values.
        load_dotenv(dotenv_path=str((PROJECT_ROOT / ".env").resolve()), override=True)
    except Exception:
        return


def _set_active_slate(output_path: Path, *, label: str) -> None:
    """Update the canonical active slate pointers used by menu.py."""
    try:
        # Reuse the shared helper so behavior stays consistent.
        import convert_scraped  # type: ignore

        convert_scraped._set_active_slate(output_path, label=label)  # pylint: disable=protected-access
        return
    except Exception:
        # Fallback: best-effort write canonical pointer.
        try:
            state_dir = PROJECT_ROOT / "state"
            state_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "path": str(output_path),
                "label": label,
                "updated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            (state_dir / "active_slate.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass


def _find_latest_validated_parquet(*, sport: str) -> Optional[Path]:
    processed = PROJECT_ROOT / "data" / "processed"
    if not processed.exists():
        return None
    files = sorted(processed.glob(f"validated_props_{sport}_*.parquet"))
    return files[-1] if files else None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sport",
        default="NBA",
        help=(
            "Sport tag for Odds API ingest (e.g., NBA/WNBA/NHL/NFL/MLB, or SOCCER / SOCCER_EPL / SOCCER_MLS). "
            "For generic SOCCER, set ODDS_API_SOCCER_SPORT_KEY (default: soccer_epl)."
        ),
    )
    args = ap.parse_args(argv)

    sport = (args.sport or "NBA").strip().upper()

    _load_dotenv()

    api_key = (os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY") or "").strip()
    if not api_key:
        print("\n Missing ODDS_API_KEY. Set it in the repo root .env and retry.")
        print(f"  Expected: {(PROJECT_ROOT / '.env').resolve()}")
        return 2

    # Stage 1: ingest
    try:
        from ingestion.prop_ingestion_pipeline import run_odds_api

        ingested = run_odds_api(sport=sport)
    except Exception as e:
        print(f"\n Odds API ingest failed: {e}")
        return 3

    if not ingested:
        print("\n Odds API ingest returned 0 props. Check credits/markets/bookmakers.")
        return 4

    # Stage 2: validate
    try:
        from src.validation.validate_scraped_data import main as validate_main

        validate_main(["--sport", sport, "--allow-discrepancies", "--platforms", "oddsapi"])
    except Exception as e:
        print(f"\n Validation failed: {e}")
        return 5

    # Stage 3: set slate from validated parquet
    latest = _find_latest_validated_parquet(sport=sport)
    if not latest:
        print("\n No validated parquet found in data/processed")
        return 6

    try:
        import pandas as pd  # type: ignore

        df = pd.read_parquet(latest)
    except Exception as e:
        print(f"\n Could not read validated parquet: {latest.name}: {e}")
        return 7

    if getattr(df, "empty", False):
        print("\n Validated parquet is empty")
        return 8

    menu_props: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        player = row.get("player_normalized") or row.get("player")
        stat = row.get("stat_normalized") or row.get("stat")
        line = row.get("line")
        direction = row.get("direction")

        # Guard against NaN and missing values.
        if not (player and stat and direction):
            continue
        if line is None:
            continue
        try:
            # pandas NaN check: NaN != NaN
            if line != line:  # noqa: PLR0124
                continue
        except Exception:
            continue

        try:
            line_f = float(line)
        except Exception:
            continue

        prop: Dict[str, Any] = {
            "player": str(player),
            "stat": str(stat),
            "line": line_f,
            "direction": str(direction),
            "league": sport,
            "source": str(row.get("platform") or "OddsAPI"),
        }

        for k in [
            "event_id",
            "commence_time",
            "home_team",
            "away_team",
            "bookmaker_key",
            "market_key",
        ]:
            try:
                v = row.get(k)
                if v is None:
                    continue
                if v != v:
                    continue
                prop[k] = str(v)
            except Exception:
                continue

        if prop.get("away_team") and prop.get("home_team"):
            prop.setdefault("matchup_away", prop.get("away_team"))
            prop.setdefault("matchup_home", prop.get("home_team"))

        menu_props.append(prop)

    if not menu_props:
        print("\n Could not build any slate plays from validated data")
        return 9

    label = f"ODDSAPI_{sport}_{date.today().strftime('%Y%m%d')}"
    ts = datetime.now().strftime("%H%M%S")
    out_path = (OUTPUTS_DIR / f"{label}_FUOOM_VALIDATED_{date.today().strftime('%Y%m%d')}_{ts}.json").resolve()

    # === FRESHNESS VALIDATION ===
    today_str = date.today().strftime("%Y-%m-%d")
    stale_props = []
    fresh_props = []
    games_by_date = {}
    for prop in menu_props:
        ct = prop.get("commence_time", "")
        if ct:
            game_date = ct[:10]  # Extract YYYY-MM-DD from ISO timestamp
            games_by_date[game_date] = games_by_date.get(game_date, 0) + 1
            if game_date < today_str:
                stale_props.append(prop)
            else:
                fresh_props.append(prop)
        else:
            fresh_props.append(prop)  # No timestamp = can't verify, keep

    print(f"\n  [FRESHNESS CHECK]")
    for gd, cnt in sorted(games_by_date.items()):
        marker = "TODAY" if gd == today_str else ("TOMORROW" if gd > today_str else "STALE")
        print(f"    {gd}: {cnt} props ({marker})")

    if stale_props:
        print(f"  [WARNING] {len(stale_props)} props have PAST commence_time (stale data)")
        print(f"  [ACTION] Removing {len(stale_props)} stale props, keeping {len(fresh_props)}")
        menu_props = fresh_props

    if not menu_props:
        print("\n All OddsAPI props were stale (past games). No fresh data available.")
        return 9

    out_payload = {"plays": menu_props, "raw_lines": []}
    out_path.write_text(json.dumps(out_payload, indent=2), encoding="utf-8")

    _set_active_slate(out_path, label=label)

    print("\n FUOOM No-Scrape ingest complete")
    print(f"   Sport: {sport}")
    print(f"   Ingested props: {len(ingested)}")
    print(f"   Validated props: {len(menu_props)}")
    if stale_props:
        print(f"   Stale removed: {len(stale_props)}")
    # Show unique games
    unique_games = set()
    for p in menu_props:
        away = p.get("away_team") or p.get("matchup_away") or "?"
        home = p.get("home_team") or p.get("matchup_home") or "?"
        unique_games.add(f"{away} @ {home}")
    print(f"   Games: {len(unique_games)}")
    for g in sorted(unique_games):
        print(f"     - {g}")
    print(f"   Slate file: {out_path}")
    print("\nNext: run menu.py and press [2] Analyze Slate.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
