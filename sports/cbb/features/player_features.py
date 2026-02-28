"""
CBB Player Features

Required features for college basketball edge generation.

IMPORTANT: These are CBB-specific. NBA features will FAIL if reused blindly.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import statistics
import math

# Filtering imports
from core.kalman_filter import KalmanFilter
from core.bayesian_smoothing import bayesian_shrinkage

# Stat-family priors and k-values (extend as needed)
STAT_PRIORS = {
    'PTS': {'prior': 10.0, 'k': 8},
    'AST': {'prior': 3.0, 'k': 6},
    'REB': {'prior': 5.0, 'k': 6},
    # ... add more as needed ...
}

def bayesian_average(stat, sample_mean, sample_n):
    """
    Bayesian averaging for low-sample stats.
    Args:
        stat (str): Stat type (e.g., 'PTS')
        sample_mean (float): Observed mean
        sample_n (int): Sample size
    Returns:
        float: Bayesian average
    """
    prior = STAT_PRIORS.get(stat, {'prior': sample_mean, 'k': 0})['prior']
    k = STAT_PRIORS.get(stat, {'prior': sample_mean, 'k': 0})['k']
    return (sample_n * sample_mean + k * prior) / (sample_n + k)

def calculate_variance(values):
    """
    Calculate variance and coefficient of variation (CV).
    Args:
        values (list of float): Stat values
    Returns:
        (float, float): (variance, coefficient of variation)
    """
    n = len(values)
    if n < 2:
        return 0.0, 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    stddev = math.sqrt(variance)
    cv = stddev / mean if mean != 0 else 0.0
    return variance, cv


@dataclass
class PlayerFeatures:
    """CBB player feature set for edge generation"""
    player_id: str
    player_name: str
    team: str

    # Filtered features
    kalman_points_mean: float = 0.0
    kalman_points_var: float = 0.0
    filtered_points_mean: float = 0.0
    kalman_gain_points_last: float = 0.0
    
    # Rolling averages (minutes-weighted)
    avg_points_l5: float = 0.0
    avg_points_l10: float = 0.0
    avg_points_season: float = 0.0
    blended_points: float = 0.0
    avg_rebounds_l5: float = 0.0
    avg_rebounds_l10: float = 0.0
    avg_rebounds_season: float = 0.0
    blended_rebounds: float = 0.0
    avg_assists_l5: float = 0.0
    avg_assists_l10: float = 0.0
    avg_assists_season: float = 0.0
    blended_assists: float = 0.0
    
    # Minutes stability
    avg_minutes_l5: float = 0.0
    avg_minutes_l10: float = 0.0
    minutes_std_l10: float = 0.0
    
    # Usage proxy (CBB-specific)
    usage_proxy_l5: float = 0.0
    usage_proxy_l10: float = 0.0
    
    # Foul trouble risk (critical in CBB)
    foul_rate_l5: float = 0.0
    fouled_out_count: int = 0
    
    # Role indicators
    is_starter: bool = False
    games_started_pct: float = 0.0
    
    # Sample size
    games_played: int = 0
    
    # Blocking flags
    is_blocked: bool = False
    block_reason: Optional[str] = None


def build_player_features(
    player_id: str,
    game_logs: List[Dict],
    min_games: int = 5
) -> PlayerFeatures:
    """
    Build CBB player features from game logs.
    
    Args:
        player_id: Player identifier
        game_logs: List of game log dictionaries (most recent first)
        min_games: Minimum games required for valid features
        
    Returns:
        PlayerFeatures dataclass
    """
    if not game_logs:
        return PlayerFeatures(
            player_id=player_id,
            player_name="Unknown",
            team="Unknown",
            is_blocked=True,
            block_reason="NO_GAME_LOGS"
        )
    
    # Sort by date descending
    sorted_logs = sorted(game_logs, key=lambda x: x.get("date", ""), reverse=True)
    
    # Get basic info from most recent game
    latest = sorted_logs[0]
    player_name = latest.get("player_name", "Unknown")
    team = latest.get("team", "Unknown")
    
    games_played = len(sorted_logs)
    
    # Check minimum sample
    if games_played < min_games:
        return PlayerFeatures(
            player_id=player_id,
            player_name=player_name,
            team=team,
            games_played=games_played,
            is_blocked=True,
            block_reason=f"INSUFFICIENT_SAMPLE ({games_played} < {min_games})"
        )
    
    # Extract stats arrays
    l5 = sorted_logs[:5]
    l10 = sorted_logs[:10]
    
    def safe_avg(logs: List[Dict], key: str) -> float:
        vals = [g.get(key, 0) for g in logs]
        return round(statistics.mean(vals), 2) if vals else 0.0
    
    def safe_std(logs: List[Dict], key: str) -> float:
        vals = [g.get(key, 0) for g in logs]
        return round(statistics.stdev(vals), 2) if len(vals) > 1 else 0.0
    
    # Calculate season averages
    avg_points_season = safe_avg(sorted_logs, "points")
    avg_rebounds_season = safe_avg(sorted_logs, "rebounds")
    avg_assists_season = safe_avg(sorted_logs, "assists")

    # Blended projections (weights: 0.4 last5, 0.3 last10, 0.3 season)
    def blend(l5, l10, season):
        return round(0.4 * l5 + 0.3 * l10 + 0.3 * season, 2)

    avg_points_l5 = safe_avg(l5, "points")
    avg_points_l10 = safe_avg(l10, "points")
    avg_rebounds_l5 = safe_avg(l5, "rebounds")
    avg_rebounds_l10 = safe_avg(l10, "rebounds")
    avg_assists_l5 = safe_avg(l5, "assists")
    avg_assists_l10 = safe_avg(l10, "assists")

    # --- Kalman Filtering for Points ---
    points_history = [g.get("points", 0) for g in sorted_logs]
    if len(points_history) >= 3:
        initial_mean = sum(points_history[:3]) / 3
        initial_var = 5.0
        process_var = 2.0
        measurement_var = 8.0
        kf = KalmanFilter(initial_mean, initial_var, process_var, measurement_var)
        kalman_means = []
        kalman_vars = []
        kalman_gains = []
        for obs in points_history:
            mean, var, K = kf.update(obs)
            kalman_means.append(mean)
            kalman_vars.append(var)
            kalman_gains.append(K)
        kalman_points_mean = kalman_means[-1]
        kalman_points_var = kalman_vars[-1]
        kalman_gain_points_last = kalman_gains[-1]
    else:
        kalman_points_mean = avg_points_season
        kalman_points_var = 0.0
        kalman_gain_points_last = 0.0

    # --- Bayesian Smoothing for Points ---
    player_n = len(points_history)
    prior_mean = STAT_PRIORS.get('PTS', {'prior': avg_points_season})['prior']
    prior_n = STAT_PRIORS.get('PTS', {'k': 8})['k']
    if player_n < 8:
        filtered_points_mean = bayesian_shrinkage(kalman_points_mean, player_n, prior_mean, prior_n)
    else:
        filtered_points_mean = kalman_points_mean

    features = PlayerFeatures(
        player_id=player_id,
        player_name=player_name,
        team=team,

        avg_points_l5=avg_points_l5,
        avg_points_l10=avg_points_l10,
        avg_points_season=avg_points_season,
        blended_points=blend(avg_points_l5, avg_points_l10, avg_points_season),

        avg_rebounds_l5=avg_rebounds_l5,
        avg_rebounds_l10=avg_rebounds_l10,
        avg_rebounds_season=avg_rebounds_season,
        blended_rebounds=blend(avg_rebounds_l5, avg_rebounds_l10, avg_rebounds_season),

        avg_assists_l5=avg_assists_l5,
        avg_assists_l10=avg_assists_l10,
        avg_assists_season=avg_assists_season,
        blended_assists=blend(avg_assists_l5, avg_assists_l10, avg_assists_season),

        avg_minutes_l5=safe_avg(l5, "minutes"),
        avg_minutes_l10=safe_avg(l10, "minutes"),
        minutes_std_l10=safe_std(l10, "minutes"),

        usage_proxy_l5=safe_avg(l5, "usage_proxy"),
        usage_proxy_l10=safe_avg(l10, "usage_proxy"),

        foul_rate_l5=safe_avg(l5, "foul_rate"),
        fouled_out_count=sum(1 for g in sorted_logs if g.get("fouls", 0) >= 5),

        is_starter=latest.get("started", False),
        games_started_pct=sum(1 for g in sorted_logs if g.get("started")) / games_played,

        games_played=games_played,
        is_blocked=False,
        block_reason=None,

        # Filtered features
        kalman_points_mean=kalman_points_mean,
        kalman_points_var=kalman_points_var,
        filtered_points_mean=filtered_points_mean,
        kalman_gain_points_last=kalman_gain_points_last,
    )
    
    # Apply CBB-specific blocks
    features = apply_cbb_player_blocks(features)
    
    return features


def apply_cbb_player_blocks(features: PlayerFeatures) -> PlayerFeatures:
    """
    Apply CBB-specific blocking rules to player features.
    
    Blocks:
    - Players averaging < 20 mpg
    - Players with high foul rates
    - Bench players with high minutes variance
    """
    from sports.cbb.config import CBB_EDGE_GATES
    
    # Block low-minutes players
    if features.avg_minutes_l10 < CBB_EDGE_GATES.min_minutes_avg:
        features.is_blocked = True
        features.block_reason = f"LOW_MINUTES ({features.avg_minutes_l10:.1f} < {CBB_EDGE_GATES.min_minutes_avg})"
        return features
    
    # Block high foul-rate players
    if features.foul_rate_l5 > 0.15:  # More than 1 foul per 6.7 minutes
        features.is_blocked = True
        features.block_reason = f"HIGH_FOUL_RATE ({features.foul_rate_l5:.3f})"
        return features
    
    # Block bench players with unstable minutes
    if not features.is_starter and features.minutes_std_l10 > 8.0:
        features.is_blocked = True
        features.block_reason = f"BENCH_MINUTES_VOLATILE (std={features.minutes_std_l10:.1f})"
        return features
    
    return features
