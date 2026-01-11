"""
Dependency Edge - Models constraints and relationships between player nodes

Edges represent how players' performances are linked through game situations,
team strategies, and matchup dynamics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import json


class EdgeType(Enum):
    """Types of dependencies between players."""
    TEAMMATE_USAGE = "teammate_usage"  # Minutes/usage competition
    OPPONENT_MATCHUP = "opponent_matchup"  # Defensive assignment
    PACE_DEPENDENCY = "pace_dependency"  # Game tempo effects
    INJURY_BACKUP = "injury_backup"  # Backup player activation
    ROLE_CONSTRAINT = "role_constraint"  # Strategic role dependencies


class ConstraintType(Enum):
    """Types of constraints that edges can enforce."""
    MUTUAL_EXCLUSION = "mutual_exclusion"  # Players can't both perform highly
    CORRELATION = "correlation"  # Performances are linked
    THRESHOLD_TRIGGER = "threshold_trigger"  # One player's performance triggers another's
    RESOURCE_SHARING = "resource_sharing"  # Shared team resources (minutes, possessions)


@dataclass
class Constraint:
    """
    Individual constraint within a dependency edge.

    Defines how two players' performances are linked.
    """
    constraint_type: ConstraintType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    strength: float = 1.0  # How strongly to enforce (0.0 to 1.0)
    active: bool = True

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "constraint_type": self.constraint_type.value,
            "description": self.description,
            "parameters": self.parameters,
            "strength": self.strength,
            "active": self.active
        }

    def evaluate(self, player_a_state: Dict, player_b_state: Dict) -> Dict[str, Any]:
        """
        Evaluate constraint given current player states.

        Returns adjustment factors for each player.
        """
        if not self.active:
            return {"player_a_adjustment": 1.0, "player_b_adjustment": 1.0}

        if self.constraint_type == ConstraintType.MUTUAL_EXCLUSION:
            return self._evaluate_mutual_exclusion(player_a_state, player_b_state)
        elif self.constraint_type == ConstraintType.CORRELATION:
            return self._evaluate_correlation(player_a_state, player_b_state)
        elif self.constraint_type == ConstraintType.THRESHOLD_TRIGGER:
            return self._evaluate_threshold_trigger(player_a_state, player_b_state)
        elif self.constraint_type == ConstraintType.RESOURCE_SHARING:
            return self._evaluate_resource_sharing(player_a_state, player_b_state)

        return {"player_a_adjustment": 1.0, "player_b_adjustment": 1.0}

    def _evaluate_mutual_exclusion(self, player_a: Dict, player_b: Dict) -> Dict[str, Any]:
        """Players can't both be high performers (e.g., two stars sharing minutes)."""
        a_performance = player_a.get("performance_factor", 1.0)
        b_performance = player_b.get("performance_factor", 1.0)

        # If both are performing well, dampen the effect
        if a_performance > 1.2 and b_performance > 1.2:
            dampening = 0.9 ** self.strength  # Stronger constraint = more dampening
            return {
                "player_a_adjustment": dampening,
                "player_b_adjustment": dampening,
                "reason": "Mutual exclusion: both performing highly"
            }

        return {"player_a_adjustment": 1.0, "player_b_adjustment": 1.0}

    def _evaluate_correlation(self, player_a: Dict, player_b: Dict) -> Dict[str, Any]:
        """Performances are linked (e.g., point guard and shooting guard)."""
        correlation_coeff = self.parameters.get("correlation", 0.3)

        a_performance = player_a.get("performance_factor", 1.0)
        b_performance = player_b.get("performance_factor", 1.0)

        # Adjust based on correlation
        if correlation_coeff > 0:
            # Positive correlation: boost both if one is doing well
            if a_performance > 1.1:
                b_boost = 1.0 + (correlation_coeff * (a_performance - 1.0) * self.strength)
                return {
                    "player_a_adjustment": 1.0,
                    "player_b_adjustment": b_boost,
                    "reason": f"Positive correlation: A performing well boosts B"
                }
            elif b_performance > 1.1:
                a_boost = 1.0 + (correlation_coeff * (b_performance - 1.0) * self.strength)
                return {
                    "player_a_adjustment": a_boost,
                    "player_b_adjustment": 1.0,
                    "reason": f"Positive correlation: B performing well boosts A"
                }

        return {"player_a_adjustment": 1.0, "player_b_adjustment": 1.0}

    def _evaluate_threshold_trigger(self, player_a: Dict, player_b: Dict) -> Dict[str, Any]:
        """One player's performance triggers changes in another's role."""
        threshold = self.parameters.get("threshold", 1.5)
        trigger_player = self.parameters.get("trigger_player", "A")

        if trigger_player == "A":
            if player_a.get("performance_factor", 1.0) > threshold:
                # A is performing well, might reduce B's minutes
                return {
                    "player_a_adjustment": 1.0,
                    "player_b_adjustment": 0.8 ** self.strength,
                    "reason": f"Threshold trigger: A exceeding {threshold}"
                }
        else:
            if player_b.get("performance_factor", 1.0) > threshold:
                return {
                    "player_a_adjustment": 0.8 ** self.strength,
                    "player_b_adjustment": 1.0,
                    "reason": f"Threshold trigger: B exceeding {threshold}"
                }

        return {"player_a_adjustment": 1.0, "player_b_adjustment": 1.0}

    def _evaluate_resource_sharing(self, player_a: Dict, player_b: Dict) -> Dict[str, Any]:
        """Players share team resources (minutes, possessions)."""
        total_minutes = self.parameters.get("total_minutes", 240)  # 4 quarters
        a_minutes = player_a.get("projected_minutes", 30)
        b_minutes = player_b.get("projected_minutes", 30)

        if a_minutes + b_minutes > total_minutes * 0.8:  # Over 80% of available minutes
            # Reduce both projections
            reduction = 0.95 ** self.strength
            return {
                "player_a_adjustment": reduction,
                "player_b_adjustment": reduction,
                "reason": f"Resource sharing: combined minutes {a_minutes + b_minutes} > {total_minutes * 0.8}"
            }

        return {"player_a_adjustment": 1.0, "player_b_adjustment": 1.0}


@dataclass
class DependencyEdge:
    """
    Edge connecting two player nodes with constraints.

    Represents relationships that affect performance projections.
    """

    edge_id: str
    player_a_id: str
    player_b_id: str
    edge_type: EdgeType

    # Core properties
    constraints: List[Constraint] = field(default_factory=list)
    bidirectional: bool = True  # True if constraint applies both ways

    # Metadata
    description: str = ""
    confidence: float = 1.0  # How certain we are about this dependency
    active: bool = True

    # Diagnostic info
    last_evaluated: Optional[datetime] = None
    evaluation_count: int = 0
    average_adjustment: float = 1.0

    def add_constraint(self, constraint: Constraint):
        """Add a constraint to this edge."""
        self.constraints.append(constraint)

    def evaluate(self, player_a_state: Dict, player_b_state: Dict) -> Dict[str, Any]:
        """
        Evaluate all constraints and return combined adjustments.

        Returns adjustment factors for each player.
        """
        if not self.active:
            return {
                "player_a_adjustment": 1.0,
                "player_b_adjustment": 1.0,
                "constraints_evaluated": 0,
                "reason": "Edge inactive"
            }

        total_a_adjustment = 1.0
        total_b_adjustment = 1.0
        evaluated_constraints = []

        for constraint in self.constraints:
            result = constraint.evaluate(player_a_state, player_b_state)
            total_a_adjustment *= result["player_a_adjustment"]
            total_b_adjustment *= result["player_b_adjustment"]
            evaluated_constraints.append({
                "constraint": constraint.constraint_type.value,
                "result": result
            })

        # Update diagnostics
        self.last_evaluated = datetime.now()
        self.evaluation_count += 1
        self.average_adjustment = (
            (self.average_adjustment * (self.evaluation_count - 1)) +
            ((total_a_adjustment + total_b_adjustment) / 2.0)
        ) / self.evaluation_count

        return {
            "player_a_adjustment": total_a_adjustment,
            "player_b_adjustment": total_b_adjustment,
            "constraints_evaluated": len(evaluated_constraints),
            "constraint_details": evaluated_constraints,
            "edge_confidence": self.confidence
        }

    def get_health_score(self) -> float:
        """
        Calculate health score for this edge.

        Based on evaluation frequency, adjustment stability, and confidence.
        """
        if self.evaluation_count == 0:
            return 0.5  # Neutral for unevaluated edges

        # Factor in how recently evaluated
        hours_since_evaluation = 0
        if self.last_evaluated:
            hours_since_evaluation = (datetime.now() - self.last_evaluated).total_seconds() / 3600

        recency_score = max(0.0, 1.0 - (hours_since_evaluation / 24.0))  # Decay over 24 hours

        # Factor in adjustment stability (closer to 1.0 is more stable)
        stability_score = 1.0 - abs(self.average_adjustment - 1.0)

        # Combine factors
        health = (self.confidence * 0.4) + (recency_score * 0.3) + (stability_score * 0.3)

        return min(1.0, max(0.0, health))

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "edge_id": self.edge_id,
            "player_a_id": self.player_a_id,
            "player_b_id": self.player_b_id,
            "edge_type": self.edge_type.value,
            "constraints": [c.to_dict() for c in self.constraints],
            "bidirectional": self.bidirectional,
            "description": self.description,
            "confidence": self.confidence,
            "active": self.active,
            "last_evaluated": self.last_evaluated.isoformat() if self.last_evaluated else None,
            "evaluation_count": self.evaluation_count,
            "average_adjustment": self.average_adjustment
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DependencyEdge":
        """Deserialize from dict."""
        constraints = []
        for c_dict in d.get("constraints", []):
            constraint = Constraint(**c_dict)
            constraints.append(constraint)

        return cls(
            edge_id=d["edge_id"],
            player_a_id=d["player_a_id"],
            player_b_id=d["player_b_id"],
            edge_type=EdgeType(d["edge_type"]),
            constraints=constraints,
            bidirectional=d.get("bidirectional", True),
            description=d.get("description", ""),
            confidence=d.get("confidence", 1.0),
            active=d.get("active", True),
            last_evaluated=datetime.fromisoformat(d["last_evaluated"]) if d.get("last_evaluated") else None,
            evaluation_count=d.get("evaluation_count", 0),
            average_adjustment=d.get("average_adjustment", 1.0)
        )


class EdgeFactory:
    """
    Factory for creating common dependency edge patterns.
    """

    @staticmethod
    def create_teammate_usage_edge(player_a_id: str, player_b_id: str,
                                 shared_minutes: float = 60.0) -> DependencyEdge:
        """Create edge for teammates competing for minutes."""
        edge = DependencyEdge(
            edge_id=f"usage_{player_a_id}_{player_b_id}",
            player_a_id=player_a_id,
            player_b_id=player_b_id,
            edge_type=EdgeType.TEAMMATE_USAGE,
            description=f"Minutes competition between {player_a_id} and {player_b_id}"
        )

        # Add resource sharing constraint
        constraint = Constraint(
            constraint_type=ConstraintType.RESOURCE_SHARING,
            description="Shared team minutes constraint",
            parameters={"total_minutes": shared_minutes},
            strength=0.7
        )
        edge.add_constraint(constraint)

        return edge

    @staticmethod
    def create_opponent_matchup_edge(player_id: str, defender_id: str,
                                   matchup_strength: float = 0.8) -> DependencyEdge:
        """Create edge for player vs defender matchup."""
        edge = DependencyEdge(
            edge_id=f"matchup_{player_id}_{defender_id}",
            player_a_id=player_id,
            player_b_id=defender_id,
            edge_type=EdgeType.OPPONENT_MATCHUP,
            description=f"Defensive matchup: {defender_id} guarding {player_id}",
            bidirectional=False  # Matchup primarily affects offensive player
        )

        # Add correlation constraint (defender performance affects player)
        constraint = Constraint(
            constraint_type=ConstraintType.CORRELATION,
            description="Defensive impact on offensive performance",
            parameters={"correlation": -matchup_strength},  # Negative correlation
            strength=0.6
        )
        edge.add_constraint(constraint)

        return edge

    @staticmethod
    def create_role_dependency_edge(star_player_id: str, role_player_id: str) -> DependencyEdge:
        """Create edge for star player affecting role player's minutes."""
        edge = DependencyEdge(
            edge_id=f"role_{star_player_id}_{role_player_id}",
            player_a_id=star_player_id,
            player_b_id=role_player_id,
            edge_type=EdgeType.ROLE_CONSTRAINT,
            description=f"{role_player_id} minutes depend on {star_player_id} performance",
            bidirectional=False
        )

        # Add threshold trigger constraint
        constraint = Constraint(
            constraint_type=ConstraintType.THRESHOLD_TRIGGER,
            description="Role player minutes reduce if star performs well",
            parameters={"threshold": 1.3, "trigger_player": "A"},
            strength=0.8
        )
        edge.add_constraint(constraint)

        return edge