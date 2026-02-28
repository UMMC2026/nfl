import json
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
STATE_DIR = PROJECT_ROOT / "state"
ACTIVE_SLATE_FILE = STATE_DIR / "active_slate.json"
BAN_FILE = PROJECT_ROOT / "player_stat_memory.json"

DEFAULT_FAILED_PLAYERS = [
    "Cedric Coward",
    "Jordan Goodwin",
    "Jaylen Wells",
    "Karlo Matkovic",
    "Micah Peavy",
    "Kyle Kuzma",
    "Peyton Watson",
    "Toumani Camara",
    "Donovan Clingan",
]


def _load_latest_results():
    files = sorted(OUTPUTS_DIR.glob("*_RISK_FIRST_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None, []
    latest = files[0]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "results" in data:
            return latest, data["results"]
        elif isinstance(data, list):
            return latest, data
    except Exception:
        pass
    return latest, []


def _read_active_slate():
    try:
        if ACTIVE_SLATE_FILE.exists():
            return json.loads(ACTIVE_SLATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def _add_bans(players_to_ban):
    # Load existing ban file (supports nested format with 'bans'/'warnings' or flat legacy)
    data = {}
    if BAN_FILE.exists():
        try:
            data = json.loads(BAN_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if "bans" not in data:
        data = {"bans": {}, "warnings": {}}

    now_str = datetime.now().strftime("%Y-%m-%d")
    for key in players_to_ban:
        # key format: "Player|stat"
        data["bans"][key] = {
            "fails_10": 99,
            "fails_30": 99,
            "last_fail": now_str,
            "banned": True,
            "reason": "Auto-ban due to NBA API hydration failure"
        }
    BAN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scan latest RISK_FIRST results for players with NBA API hydration failures; optionally ban and re-run analysis.")
    parser.add_argument("--players", nargs="*", default=[], help="Override list of failed players (names)")
    parser.add_argument("--ban", action="store_true", help="Add bans for any matching picks")
    parser.add_argument("--re_run", action="store_true", help="Re-run analysis after banning (uses active slate)")
    args = parser.parse_args()

    failed = args.players or DEFAULT_FAILED_PLAYERS
    failed_upper = {p.upper() for p in failed}

    results_file, picks = _load_latest_results()
    if not picks:
        print("No RISK_FIRST results found. Run analysis first.")
        sys.exit(0)

    print(f"Scanning: {results_file.name}")
    matches = []
    for p in picks:
        player = str(p.get("player", "")).strip()
        if player.upper() in failed_upper:
            matches.append({
                "player": player,
                "stat": p.get("stat"),
                "direction": p.get("direction"),
                "line": p.get("line"),
                "status": p.get("status") or p.get("decision") or p.get("tier"),
                "team": p.get("team"),
            })

    if not matches:
        print("No affected players found in latest results.")
    else:
        print(f"Found {len(matches)} affected picks:")
        for m in matches:
            print(f" - {m['player']} {m['stat']} {m['direction']} {m['line']} | {m['status']} | {m.get('team','')}")

        if args.ban:
            keys = [f"{m['player']}|{m['stat']}" for m in matches if m.get('stat')]
            if keys:
                _add_bans(keys)
                print(f"Added {len(keys)} bans to {BAN_FILE.name}.")
            else:
                print("No stat field found for matches; skipping bans.")

    if args.ban and args.re_run:
        # Re-run analysis on active slate
        state = _read_active_slate()
        slate_path = state.get("path")
        label = state.get("label") or "SLATE"
        if slate_path and Path(slate_path).exists():
            print(f"Re-running analysis for active slate: {slate_path}")
            import subprocess
            subprocess.run([sys.executable, str(PROJECT_ROOT / "analyze_from_underdog_json.py"), "--slate", slate_path, "--label", label], cwd=str(PROJECT_ROOT))
        else:
            print("No active slate found; skipping re-run.")

if __name__ == "__main__":
    main()
