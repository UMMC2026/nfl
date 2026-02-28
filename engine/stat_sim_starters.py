import numpy as np
from typing import Dict, List

def simulate_1q_points(player_game_logs: List[Dict], context: Dict) -> Dict:
    """
    Simulate 1st Quarter Points for a player using historical 1Q data.
    player_game_logs: List of dicts with '1q_points', 'minutes', etc.
    context: Game context (pace, spread, etc.)
    Returns: dict with mean, std, hist_min, etc.
    """
    one_q_points = [g['1q_points'] for g in player_game_logs if '1q_points' in g]
    if not one_q_points:
        return {'mean': 0, 'std': 0, 'hist_min': [], 'role_entropy': 0.2, 'left_tail_prob': 0.2, 'right_tail_prob': 0.2}
    mean = np.mean(one_q_points)
    std = np.std(one_q_points)
    # Optionally adjust for context (pace, spread, etc.)
    adj_mean = mean * context.get('pace_adj', 1.0)
    left_tail_prob = float(np.mean([p < mean for p in one_q_points]))
    right_tail_prob = float(np.mean([p > mean for p in one_q_points]))
    return {
        'mean': adj_mean,
        'std': std,
        'hist_min': [g['minutes'] for g in player_game_logs if 'minutes' in g],
        'role_entropy': context.get('role_entropy', 0.2),
        'left_tail_prob': left_tail_prob,
        'right_tail_prob': right_tail_prob
    }

def simulate_double_double(player_game_logs: List[Dict], context: Dict) -> Dict:
    """
    Simulate probability of Double Double for a player.
    player_game_logs: List of dicts with 'points', 'rebounds', 'assists', etc.
    context: Game context (pace, etc.)
    Returns: dict with mean (probability), std, hist_min, etc.
    """
    double_doubles = [
        (g.get('points', 0) >= 10) + (g.get('rebounds', 0) >= 10) + (g.get('assists', 0) >= 10) >= 2
        for g in player_game_logs
    ]
    prob = float(np.mean(double_doubles)) if double_doubles else 0.0
    std = np.std(double_doubles) if double_doubles else 0.0
    return {
        'mean': prob,
        'std': std,
        'hist_min': [g['minutes'] for g in player_game_logs if 'minutes' in g],
        'role_entropy': context.get('role_entropy', 0.2),
        'left_tail_prob': 1 - prob,
        'right_tail_prob': prob
    }
