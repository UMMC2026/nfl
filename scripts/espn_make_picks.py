import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ufa.ingest.espn import ESPNFetcher

"""
Build PropPick JSON using ESPN gamelogs for recent_values (verifiable source).

Edit the SPEC list below to add/change props. Supported stat keys:
  - pass_yds, rush_yds, rec_yds, receptions

Example run:
  python scripts/espn_make_picks.py --out scripts/chi_sf_picks.json
"""

SPEC = [
    # CHI @ SF core props (expanded, supported stat keys only)
    {"player": "Caleb Williams", "team": "CHI", "opponent": "SF", "stat": "pass_yds", "line": 224.5, "direction": "higher"},
    {"player": "Caleb Williams", "team": "CHI", "opponent": "SF", "stat": "rush_yds", "line": 16.5, "direction": "higher"},

    {"player": "D'Andre Swift", "team": "CHI", "opponent": "SF", "stat": "rush_yds", "line": 58.5, "direction": "higher"},
    {"player": "D'Andre Swift", "team": "CHI", "opponent": "SF", "stat": "receptions", "line": 2.5, "direction": "higher"},
    {"player": "D'Andre Swift", "team": "CHI", "opponent": "SF", "stat": "rec_yds", "line": 12.5, "direction": "higher"},

    {"player": "Ricky Pearsall", "team": "SF", "opponent": "CHI", "stat": "rec_yds", "line": 39.5, "direction": "higher"},
    {"player": "Ricky Pearsall", "team": "SF", "opponent": "CHI", "stat": "receptions", "line": 3.5, "direction": "higher"},

    {"player": "Cole Kmet", "team": "CHI", "opponent": "SF", "stat": "receptions", "line": 2.5, "direction": "higher"},
    {"player": "Cole Kmet", "team": "CHI", "opponent": "SF", "stat": "rec_yds", "line": 22.5, "direction": "higher"},

    {"player": "Brock Purdy", "team": "SF", "opponent": "CHI", "stat": "pass_yds", "line": 255.5, "direction": "higher"},

    {"player": "Demarcus Robinson", "team": "SF", "opponent": "CHI", "stat": "receptions", "line": 1.5, "direction": "higher"},
    {"player": "Demarcus Robinson", "team": "SF", "opponent": "CHI", "stat": "rec_yds", "line": 16.5, "direction": "higher"},
]

STAT_KEY_MAP = {
    "pass_yds": "pass_yds",
    "rush_yds": "rush_yds",
    "rec_yds": "rec_yds",
    "receptions": "receptions",
}

DEFAULT_SIGMA = {
    "pass_yds": 35.0,
    "rush_yds": 18.0,
    "rec_yds": 22.0,
    "receptions": 1.2,
}


def _recent_values_from_gamelog(fetcher: ESPNFetcher, name: str, stat_key: str, n: int = 8) -> List[float]:
    # Search for player
    s = fetcher.search_player(name)
    if not s or not s.get("id"):
        return []
    games = fetcher.get_player_gamelog(s["id"], limit=n)
    key = STAT_KEY_MAP.get(stat_key)
    if not key:
        return []
    vals: List[float] = []
    for g in games:
        v = g.get("stats", {}).get(key)
        if v is not None:
            vals.append(float(v))
    return vals


def build(out_path: str):
    fetcher = ESPNFetcher(season=2025)
    picks: List[Dict[str, Any]] = []
    try:
        for item in SPEC:
            name = item["player"]
            stat_key = item["stat"]
            recent = _recent_values_from_gamelog(fetcher, name, stat_key, n=8)
            if len(recent) < 2:
                # Fallback: neutral prior with line as mean and default sigma
                print(f"Warning: insufficient gamelog for {name} {stat_key}; using neutral prior mu=line, default sigma")
                mu = float(item["line"])
                sigma = float(DEFAULT_SIGMA.get(stat_key, 20.0))
                payload = {
                    "league": "NFL",
                    "player": name,
                    "team": item.get("team"),
                    "opponent": item.get("opponent"),
                    "stat": stat_key,
                    "line": float(item["line"]),
                    "direction": item["direction"],
                    "mu": mu,
                    "sigma": sigma,
                }
            else:
                payload = {
                    "league": "NFL",
                    "player": name,
                    "team": item.get("team"),
                    "opponent": item.get("opponent"),
                    "stat": stat_key,
                    "line": float(item["line"]),
                    "direction": item["direction"],
                    "recent_values": recent,
                }
            picks.append(payload)
    finally:
        fetcher.close()

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(picks, indent=2))
    print(f"Wrote {len(picks)} picks to {out_path}")


if __name__ == "__main__":
    import sys
    out = "scripts/chi_sf_picks.json"
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        if i + 1 < len(sys.argv):
            out = sys.argv[i+1]
    build(out)
