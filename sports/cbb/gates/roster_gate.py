"""
CBB Roster Gate

Verifies player is on active roster before generating edges.
Borrowed from ufa/roster_gate.py pattern.
"""

from typing import Tuple, List, Set
from pathlib import Path
from datetime import datetime


def check_roster_gate(player_name: str, team_abbr: str) -> Tuple[bool, str]:
    """
    Verify player is on active roster.
    
    Gate conditions:
    1. Player must be found on team roster
    2. Player status must be Active (not Out, Injured Reserve, etc.)
    
    Returns: (passed, reason)
    """
    import os
    # Respect CBB_OFFLINE mode — skip ESPN calls entirely
    if (os.environ.get("CBB_OFFLINE") or "").strip().lower() in ("1", "true", "yes"):
        return True, "OFFLINE_SKIP"
    
    try:
        from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
        
        provider = CBBDataProvider()
        is_active, status = provider.check_player_status(player_name, team_abbr)
        
        if status == "UNKNOWN_TEAM":
            # Team not found - allow but warn
            return True, f"WARN: Team {team_abbr} not found in ESPN"
        
        if status == "NOT_ON_ROSTER":
            return False, f"ROSTER_FAIL: {player_name} not on {team_abbr} roster"
        
        if not is_active:
            return False, f"INJURY_FAIL: {player_name} status={status}"
        
        return True, "ACTIVE"
        
    except Exception as e:
        # On error, pass with warning (don't block due to API issues)
        return True, f"WARN: Roster check error - {e}"


def check_minutes_gate(player_name: str, team_abbr: str, min_mpg: float = 20.0) -> Tuple[bool, str]:
    """
    Verify player plays enough minutes.
    
    CBB specific: Requires ≥20 MPG (configurable).
    
    Returns: (passed, reason)
    """
    try:
        from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
        
        provider = CBBDataProvider()
        mpg = provider.get_minutes_avg(player_name, team_abbr)
        
        if mpg is None:
            # No data - allow but warn
            return True, f"WARN: No MPG data for {player_name}"
        
        if mpg < min_mpg:
            return False, f"MINUTES_FAIL: {player_name} MPG={mpg:.1f} < {min_mpg}"
        
        return True, f"MPG={mpg:.1f}"
        
    except Exception as e:
        return True, f"WARN: Minutes check error - {e}"


def get_active_roster(team_abbr: str) -> Set[str]:
    """Get set of active player names for a team."""
    try:
        from sports.cbb.ingest.cbb_data_provider import CBBDataProvider
        
        provider = CBBDataProvider()
        players = provider.verify_roster(team_abbr)
        return set(players)
        
    except Exception:
        return set()


def batch_check_roster(props: List[dict]) -> List[Tuple[dict, bool, str]]:
    """
    Batch check roster status for multiple props.
    
    Returns: List of (prop, passed, reason) tuples
    """
    results = []
    
    # Cache roster lookups by team
    roster_cache = {}
    
    for prop in props:
        player = prop.get("player", "")
        team = prop.get("team", "")
        
        # Check roster
        if team not in roster_cache:
            roster_cache[team] = get_active_roster(team)
        
        roster = roster_cache[team]
        
        if not roster:
            # No roster data - pass with warning
            results.append((prop, True, "WARN: No roster data"))
        elif any(player.lower() in r.lower() or r.lower() in player.lower() for r in roster):
            results.append((prop, True, "ACTIVE"))
        else:
            results.append((prop, False, f"NOT_ON_ROSTER: {player}"))
    
    return results
