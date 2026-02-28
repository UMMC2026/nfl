"""Agent councils for NFL / NBA / Soccer.

These are orchestration helpers that combine multiple agent opinions into a
single pick, then run the SOP enforcer. They do not change any existing
pipelines unless explicitly called.
"""

from dataclasses import asdict
from typing import Dict, List

from .sop_enforcer import AgentPick, SOPEnforcer


class SportCouncilBase:
    def __init__(self, sport: str, agent_weights: Dict[str, float]):
        self.sport = sport.upper()
        # Normalize weights
        total = sum(agent_weights.values()) or 1.0
        self.agent_weights = {k: v / total for k, v in agent_weights.items()}
        self.enforcer = SOPEnforcer()

    def aggregate(self, picks: List[AgentPick]) -> Dict:
        """Aggregate multiple AgentPick objects for the same underlying market.

        We compute a weighted average probability based on source weights, then
        pass a representative pick through the SOPEnforcer.
        """
        if not picks:
            raise ValueError("No picks provided to council")

        # Use the first pick as template
        base = picks[0]

        # Weighted probability; ignore sources with zero weight
        num = 0.0
        den = 0.0
        for p in picks:
            w = self.agent_weights.get(p.source, 0.0)
            if w <= 0.0:
                continue
            prob = p.probability
            if prob > 1.0:
                prob = prob / 100.0
            num += w * prob
            den += w
        p_agg = (num / den) if den > 0 else 0.5

        agg_pick = AgentPick(
            sport=self.sport,
            entity=base.entity,
            market=base.market,
            line=base.line,
            direction=base.direction,
            probability=p_agg,
            edge=base.edge,
            tier=base.tier,
            source="council",
            metadata={"agents": [p.source for p in picks]},
        )

        sop = self.enforcer.enforce(agg_pick)
        return {
            "entity": agg_pick.entity,
            "market": agg_pick.market,
            "line": agg_pick.line,
            "direction": agg_pick.direction,
            "sport": self.sport,
            "probability": sop.probability,
            "tier": sop.tier,
            "decision": sop.decision,
            "sop": asdict(sop),
            "agents": [asdict(p) for p in picks],
        }


class NBACouncil(SportCouncilBase):
    def __init__(self):
        super().__init__(
            sport="NBA",
            agent_weights={
                "oracle": 0.5,
                "risk_engine": 0.3,
                "market": 0.2,
            },
        )


class NFLCouncil(SportCouncilBase):
    def __init__(self):
        super().__init__(
            sport="NFL",
            agent_weights={
                "oracle": 0.4,
                "truth_engine": 0.4,
                "market": 0.2,
            },
        )


class SoccerCouncil(SportCouncilBase):
    def __init__(self):
        super().__init__(
            sport="SOCCER",
            agent_weights={
                "oracle": 0.5,
                "model": 0.3,
                "market": 0.2,
            },
        )
