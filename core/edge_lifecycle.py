from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import math

@dataclass
class MarketSnapshot:
    timestamp: datetime
    line: float
    implied_probability: float

@dataclass
class EdgeLifecycle:
    edge_id: str
    platform: str
    publish_time: datetime
    initial_line: float
    initial_probability: float
    snapshots: List[MarketSnapshot]
    decay_rate: float
    half_life_minutes: float
    invalidated: bool = False
    outcome: Optional[bool] = None

def compute_half_life(snapshots: List[MarketSnapshot], base_prob: float):
    if len(snapshots) < 2:
        return None
    t0 = snapshots[0].timestamp
    p0 = base_prob
    for snap in snapshots[1:]:
        delta_p = abs(snap.implied_probability - p0)
        if delta_p >= 0.5 * p0:
            dt = (snap.timestamp - t0).total_seconds() / 60
            return dt
    return None

def execution_probability(raw_p, half_life, minutes_since_publish):
    if half_life is None:
        return raw_p * 0.85  # uncertainty penalty
    decay = math.exp(-minutes_since_publish / half_life)
    return raw_p * decay

def should_suppress_edge(edge: EdgeLifecycle):
    if edge.invalidated:
        return True
    if edge.half_life_minutes is not None and edge.half_life_minutes < 5:
        return True  # market too fast
    return False
