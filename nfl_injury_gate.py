"""
NFL Injury & Roster Gate — Pre-Analysis Verification

Fetches LIVE injury data from ESPN before analysis runs.
Flags OUT/IR/Doubtful players and applies probability penalties.

Mirrors the NBA system (ufa/ingest/espn_nba_context.py + data_center/guards/roster_gate.py).
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ufa.ingest.espn_nfl import ESPNFetcher, NFL_TEAMS
    ESPN_AVAILABLE = True
except ImportError:
    ESPN_AVAILABLE = False

OUTPUTS_DIR = Path("outputs")
INJURY_CACHE_FILE = OUTPUTS_DIR / "nfl_injury_report.json"


@dataclass
class InjuryEntry:
    """Single player injury status."""
    player: str
    team: str
    position: str
    status: str  # Active, Out, Doubtful, Questionable, Probable, Injured Reserve
    injury_type: str = ""
    injury_detail: str = ""
    is_playable: bool = True
    penalty: float = 0.0  # Probability penalty to apply


# Status penalties (matches NBA system)
STATUS_PENALTIES = {
    "Out": 1.0,           # Full block — probability = 0
    "Injured Reserve": 1.0,  # Full block
    "Doubtful": 0.15,     # -15% probability
    "Questionable": 0.08, # -8% probability  
    "Probable": 0.02,     # -2% probability
    "Active": 0.0,        # No penalty
}


def fetch_nfl_injury_report(teams: list[str] = None) -> dict[str, list[InjuryEntry]]:
    """
    Fetch live injury report from ESPN for specified teams.
    
    Args:
        teams: List of team abbreviations (e.g., ["KC", "PHI"]).
               If None, fetches all 32 teams.
    
    Returns:
        Dict mapping team -> list of InjuryEntry for players with injury status
    """
    if not ESPN_AVAILABLE:
        print("  [!] ESPN NFL module not available")
        return {}
    
    if teams is None:
        teams = list(NFL_TEAMS.keys())
    
    fetcher = ESPNFetcher()
    injury_report = {}
    
    for team in teams:
        team = team.upper()
        if team not in NFL_TEAMS:
            print(f"  [!] Unknown team: {team}")
            continue
        
        try:
            roster = fetcher.get_team_roster(team)
            
            injured = []
            for player in roster:
                status = player.status or "Active"
                injury_status = player.injury_status or ""
                injury_detail = player.injury_detail or ""
                
                # Determine effective status
                effective_status = status
                if injury_status:
                    effective_status = injury_status
                
                # Check if any injury designation
                if effective_status not in ["Active", ""] or injury_status:
                    penalty = STATUS_PENALTIES.get(effective_status, 0.0)
                    is_playable = effective_status not in ["Out", "Injured Reserve"]
                    
                    injured.append(InjuryEntry(
                        player=player.name,
                        team=team,
                        position=player.position,
                        status=effective_status,
                        injury_type=injury_detail,
                        injury_detail=f"{injury_status}: {injury_detail}" if injury_detail else injury_status,
                        is_playable=is_playable,
                        penalty=penalty
                    ))
            
            if injured:
                injury_report[team] = injured
                
        except Exception as e:
            print(f"  [!] Error fetching {team} roster: {e}")
    
    return injury_report


def save_injury_report(report: dict[str, list[InjuryEntry]]) -> Path:
    """Save injury report to JSON for reference."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "teams": {}
    }
    
    for team, entries in report.items():
        data["teams"][team] = [
            {
                "player": e.player,
                "team": e.team,
                "position": e.position,
                "status": e.status,
                "injury_type": e.injury_type,
                "injury_detail": e.injury_detail,
                "is_playable": e.is_playable,
                "penalty": e.penalty
            }
            for e in entries
        ]
    
    with open(INJURY_CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    
    return INJURY_CACHE_FILE


def load_cached_injury_report() -> dict:
    """Load the most recent injury report from cache."""
    if INJURY_CACHE_FILE.exists():
        with open(INJURY_CACHE_FILE) as f:
            return json.load(f)
    return {}


def display_injury_report(report: dict[str, list[InjuryEntry]], teams_playing: list[str] = None):
    """Display injury report in a clean format."""
    if not report:
        print("\n  No injury data available.")
        return
    
    total_out = 0
    total_questionable = 0
    
    for team in sorted(report.keys()):
        # Only show teams playing today if filter specified
        if teams_playing and team not in teams_playing:
            continue
        
        entries = report[team]
        if not entries:
            continue
        
        print(f"\n  {team}:")
        for e in entries:
            if e.status in ["Out", "Injured Reserve"]:
                icon = "X"
                total_out += 1
            elif e.status == "Doubtful":
                icon = "!!"
                total_out += 1  # Treat as likely out
            elif e.status == "Questionable":
                icon = "?"
                total_questionable += 1
            elif e.status == "Probable":
                icon = "~"
            else:
                icon = " "
            
            detail = f" ({e.injury_type})" if e.injury_type else ""
            penalty_str = f" [-{e.penalty*100:.0f}%]" if e.penalty > 0 else ""
            print(f"    [{icon}] {e.player} ({e.position}) — {e.status}{detail}{penalty_str}")
    
    print(f"\n  Summary: {total_out} OUT/IR/DOUBTFUL, {total_questionable} QUESTIONABLE")


def apply_injury_gate(picks: list[dict], report: dict[str, list[InjuryEntry]]) -> list[dict]:
    """
    Apply injury gate to picks BEFORE analysis.
    
    - OUT/IR players: probability = 0, action = EXCLUDE
    - Doubtful: probability penalty = -15%
    - Questionable: probability penalty = -8%
    - Probable: probability penalty = -2%
    
    Returns:
        Modified picks list with injury flags applied
    """
    # Build lookup: player_name -> InjuryEntry
    injury_lookup = {}
    for team, entries in report.items():
        for entry in entries:
            # Normalize name for matching
            key = entry.player.lower().strip()
            injury_lookup[key] = entry
    
    modified = 0
    excluded = 0
    
    for pick in picks:
        player_name = pick.get("player", "").lower().strip()
        
        # Check exact match first
        entry = injury_lookup.get(player_name)
        
        # Try partial match if no exact match
        if not entry:
            for key, e in injury_lookup.items():
                # Match last name + first initial
                if player_name in key or key in player_name:
                    entry = e
                    break
        
        if entry:
            pick["injury_status"] = entry.status
            pick["injury_detail"] = entry.injury_detail
            pick["injury_penalty"] = entry.penalty
            
            if not entry.is_playable:
                # OUT / IR — exclude completely
                pick["on_ir"] = True
                pick["probability"] = 0.0
                pick["grade"] = "IR"
                pick["action"] = "EXCLUDE"
                pick["exclude_reason"] = f"INJURY: {entry.status} - {entry.injury_type}"
                excluded += 1
            elif entry.penalty > 0:
                # Questionable/Doubtful — flag for penalty  
                pick["injury_flag"] = True
                modified += 1
        else:
            pick["injury_status"] = "Active"
            pick["injury_penalty"] = 0.0
    
    return picks, modified, excluded


def run_injury_check(teams: list[str] = None, verbose: bool = True) -> dict[str, list[InjuryEntry]]:
    """
    Full injury check flow — fetch, display, save.
    
    Args:
        teams: Team abbreviations to check. None = auto-detect from today's games
        verbose: Print detailed report
    
    Returns:
        Injury report dict
    """
    if verbose:
        print("\n" + "=" * 70)
        print("  NFL INJURY & ROSTER CHECK")
        print("=" * 70)
        print("\n  Fetching live ESPN injury data...")
    
    report = fetch_nfl_injury_report(teams)
    
    if verbose:
        display_injury_report(report, teams_playing=teams)
    
    # Save to cache
    cache_path = save_injury_report(report)
    if verbose:
        print(f"\n  Saved to: {cache_path.name}")
    
    return report


if __name__ == "__main__":
    # Quick test — fetch injury report for today's games
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", nargs="*", help="Team abbreviations (e.g. KC PHI)")
    args = parser.parse_args()
    
    teams = args.teams if args.teams else None
    run_injury_check(teams)
