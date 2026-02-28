import numpy as np
from core.kalman_filter import KalmanFilter

def apply_kalman_filter_to_series(series, initial_var=1.0, process_var=1.0, measurement_var=1.0):
    """
    Apply Kalman filter to a time series (e.g., assists per match).
    Returns filtered mean and variance.
    """
    if not series:
        return None, None
    kf = KalmanFilter(initial_mean=series[0], initial_var=initial_var, process_var=process_var, measurement_var=measurement_var)
    filtered = []
    for obs in series:
        mu, var, _ = kf.update(obs)
        filtered.append(mu)
    return filtered[-1], var

# Example usage:
# assists_series = [0, 1, 0, 2, 0, 1]
# filtered_mean, filtered_var = apply_kalman_filter_to_series(assists_series)
# print(f"Filtered assists mean: {filtered_mean:.2f}, variance: {filtered_var:.2f}")


def add_filtered_features(player_stats):
    """
    For each player, add filtered features (e.g., kalman_assists_mean, kalman_assists_var)
    to the player stats dict, using their assists history if available.
    """
    for player, stats in player_stats.items():
        assists_hist = stats.get('assists_history')
        if assists_hist:
            mu, var = apply_kalman_filter_to_series(assists_hist)
            stats['kalman_assists_mean'] = mu
            stats['kalman_assists_var'] = var
    return player_stats
