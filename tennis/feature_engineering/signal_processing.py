import numpy as np
from core.kalman_filter import KalmanFilter

def apply_kalman_filter_to_series(series, initial_var=1.0, process_var=1.0, measurement_var=1.0):
    if not series:
        return None, None
    kf = KalmanFilter(initial_mean=series[0], initial_var=initial_var, process_var=process_var, measurement_var=measurement_var)
    filtered = []
    for obs in series:
        mu, var, _ = kf.update(obs)
        filtered.append(mu)
    return filtered[-1], var


def add_filtered_features(player_stats):
    """
    For each player, add filtered features (e.g., kalman_aces_mean, kalman_aces_var, kalman_games_mean, kalman_games_var)
    to the player stats dict, using their stat histories if available.
    """
    for player, stats in player_stats.items():
        for stat_key, out_keys in [
            ('aces_history', ('kalman_aces_mean', 'kalman_aces_var')),
            ('games_history', ('kalman_games_mean', 'kalman_games_var'))
        ]:
            hist = stats.get(stat_key)
            if hist:
                mu, var = apply_kalman_filter_to_series(hist)
                stats[out_keys[0]] = mu
                stats[out_keys[1]] = var
    return player_stats
