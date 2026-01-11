"""
Stability scoring module - measures signal reliability based on edge-to-variance ratio.
"""


def stability_score(edge: float, std: float) -> float:
    """
    Calculate stability score as edge / standard deviation.
    Higher score = more reliable signal.
    """
    if std <= 0:
        return 0.0
    return round(edge / std, 2)


def stability_class(score: float) -> str:
    """
    Classify stability into tiers:
    - ELITE: score >= 1.4 (signal is 1.4+ std devs from line)
    - SOLID: score >= 1.0 (signal is 1+ std devs from line)
    - FRAGILE: score < 1.0 (too close to line, high variance risk)
    """
    if score >= 1.4:
        return "ELITE"
    elif score >= 1.0:
        return "SOLID"
    else:
        return "FRAGILE"
