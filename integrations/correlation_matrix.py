"""
Correlation Matrix System for NBA Parlay AI
- Stores and retrieves stat, player, and game correlations
- Used to flag dangerous parlay combinations and apply correlation penalties
"""

STAT_CORRELATIONS = {
    ('PTS', 'AST'): 0.15,  # Slightly positive
    ('PTS', 'REB'): -0.05,  # Slightly negative
    ('REB', 'AST'): -0.20,  # Negative (usage trade-off)
    ('3PM', 'FGA'): 0.45,  # Positive (volume dependent)
}

PLAYER_CORRELATIONS = {
    ('Markkanen', 'Filipowski'): -0.35,  # Usage conflict
    ('LeBron', 'AD'): -0.15,  # Slight usage conflict
    ('Curry', 'Poole'): 0.20,  # Complementary
}

def get_stat_correlation(stat_a, stat_b):
    return STAT_CORRELATIONS.get((stat_a, stat_b)) or STAT_CORRELATIONS.get((stat_b, stat_a), 0.0)

def get_player_correlation(player_a, player_b):
    return PLAYER_CORRELATIONS.get((player_a, player_b)) or PLAYER_CORRELATIONS.get((player_b, player_a), 0.0)

def check_parlay_correlation(legs):
    """
    Returns: ("SAFE", None) or ("DANGEROUS", reason)
    """
    import itertools
    for leg_a, leg_b in itertools.combinations(legs, 2):
        if getattr(leg_a, 'game_id', None) == getattr(leg_b, 'game_id', None):
            # Same game correlation check
            if leg_a.player == leg_b.player:
                corr = get_stat_correlation(leg_a.stat, leg_b.stat)
                if abs(corr) > 0.3:
                    return ("DANGEROUS", f"Stats correlated: {leg_a.stat} & {leg_b.stat} ({corr:+.2f})")
            elif leg_a.player != leg_b.player:
                corr = get_player_correlation(leg_a.player, leg_b.player)
                if abs(corr) > 0.3:
                    return ("DANGEROUS", f"Players correlated: {leg_a.player} & {leg_b.player} ({corr:+.2f})")
    return ("SAFE", None)
