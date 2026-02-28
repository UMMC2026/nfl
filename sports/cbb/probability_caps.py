"""
CBB Probability Capping and Confidence Badge Logic
Implements stat-specific probability caps and badge assignment for output realism.
"""

def cap_probability(stat: str, probability: float, sample_n: int, variance: float) -> float:
    # Stat-specific hard caps (example values)
    STAT_CAPS = {
        'PTS': 0.80,
        'AST': 0.75,
        'REB': 0.78,
        # ... extend as needed ...
    }
    # Lower cap for low sample or high variance
    if sample_n < 5 or variance > 10:
        return min(probability, 0.70)
    return min(probability, STAT_CAPS.get(stat, 0.80))

def assign_confidence_badge(probability: float, sample_n: int, variance: float) -> str:
    # Simple badge logic: GREEN, AMBER, RED
    if probability >= 0.75 and sample_n >= 8 and variance < 6:
        return "GREEN"
    elif probability >= 0.60 and sample_n >= 5 and variance < 12:
        return "AMBER"
    return "RED"
