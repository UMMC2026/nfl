from dataclasses import dataclass
from typing import Optional

@dataclass
class EdgeRegret:
    edge_id: str
    raw_probability: float
    execution_probability: float
    executed: bool
    outcome: Optional[bool]        # True = win, False = loss
    regret_score: float            # signed EV delta
    opportunity_cost: float        # missed EV if skipped

def compute_regret(edge, stake=1.0):
    if edge.outcome is None:
        return None
    fair_odds = 1 / edge.raw_probability
    ev = (edge.raw_probability * (fair_odds - 1) - (1 - edge.raw_probability)) * stake
    if edge.executed:
        realized = ev if edge.outcome else -stake
        regret = realized - ev
        opp_cost = 0.0
    else:
        realized = 0.0
        regret = -ev
        opp_cost = max(ev, 0)
    return EdgeRegret(
        edge_id=edge.edge_id,
        raw_probability=edge.raw_probability,
        execution_probability=edge.execution_probability,
        executed=edge.executed,
        outcome=edge.outcome,
        regret_score=regret,
        opportunity_cost=opp_cost
    )
