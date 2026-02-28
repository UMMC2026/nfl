#!/usr/bin/env python3
"""
EXTENDED Stats Dictionary - Adding Thursday MEM @ ORL players
Based on 2025-26 season averages (10-game recent form)
"""

import numpy as np

# Import existing Wednesday stats
from comprehensive_stats_dict import PLAYER_STATS as WEDNESDAY_STATS

def calculate_combo_stats(player, combo_type):
    """Calculate combo stat (PRA, PR, PA, RA, Stocks) from base stats"""
    combo_map = {
        'pra': ['points', 'rebounds', 'assists'],
        'pr': ['points', 'rebounds'],
        'pa': ['points', 'assists'],
        'ra': ['rebounds', 'assists'],
        'stocks': ['blocks', 'steals']
    }
    
    if combo_type not in combo_map:
        return None, None
    
    components = combo_map[combo_type]
    mu_total = 0
    var_total = 0
    
    for comp in components:
        key = (player, comp)
        if key not in PLAYER_STATS:
            return None, None
        mu, sigma = PLAYER_STATS[key]
        mu_total += mu
        var_total += sigma ** 2
    
    sigma_total = np.sqrt(var_total)
    return mu_total, sigma_total

# Add Thursday MEM @ ORL players (10-game averages estimated from current season stats)
THURSDAY_STATS = {
    # Paolo Banchero (ORL) - 27/9/6 season avg
    ('Paolo Banchero', 'points'): (27.2, 6.8),
    ('Paolo Banchero', 'rebounds'): (9.1, 2.6),
    ('Paolo Banchero', 'assists'): (5.8, 2.1),
    ('Paolo Banchero', '3pm'): (1.1, 0.9),
    ('Paolo Banchero', 'steals'): (0.9, 0.7),
    ('Paolo Banchero', 'blocks'): (0.6, 0.5),
    ('Paolo Banchero', 'turnovers'): (3.2, 1.4),
    
    # Franz Wagner (ORL) - 22/5/5 season avg
    ('Franz Wagner', 'points'): (21.8, 5.9),
    ('Franz Wagner', 'rebounds'): (5.4, 1.8),
    ('Franz Wagner', 'assists'): (4.8, 1.9),
    ('Franz Wagner', '3pm'): (1.3, 1.0),
    ('Franz Wagner', 'steals'): (1.1, 0.8),
    ('Franz Wagner', 'blocks'): (0.4, 0.5),
    
    # Wendell Carter Jr (ORL) - 12/9/2 season avg
    ('Wendell Carter Jr', 'points'): (12.1, 4.2),
    ('Wendell Carter Jr', 'rebounds'): (9.3, 2.4),
    ('Wendell Carter Jr', 'assists'): (2.1, 1.1),
    ('Wendell Carter Jr', '3pm'): (0.8, 0.8),
    ('Wendell Carter Jr', 'blocks'): (0.9, 0.7),
    ('Wendell Carter Jr', 'oreb'): (3.2, 1.4),
    
    # Anthony Black (ORL) - 12/5/4 season avg
    ('Anthony Black', 'points'): (11.8, 4.9),
    ('Anthony Black', 'rebounds'): (4.9, 1.9),
    ('Anthony Black', 'assists'): (3.9, 1.8),
    ('Anthony Black', '3pm'): (0.9, 0.9),
    ('Anthony Black', 'steals'): (1.2, 0.9),
    ('Anthony Black', 'blocks'): (0.6, 0.6),
    
    # Tristan da Silva (ORL) - role player
    ('Tristan da Silva', 'points'): (8.2, 3.8),
    ('Tristan da Silva', 'rebounds'): (3.1, 1.6),
    ('Tristan da Silva', 'assists'): (1.3, 0.9),
    ('Tristan da Silva', '3pm'): (1.4, 1.1),
    
    # Noah Penda (ORL) - bench player
    ('Noah Penda', 'points'): (6.8, 3.5),
    ('Noah Penda', 'rebounds'): (3.2, 1.8),
    ('Noah Penda', 'assists'): (1.1, 0.8),
    ('Noah Penda', '3pm'): (0.7, 0.8),
    
    # Desmond Bane (MEM) - 24/5/5 season avg
    ('Desmond Bane', 'points'): (23.8, 6.2),
    ('Desmond Bane', 'rebounds'): (5.1, 1.9),
    ('Desmond Bane', 'assists'): (4.9, 2.0),
    ('Desmond Bane', '3pm'): (3.2, 1.6),
    ('Desmond Bane', 'steals'): (1.0, 0.8),
    ('Desmond Bane', 'turnovers'): (2.4, 1.2),
    ('Desmond Bane', 'ftm'): (4.1, 1.8),
    
    # Jaren Jackson Jr (MEM) - 22/6/2 season avg
    ('Jaren Jackson Jr', 'points'): (22.1, 6.8),
    ('Jaren Jackson Jr', 'rebounds'): (6.2, 2.3),
    ('Jaren Jackson Jr', 'assists'): (2.3, 1.2),
    ('Jaren Jackson Jr', '3pm'): (2.1, 1.4),
    ('Jaren Jackson Jr', 'blocks'): (2.2, 1.3),
    ('Jaren Jackson Jr', 'steals'): (0.9, 0.7),
    ('Jaren Jackson Jr', 'turnovers'): (2.1, 1.1),
    ('Jaren Jackson Jr', 'ftm'): (3.8, 1.9),
    
    # Santi Aldama (MEM) - 13/7/2 season avg
    ('Santi Aldama', 'points'): (12.9, 5.1),
    ('Santi Aldama', 'rebounds'): (6.8, 2.4),
    ('Santi Aldama', 'assists'): (2.1, 1.2),
    ('Santi Aldama', '3pm'): (1.8, 1.3),
    ('Santi Aldama', 'oreb'): (1.9, 1.2),
    
    # Vince Williams Jr (MEM) - role player
    ('Vince Williams Jr', 'points'): (8.4, 4.2),
    ('Vince Williams Jr', 'rebounds'): (4.1, 1.8),
    ('Vince Williams Jr', 'assists'): (3.8, 1.7),
    ('Vince Williams Jr', '3pm'): (1.2, 1.0),
    
    # Cam Spencer (MEM) - backup guard
    ('Cam Spencer', 'points'): (10.8, 4.6),
    ('Cam Spencer', 'rebounds'): (2.9, 1.4),
    ('Cam Spencer', 'assists'): (5.9, 2.3),
    ('Cam Spencer', '3pm'): (2.1, 1.4),
    
    # Jock Landale (MEM) - backup center
    ('Jock Landale', 'points'): (9.8, 4.5),
    ('Jock Landale', 'rebounds'): (5.9, 2.6),
    ('Jock Landale', 'assists'): (1.4, 0.9),
    ('Jock Landale', '3pm'): (0.9, 0.9),
    
    # Kentavious Caldwell-Pope (MEM) - 3&D role player
    ('Kentavious Caldwell-Pope', 'points'): (9.1, 3.8),
    ('Kentavious Caldwell-Pope', 'rebounds'): (2.4, 1.2),
    ('Kentavious Caldwell-Pope', 'assists'): (2.1, 1.0),
    ('Kentavious Caldwell-Pope', '3pm'): (1.8, 1.2),
    
    # Cedric Coward (MEM) - bench player
    ('Cedric Coward', 'points'): (11.2, 5.2),
    ('Cedric Coward', 'rebounds'): (5.8, 2.5),
    ('Cedric Coward', 'assists'): (2.2, 1.3),
    ('Cedric Coward', '3pm'): (1.3, 1.1),
    
    # Jaylen Wells (MEM) - bench player
    ('Jaylen Wells', 'points'): (10.4, 4.8),
    ('Jaylen Wells', 'rebounds'): (3.1, 1.6),
    ('Jaylen Wells', 'assists'): (1.6, 1.0),
    ('Jaylen Wells', '3pm'): (1.7, 1.2),
    
    # OKC @ HOU - January 15, 2026
    # Shai Gilgeous-Alexander (OKC)
    ("Shai Gilgeous-Alexander", "points"): (31.2, 6.5),
    ("Shai Gilgeous-Alexander", "rebounds"): (5.6, 1.9),
    ("Shai Gilgeous-Alexander", "assists"): (6.1, 2.2),
    ("Shai Gilgeous-Alexander", "3pm"): (1.8, 1.1),
    ("Shai Gilgeous-Alexander", "steals"): (2.0, 1.0),
    ("Shai Gilgeous-Alexander", "turnovers"): (2.8, 1.3),
    ("Shai Gilgeous-Alexander", "pts+reb+ast"): (42.9, 7.8),
    ("Shai Gilgeous-Alexander", "reb+ast"): (11.7, 2.9),
    ("Shai Gilgeous-Alexander", "1q_pts"): (8.2, 4.1),
    ("Shai Gilgeous-Alexander", "1q_reb"): (1.4, 1.1),
    ("Shai Gilgeous-Alexander", "1q_ast"): (1.5, 1.3),
    ("Shai Gilgeous-Alexander", "1q_pts+reb+ast"): (11.1, 5.2),
    
    # Jalen Williams (OKC)
    ("Jalen Williams", "points"): (20.5, 5.8),
    ("Jalen Williams", "rebounds"): (5.8, 2.1),
    ("Jalen Williams", "assists"): (5.2, 2.0),
    ("Jalen Williams", "3pm"): (1.2, 0.9),
    ("Jalen Williams", "steals"): (1.8, 1.1),
    ("Jalen Williams", "turnovers"): (2.1, 1.2),
    ("Jalen Williams", "reb+ast"): (11.0, 3.1),
    ("Jalen Williams", "1q_pts"): (5.1, 3.2),
    ("Jalen Williams", "1q_pts+reb+ast"): (7.7, 4.5),
    
    # Chet Holmgren (OKC)
    ("Chet Holmgren", "points"): (17.2, 5.5),
    ("Chet Holmgren", "rebounds"): (8.1, 2.5),
    ("Chet Holmgren", "assists"): (2.5, 1.4),
    ("Chet Holmgren", "blocks"): (2.6, 1.5),
    ("Chet Holmgren", "3pm"): (1.5, 1.0),
    
    # Lu Dort (OKC)
    ("Lu Dort", "points"): (8.5, 4.2),
    ("Lu Dort", "rebounds"): (3.8, 1.8),
    ("Lu Dort", "3pm"): (1.3, 1.0),
    ("Lu Dort", "pts+reb+ast"): (12.8, 5.5),
    
    # Alex Caruso (OKC)
    ("Alex Caruso", "points"): (7.2, 3.8),
    ("Alex Caruso", "rebounds"): (2.8, 1.5),
    ("Alex Caruso", "assists"): (2.1, 1.3),
    ("Alex Caruso", "3pm"): (0.9, 0.8),
    ("Alex Caruso", "steals"): (1.5, 1.0),
    
    # Cason Wallace (OKC)
    ("Cason Wallace", "points"): (7.5, 4.1),
    ("Cason Wallace", "rebounds"): (2.5, 1.4),
    ("Cason Wallace", "assists"): (1.8, 1.2),
    ("Cason Wallace", "3pm"): (0.8, 0.7),
    ("Cason Wallace", "steals"): (1.2, 0.9),
    
    # Jaylin Williams (OKC)
    ("Jaylin Williams", "points"): (5.2, 3.5),
    ("Jaylin Williams", "rebounds"): (4.1, 2.0),
    ("Jaylin Williams", "assists"): (1.5, 1.1),
    ("Jaylin Williams", "3pm"): (0.6, 0.7),
    ("Jaylin Williams", "1q_reb"): (1.0, 0.9),
    
    # Ajay Mitchell (OKC)
    ("Ajay Mitchell", "points"): (9.8, 4.8),
    ("Ajay Mitchell", "rebounds"): (3.2, 1.6),
    ("Ajay Mitchell", "assists"): (2.8, 1.5),
    ("Ajay Mitchell", "3pm"): (0.7, 0.8),
    ("Ajay Mitchell", "steals"): (1.0, 0.8),
    
    # Alperen Sengun (HOU)
    ("Alperen Sengun", "points"): (18.8, 5.9),
    ("Alperen Sengun", "rebounds"): (10.2, 2.8),
    ("Alperen Sengun", "assists"): (5.0, 2.1),
    ("Alperen Sengun", "3pm"): (0.6, 0.7),
    ("Alperen Sengun", "steals"): (1.2, 0.9),
    ("Alperen Sengun", "turnovers"): (3.1, 1.4),
    ("Alperen Sengun", "reb+ast"): (15.2, 3.6),
    ("Alperen Sengun", "1q_pts"): (4.7, 3.1),
    ("Alperen Sengun", "1q_reb"): (2.6, 1.5),
    ("Alperen Sengun", "1q_pts+reb+ast"): (8.5, 4.2),
    
    # Jabari Smith Jr (HOU)
    ("Jabari Smith Jr", "points"): (13.2, 5.1),
    ("Jabari Smith Jr", "rebounds"): (8.1, 2.6),
    ("Jabari Smith Jr", "assists"): (1.2, 1.0),
    ("Jabari Smith Jr", "3pm"): (2.1, 1.2),
    ("Jabari Smith Jr", "1q_pts"): (3.3, 2.5),
    ("Jabari Smith Jr", "1q_3pm"): (0.5, 0.6),
    
    # Amen Thompson (HOU)
    ("Amen Thompson", "points"): (15.8, 6.2),
    ("Amen Thompson", "rebounds"): (7.8, 2.7),
    ("Amen Thompson", "assists"): (3.9, 1.9),
    ("Amen Thompson", "3pm"): (0.3, 0.5),
    ("Amen Thompson", "steals"): (1.3, 1.0),
    ("Amen Thompson", "turnovers"): (2.2, 1.3),
    ("Amen Thompson", "reb+ast"): (11.7, 3.5),
    ("Amen Thompson", "1q_pts"): (3.9, 3.0),
    ("Amen Thompson", "1q_reb"): (2.0, 1.4),
    ("Amen Thompson", "1q_pts+reb+ast"): (6.8, 4.1),
    
    # Reed Sheppard (HOU)
    ("Reed Sheppard", "points"): (8.5, 5.2),
    ("Reed Sheppard", "rebounds"): (2.2, 1.4),
    ("Reed Sheppard", "assists"): (2.5, 1.5),
    ("Reed Sheppard", "3pm"): (1.8, 1.3),
    ("Reed Sheppard", "steals"): (1.1, 0.9),
    
    # Steven Adams (HOU)
    ("Steven Adams", "points"): (5.8, 3.2),
    ("Steven Adams", "rebounds"): (7.5, 2.5),
    ("Steven Adams", "assists"): (1.8, 1.2),
    ("Steven Adams", "pts+reb+ast"): (15.1, 4.8),
    ("Steven Adams", "1q_reb"): (1.9, 1.3),
    
    # =========================================================================
    # MISSING PLAYERS PATCH (2026-01-30)
    # Added from pipeline_fixes.py analysis
    # =========================================================================
    
    # Jaden Ivey (DET) - 15.3/3.8/3.9 season avg
    ("Jaden Ivey", "points"): (15.3, 6.2),
    ("Jaden Ivey", "rebounds"): (3.8, 1.9),
    ("Jaden Ivey", "assists"): (3.9, 2.1),
    ("Jaden Ivey", "3pm"): (1.8, 1.3),
    ("Jaden Ivey", "steals"): (0.9, 0.8),
    ("Jaden Ivey", "pts+reb+ast"): (23.0, 7.5),
    ("Jaden Ivey", "pra"): (23.0, 7.5),
    
    # Mouhamed Gueye (WAS) - 4.8/4.2/0.8 season avg
    ("Mouhamed Gueye", "points"): (4.8, 3.2),
    ("Mouhamed Gueye", "rebounds"): (4.2, 2.4),
    ("Mouhamed Gueye", "assists"): (0.8, 0.7),
    ("Mouhamed Gueye", "3pm"): (0.3, 0.5),
    ("Mouhamed Gueye", "pts+reb+ast"): (9.8, 4.8),
    ("Mouhamed Gueye", "pra"): (9.8, 4.8),
    ("Mouhamed Gueye", "blocks"): (0.9, 0.8),
}

# Combine Wednesday + Thursday stats
PLAYER_STATS = {**WEDNESDAY_STATS, **THURSDAY_STATS}

# Test combo calculations
if __name__ == "__main__":
    print("Testing Thursday players combo stats:\n")
    
    # Paolo Banchero PRA
    pra_mu, pra_sigma = calculate_combo_stats('Paolo Banchero', 'pra')
    print(f"Paolo Banchero PRA:")
    print(f"  Points: {PLAYER_STATS[('Paolo Banchero', 'points')]}")
    print(f"  Rebounds: {PLAYER_STATS[('Paolo Banchero', 'rebounds')]}")
    print(f"  Assists: {PLAYER_STATS[('Paolo Banchero', 'assists')]}")
    print(f"  PRA: ({pra_mu:.1f}, {pra_sigma:.1f})")
    print(f"  Line: 36.5 (Average: {pra_mu:.1f})")
    
    # Jaren Jackson Jr blocks
    print(f"\nJaren Jackson Jr Blocks:")
    print(f"  Average: {PLAYER_STATS[('Jaren Jackson Jr', 'blocks')]}")
    print(f"  Line: 1.5")
    
    # Desmond Bane PA
    pa_mu, pa_sigma = calculate_combo_stats('Desmond Bane', 'pa')
    print(f"\nDesmond Bane PA (Points + Assists):")
    print(f"  PA: ({pa_mu:.1f}, {pa_sigma:.1f})")
    print(f"  Line: 24.5")
    
    total_players = len(set([k[0] for k in PLAYER_STATS.keys()]))
    total_entries = len(PLAYER_STATS)
    print(f"\n✅ Total players in EXTENDED dictionary: {total_players}")
    print(f"✅ Total stat entries: {total_entries}")

