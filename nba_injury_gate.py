"""
NBA Injury Gate — Pre-Analysis Verification & Enforcement

Fetches LIVE injury data from ESPN before analysis runs.
- BLOCKS OUT/IR players (probability = 0, decision = BLOCKED)
- Applies penalties to Questionable (-8%) and Doubtful (-15%)
- Saves injury report to outputs/nba_injury_report.json

Mirrors NFL system (nfl_injury_gate.py).
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))

try:
    from ufa.ingest.espn_nba_context import (
        get_team_injury_report,
        PlayerInjuryStatus,
        NBA_TEAM_IDS,
    )
    ESPN_AVAILABLE = True
except ImportError:
    ESPN_AVAILABLE = False

OUTPUTS_DIR = Path("outputs")
INJURY_CACHE_FILE = OUTPUTS_DIR / "nba_injury_report.json"

# Status penalties
STATUS_PENALTIES = {
    "Out": 1.0,              # Full block — probability = 0
    "Injured Reserve": 1.0,  # Full block
    "Suspension": 1.0,       # Full block
    "Doubtful": 0.15,        # -15% probability
    "Questionable": 0.08,    # -8% probability
    "Probable": 0.02,        # -2% probability
    "Day-To-Day": 0.05,      # -5% probability
    "Active": 0.0,           # No penalty
}

NON_PLAYABLE = {"Out", "Injured Reserve", "Suspension"}


def fetch_nba_injuries(teams: list[str] = None) -> dict[str, list]:
    """
    Fetch live injury report from ESPN for specified NBA teams.
    
    Args:
        teams: List of team abbreviations (e.g., ["LAL", "BOS"]).
               If None, fetches all 30 teams.
    
    Returns:
        Dict mapping team -> list of injury entries
    """
    if not ESPN_AVAILABLE:
        print("  [!] ESPN NBA module not available")
        return {}

    if teams is None:
        teams = list(NBA_TEAM_IDS.keys())
    # Dedupe while preserving order
    teams = list(dict.fromkeys(t.upper() for t in teams))

    injury_report = {}

    for team in teams:
        if team not in NBA_TEAM_IDS:
            continue

        try:
            injuries = get_team_injury_report(team)

            team_injuries = []
            for inj in injuries:
                status = inj.status or "Active"
                penalty = STATUS_PENALTIES.get(status, 0.0)
                is_playable = status not in NON_PLAYABLE

                team_injuries.append({
                    "player": inj.player,
                    "team": team,
                    "status": status,
                    "injury_type": inj.injury_type or "",
                    "details": inj.details or "",
                    "is_playable": is_playable,
                    "penalty": penalty,
                })

            if team_injuries:
                injury_report[team] = team_injuries

        except Exception as e:
            print(f"  [!] Error fetching {team} injuries: {e}")

    return injury_report


def save_injury_report(report: dict) -> Path:
    """Save injury report to JSON for reference."""
    OUTPUTS_DIR.mkdir(exist_ok=True)

    data = {
        "sport": "NBA",
        "timestamp": datetime.now().isoformat(),
        "teams": report,
    }

    with open(INJURY_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return INJURY_CACHE_FILE


def load_cached_injury_report() -> dict:
    """Load the most recent injury report from cache."""
    if INJURY_CACHE_FILE.exists():
        with open(INJURY_CACHE_FILE) as f:
            return json.load(f)
    return {}


def display_injury_report(report: dict, teams_filter: list[str] = None):
    """Display injury report cleanly."""
    if not report:
        print("\n  No injury data available.")
        return

    total_out = 0
    total_questionable = 0

    for team in sorted(report.keys()):
        if teams_filter and team not in teams_filter:
            continue

        entries = report[team]
        if not entries:
            continue

        print(f"\n  {team}:")
        for e in entries:
            status = e["status"]
            if status in NON_PLAYABLE:
                icon = "X"
                total_out += 1
            elif status == "Doubtful":
                icon = "!!"
                total_out += 1
            elif status == "Questionable":
                icon = "?"
                total_questionable += 1
            elif status == "Day-To-Day":
                icon = "~"
                total_questionable += 1
            elif status == "Probable":
                icon = "~"
            else:
                icon = " "

            detail = f" ({e['injury_type']})" if e.get("injury_type") else ""
            penalty_pct = e["penalty"] * 100
            penalty_str = f" [-{penalty_pct:.0f}%]" if penalty_pct > 0 else ""
            print(f"    [{icon}] {e['player']} - {status}{detail}{penalty_str}")

    print(f"\n  Summary: {total_out} OUT/IR/DOUBTFUL, {total_questionable} QUESTIONABLE/DTD")


def apply_injury_gate(picks: list[dict], report: dict) -> tuple:
    """
    Apply injury gate to picks BEFORE analysis.

    - OUT/IR players: probability = 0, decision = BLOCKED
    - Doubtful: -15% penalty
    - Questionable: -8% penalty
    - Day-To-Day: -5% penalty
    - Probable: -2% penalty

    Returns:
        (modified_picks, modified_count, excluded_count)
    """
    # Build lookup: normalized_name -> injury entry
    injury_lookup = {}
    for team, entries in report.items():
        for entry in entries:
            key = entry["player"].lower().strip()
            injury_lookup[key] = entry

    modified = 0
    excluded = 0

    for pick in picks:
        player_name = pick.get("player", "").lower().strip()

        # Exact match
        entry = injury_lookup.get(player_name)

        # Partial match fallback
        if not entry:
            for key, e in injury_lookup.items():
                if player_name in key or key in player_name:
                    entry = e
                    break

        if entry:
            pick["injury_status"] = entry["status"]
            pick["injury_detail"] = entry.get("injury_type", "")
            pick["injury_penalty"] = entry["penalty"]

            if not entry["is_playable"]:
                # OUT / IR — BLOCK completely
                pick["probability"] = 0.0
                pick["decision"] = "BLOCKED"
                pick["status"] = "BLOCKED"
                pick["exclude_reason"] = f"INJURY: {entry['status']} - {entry.get('injury_type', '')}"
                pick["on_ir"] = True
                excluded += 1
            elif entry["penalty"] > 0:
                # Questionable/Doubtful — flag for penalty during analysis
                pick["injury_flag"] = True
                modified += 1
        else:
            pick["injury_status"] = "Active"
            pick["injury_penalty"] = 0.0

    return picks, modified, excluded


def run_full_injury_check(teams: list[str] = None, verbose: bool = True) -> dict:
    """
    Full injury check flow: fetch → display → save.

    Args:
        teams: Team abbreviations to check. None = all 30 teams.
        verbose: Print detailed report.

    Returns:
        Injury report dict
    """
    if verbose:
        print("\n" + "=" * 70)
        print("  NBA INJURY & ROSTER CHECK (ESPN Live)")
        print("=" * 70)
        print("\n  Fetching live ESPN injury data...")

    report = fetch_nba_injuries(teams)

    if verbose:
        display_injury_report(report, teams_filter=teams)

    # Save to cache
    cache_path = save_injury_report(report)
    if verbose:
        print(f"\n  Saved to: {cache_path.name}")

    return report


def get_out_players_for_teams(teams: list[str]) -> list[str]:
    """Quick helper: return list of OUT/IR player names for given teams."""
    report = fetch_nba_injuries(teams)
    out = []
    for team, entries in report.items():
        for e in entries:
            if not e["is_playable"]:
                out.append(e["player"])
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", nargs="*", help="Team abbreviations (e.g. LAL BOS)")
    args = parser.parse_args()

    teams = args.teams if args.teams else None
    run_full_injury_check(teams)
