import numpy as np


def expected_value(prob: float, odds: float) -> float:
    """Compute expected value given probability and decimal odds.

    EV = p * (odds - 1) - (1 - p)

    Args:
        prob: Win probability in [0, 1].
        odds: Decimal odds (> 1.0).
    """
    p = float(prob)
    o = float(odds)
    return p * (o - 1.0) - (1.0 - p)


def kelly_fraction(prob: float, odds: float, fraction: float = 0.25) -> float:
    """Compute fractional Kelly bet size.

    Args:
        prob: Win probability in [0, 1].
        odds: Decimal odds (> 1.0).
        fraction: Fraction of full Kelly (e.g., 0.25 for quarter Kelly).
    """
    p = float(prob)
    o = float(odds)
    b = o - 1.0
    q = 1.0 - p

    if b <= 0:
        return 0.0

    raw_kelly = (b * p - q) / b
    if raw_kelly <= 0:
        return 0.0
    return raw_kelly * float(fraction)


def brier_score(y_true, y_prob) -> float:
    """Compute Brier score for probability forecasts.

    Args:
        y_true: Iterable of 0/1 outcomes.
        y_prob: Iterable of forecast probabilities in [0, 1].
    """
    y_true = np.asarray(y_true, dtype=float)
    y_prob = np.asarray(y_prob, dtype=float)
    return float(np.mean((y_prob - y_true) ** 2))
