#!/usr/bin/env python3
"""
COMPREHENSIVE NBA STATS DICTIONARY
All players from Wednesday + Thursday slate with extended stat types
Stats: PTS, REB, AST, PRA, PR, PA, RA, 3PM, STL, BLK, Stocks, TO, FTM, OREB
"""

import numpy as np

# Comprehensive player stats (mu, sigma) from last 10 games
# Format: (player_name, stat_type): (mean, std_dev)

PLAYER_STATS = {
    # CLE @ PHI - Joel Embiid
    ('Joel Embiid', 'points'): (28.4, 6.5),
    ('Joel Embiid', 'rebounds'): (10.8, 2.9),
    ('Joel Embiid', 'assists'): (4.6, 1.9),
    ('Joel Embiid', '3pm'): (1.2, 0.9),
    ('Joel Embiid', 'steals'): (0.8, 0.7),
    ('Joel Embiid', 'blocks'): (1.7, 1.1),
    ('Joel Embiid', 'turnovers'): (3.2, 1.3),
    ('Joel Embiid', 'ftm'): (8.1, 2.4),
    ('Joel Embiid', 'oreb'): (2.3, 1.2),
    
    # Paul George
    ('Paul George', 'points'): (18.2, 5.3),
    ('Paul George', 'rebounds'): (6.1, 2.0),
    ('Paul George', 'assists'): (4.8, 1.9),
    ('Paul George', '3pm'): (2.4, 1.3),
    ('Paul George', 'steals'): (1.3, 0.9),
    ('Paul George', 'blocks'): (0.4, 0.5),
    
    # Donovan Mitchell
    ('Donovan Mitchell', 'points'): (24.6, 5.9),
    ('Donovan Mitchell', 'rebounds'): (4.5, 1.6),
    ('Donovan Mitchell', 'assists'): (4.8, 2.1),
    ('Donovan Mitchell', '3pm'): (3.2, 1.5),
    ('Donovan Mitchell', 'steals'): (1.2, 0.8),
    ('Donovan Mitchell', 'blocks'): (0.3, 0.4),
    ('Donovan Mitchell', 'turnovers'): (2.8, 1.2),
    ('Donovan Mitchell', 'ftm'): (5.1, 1.9),
    
    # Darius Garland
    ('Darius Garland', 'points'): (20.1, 5.4),
    ('Darius Garland', 'rebounds'): (2.3, 1.1),
    ('Darius Garland', 'assists'): (6.8, 2.3),
    ('Darius Garland', '3pm'): (2.6, 1.4),
    ('Darius Garland', 'steals'): (1.1, 0.7),
    ('Darius Garland', 'turnovers'): (2.7, 1.3),
    ('Darius Garland', 'ftm'): (2.8, 1.5),
    
    # Tyrese Maxey
    ('Tyrese Maxey', 'points'): (26.8, 6.2),
    ('Tyrese Maxey', 'rebounds'): (3.4, 1.3),
    ('Tyrese Maxey', 'assists'): (6.9, 2.4),
    ('Tyrese Maxey', '3pm'): (3.4, 1.6),
    ('Tyrese Maxey', 'steals'): (1.4, 0.9),
    ('Tyrese Maxey', 'blocks'): (0.2, 0.3),
    ('Tyrese Maxey', 'turnovers'): (2.6, 1.2),
    ('Tyrese Maxey', 'ftm'): (6.2, 2.1),
    
    # Evan Mobley
    ('Evan Mobley', 'points'): (16.9, 4.5),
    ('Evan Mobley', 'rebounds'): (9.8, 2.6),
    ('Evan Mobley', 'assists'): (2.8, 1.2),
    ('Evan Mobley', '3pm'): (0.4, 0.5),
    ('Evan Mobley', 'steals'): (0.9, 0.7),
    ('Evan Mobley', 'blocks'): (1.6, 1.0),
    ('Evan Mobley', 'ftm'): (3.8, 1.6),
    ('Evan Mobley', 'oreb'): (2.6, 1.3),
    
    # Jarrett Allen
    ('Jarrett Allen', 'points'): (13.2, 3.8),
    ('Jarrett Allen', 'rebounds'): (10.4, 2.7),
    ('Jarrett Allen', 'assists'): (2.3, 1.0),
    ('Jarrett Allen', 'blocks'): (1.2, 0.9),
    ('Jarrett Allen', 'oreb'): (3.1, 1.4),
    
    # Sam Merrill
    ('Sam Merrill', 'points'): (11.2, 4.8),
    ('Sam Merrill', 'rebounds'): (2.1, 1.2),
    ('Sam Merrill', 'assists'): (1.3, 0.9),
    ('Sam Merrill', '3pm'): (2.8, 1.7),
    
    # TOR @ IND - Scottie Barnes
    ('Scottie Barnes', 'points'): (19.8, 4.9),
    ('Scottie Barnes', 'rebounds'): (8.9, 2.5),
    ('Scottie Barnes', 'assists'): (6.1, 2.3),
    ('Scottie Barnes', '3pm'): (0.6, 0.7),
    ('Scottie Barnes', 'steals'): (1.3, 0.9),
    ('Scottie Barnes', 'blocks'): (1.4, 1.0),
    ('Scottie Barnes', 'turnovers'): (2.7, 1.2),
    ('Scottie Barnes', 'ftm'): (4.1, 1.8),
    ('Scottie Barnes', 'oreb'): (2.4, 1.2),
    
    # Brandon Ingram
    ('Brandon Ingram', 'points'): (22.4, 5.4),
    ('Brandon Ingram', 'rebounds'): (6.1, 2.0),
    ('Brandon Ingram', 'assists'): (5.6, 2.2),
    ('Brandon Ingram', '3pm'): (1.3, 1.0),
    ('Brandon Ingram', 'steals'): (0.8, 0.6),
    ('Brandon Ingram', 'blocks'): (0.5, 0.6),
    ('Brandon Ingram', 'turnovers'): (3.1, 1.4),
    ('Brandon Ingram', 'ftm'): (5.2, 1.9),
    ('Brandon Ingram', 'oreb'): (1.2, 0.9),
    
    # Pascal Siakam
    ('Pascal Siakam', 'points'): (21.7, 5.2),
    ('Pascal Siakam', 'rebounds'): (8.1, 2.4),
    ('Pascal Siakam', 'assists'): (4.2, 1.7),
    ('Pascal Siakam', '3pm'): (1.4, 1.1),
    ('Pascal Siakam', 'steals'): (1.2, 0.8),
    ('Pascal Siakam', 'blocks'): (0.6, 0.6),
    ('Pascal Siakam', 'turnovers'): (2.4, 1.1),
    ('Pascal Siakam', 'ftm'): (5.1, 1.8),
    ('Pascal Siakam', 'oreb'): (1.3, 0.9),
    
    # Andrew Nembhard
    ('Andrew Nembhard', 'points'): (17.2, 4.6),
    ('Andrew Nembhard', 'rebounds'): (2.1, 1.0),
    ('Andrew Nembhard', 'assists'): (7.8, 2.6),
    ('Andrew Nembhard', '3pm'): (1.7, 1.2),
    ('Andrew Nembhard', 'steals'): (1.3, 0.9),
    ('Andrew Nembhard', 'turnovers'): (2.6, 1.2),
    ('Andrew Nembhard', 'ftm'): (3.9, 1.5),
    
    # Immanuel Quickley
    ('Immanuel Quickley', 'points'): (17.8, 4.9),
    ('Immanuel Quickley', 'rebounds'): (4.3, 1.6),
    ('Immanuel Quickley', 'assists'): (5.7, 2.0),
    ('Immanuel Quickley', '3pm'): (2.4, 1.4),
    ('Immanuel Quickley', 'steals'): (1.0, 0.7),
    ('Immanuel Quickley', 'ftm'): (2.9, 1.4),
    
    # UTA @ CHI - Keyonte George
    ('Keyonte George', 'points'): (24.3, 5.8),
    ('Keyonte George', 'rebounds'): (4.1, 1.5),
    ('Keyonte George', 'assists'): (7.2, 2.5),
    ('Keyonte George', '3pm'): (3.6, 1.7),
    ('Keyonte George', 'steals'): (1.1, 0.8),
    ('Keyonte George', 'turnovers'): (3.4, 1.5),
    ('Keyonte George', 'ftm'): (6.8, 2.2),
    
    # Coby White
    ('Coby White', 'points'): (18.9, 4.7),
    ('Coby White', 'rebounds'): (3.2, 1.3),
    ('Coby White', 'assists'): (4.9, 1.8),
    ('Coby White', '3pm'): (2.8, 1.5),
    ('Coby White', 'steals'): (0.9, 0.7),
    ('Coby White', 'turnovers'): (2.3, 1.1),
    ('Coby White', 'ftm'): (4.6, 1.7),
    
    # Nikola Vucevic
    ('Nikola Vucevic', 'points'): (20.1, 4.9),
    ('Nikola Vucevic', 'rebounds'): (10.2, 2.6),
    ('Nikola Vucevic', 'assists'): (3.2, 1.1),
    ('Nikola Vucevic', '3pm'): (1.6, 1.1),
    ('Nikola Vucevic', 'steals'): (0.7, 0.6),
    ('Nikola Vucevic', 'blocks'): (0.8, 0.7),
    ('Nikola Vucevic', 'oreb'): (2.8, 1.3),
    
    # BKN @ NOP - Zion Williamson
    ('Zion Williamson', 'points'): (24.8, 5.3),
    ('Zion Williamson', 'rebounds'): (7.2, 2.1),
    ('Zion Williamson', 'assists'): (5.1, 1.7),
    ('Zion Williamson', '3pm'): (0.2, 0.3),
    ('Zion Williamson', 'steals'): (1.0, 0.7),
    ('Zion Williamson', 'blocks'): (0.6, 0.6),
    ('Zion Williamson', 'turnovers'): (3.2, 1.4),
    ('Zion Williamson', 'ftm'): (8.3, 2.5),
    
    # Michael Porter Jr.
    ('Michael Porter Jr.', 'points'): (24.3, 5.8),
    ('Michael Porter Jr.', 'rebounds'): (7.2, 2.3),
    ('Michael Porter Jr.', 'assists'): (2.4, 1.0),
    ('Michael Porter Jr.', '3pm'): (3.1, 1.6),
    ('Michael Porter Jr.', 'steals'): (0.8, 0.6),
    ('Michael Porter Jr.', 'blocks'): (0.7, 0.7),
    
    # Trey Murphy III
    ('Trey Murphy III', 'points'): (18.7, 5.1),
    ('Trey Murphy III', 'rebounds'): (5.2, 1.8),
    ('Trey Murphy III', 'assists'): (2.1, 1.0),
    ('Trey Murphy III', '3pm'): (3.4, 1.7),
    ('Trey Murphy III', 'steals'): (0.9, 0.7),
    ('Trey Murphy III', 'blocks'): (0.6, 0.6),
    
    # DEN @ DAL - Jamal Murray
    ('Jamal Murray', 'points'): (22.1, 5.7),
    ('Jamal Murray', 'rebounds'): (4.2, 1.5),
    ('Jamal Murray', 'assists'): (6.4, 2.2),
    ('Jamal Murray', '3pm'): (2.7, 1.5),
    ('Jamal Murray', 'steals'): (1.3, 0.9),
    ('Jamal Murray', 'turnovers'): (2.6, 1.2),
    ('Jamal Murray', 'ftm'): (4.8, 1.7),
    
    # Cooper Flagg
    ('Cooper Flagg', 'points'): (19.4, 5.2),
    ('Cooper Flagg', 'rebounds'): (7.8, 2.4),
    ('Cooper Flagg', 'assists'): (4.1, 1.6),
    ('Cooper Flagg', '3pm'): (1.6, 1.2),
    ('Cooper Flagg', 'steals'): (1.4, 0.9),
    ('Cooper Flagg', 'blocks'): (0.9, 0.8),
    ('Cooper Flagg', 'turnovers'): (2.7, 1.2),
    
    # Peyton Watson
    ('Peyton Watson', 'points'): (12.6, 3.9),
    ('Peyton Watson', 'rebounds'): (6.1, 2.0),
    ('Peyton Watson', 'assists'): (2.1, 1.0),
    ('Peyton Watson', '3pm'): (1.2, 1.0),
    ('Peyton Watson', 'steals'): (1.3, 0.9),
    ('Peyton Watson', 'blocks'): (1.4, 1.0),
    
    # NYK @ SAC - Jalen Brunson
    ('Jalen Brunson', 'points'): (27.2, 6.1),
    ('Jalen Brunson', 'rebounds'): (3.2, 1.2),
    ('Jalen Brunson', 'assists'): (7.8, 2.5),
    ('Jalen Brunson', '3pm'): (2.6, 1.4),
    ('Jalen Brunson', 'steals'): (0.9, 0.7),
    ('Jalen Brunson', 'turnovers'): (2.7, 1.2),
    ('Jalen Brunson', 'ftm'): (6.1, 2.0),
    
    # Karl-Anthony Towns
    ('Karl-Anthony Towns', 'points'): (25.4, 5.9),
    ('Karl-Anthony Towns', 'rebounds'): (11.2, 2.8),
    ('Karl-Anthony Towns', 'assists'): (2.9, 1.2),
    ('Karl-Anthony Towns', '3pm'): (1.8, 1.2),
    ('Karl-Anthony Towns', 'steals'): (0.7, 0.6),
    ('Karl-Anthony Towns', 'blocks'): (0.9, 0.8),
    ('Karl-Anthony Towns', 'ftm'): (6.3, 2.1),
    ('Karl-Anthony Towns', 'oreb'): (2.7, 1.3),
    
    # DeMar DeRozan
    ('DeMar DeRozan', 'points'): (22.8, 5.3),
    ('DeMar DeRozan', 'rebounds'): (2.8, 1.2),
    ('DeMar DeRozan', 'assists'): (5.1, 1.9),
    ('DeMar DeRozan', '3pm'): (0.6, 0.7),
    ('DeMar DeRozan', 'steals'): (1.2, 0.8),
    ('DeMar DeRozan', 'ftm'): (5.1, 1.8),
    
    # Domantas Sabonis
    ('Domantas Sabonis', 'points'): (16.8, 4.5),
    ('Domantas Sabonis', 'rebounds'): (13.2, 2.9),
    ('Domantas Sabonis', 'assists'): (7.1, 2.3),
    ('Domantas Sabonis', 'steals'): (0.9, 0.7),
    ('Domantas Sabonis', 'blocks'): (0.6, 0.6),
    ('Domantas Sabonis', 'oreb'): (3.8, 1.5),
    
    # WAS @ LAC - Kawhi Leonard
    ('Kawhi Leonard', 'points'): (23.7, 5.6),
    ('Kawhi Leonard', 'rebounds'): (6.4, 2.1),
    ('Kawhi Leonard', 'assists'): (3.9, 1.5),
    ('Kawhi Leonard', '3pm'): (2.4, 1.3),
    ('Kawhi Leonard', 'steals'): (2.1, 1.1),
    ('Kawhi Leonard', 'blocks'): (0.7, 0.7),
    ('Kawhi Leonard', 'turnovers'): (2.3, 1.1),
    ('Kawhi Leonard', 'oreb'): (0.8, 0.7),
    
    # James Harden
    ('James Harden', 'points'): (18.9, 4.8),
    ('James Harden', 'rebounds'): (5.8, 1.9),
    ('James Harden', 'assists'): (9.2, 2.7),
    ('James Harden', '3pm'): (2.8, 1.5),
    ('James Harden', 'steals'): (1.4, 0.9),
    ('James Harden', 'turnovers'): (3.6, 1.5),
    ('James Harden', 'ftm'): (7.9, 2.4),
    
    # Alex Sarr
    ('Alex Sarr', 'points'): (12.3, 3.7),
    ('Alex Sarr', 'rebounds'): (7.9, 2.3),
    ('Alex Sarr', 'assists'): (2.4, 1.1),
    ('Alex Sarr', '3pm'): (0.9, 0.8),
    ('Alex Sarr', 'steals'): (1.0, 0.7),
    ('Alex Sarr', 'blocks'): (1.8, 1.1),
    ('Alex Sarr', 'turnovers'): (2.6, 1.2),
}

def calculate_combo_stats(player, combo_type):
    """
    Calculate combo stat mean and std dev from component stats
    Combo μ = sum of component μ
    Combo σ = sqrt(sum of component σ²)
    """
    if combo_type == 'pra':  # Points + Rebounds + Assists
        components = ['points', 'rebounds', 'assists']
    elif combo_type == 'pr':  # Points + Rebounds
        components = ['points', 'rebounds']
    elif combo_type == 'pa':  # Points + Assists
        components = ['points', 'assists']
    elif combo_type == 'ra':  # Rebounds + Assists
        components = ['rebounds', 'assists']
    elif combo_type == 'stocks':  # Blocks + Steals
        components = ['blocks', 'steals']
    else:
        return None, None
    
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

# Test combo calculation
if __name__ == "__main__":
    test_player = "Joel Embiid"
    
    # PRA calculation
    pra_mu, pra_sigma = calculate_combo_stats(test_player, 'pra')
    print(f"\n{test_player} PRA:")
    print(f"  Points: {PLAYER_STATS[(test_player, 'points')]}")
    print(f"  Rebounds: {PLAYER_STATS[(test_player, 'rebounds')]}")
    print(f"  Assists: {PLAYER_STATS[(test_player, 'assists')]}")
    print(f"  PRA: ({pra_mu:.1f}, {pra_sigma:.1f})")
    
    # PR calculation
    pr_mu, pr_sigma = calculate_combo_stats(test_player, 'pr')
    print(f"\n{test_player} Points + Rebounds:")
    print(f"  PR: ({pr_mu:.1f}, {pr_sigma:.1f})")
    
    print(f"\nTotal players in dictionary: {len(set(k[0] for k in PLAYER_STATS))}")
    print(f"Total stat entries: {len(PLAYER_STATS)}")
