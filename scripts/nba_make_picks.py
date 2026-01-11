import json
from pathlib import Path
from typing import List, Dict, Any

"""
Build NBA picks from a small SPEC with neutral priors (mu=line with default sigma).
Use roster gate with data_center/rosters/NBA_active_roster_current.csv when ranking/simulating.
"""

SPEC = [
    # BOS @ POR
    {"player": "Derrick White", "team": "BOS", "opponent": "POR", "stat": "rebounds", "line": 4.5, "direction": "higher"},
    {"player": "Jaylen Brown", "team": "BOS", "opponent": "POR", "stat": "points", "line": 29.5, "direction": "higher"},
    {"player": "Anfernee Simons", "team": "POR", "opponent": "BOS", "stat": "points", "line": 11.5, "direction": "higher"},
    {"player": "Shaedon Sharpe", "team": "POR", "opponent": "BOS", "stat": "points", "line": 23.5, "direction": "higher"},
    {"player": "Donovan Clingan", "team": "POR", "opponent": "BOS", "stat": "rebounds", "line": 11.5, "direction": "higher"},
]

DEFAULT_SIGMA = {
    "points": 4.0,
    "rebounds": 2.0,
    "assists": 2.0,
    "pras": 5.0,
    "3pm": 1.0,
}


def build(out_path: str):
    picks: List[Dict[str, Any]] = []
    for item in SPEC:
        stat = item["stat"]
        picks.append({
            "league": "NBA",
            "player": item["player"],
            "team": item["team"],
            "opponent": item.get("opponent"),
            "stat": stat,
            "line": float(item["line"]),
            "direction": item["direction"],
            "mu": float(item["line"]),
            "sigma": float(DEFAULT_SIGMA.get(stat, 3.0)),
        })
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(picks, indent=2))
    print(f"Wrote {len(picks)} NBA picks to {out_path}")


if __name__ == "__main__":
    import sys
    out = "scripts/bos_por_picks.json"
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        if i + 1 < len(sys.argv):
            out = sys.argv[i+1]
    build(out)
