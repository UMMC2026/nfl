"""
Generate official 10-game per-game averages for key players
and emit a corrected analysis file for Jan 03, 2026.

Outputs:
- outputs/ground_truth_jan03.json
- outputs/CORRECTED_ANALYSIS_JAN03.txt
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from nba_api.stats.endpoints import leaguedashplayerstats

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Target players and their primary props for this slate
TARGET_PROPS = {
    "Jordan Clarkson": "assists",
    "OG Anunoby": "pts+reb+ast",
    "Bobby Portis": "rebounds",
    "Myles Turner": "pts+reb+ast",
}

GROUND_TRUTH_FILE = OUTPUT_DIR / "ground_truth_jan03.json"
CORRECTED_FILE = OUTPUT_DIR / "CORRECTED_ANALYSIS_JAN03.txt"


def fetch_last10_per_game(players: List[str]) -> Tuple[Dict[str, dict], List[str]]:
    """Fetch 10-game per-game stats from NBA official endpoint."""
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season="2025-26",
        per_mode_detailed="PerGame",
        last_n_games=10,
    )
    df = stats.get_data_frames()[0]
    subset = df[df["PLAYER_NAME"].isin(players)]

    result: Dict[str, dict] = {}
    for _, row in subset.iterrows():
        name = row["PLAYER_NAME"]
        result[name] = {
            "team": row["TEAM_ABBREVIATION"],
            "games_played": int(row["GP"]),
            "minutes": float(row["MIN"]),
            "points": float(row["PTS"]),
            "rebounds": float(row["REB"]),
            "assists": float(row["AST"]),
            "pra": float(row["PTS"] + row["REB"] + row["AST"]),
            "last_n_games": 10,
        }

    missing = sorted(set(players) - set(subset["PLAYER_NAME"]))
    return result, missing


def load_model_picks() -> List[dict]:
    """Load hydrated picks to compare against ground truth."""
    picks_path = Path("picks_hydrated.json")
    if not picks_path.exists():
        raise FileNotFoundError("picks_hydrated.json not found")
    return json.load(open(picks_path, encoding="utf-8"))


def find_pick_for_player(picks: List[dict], player: str, desired_stat: str) -> dict | None:
    """Find the pick matching the desired stat for a player."""
    candidates = [p for p in picks if p.get("player") == player]
    # Exact stat match first
    for p in candidates:
        if p.get("stat") == desired_stat:
            return p
    # Fallback to first candidate if stat variant differs (e.g., pra vs pts+reb+ast)
    return candidates[0] if candidates else None


def verdict(model_avg: float | None, official_avg: float | None, line: float | None) -> str:
    if official_avg is None:
        return "No official data"
    if model_avg is None:
        return "Model missing avg"
    if line is None:
        return "No line provided"

    diff_pct = abs(model_avg - official_avg) / official_avg if official_avg else 0
    if diff_pct > 0.50:
        return f"Mismatch ({model_avg:.1f} vs {official_avg:.1f}, {diff_pct*100:.0f}% diff)"
    if official_avg < line and model_avg > line:
        return "Model overstates over edge"
    if official_avg > line and model_avg < line:
        return "Model understates over edge"
    return "Aligned within tolerance"


def write_corrected_report(ground_truth: Dict[str, dict], missing: List[str], picks: List[dict]):
    lines: List[str] = []
    lines.append("CORRECTED ANALYSIS — Jan 03, 2026")
    lines.append("Generated: " + datetime.now(timezone.utc).isoformat())
    lines.append("Source: NBA.com stats (Last 10 games, PerGame)")
    lines.append("")

    for player, desired_stat in TARGET_PROPS.items():
        gt = ground_truth.get(player)
        pick = find_pick_for_player(picks, player, desired_stat)

        model_avg = pick.get("mu") if pick else None
        line_val = pick.get("line") if pick else None
        direction = pick.get("direction") if pick else None
        official_avg = None
        if gt:
            if desired_stat in ("pts+reb+ast", "pra"):
                official_avg = gt.get("pra")
            elif desired_stat == "rebounds":
                official_avg = gt.get("rebounds")
            elif desired_stat == "assists":
                official_avg = gt.get("assists")
            elif desired_stat == "points":
                official_avg = gt.get("points")

        lines.append(f"Player: {player}")
        lines.append(f"  Prop: {direction or 'N/A'} {line_val or 'N/A'} {desired_stat}")
        if gt:
            lines.append(
                f"  Official Last10 Avg: {official_avg if official_avg is not None else 'N/A'} (team={gt['team']}, games={gt['games_played']})"
            )
        else:
            lines.append("  Official Last10 Avg: NOT FOUND (did not qualify or no games)")
        lines.append(f"  Model Avg: {model_avg if model_avg is not None else 'N/A'}")
        lines.append(f"  Verdict: {verdict(model_avg, official_avg, line_val)}")
        lines.append("")

    if missing:
        lines.append("Missing from NBA Last10 dataset: " + ", ".join(missing))

    CORRECTED_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Corrected analysis written to {CORRECTED_FILE}")


def main():
    players = list(TARGET_PROPS.keys())
    ground_truth, missing = fetch_last10_per_game(players)

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "season": "2025-26",
        "last_n_games": 10,
        "players": ground_truth,
        "missing": missing,
    }
    GROUND_TRUTH_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"✅ Ground truth saved to {GROUND_TRUTH_FILE}")

    try:
        picks = load_model_picks()
    except Exception as e:
        print(f"⚠️ Could not load model picks for comparison: {e}")
        return

    write_corrected_report(ground_truth, missing, picks)


if __name__ == "__main__":
    main()
