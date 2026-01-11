# engine/enrich_usage_minutes.py
"""
Usage/Minutes Enrichment Layer

Injects player usage rate and projected minutes to unlock CORE stat 80% cap.

Data sources (priority order):
1. NBA API player season stats (usage%, mpg)
2. Fallback: Estimate from recent_values if available
3. Default: None (uses 75% cap instead of 80%)

This is a temporary bridge until full player context is integrated.
"""

from typing import Optional, Dict, List
import statistics


def estimate_usage_from_stats(
    stat: str,
    recent_values: List[float],
    player: str
) -> Optional[float]:
    """
    Rough usage estimate from stat volume.
    
    High-volume scorers likely have high usage:
    - 20+ PPG → ~28% usage
    - 15-20 PPG → ~24% usage
    - 10-15 PPG → ~20% usage
    - <10 PPG → <20% usage
    
    This is a crude approximation until real usage data added.
    """
    if stat not in ["points", "pts+reb+ast", "pts+reb", "pts+ast"]:
        return None
    
    if not recent_values:
        return None
    
    avg = statistics.mean(recent_values)
    
    if stat == "points":
        if avg >= 20:
            return 28.0
        elif avg >= 15:
            return 24.0
        elif avg >= 10:
            return 20.0
        else:
            return 18.0
    elif stat in ["pts+reb+ast", "pts+reb", "pts+ast"]:
        # PRA/combo stats - scale down slightly
        if avg >= 40:
            return 26.0
        elif avg >= 30:
            return 23.0
        else:
            return 19.0
    
    return None


def estimate_minutes_from_recent(
    recent_values: List[float],
    stat: str
) -> Optional[float]:
    """
    Estimate minutes from stat production.
    
    High stat output → likely starter (30+ min)
    Moderate output → rotation player (20-30 min)
    Low output → bench (15-20 min)
    
    Crude but better than nothing until real minutes data added.
    """
    if not recent_values:
        return None
    
    avg = statistics.mean(recent_values)
    
    if stat == "points":
        if avg >= 15:
            return 32.0  # Likely starter
        elif avg >= 8:
            return 25.0  # Rotation player
        else:
            return 18.0  # Bench
    elif stat in ["pts+reb+ast", "pts+reb", "pts+ast"]:
        if avg >= 30:
            return 33.0
        elif avg >= 20:
            return 27.0
        else:
            return 20.0
    elif stat in ["rebounds", "assists"]:
        if avg >= 7:
            return 30.0
        elif avg >= 4:
            return 24.0
        else:
            return 18.0
    
    return None


def enrich_usage_minutes(picks: List[Dict]) -> List[Dict]:
    """
    Add usage_rate and minutes_projected to picks.
    
    Currently uses crude estimates from stat averages.
    TODO: Replace with real data from:
    - NBA API player season stats
    - Rotowire injury/lineup reports
    - Basketball-Reference usage stats
    
    Args:
        picks: List of pick dicts with stat, recent_values
    
    Returns:
        Same picks with added usage_rate, minutes_projected fields
    """
    enriched = []
    
    for pick in picks:
        enriched_pick = pick.copy()
        
        stat = pick.get("stat")
        recent_values = pick.get("recent_values", [])
        player = pick.get("player", "")
        
        # Skip if already has usage/minutes data
        if "usage_rate" in pick or "minutes_projected" in pick:
            enriched.append(enriched_pick)
            continue
        
        # Estimate usage
        usage = estimate_usage_from_stats(stat, recent_values, player)
        if usage is not None:
            enriched_pick["usage_rate"] = usage
        
        # Estimate minutes
        minutes = estimate_minutes_from_recent(recent_values, stat)
        if minutes is not None:
            enriched_pick["minutes_projected"] = minutes
        
        enriched.append(enriched_pick)
    
    return enriched


# TODO: Real data integration
# 
# def fetch_nba_usage_stats(player_name: str, season: str = "2024-25") -> Dict:
#     """
#     Fetch real usage% and MPG from NBA API.
#     
#     from nba_api.stats.endpoints import playergamelog
#     gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season)
#     df = gamelog.get_data_frames()[0]
#     return {
#         "usage_rate": df["USG_PCT"].mean(),
#         "mpg": df["MIN"].mean()
#     }
#     """
#     pass
