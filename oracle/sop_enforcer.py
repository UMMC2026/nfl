"""SOP enforcement layer for Oracle-generated picks.

This module does NOT touch sport-specific pipelines directly. It defines a
simple, auditable contract for enforcing NO PLAY / PLAY decisions based on
probability, edge, and tier thresholds imported from config/thresholds.py.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from config.thresholds import TIERS, implied_tier


@dataclass
class AgentPick:
    sport: str
    entity: str  # player or team name
    market: str  # stat/market name
    line: float
    direction: str  # "Higher" / "Lower"
    probability: float  # decimal [0,1] or percentage [0,100]
    edge: Optional[float] = None  # EV or projected advantage (arbitrary units)
    tier: Optional[str] = None  # Declared tier (SLAM/STRONG/LEAN/etc.)
    source: str = "oracle"  # agent name
    metadata: Optional[Dict] = None


@dataclass
class SOPResult:
    decision: str  # PLAY | LEAN | NO PLAY | BLOCKED
    probability: float  # percentage 0-100
    tier: str
    risk_flags: List[str]
    reasons: List[str]


class SOPEnforcer:
    """Sport-agnostic SOP hard-gate layer.

    Rules are intentionally conservative and can be extended, but they should
    not be sport-pipeline-specific. That wiring is handled by councils or
    higher layers.
    """

    def __init__(self, min_play_prob: float = 0.55, min_edge: float = 0.0):
        # Probabilities are in decimal [0,1]
        self.min_play_prob = float(min_play_prob)
        self.min_edge = float(min_edge)

    def _normalize_prob(self, p: float) -> float:
        """Accept decimal or percentage; return decimal in [0,1]."""
        p = float(p)
        if p > 1.0:
            p = p / 100.0
        return max(0.0, min(1.0, p))

    def enforce(self, pick: AgentPick) -> SOPResult:
        risk_flags: List[str] = []
        reasons: List[str] = []

        p_dec = self._normalize_prob(pick.probability)
        p_pct = p_dec * 100.0

        if p_dec <= 0.0 or p_dec >= 1.0:
            risk_flags.append("bad_probability")
            reasons.append(f"Probability out of bounds: {p_dec:.3f}")

        # Tier check using canonical thresholds
        implied = implied_tier(p_dec, pick.sport.upper())
        declared = (pick.tier or "").upper() or implied
        if declared != implied:
            risk_flags.append("tier_mismatch")
            reasons.append(f"Declared tier {declared} != implied {implied}")

        # Edge gate (if provided)
        if pick.edge is not None and pick.edge < self.min_edge:
            risk_flags.append("negative_edge")
            reasons.append(f"Edge {pick.edge:.3f} < min_edge {self.min_edge:.3f}")

        # Probability gate for PLAY/LEAN
        if p_dec < self.min_play_prob:
            reasons.append(
                f"Probability {p_pct:.1f}% below play threshold {self.min_play_prob*100:.1f}%"
            )
            decision = "NO PLAY"
        else:
            # Map implied tier to simple council decision
            if implied == "SLAM" or implied == "STRONG":
                decision = "PLAY"
            elif implied == "LEAN":
                decision = "LEAN"
            else:
                decision = "NO PLAY"

        # Hard NO PLAY if any severe flags
        if "bad_probability" in risk_flags:
            decision = "NO PLAY"

        return SOPResult(
            decision=decision,
            probability=p_pct,
            tier=implied,
            risk_flags=risk_flags,
            reasons=reasons,
        )


def sop_enforce_pick(pick_dict: Dict) -> Dict:
    """Convenience helper for JSON-style dict picks.

    Expects keys: sport, entity, market, line, direction, probability, edge?, tier?.
    Returns a dict with SOPResult merged in under `sop`.
    """
    pick = AgentPick(
        sport=str(pick_dict.get("sport", "NBA")),
        entity=str(pick_dict.get("entity", pick_dict.get("player", "?"))),
        market=str(pick_dict.get("market", pick_dict.get("stat", "?"))),
        line=float(pick_dict.get("line", 0.0)),
        direction=str(pick_dict.get("direction", "Higher")),
        probability=float(pick_dict.get("probability", 0.5)),
        edge=float(pick_dict.get("edge")) if pick_dict.get("edge") is not None else None,
        tier=str(pick_dict.get("tier")) if pick_dict.get("tier") is not None else None,
        source=str(pick_dict.get("source", "oracle")),
        metadata=pick_dict.get("metadata"),
    )
    enforcer = SOPEnforcer()
    res = enforcer.enforce(pick)
    out = dict(pick_dict)
    out["sop"] = asdict(res)
    return out
