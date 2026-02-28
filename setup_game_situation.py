"""
Game Situation Setup Helper
Provides easy ways to set B2B, Home/Away, and rest days for slates.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from nba_game_situation import set_game_situation, get_situation_summary


# ============================================================================
# NBA SCHEDULE LOOKUP (simplified - can be extended with API)
# ============================================================================

def load_schedule_from_json(filepath: str = "data/nba_schedule.json") -> Dict:
    """Load schedule from JSON file if available."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SCHEDULE] Error loading: {e}")
    return {}


def detect_home_team_from_slate(slate_path: str) -> Optional[Tuple[str, str]]:
    """
    Try to detect home/away from slate filename or content.
    Convention: AWAY_HOME format (e.g., CLE_PHI = CLE @ PHI)
    
    Returns: (away_team, home_team) or None
    """
    try:
        filename = os.path.basename(slate_path).upper()
        
        # Look for pattern like CLE_PHI or MIN_HOU
        import re
        match = re.search(r'([A-Z]{2,3})_([A-Z]{2,3})', filename)
        if match:
            away = match.group(1)
            home = match.group(2)
            return (away, home)
    except Exception:
        pass
    
    return None


def setup_game_situations_interactive():
    """Interactive prompt to set up game situations."""
    print("\n" + "=" * 60)
    print("GAME SITUATION SETUP")
    print("=" * 60)
    
    game_date = datetime.now().strftime("%Y-%m-%d")
    print(f"\nGame date: {game_date}")
    
    games = []
    
    while True:
        print("\n--- Add Game ---")
        
        # Get teams
        away = input("Away team (e.g., CLE) or 'done': ").strip().upper()
        if away.lower() == 'done' or not away:
            break
        
        home = input("Home team (e.g., PHI): ").strip().upper()
        if not home:
            continue
        
        # Get away team situation
        print(f"\n{away} (AWAY):")
        away_b2b = input("  Is B2B? (y/n) [n]: ").strip().lower() == 'y'
        away_3in4 = False
        if away_b2b:
            away_3in4 = input("  Is 3-in-4? (y/n) [n]: ").strip().lower() == 'y'
        
        away_rest_str = input("  Days rest (0=B2B, 1=normal, 2+=extra) [1]: ").strip()
        away_rest = int(away_rest_str) if away_rest_str.isdigit() else (0 if away_b2b else 1)
        
        # Get home team situation
        print(f"\n{home} (HOME):")
        home_b2b = input("  Is B2B? (y/n) [n]: ").strip().lower() == 'y'
        home_3in4 = False
        if home_b2b:
            home_3in4 = input("  Is 3-in-4? (y/n) [n]: ").strip().lower() == 'y'
        
        home_rest_str = input("  Days rest (0=B2B, 1=normal, 2+=extra) [1]: ").strip()
        home_rest = int(home_rest_str) if home_rest_str.isdigit() else (0 if home_b2b else 1)
        
        # Set situations
        set_game_situation(
            team=away,
            game_date=game_date,
            is_home=False,
            days_rest=away_rest,
            is_back_to_back=away_b2b,
            is_3_in_4=away_3in4,
            opponent=home,
            opponent_b2b=home_b2b,
            opponent_days_rest=home_rest
        )
        
        set_game_situation(
            team=home,
            game_date=game_date,
            is_home=True,
            days_rest=home_rest,
            is_back_to_back=home_b2b,
            is_3_in_4=home_3in4,
            opponent=away,
            opponent_b2b=away_b2b,
            opponent_days_rest=away_rest
        )
        
        games.append((away, home))
        
        print(f"\n✓ {away} @ {home} situation set!")
        print(f"  {away}: {get_situation_summary(away, game_date)}")
        print(f"  {home}: {get_situation_summary(home, game_date)}")
    
    if games:
        print("\n" + "=" * 60)
        print("GAME SITUATIONS SET:")
        print("=" * 60)
        for away, home in games:
            print(f"\n{away} @ {home}:")
            print(f"  {away}: {get_situation_summary(away, game_date)}")
            print(f"  {home}: {get_situation_summary(home, game_date)}")
    
    return games


def setup_game_situations_quick(
    away_team: str,
    home_team: str,
    away_b2b: bool = False,
    home_b2b: bool = False,
    away_rest: int = 1,
    home_rest: int = 1,
    game_date: str = None
):
    """
    Quick setup for a single game.
    
    Example:
        setup_game_situations_quick('CLE', 'PHI', away_b2b=True)
    """
    if game_date is None:
        game_date = datetime.now().strftime("%Y-%m-%d")
    
    # Away team
    set_game_situation(
        team=away_team,
        game_date=game_date,
        is_home=False,
        days_rest=away_rest if not away_b2b else 0,
        is_back_to_back=away_b2b,
        opponent=home_team,
        opponent_b2b=home_b2b,
        opponent_days_rest=home_rest if not home_b2b else 0
    )
    
    # Home team
    set_game_situation(
        team=home_team,
        game_date=game_date,
        is_home=True,
        days_rest=home_rest if not home_b2b else 0,
        is_back_to_back=home_b2b,
        opponent=away_team,
        opponent_b2b=away_b2b,
        opponent_days_rest=away_rest if not away_b2b else 0
    )
    
    print(f"✓ {away_team} @ {home_team} situation set!")
    print(f"  {away_team}: {get_situation_summary(away_team, game_date)}")
    print(f"  {home_team}: {get_situation_summary(home_team, game_date)}")


def setup_from_slate(slate_path: str, away_b2b: bool = False, home_b2b: bool = False):
    """
    Auto-detect teams from slate filename and set situations.
    
    Example:
        setup_from_slate('slates/CLE_PHI_USERPASTE_20260116.json', away_b2b=True)
    """
    teams = detect_home_team_from_slate(slate_path)
    
    if teams:
        away, home = teams
        setup_game_situations_quick(away, home, away_b2b=away_b2b, home_b2b=home_b2b)
    else:
        print(f"Could not detect teams from slate: {slate_path}")
        print("Use setup_game_situations_quick() instead")


# ============================================================================
# COMMON SITUATION PRESETS
# ============================================================================

def preset_away_b2b(away_team: str, home_team: str, game_date: str = None):
    """Quick preset: Away team on B2B, home team rested."""
    setup_game_situations_quick(
        away_team, home_team,
        away_b2b=True, home_b2b=False,
        away_rest=0, home_rest=2,
        game_date=game_date
    )


def preset_home_b2b(away_team: str, home_team: str, game_date: str = None):
    """Quick preset: Home team on B2B, away team rested."""
    setup_game_situations_quick(
        away_team, home_team,
        away_b2b=False, home_b2b=True,
        away_rest=2, home_rest=0,
        game_date=game_date
    )


def preset_both_rested(away_team: str, home_team: str, game_date: str = None):
    """Quick preset: Both teams well rested (2+ days)."""
    setup_game_situations_quick(
        away_team, home_team,
        away_b2b=False, home_b2b=False,
        away_rest=2, home_rest=2,
        game_date=game_date
    )


def preset_normal(away_team: str, home_team: str, game_date: str = None):
    """Quick preset: Normal rest, no special situations."""
    setup_game_situations_quick(
        away_team, home_team,
        away_b2b=False, home_b2b=False,
        away_rest=1, home_rest=1,
        game_date=game_date
    )


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command line usage
        cmd = sys.argv[1].lower()
        
        if cmd == "interactive":
            setup_game_situations_interactive()
        
        elif cmd == "quick" and len(sys.argv) >= 4:
            # quick AWAY HOME [away_b2b] [home_b2b]
            away = sys.argv[2].upper()
            home = sys.argv[3].upper()
            away_b2b = len(sys.argv) > 4 and sys.argv[4].lower() in ('y', 'yes', 'true', '1', 'b2b')
            home_b2b = len(sys.argv) > 5 and sys.argv[5].lower() in ('y', 'yes', 'true', '1', 'b2b')
            setup_game_situations_quick(away, home, away_b2b=away_b2b, home_b2b=home_b2b)
        
        elif cmd == "slate" and len(sys.argv) >= 3:
            # slate PATH [away_b2b] [home_b2b]
            slate = sys.argv[2]
            away_b2b = len(sys.argv) > 3 and sys.argv[3].lower() in ('y', 'yes', 'true', '1', 'b2b')
            home_b2b = len(sys.argv) > 4 and sys.argv[4].lower() in ('y', 'yes', 'true', '1', 'b2b')
            setup_from_slate(slate, away_b2b=away_b2b, home_b2b=home_b2b)
        
        else:
            print("Usage:")
            print("  python setup_game_situation.py interactive")
            print("  python setup_game_situation.py quick AWAY HOME [away_b2b] [home_b2b]")
            print("  python setup_game_situation.py slate SLATE_PATH [away_b2b] [home_b2b]")
            print("")
            print("Examples:")
            print("  python setup_game_situation.py quick CLE PHI b2b")
            print("  python setup_game_situation.py slate slates/CLE_PHI_USERPASTE_20260116.json b2b")
    
    else:
        # Interactive mode by default
        setup_game_situations_interactive()
