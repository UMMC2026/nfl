import itertools
from typing import List, Dict, Any, Optional
from collections import Counter
from ufa.analysis.ev import entry_ev


def build_entries(
    picks: List[Dict[str, Any]],
    payout_table,
    legs: int,
    min_teams: int = 2,
    max_entries: int = 25,
    same_team_penalty: float = 0.0,
    max_player_legs: int = 0,      # NEW: max legs per player (0 = unlimited)
    max_team_legs: int = 0,        # NEW: max legs per team (0 = unlimited)
    correlation_penalty: float = 0.0,  # NEW: penalty for correlated picks
    correlation_groups: Optional[List[Dict]] = None,  # NEW: correlation definitions
) -> List[Dict[str, Any]]:
    """
    Builds top EV entries under constraints.
    
    picks: list of dict with: id, player, team, stat, p_hit, (optional) game_key
    same_team_penalty: if >0, reduce EV for entries with repeated team(s)
    max_player_legs: max props from same player (0 = no limit)
    max_team_legs: max props from same team (0 = no limit)
    correlation_penalty: 0-1 penalty applied per correlated pair
    correlation_groups: list of {"players": [...], "props": [...]} dicts
    """
    if legs < 2:
        raise ValueError("legs must be >= 2")

    picks_sorted = sorted(picks, key=lambda x: float(x["p_hit"]), reverse=True)
    candidate_pool = picks_sorted[:min(60, len(picks_sorted))]

    results = []

    for combo in itertools.combinations(candidate_pool, legs):
        teams = [c["team"] for c in combo]
        players = [c["player"] for c in combo]
        uniq_teams = set(teams)
        
        # === CONSTRAINT: Minimum unique teams ===
        if len(uniq_teams) < min_teams:
            continue
        
        # === CONSTRAINT: Max legs per player ===
        if max_player_legs > 0:
            player_counts = Counter(players)
            if max(player_counts.values()) > max_player_legs:
                continue
        
        # === CONSTRAINT: Max legs per team ===
        if max_team_legs > 0:
            team_counts = Counter(teams)
            if max(team_counts.values()) > max_team_legs:
                continue

        p_list = [float(c["p_hit"]) for c in combo]
        ev = entry_ev(p_list, payout_table, legs)

        # === PENALTY: Same team stacking ===
        if same_team_penalty > 0:
            counts = Counter(teams)
            max_team_count = max(counts.values())
            if legs > 1 and max_team_count > 1:
                factor = 1.0 - same_team_penalty * (max_team_count - 1) / (legs - 1)
                ev *= max(0.0, factor)
        
        # === PENALTY: Correlation groups ===
        if correlation_penalty > 0 and correlation_groups:
            corr_pairs = 0
            for group in correlation_groups:
                group_players = group.get("players", [])
                matched = [c for c in combo if c["player"] in group_players]
                if len(matched) >= 2:
                    # Count correlated pairs: n players = n*(n-1)/2 pairs
                    corr_pairs += len(matched) * (len(matched) - 1) // 2
            
            if corr_pairs > 0:
                factor = 1.0 - (correlation_penalty * corr_pairs)
                ev *= max(0.1, factor)  # Floor at 10% to not completely zero out

        # Build result with more metadata
        stats = [c.get("stat", "") for c in combo]
        directions = [c.get("direction", "") for c in combo]
        lines = [c.get("line", None) for c in combo]
        opponents = [c.get("opponent", "") for c in combo]

        results.append({
            "legs": legs,
            "teams": sorted(list(uniq_teams)),
            "players": players,
            "stats": stats,
            "directions": directions,
            "lines": lines,
            "opponents": opponents,
            "p_list": [round(p, 4) for p in p_list],
            "ev_units": round(float(ev), 4),
        })

    results.sort(key=lambda r: r["ev_units"], reverse=True)
    return results[:max_entries]
