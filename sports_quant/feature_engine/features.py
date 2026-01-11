from typing import Sequence, Tuple
import numpy as np


def ewma(values: Sequence[float], alpha: float = 0.3) -> float:
    """Exponentially weighted moving average."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    w = (1 - alpha) ** np.arange(arr.size - 1, -1, -1)
    w = w / w.sum()
    return float(np.dot(arr, w))


def rolling_std(values: Sequence[float], window: int = 5) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    if arr.size < window:
        return float(np.std(arr, ddof=1) if arr.size > 1 else 0.0)
    return float(np.std(arr[-window:], ddof=1))


def normalize_mean_variance(values: Sequence[float], opponent_delta: float = 0.0, pace_factor: float = 1.0,
                             recency_alpha: float = 0.3) -> Tuple[float, float]:
    """Compute mean and variance ready for simulation, adjusted by opponent and pace with recency weighting."""
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0, 1.0  # default variance guard
    mean_recency = ewma(arr, alpha=recency_alpha)
    mean_adj = (mean_recency + opponent_delta) * pace_factor
    var = float(np.var(arr, ddof=1) if arr.size > 1 else 1.0)
    return float(mean_adj), max(var, 1e-6)
