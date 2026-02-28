from typing import List, Dict, Optional
from sports.cbb.ingest.cbb_data_provider import CBBDataProvider, CBBPlayer

def generate_roster_table(team_abbr: str, provider: CBBDataProvider, active_edges: Optional[List[Dict]] = None) -> List[str]:
    """
    Generates an ASCII table of roster averages for key players.
    Prioritizes players involved in edges + cached superstars.
    """
    lines = []
    
    # Header
    # ASCII-only header to avoid Windows console mojibake.
    lines.append(f"ROSTER SNAPSHOT - {team_abbr}")
    # Dynamically determine stat fields from CBBPlayer dataclass
    stat_fields = [
        'minutes_per_game', 'points_per_game', 'rebounds_per_game', 'assists_per_game',
        'steals_per_game', 'blocks_per_game', 'turnovers_per_game', 'fg_pct',
        'three_pt_pct', 'three_pm_per_game'
    ]
    stat_labels = {
        'minutes_per_game': 'MIN',
        'points_per_game': 'PTS',
        'rebounds_per_game': 'REB',
        'assists_per_game': 'AST',
        'steals_per_game': 'STL',
        'blocks_per_game': 'BLK',
        'turnovers_per_game': 'TO',
        'fg_pct': 'FG%',
        'three_pt_pct': '3P%',
        'three_pm_per_game': '3PM',
    }
    header = f"{'PLAYER':<20} " + " ".join([f"{stat_labels.get(f, f):>5}" for f in stat_fields])
    lines.append(header)
    lines.append("-" * (22 + 6 * len(stat_fields)))

    players_to_show = []
    
    # Add players from current edges
    if active_edges:
        for e in active_edges:
            if e.get('team') == team_abbr:
                p_obj = provider.get_player_stats_by_name(e['player'], team_abbr)
                if p_obj:
                    players_to_show.append(p_obj)

    # Unique filtering
    seen = set()
    unique_players = []
    for p in players_to_show:
        if p.name not in seen:
            unique_players.append(p)
            seen.add(p.name)
    
    # Sort by PPG (descending)
    sorted_players = sorted(unique_players, key=lambda p: p.points_per_game, reverse=True)

    if not sorted_players:
        lines.append(f"{'[No player data loaded]':<20} {'-':>5} {'-':>5} {'-':>5} {'-':>5} {'-':>5}")
        return lines

    for p in sorted_players:
        row = f"{p.name[:18]:<20} "
        for f in stat_fields:
            val = getattr(p, f, '-')
            if isinstance(val, float):
                row += f"{val:>5.1f} "
            elif isinstance(val, int):
                row += f"{val:>5} "
            else:
                row += f"{'-':>5} "
        lines.append(row.rstrip())
    
    return lines
