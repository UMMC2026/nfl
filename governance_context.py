"""
Governance Context System
Provides blowout risk, minutes survival, garbage-time eligibility
for CALIBRATED report generation.
"""

import json
from pathlib import Path

# Game spread data (Jan 02, 2026 games)
# Format: (away, home): spread_abs (positive = home favored)
GAME_SPREADS = {
    ('BKN', 'WAS'): 3.5,
    ('ATL', 'NYK'): 5.0,
    ('DEN', 'CLE'): 2.5,
    ('ORL', 'CHI'): 1.5,
    ('CHA', 'MIL'): 8.5,
    ('POR', 'NOP'): 4.0,
    ('SAC', 'PHX'): 3.0,
    ('OKC', 'GSW'): 4.5,
    ('MEM', 'LAL'): 6.5,
}

# Player role classifications (for minutes survival and garbage-time eligibility)
PLAYER_ROLES = {
    # Franchise stars (high survivability)
    'Giannis Antetokounmpo': {'role': 'franchise_star', 'minutes_survival': 0.94, 'garbage_time_eligible': False},
    'OG Anunoby': {'role': 'star_starter', 'minutes_survival': 0.92, 'garbage_time_eligible': False},
    'Jalen Williams': {'role': 'star_starter', 'minutes_survival': 0.91, 'garbage_time_eligible': False},
    'Shai Gilgeous-Alexander': {'role': 'franchise_star', 'minutes_survival': 0.93, 'garbage_time_eligible': False},
    'Jamal Murray': {'role': 'star_starter', 'minutes_survival': 0.90, 'garbage_time_eligible': False},
    'Chet Holmgren': {'role': 'defensive_big', 'minutes_survival': 0.85, 'garbage_time_eligible': False},
    'Victor Wembanyama': {'role': 'defensive_big', 'minutes_survival': 0.87, 'garbage_time_eligible': False},
    
    # High-usage starters (moderate survivability)
    'Jaden Ivey': {'role': 'high_usage_starter', 'minutes_survival': 0.88, 'garbage_time_eligible': False},
    'Deni Avdija': {'role': 'high_usage_starter', 'minutes_survival': 0.87, 'garbage_time_eligible': False},
    'Anthony Davis': {'role': 'franchise_star', 'minutes_survival': 0.92, 'garbage_time_eligible': False},
    'Kevin Durant': {'role': 'franchise_star', 'minutes_survival': 0.91, 'garbage_time_eligible': False},
    'Jamal Shead': {'role': 'high_usage_starter', 'minutes_survival': 0.86, 'garbage_time_eligible': False},
    
    # Role players & bench scorers (lower survivability, garbage-time eligible)
    'Jordan Clarkson': {'role': 'bench_scorer', 'minutes_survival': 0.78, 'garbage_time_eligible': True},
    'Bobby Portis': {'role': 'bench_big', 'minutes_survival': 0.80, 'garbage_time_eligible': True},
    'Myles Turner': {'role': 'role_starter', 'minutes_survival': 0.82, 'garbage_time_eligible': False},
    'Ryan Rollins': {'role': 'bench_scorer', 'minutes_survival': 0.72, 'garbage_time_eligible': True},
    'Harrison Barnes': {'role': 'role_starter', 'minutes_survival': 0.83, 'garbage_time_eligible': False},
    'Bam Adebayo': {'role': 'star_starter', 'minutes_survival': 0.90, 'garbage_time_eligible': False},
    'Terance Mann': {'role': 'bench_scorer', 'minutes_survival': 0.70, 'garbage_time_eligible': True},
    'Shaedon Sharpe': {'role': 'bench_scorer', 'minutes_survival': 0.75, 'garbage_time_eligible': True},
    'P.J. Washington': {'role': 'role_starter', 'minutes_survival': 0.84, 'garbage_time_eligible': False},
    'Davion Mitchell': {'role': 'bench_scorer', 'minutes_survival': 0.76, 'garbage_time_eligible': True},
    'Jonas Valanciunas': {'role': 'role_starter', 'minutes_survival': 0.85, 'garbage_time_eligible': False},
    'Scottie Barnes': {'role': 'high_usage_starter', 'minutes_survival': 0.88, 'garbage_time_eligible': False},
    'Immanuel Quickley': {'role': 'bench_scorer', 'minutes_survival': 0.74, 'garbage_time_eligible': True},
    'Justin Champagnie': {'role': 'bench_scorer', 'minutes_survival': 0.68, 'garbage_time_eligible': True},
    'Jalen Brunson': {'role': 'star_starter', 'minutes_survival': 0.91, 'garbage_time_eligible': False},
    "De'Aaron Fox": {'role': 'franchise_star', 'minutes_survival': 0.92, 'garbage_time_eligible': False},
    'Tyrese Maxey': {'role': 'high_usage_starter', 'minutes_survival': 0.89, 'garbage_time_eligible': False},
    'Joel Embiid': {'role': 'franchise_star', 'minutes_survival': 0.88, 'garbage_time_eligible': False},
    'Alex Sarr': {'role': 'high_usage_starter', 'minutes_survival': 0.86, 'garbage_time_eligible': False},
    'Alperen Sengun': {'role': 'star_starter', 'minutes_survival': 0.89, 'garbage_time_eligible': False},
    'Keyonte George': {'role': 'high_usage_starter', 'minutes_survival': 0.87, 'garbage_time_eligible': False},
    'Lauri Markkanen': {'role': 'high_usage_starter', 'minutes_survival': 0.88, 'garbage_time_eligible': False},
    'RJ Barrett': {'role': 'role_starter', 'minutes_survival': 0.83, 'garbage_time_eligible': False},
    'Andrew Wiggins': {'role': 'role_starter', 'minutes_survival': 0.82, 'garbage_time_eligible': False},
    'Naji Marshall': {'role': 'bench_scorer', 'minutes_survival': 0.73, 'garbage_time_eligible': True},
    'Brandon Ingram': {'role': 'star_starter', 'minutes_survival': 0.90, 'garbage_time_eligible': False},
    'Jaime Jaquez': {'role': 'bench_scorer', 'minutes_survival': 0.71, 'garbage_time_eligible': True},
}

def get_blowout_risk(away_team, home_team, away_team_pick=True):
    """
    Determine blowout risk from spread.
    Returns: 'Low' | 'Moderate' | 'High'
    """
    spread_key = (away_team, home_team)
    if spread_key not in GAME_SPREADS:
        # Unknown game, assume moderate
        return 'Moderate'
    
    spread = GAME_SPREADS[spread_key]
    
    # Adjust spread direction based on team
    if not away_team_pick:
        spread = -spread
    
    if abs(spread) <= 3.5:
        return 'Low'
    elif abs(spread) <= 6.0:
        return 'Moderate'
    else:
        return 'High'

def get_governance_context(player_name, team, spread_info=None):
    """
    Get governance context for a player.
    Returns dict with blowout_risk, minutes_survival, garbage_time_eligible, role
    """
    # Get player role (default to role_starter if unknown)
    if player_name in PLAYER_ROLES:
        context = PLAYER_ROLES[player_name].copy()
    else:
        context = {
            'role': 'unknown',
            'minutes_survival': 0.80,
            'garbage_time_eligible': False
        }
    
    # Blowout risk is computed externally (needs game info)
    # For now, default to 'Moderate'
    context['blowout_risk'] = 'Moderate'
    
    return context

def apply_blowout_penalty(base_prob, blowout_risk, role):
    """
    Apply soft confidence penalty based on blowout risk and player role.
    Does NOT hard-block plays, just adjusts confidence.
    
    Returns: adjusted probability
    """
    if blowout_risk == 'Low':
        return base_prob  # No penalty
    elif blowout_risk == 'Moderate':
        # Slight penalty for role players, minimal for stars
        if role in ['bench_scorer', 'bench_big']:
            return base_prob * 0.96  # –4%
        else:
            return base_prob * 0.98  # –2%
    else:  # High blowout risk
        # Meaningful penalty for vulnerable players
        if role in ['bench_scorer', 'bench_big']:
            return base_prob * 0.92  # –8%
        elif role in ['high_usage_starter', 'role_starter']:
            return base_prob * 0.95  # –5%
        else:  # Stars
            return base_prob * 0.97  # –3%

def format_governance_annotation(player_name, blowout_risk, role, team=None):
    """
    Format inline governance annotation for report display.
    Example: [Min:28-33 ✅ | Rest:2d+ | Blowout:Moderate ⚠️ | Survival:0.80]
    """
    if player_name in PLAYER_ROLES:
        context = PLAYER_ROLES[player_name].copy()
    else:
        context = {
            'role': 'unknown',
            'minutes_survival': 0.80,
            'garbage_time_eligible': False
        }
    
    blowout_emoji = '✅' if blowout_risk == 'Low' else ('⚠️' if blowout_risk == 'Moderate' else '❌')
    survival_prob = context['minutes_survival']
    garbage_eligible = '(+GT)' if context['garbage_time_eligible'] else ''
    
    return f"[Blowout:{blowout_risk} {blowout_emoji} | Survival:{survival_prob:.0%} {garbage_eligible}]"

if __name__ == '__main__':
    # Quick test
    print(format_governance_annotation('Jordan Clarkson', 'High', 'bench_scorer'))
    print(format_governance_annotation('Giannis Antetokounmpo', 'High', 'franchise_star'))
