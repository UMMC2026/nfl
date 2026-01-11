import json
import random
import argparse
from pathlib import Path
from typing import List, Dict
import sys

# Ensure workspace root is on sys.path when running as a script
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from ufa.analysis.payouts import power_table, flex_table, PayoutTable
from ufa.analysis.prob import prob_hit
from ufa.optimizer.entry_builder import build_entries


def load_picks(path: str) -> List[Dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    # Convert to internal ranked structure with p_hit
    ranked = []
    for i, p in enumerate(raw):
        p_hit = prob_hit(p["line"], p["direction"], recent_values=p.get("recent_values"), mu=p.get("mu"), sigma=p.get("sigma"))
        ranked.append({
            "id": i,
            "league": p["league"],
            "player": p["player"],
            "team": p["team"],
            "stat": p["stat"],
            "line": p["line"],
            "direction": p["direction"],
            "p_hit": float(p_hit),
        })
    return ranked


def simulate_entry_ev(p_list: List[float], table: PayoutTable, legs: int, trials: int = 200000, seed: int = 42) -> Dict:
    rng = random.Random(seed)
    payout_map = table.payout_units.get(legs, {})
    total = 0.0
    total_sq = 0.0
    sweeps = 0
    for _ in range(trials):
        k = 0
        for p in p_list:
            hit = 1 if rng.random() < p else 0
            k += hit
        payout = float(payout_map.get(k, 0.0))
        total += payout
        total_sq += payout * payout
        if k == legs:
            sweeps += 1
    mean_payout = total / trials
    var_payout = max(0.0, total_sq / trials - mean_payout ** 2)
    ev_units = mean_payout - 1.0
    return {
        "legs": legs,
        "mean_payout": round(mean_payout, 6),
        "ev_units": round(ev_units, 6),
        "variance": round(var_payout, 6),
        "stddev": round(var_payout ** 0.5, 6),
        "sweep_prob": round(sweeps / trials, 6),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="picks.json")
    ap.add_argument("--format", choices=["power", "flex"], default="power")
    ap.add_argument("--legs", type=int, default=8)
    ap.add_argument("--min-teams", type=int, default=3)
    ap.add_argument("--max-player-legs", type=int, default=1)
    ap.add_argument("--max-team-legs", type=int, default=3)
    ap.add_argument("--corr-penalty", type=float, default=0.35)
    ap.add_argument("--max-entries", type=int, default=5)
    ap.add_argument("--trials", type=int, default=200000)
    args = ap.parse_args()

    ranked = load_picks(args.file)
    table = power_table() if args.format == "power" else flex_table()

    entries = build_entries(
        picks=ranked,
        payout_table=table,
        legs=args.legs,
        min_teams=args.min_teams,
        max_entries=args.max_entries,
        same_team_penalty=0.0,
        max_player_legs=args.max_player_legs,
        max_team_legs=args.max_team_legs,
        correlation_penalty=args.corr_penalty,
    )

    if not entries:
        print("No entries built under constraints.")
        return

    report = {"format": args.format, "legs": args.legs, "entries": []}
    for i, e in enumerate(entries, 1):
        sim = simulate_entry_ev(e["p_list"], table, args.legs, trials=args.trials, seed=123 + i)
        report["entries"].append({
            "rank": i,
            "ev_units": e["ev_units"],
            "teams": e["teams"],
            "players": e["players"],
            "stats": e.get("stats", []),
            "p_list": e["p_list"],
            "simulation": sim,
        })

    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"monte_carlo_{args.format}_{args.legs}L.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(f"Saved Monte Carlo report to {out_path}")


if __name__ == "__main__":
    main()
