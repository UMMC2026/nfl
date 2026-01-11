import sys
import csv
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ufa.ingest.espn import ESPNFetcher

"""
Export a canonical NFL roster CSV for specified teams using ESPN (verifiable source).

Usage:
  python scripts/export_nfl_roster.py CHI SF --out data_center/rosters/NFL_active_roster_current.csv

Columns:
  player_name,team,status,game_id,updated_utc
"""

def main(args):
    if not args:
        print("Usage: python scripts/export_nfl_roster.py TEAM1 TEAM2 [--out OUTFILE] [--game-id GAMEID]")
        sys.exit(1)

    teams = []
    out = "data_center/rosters/NFL_active_roster_current.csv"
    game_id = None

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--out" and i + 1 < len(args):
            out = args[i+1]
            i += 2
        elif a == "--game-id" and i + 1 < len(args):
            game_id = args[i+1]
            i += 2
        else:
            teams.append(a.upper())
            i += 1

    if not teams:
        print("Provide at least one team abbr (e.g., CHI SF)")
        sys.exit(1)

    fetcher = ESPNFetcher(season=2025)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    try:
        for t in teams:
            roster = fetcher.get_team_roster(t)
            for p in roster:
                rows.append({
                    "player_name": p.name,
                    "team": t,
                    "status": p.status.upper() if p.status else "ACTIVE",
                    "game_id": game_id or f"{teams[0]}@{teams[-1]}-2025-Week",
                    "updated_utc": now_iso,
                })
    finally:
        fetcher.close()

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["player_name","team","status","game_id","updated_utc"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} players to {out}")

if __name__ == "__main__":
    main(sys.argv[1:])
