"""
TENNIS INJURY DETECTION GATE — Phase 5B Enhancement
=====================================================

Detects players returning from injury and applies confidence penalties:
- Returning <2 weeks: -15% confidence adjustment
- Returning 2-4 weeks: -7% confidence adjustment
- Returning >4 weeks: No penalty (fully recovered)

Data Sources:
- ATP/WTA injury reports (manual tracking for now)
- Match gap detection (if no matches in 3+ weeks = potential injury)
- Known injury list (maintained in injury_database.json)

Usage:
    from tennis.injury_gate import get_injury_penalty, is_returning_from_injury
    
    penalty = get_injury_penalty("Novak Djokovic")
    if penalty > 0:
        adjusted_prob = raw_prob * (1 - penalty)

Created: 2026-02-05
Phase: 5B Week 2
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

TENNIS_DIR = Path(__file__).parent
INJURY_DB_PATH = TENNIS_DIR / "data" / "injury_database.json"


@dataclass
class InjuryStatus:
    """Player injury status."""
    player: str
    is_injured: bool
    injury_type: Optional[str]  # "knee", "back", "wrist", etc.
    return_date: Optional[datetime]
    weeks_since_return: Optional[float]
    confidence_penalty: float  # 0.0 to 0.15
    status: str  # "ACTIVE", "RECOVERING", "INJURED"


# =============================================================================
# INJURY PENALTY CONFIGURATION
# =============================================================================

INJURY_PENALTIES = {
    # Weeks since return -> penalty
    "JUST_RETURNED": 0.15,      # <2 weeks since return
    "EARLY_RECOVERY": 0.10,     # 2-3 weeks
    "RECOVERING": 0.07,         # 3-4 weeks
    "LATE_RECOVERY": 0.03,      # 4-6 weeks
    "FULLY_RECOVERED": 0.0,     # >6 weeks
}

# Injury type severity multipliers
INJURY_SEVERITY = {
    "knee": 1.2,           # Knee injuries affect mobility significantly
    "back": 1.3,           # Back injuries are hardest to fully recover
    "shoulder": 1.1,       # Serve impact
    "wrist": 1.15,         # Shot power impact
    "ankle": 1.0,          # Standard
    "hip": 1.1,            # Movement impact
    "elbow": 1.0,          # Tennis elbow common
    "abdominal": 1.1,      # Core strength impact
    "unknown": 1.0,        # Default
}

# Known currently injured/recovering players (manual maintenance)
# Format: "player_name": {"return_date": "YYYY-MM-DD", "injury_type": "type"}
KNOWN_INJURIES: Dict[str, Dict] = {}


def load_injury_database() -> Dict[str, Dict]:
    """Load injury database from JSON file."""
    if INJURY_DB_PATH.exists():
        try:
            with open(INJURY_DB_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[INJURY_GATE] Warning: Could not load injury database: {e}")
    return {}


def save_injury_database(data: Dict[str, Dict]) -> None:
    """Save injury database to JSON file."""
    INJURY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INJURY_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def normalize_player_name(name: str) -> str:
    """Normalize player name for matching."""
    return name.lower().strip().replace("-", " ").replace("'", "")


def get_weeks_since_return(return_date: datetime) -> float:
    """Calculate weeks since player returned from injury."""
    now = datetime.now()
    if return_date > now:
        return -1  # Still injured
    delta = now - return_date
    return delta.days / 7.0


def calculate_injury_penalty(
    weeks_since_return: float,
    injury_type: str = "unknown",
) -> float:
    """
    Calculate confidence penalty based on recovery status.
    
    Args:
        weeks_since_return: Weeks since player returned to competition
        injury_type: Type of injury for severity adjustment
    
    Returns:
        Penalty as decimal (0.0 to 0.15)
    """
    if weeks_since_return < 0:
        # Still injured - maximum penalty
        return INJURY_PENALTIES["JUST_RETURNED"]
    
    # Determine base penalty from weeks
    if weeks_since_return < 2:
        base_penalty = INJURY_PENALTIES["JUST_RETURNED"]
    elif weeks_since_return < 3:
        base_penalty = INJURY_PENALTIES["EARLY_RECOVERY"]
    elif weeks_since_return < 4:
        base_penalty = INJURY_PENALTIES["RECOVERING"]
    elif weeks_since_return < 6:
        base_penalty = INJURY_PENALTIES["LATE_RECOVERY"]
    else:
        base_penalty = INJURY_PENALTIES["FULLY_RECOVERED"]
    
    # Apply injury severity multiplier
    severity = INJURY_SEVERITY.get(injury_type.lower(), 1.0)
    adjusted_penalty = base_penalty * severity
    
    # Cap at 20%
    return min(adjusted_penalty, 0.20)


def get_injury_status(player_name: str) -> InjuryStatus:
    """
    Get full injury status for a player.
    
    Args:
        player_name: Player's full name
    
    Returns:
        InjuryStatus dataclass with all injury info
    """
    normalized = normalize_player_name(player_name)
    
    # Load database
    db = load_injury_database()
    db.update(KNOWN_INJURIES)  # Merge with hardcoded list
    
    # Check for player in database
    for db_name, info in db.items():
        if normalize_player_name(db_name) == normalized:
            return_date_str = info.get("return_date")
            injury_type = info.get("injury_type", "unknown")
            
            if return_date_str:
                try:
                    return_date = datetime.fromisoformat(return_date_str)
                    weeks = get_weeks_since_return(return_date)
                    penalty = calculate_injury_penalty(weeks, injury_type)
                    
                    if weeks < 0:
                        status = "INJURED"
                    elif weeks < 6:
                        status = "RECOVERING"
                    else:
                        status = "ACTIVE"
                    
                    return InjuryStatus(
                        player=player_name,
                        is_injured=(weeks < 0),
                        injury_type=injury_type,
                        return_date=return_date,
                        weeks_since_return=weeks if weeks >= 0 else None,
                        confidence_penalty=penalty,
                        status=status,
                    )
                except ValueError:
                    pass
    
    # No injury record = active player
    return InjuryStatus(
        player=player_name,
        is_injured=False,
        injury_type=None,
        return_date=None,
        weeks_since_return=None,
        confidence_penalty=0.0,
        status="ACTIVE",
    )


def get_injury_penalty(player_name: str) -> float:
    """
    Quick lookup for injury penalty.
    
    Args:
        player_name: Player's full name
    
    Returns:
        Penalty as decimal (0.0 to 0.20)
    """
    status = get_injury_status(player_name)
    return status.confidence_penalty


def is_returning_from_injury(player_name: str, weeks_threshold: int = 4) -> bool:
    """
    Check if player is recently returned from injury.
    
    Args:
        player_name: Player's full name
        weeks_threshold: Consider "returning" if within this many weeks
    
    Returns:
        True if player recently returned from injury
    """
    status = get_injury_status(player_name)
    if status.weeks_since_return is None:
        return False
    return 0 <= status.weeks_since_return <= weeks_threshold


def apply_injury_adjustment(
    raw_probability: float,
    player_name: str,
    opponent_name: Optional[str] = None,
) -> Tuple[float, Dict]:
    """
    Apply injury adjustments to probability.
    
    Args:
        raw_probability: Original probability (0.0-1.0)
        player_name: Main player
        opponent_name: Opponent (for relative adjustment)
    
    Returns:
        Tuple of (adjusted_probability, adjustment_info)
    """
    player_status = get_injury_status(player_name)
    player_penalty = player_status.confidence_penalty
    
    opponent_penalty = 0.0
    if opponent_name:
        opponent_status = get_injury_status(opponent_name)
        opponent_penalty = opponent_status.confidence_penalty
    
    # Net adjustment (opponent injury helps our player)
    net_adjustment = player_penalty - (opponent_penalty * 0.5)  # Reduced impact of opponent injury
    net_adjustment = max(0, net_adjustment)  # Don't boost above raw
    
    adjusted_prob = raw_probability * (1 - net_adjustment)
    
    info = {
        "player_injury_penalty": player_penalty,
        "opponent_injury_penalty": opponent_penalty,
        "net_adjustment": net_adjustment,
        "player_status": player_status.status,
        "adjustment_applied": net_adjustment > 0,
    }
    
    if player_penalty > 0:
        info["player_weeks_since_return"] = player_status.weeks_since_return
        info["player_injury_type"] = player_status.injury_type
    
    return adjusted_prob, info


# =============================================================================
# MATCH GAP DETECTION (Alternative injury detection)
# =============================================================================

def detect_match_gap(
    player_name: str,
    last_match_date: Optional[datetime],
    gap_threshold_days: int = 21,
) -> Optional[str]:
    """
    Detect potential injury from match gap.
    
    If a player hasn't competed in 21+ days, they may be returning from injury.
    
    Args:
        player_name: Player name
        last_match_date: Date of last known match
        gap_threshold_days: Days without match to flag
    
    Returns:
        Warning string if gap detected, None otherwise
    """
    if last_match_date is None:
        return None
    
    days_since_match = (datetime.now() - last_match_date).days
    
    if days_since_match >= gap_threshold_days:
        weeks = days_since_match / 7
        return f"MATCH_GAP: {player_name} hasn't played in {weeks:.1f} weeks (potential injury return)"
    
    return None


# =============================================================================
# ADMIN FUNCTIONS
# =============================================================================

def add_injury(
    player_name: str,
    return_date: str,
    injury_type: str = "unknown",
) -> None:
    """
    Add or update a player's injury record.
    
    Args:
        player_name: Player's full name
        return_date: Expected return date (YYYY-MM-DD)
        injury_type: Type of injury
    """
    db = load_injury_database()
    db[player_name] = {
        "return_date": return_date,
        "injury_type": injury_type,
        "added_at": datetime.now().isoformat(),
    }
    save_injury_database(db)
    print(f"[INJURY_GATE] Added injury for {player_name}: {injury_type}, return {return_date}")


def remove_injury(player_name: str) -> bool:
    """Remove a player from injury database (fully recovered)."""
    db = load_injury_database()
    normalized = normalize_player_name(player_name)
    
    for key in list(db.keys()):
        if normalize_player_name(key) == normalized:
            del db[key]
            save_injury_database(db)
            print(f"[INJURY_GATE] Removed {player_name} from injury database")
            return True
    
    print(f"[INJURY_GATE] {player_name} not found in injury database")
    return False


def list_injuries() -> None:
    """Print all players in injury database."""
    db = load_injury_database()
    
    if not db:
        print("[INJURY_GATE] No players in injury database")
        return
    
    print("\n=== TENNIS INJURY DATABASE ===")
    for player, info in sorted(db.items()):
        return_date = info.get("return_date", "?")
        injury_type = info.get("injury_type", "unknown")
        status = get_injury_status(player)
        print(f"  {player}: {injury_type} | Return: {return_date} | Status: {status.status} | Penalty: {status.confidence_penalty:.1%}")
    print()


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tennis Injury Gate Management")
    parser.add_argument("--add", nargs=3, metavar=("PLAYER", "DATE", "TYPE"),
                       help="Add injury: 'Player Name' YYYY-MM-DD injury_type")
    parser.add_argument("--remove", metavar="PLAYER", help="Remove player from database")
    parser.add_argument("--list", action="store_true", help="List all injuries")
    parser.add_argument("--check", metavar="PLAYER", help="Check player injury status")
    
    args = parser.parse_args()
    
    if args.add:
        add_injury(args.add[0], args.add[1], args.add[2])
    elif args.remove:
        remove_injury(args.remove)
    elif args.list:
        list_injuries()
    elif args.check:
        status = get_injury_status(args.check)
        print(f"\n=== Injury Status: {args.check} ===")
        print(f"  Status: {status.status}")
        print(f"  Is Injured: {status.is_injured}")
        print(f"  Injury Type: {status.injury_type or 'N/A'}")
        print(f"  Weeks Since Return: {status.weeks_since_return or 'N/A'}")
        print(f"  Confidence Penalty: {status.confidence_penalty:.1%}")
    else:
        parser.print_help()
