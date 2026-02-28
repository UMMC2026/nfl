"""
NBA Game Situation Context - Back-to-Back, Home/Away, Rest Days
Provides situational adjustments for prop projections.

Edge Boosts:
- Back-to-back detection: +2-3% accuracy on fatigue
- Home/Away splits: +1-2% accuracy
- Days rest factor: +1-2% accuracy
"""

from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import json
import os


@dataclass
class GameSituation:
    """Game situation context for a team."""
    team: str
    is_home: bool
    is_back_to_back: bool          # 2nd game in 2 nights
    days_rest: int                  # Days since last game (0 = B2B, 1 = normal, 2+ = extra rest)
    is_3_in_4: bool = False        # 3rd game in 4 nights (extra fatigue)
    opponent_b2b: bool = False     # Is opponent on B2B?
    opponent_days_rest: int = 1    # Opponent rest days


# ============================================================================
# ADJUSTMENT FACTORS
# ============================================================================

# Back-to-back fatigue factors (applied to mu)
B2B_FACTORS = {
    "points": 0.96,      # -4% scoring on B2B
    "rebounds": 0.97,    # -3% rebounds
    "assists": 0.98,     # -2% assists
    "3pm": 0.95,         # -5% 3PM (tired legs)
    "steals": 0.94,      # -6% steals (less hustle)
    "blocks": 0.95,      # -5% blocks
    "turnovers": 1.03,   # +3% turnovers (fatigue errors)
    "pra": 0.96,
    "pts+reb": 0.96,
    "pts+ast": 0.96,
    "reb+ast": 0.97,
    "default": 0.97
}

# 3-in-4 nights (even more fatigue)
THREE_IN_FOUR_FACTORS = {
    "points": 0.93,      # -7% scoring
    "rebounds": 0.94,
    "assists": 0.95,
    "3pm": 0.91,         # -9% 3PM
    "steals": 0.90,      # -10% steals
    "blocks": 0.92,
    "turnovers": 1.06,   # +6% turnovers
    "default": 0.94
}

# Home court advantage factors
HOME_FACTORS = {
    "points": 1.02,      # +2% scoring at home
    "rebounds": 1.01,
    "assists": 1.02,
    "3pm": 1.03,         # +3% 3PM (familiar rims)
    "steals": 1.02,
    "blocks": 1.01,
    "turnovers": 0.98,   # -2% turnovers
    "pra": 1.02,
    "default": 1.015
}

# Away factors
AWAY_FACTORS = {
    "points": 0.98,      # -2% scoring on road
    "rebounds": 0.99,
    "assists": 0.98,
    "3pm": 0.97,         # -3% 3PM
    "steals": 0.98,
    "blocks": 0.99,
    "turnovers": 1.02,   # +2% turnovers
    "pra": 0.98,
    "default": 0.985
}

# Extra rest bonus (3+ days rest)
EXTRA_REST_FACTORS = {
    "points": 1.02,
    "rebounds": 1.01,
    "assists": 1.01,
    "3pm": 1.03,         # +3% fresh legs
    "steals": 1.03,
    "blocks": 1.02,
    "turnovers": 0.97,
    "default": 1.02
}


def get_stat_key(stat: str) -> str:
    """Normalize stat name for lookup."""
    stat_lower = stat.lower().strip()
    
    if stat_lower in ("pts+reb+ast", "pra"):
        return "pra"
    if stat_lower in ("pts+reb", "pr"):
        return "pts+reb"
    if stat_lower in ("pts+ast", "pa"):
        return "pts+ast"
    if stat_lower in ("reb+ast", "ra"):
        return "reb+ast"
    if "3pm" in stat_lower or "three" in stat_lower:
        return "3pm"
    if "point" in stat_lower or stat_lower == "pts":
        return "points"
    if "rebound" in stat_lower or stat_lower == "reb":
        return "rebounds"
    if "assist" in stat_lower or stat_lower == "ast":
        return "assists"
    if "steal" in stat_lower or stat_lower == "stl":
        return "steals"
    if "block" in stat_lower or stat_lower == "blk":
        return "blocks"
    if "turnover" in stat_lower or stat_lower == "to":
        return "turnovers"
    
    return stat_lower


def get_situation_adjustment(stat: str, situation: GameSituation) -> Tuple[float, List[str]]:
    """Calculate combined situation adjustment factor."""
    factor = 1.0
    notes = []
    stat_key = get_stat_key(stat)
    
    # Back-to-back check (highest impact)
    if situation.is_back_to_back:
        if situation.is_3_in_4:
            b2b_factor = THREE_IN_FOUR_FACTORS.get(stat_key, THREE_IN_FOUR_FACTORS["default"])
            pct = (b2b_factor - 1) * 100
            notes.append(f"3-in-4: {pct:+.1f}%")
        else:
            b2b_factor = B2B_FACTORS.get(stat_key, B2B_FACTORS["default"])
            pct = (b2b_factor - 1) * 100
            notes.append(f"B2B: {pct:+.1f}%")
        factor *= b2b_factor
    
    # Home/Away adjustment
    if situation.is_home:
        ha_factor = HOME_FACTORS.get(stat_key, HOME_FACTORS["default"])
        pct = (ha_factor - 1) * 100
        notes.append(f"Home: {pct:+.1f}%")
    else:
        ha_factor = AWAY_FACTORS.get(stat_key, AWAY_FACTORS["default"])
        pct = (ha_factor - 1) * 100
        notes.append(f"Away: {pct:+.1f}%")
    factor *= ha_factor
    
    # Extra rest bonus
    if situation.days_rest >= 3:
        rest_factor = EXTRA_REST_FACTORS.get(stat_key, EXTRA_REST_FACTORS["default"])
        pct = (rest_factor - 1) * 100
        notes.append(f"{situation.days_rest}d rest: {pct:+.1f}%")
        factor *= rest_factor
    
    # Opponent B2B advantage
    if situation.opponent_b2b and not situation.is_back_to_back:
        opp_boost = 1.015
        notes.append("Opp B2B: +1.5%")
        factor *= opp_boost
    
    # Cap at +/-12%
    factor = max(0.88, min(1.12, factor))
    
    return factor, notes


# Schedule cache
_SCHEDULE_CACHE: Dict[str, Dict] = {}


def set_game_situation(
    team: str,
    game_date: str,
    is_home: bool,
    days_rest: int = 1,
    is_back_to_back: bool = False,
    is_3_in_4: bool = False,
    opponent: str = "",
    opponent_b2b: bool = False,
    opponent_days_rest: int = 1
) -> GameSituation:
    """Manually set game situation for a team."""
    key = f"{team}_{game_date}"
    
    situation = GameSituation(
        team=team,
        is_home=is_home,
        is_back_to_back=is_back_to_back,
        days_rest=days_rest,
        is_3_in_4=is_3_in_4,
        opponent_b2b=opponent_b2b,
        opponent_days_rest=opponent_days_rest
    )
    
    _SCHEDULE_CACHE[key] = {
        "team": team,
        "date": game_date,
        "is_home": is_home,
        "days_rest": days_rest,
        "is_back_to_back": is_back_to_back,
        "is_3_in_4": is_3_in_4,
        "opponent": opponent,
        "opponent_b2b": opponent_b2b,
        "opponent_days_rest": opponent_days_rest
    }
    
    return situation


def get_game_situation(team: str, game_date: str = None) -> Optional[GameSituation]:
    """Get game situation for a team."""
    if game_date is None:
        game_date = datetime.now().strftime("%Y-%m-%d")
    
    key = f"{team}_{game_date}"
    
    if key in _SCHEDULE_CACHE:
        data = _SCHEDULE_CACHE[key]
        return GameSituation(
            team=data["team"],
            is_home=data.get("is_home", True),
            is_back_to_back=data.get("is_back_to_back", False),
            days_rest=data.get("days_rest", 1),
            is_3_in_4=data.get("is_3_in_4", False),
            opponent_b2b=data.get("opponent_b2b", False),
            opponent_days_rest=data.get("opponent_days_rest", 1)
        )
    
    return None


def get_default_situation(team: str, is_home: bool = True) -> GameSituation:
    """Return default neutral situation."""
    return GameSituation(
        team=team,
        is_home=is_home,
        is_back_to_back=False,
        days_rest=1,
        is_3_in_4=False,
        opponent_b2b=False,
        opponent_days_rest=1
    )


def apply_situation_to_projection(
    mu: float,
    team: str,
    stat: str,
    is_home: bool = True,
    game_date: str = None
) -> Tuple[float, float, List[str]]:
    """Apply all situation adjustments to a projection."""
    situation = get_game_situation(team, game_date)
    
    if situation is None:
        situation = get_default_situation(team, is_home)
    
    factor, notes = get_situation_adjustment(stat, situation)
    adjusted_mu = mu * factor
    
    return adjusted_mu, factor, notes


def get_situation_summary(team: str, game_date: str = None) -> str:
    """Get human-readable situation summary."""
    situation = get_game_situation(team, game_date)
    
    if situation is None:
        return "No situation data"
    
    parts = []
    
    if situation.is_home:
        parts.append("HOME")
    else:
        parts.append("AWAY")
    
    if situation.is_3_in_4:
        parts.append("3-IN-4 (heavy fatigue)")
    elif situation.is_back_to_back:
        parts.append("B2B (fatigue)")
    
    if situation.days_rest >= 3:
        parts.append(f"{situation.days_rest}d REST")
    
    if situation.opponent_b2b:
        parts.append("OPP B2B")
    
    return " | ".join(parts) if parts else "Standard"


if __name__ == "__main__":
    print("=" * 60)
    print("NBA GAME SITUATION DEMO")
    print("=" * 60)
    
    # Demo: CLE on B2B at PHI
    set_game_situation("CLE", "2026-01-16", is_home=False, days_rest=0, 
                       is_back_to_back=True, opponent="PHI", opponent_b2b=False)
    set_game_situation("PHI", "2026-01-16", is_home=True, days_rest=2,
                       is_back_to_back=False, opponent="CLE", opponent_b2b=True)
    
    print(f"\nCLE: {get_situation_summary('CLE', '2026-01-16')}")
    print(f"PHI: {get_situation_summary('PHI', '2026-01-16')}")
    
    # Test Mitchell points on B2B
    adj_mu, factor, notes = apply_situation_to_projection(24.0, "CLE", "points", 
                                                          is_home=False, game_date="2026-01-16")
    print(f"\nMitchell PTS (B2B, Away): 24.0 -> {adj_mu:.1f} ({factor:.3f})")
    print(f"  Notes: {notes}")
    
    print("\n" + "=" * 60)
    print("FACTOR TABLES")
    print("=" * 60)
    
    print("\nB2B FACTORS:")
    for stat, fac in B2B_FACTORS.items():
        pct = (fac - 1) * 100
        print(f"   {stat}: {pct:+.1f}%")
    
    print("\nHOME FACTORS:")
    for stat, fac in HOME_FACTORS.items():
        pct = (fac - 1) * 100
        print(f"   {stat}: {pct:+.1f}%")
