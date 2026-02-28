import numpy as np
from typing import List

def calculate_minute_stability(historical_minutes: List[float], 
                               rotation_rank: int, 
                               is_starter: bool,
                               active_teammates_count: int) -> float:
    """
    Returns a score 0.0 - 1.0. 
    1.0 = This player is guaranteed these minutes (Ironclad).
    0.0 = This player's minutes are a lottery.
    """
    if not historical_minutes: return 0.5
    avg_min = np.mean(historical_minutes)
    std_min = np.std(historical_minutes)
    cv = std_min / avg_min if avg_min > 0 else 1.0
    consistency_score = max(0, 1 - (cv * 2)) 
    crowding_penalty = 0.05 * max(0, active_teammates_count - 9)
    role_bonus = 0.15 if is_starter else 0.0
    stability = (consistency_score * 0.7) + (role_bonus) - (crowding_penalty)
    return float(np.clip(stability, 0.1, 1.0))
