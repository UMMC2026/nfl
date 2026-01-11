"""
Player Node - Core component of the Probabilistic Dependency Graph

Each player is a stateful node that maintains its own truth distribution
and updates based on evidence while respecting dependencies.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pathlib import Path


@dataclass
class Distribution:
    """Statistical distribution for a player's stat projection."""
    stat_type: str
    median: float
    mean: float
    std_dev: float
    percentiles: Dict[int, float] = field(default_factory=dict)
    confidence_interval: tuple[float, float] = (0.0, 0.0)  # 95% CI

    def to_dict(self) -> dict:
        return {
            "stat_type": self.stat_type,
            "median": self.median,
            "mean": self.mean,
            "std_dev": self.std_dev,
            "percentiles": self.percentiles,
            "confidence_interval": self.confidence_interval
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Distribution":
        return cls(**d)


@dataclass
class SensitivityAnalysis:
    """Sensitivity of projections to key variables."""
    scenarios: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def add_scenario(self, scenario_name: str, impact: Dict[str, Any]):
        """Add a sensitivity scenario (e.g., 'minutes_minus_4', 'pace_down_10pct')."""
        self.scenarios[scenario_name] = impact

    def to_dict(self) -> dict:
        return {"scenarios": self.scenarios}


@dataclass
class PlayerNode:
    """
    Stateful node representing a player's probabilistic state.

    Maintains pre-game priors, live posteriors, and dependency relationships.
    """

    player_id: str
    player_name: str
    team: str
    league: str = "NBA"

    # STATIC (pre-game priors)
    base_distributions: Dict[str, Distribution] = field(default_factory=dict)
    role_expectation: str = "STARTER"  # STARTER, BENCH, ROTATION
    minutes_prior: float = 30.0
    usage_prior: float = 20.0

    # DYNAMIC (live posteriors)
    minutes_posterior: Optional[float] = None
    usage_posterior: Optional[float] = None
    fatigue_factor: float = 1.0  # Multiplier < 1.0 = fatigued
    foul_risk: float = 0.05  # Probability of foul trouble
    injury_risk: float = 0.01  # Probability of injury impact

    # DEPENDENCIES
    teammate_nodes: List[str] = field(default_factory=list)  # Player IDs
    opponent_nodes: List[str] = field(default_factory=list)  # Player IDs

    # HEALTH & DIAGNOSTICS
    confidence_score: float = 1.0  # 0.0 to 1.0
    data_integrity_score: float = 1.0  # 0.0 to 1.0
    last_updated: Optional[datetime] = None
    evidence_sources: Dict[str, float] = field(default_factory=dict)  # source -> confidence

    # SENSITIVITY
    sensitivity: SensitivityAnalysis = field(default_factory=SensitivityAnalysis)

    # STATUS
    quarantined: bool = False
    quarantine_reason: Optional[str] = None

    def update_from_evidence(self, evidence_bundle: 'EvidenceBundle'):
        """
        Update node state from new evidence.

        RULE: Evidence may ADJUST parameters, never REPLACE truth.
        """
        if evidence_bundle.integrity_score < 0.5:
            self.quarantined = True
            self.quarantine_reason = f"Low integrity evidence: {evidence_bundle.integrity_score}"
            return

        # Update posteriors using Bayesian logic
        if evidence_bundle.minutes_signal:
            self.minutes_posterior = self._bayesian_update(
                prior=self.minutes_posterior or self.minutes_prior,
                evidence=evidence_bundle.minutes_signal
            )

        if evidence_bundle.usage_signal:
            self.usage_posterior = self._bayesian_update(
                prior=self.usage_posterior or self.usage_prior,
                evidence=evidence_bundle.usage_signal
            )

        # Update fatigue and risk factors
        if evidence_bundle.fatigue_signal:
            self.fatigue_factor *= (1.0 - evidence_bundle.fatigue_signal.strength)

        if evidence_bundle.foul_signal:
            self.foul_risk = min(1.0, self.foul_risk + evidence_bundle.foul_signal.strength)

        # Update evidence sources
        for source, confidence in evidence_bundle.source_confidences.items():
            self.evidence_sources[source] = confidence

        # Recompute confidence and integrity
        self._recompute_diagnostics()

        self.last_updated = datetime.now()

    def _bayesian_update(self, prior: float, evidence: 'EvidenceSignal') -> float:
        """
        Bayesian update of parameter.

        evidence.strength = how strongly to move toward evidence.value
        evidence.confidence = how trustworthy the evidence is
        """
        if evidence.confidence < 0.3:
            return prior  # Too weak to update

        # Simple Bayesian update (can be made more sophisticated)
        adjustment = (evidence.value - prior) * evidence.strength * evidence.confidence
        return prior + adjustment

    def _recompute_diagnostics(self):
        """Recompute confidence and integrity scores."""
        # Base confidence from evidence sources
        if self.evidence_sources:
            avg_evidence_confidence = sum(self.evidence_sources.values()) / len(self.evidence_sources)
            self.confidence_score = min(1.0, avg_evidence_confidence)

        # Integrity based on data consistency
        # (Simple implementation - can be enhanced)
        self.data_integrity_score = self.confidence_score

        # Check for quarantine conditions
        if self.confidence_score < 0.4:
            self.quarantined = True
            self.quarantine_reason = f"Low confidence: {self.confidence_score:.2f}"
        elif self.fatigue_factor < 0.3:
            self.quarantined = True
            self.quarantine_reason = f"High fatigue: {self.fatigue_factor:.2f}"
        else:
            self.quarantined = False
            self.quarantine_reason = None

    def get_projection(self, stat_type: str, line: float, direction: str) -> Optional[Dict]:
        """
        Get probability projection for a specific stat line.

        Returns None if node is quarantined or data insufficient.
        """
        if self.quarantined:
            return None

        if stat_type not in self.base_distributions:
            return None

        dist = self.base_distributions[stat_type]

        # Apply live adjustments
        adjusted_median = dist.median
        if self.minutes_posterior:
            # Scale projection based on minutes (simplified)
            minutes_ratio = self.minutes_posterior / self.minutes_prior
            adjusted_median *= minutes_ratio

        if self.usage_posterior:
            usage_ratio = self.usage_posterior / self.usage_prior
            adjusted_median *= usage_ratio

        # Apply fatigue
        adjusted_median *= self.fatigue_factor

        # Calculate hit probability using normal approximation
        from scipy.stats import norm
        if direction.lower() in ['higher', 'over']:
            prob_hit = 1.0 - norm.cdf(line, loc=adjusted_median, scale=dist.std_dev)
        else:  # lower/under
            prob_hit = norm.cdf(line, loc=adjusted_median, scale=dist.std_dev)

        return {
            "player": self.player_name,
            "stat": stat_type,
            "line": line,
            "direction": direction,
            "probability": prob_hit,
            "adjusted_median": adjusted_median,
            "confidence": self.confidence_score,
            "quarantined": self.quarantined
        }

    def to_dict(self) -> dict:
        """Serialize to dict for storage."""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "team": self.team,
            "league": self.league,
            "base_distributions": {k: v.to_dict() for k, v in self.base_distributions.items()},
            "role_expectation": self.role_expectation,
            "minutes_prior": self.minutes_prior,
            "usage_prior": self.usage_prior,
            "minutes_posterior": self.minutes_posterior,
            "usage_posterior": self.usage_posterior,
            "fatigue_factor": self.fatigue_factor,
            "foul_risk": self.foul_risk,
            "injury_risk": self.injury_risk,
            "teammate_nodes": self.teammate_nodes,
            "opponent_nodes": self.opponent_nodes,
            "confidence_score": self.confidence_score,
            "data_integrity_score": self.data_integrity_score,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "evidence_sources": self.evidence_sources,
            "sensitivity": self.sensitivity.to_dict(),
            "quarantined": self.quarantined,
            "quarantine_reason": self.quarantine_reason
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PlayerNode":
        """Deserialize from dict."""
        # Handle nested objects
        base_distributions = {}
        for k, v in d.get("base_distributions", {}).items():
            base_distributions[k] = Distribution.from_dict(v)

        sensitivity = SensitivityAnalysis()
        sensitivity.scenarios = d.get("sensitivity", {}).get("scenarios", {})

        return cls(
            player_id=d["player_id"],
            player_name=d["player_name"],
            team=d["team"],
            league=d.get("league", "NBA"),
            base_distributions=base_distributions,
            role_expectation=d.get("role_expectation", "STARTER"),
            minutes_prior=d.get("minutes_prior", 30.0),
            usage_prior=d.get("usage_prior", 20.0),
            minutes_posterior=d.get("minutes_posterior"),
            usage_posterior=d.get("usage_posterior"),
            fatigue_factor=d.get("fatigue_factor", 1.0),
            foul_risk=d.get("foul_risk", 0.05),
            injury_risk=d.get("injury_risk", 0.01),
            teammate_nodes=d.get("teammate_nodes", []),
            opponent_nodes=d.get("opponent_nodes", []),
            confidence_score=d.get("confidence_score", 1.0),
            data_integrity_score=d.get("data_integrity_score", 1.0),
            last_updated=datetime.fromisoformat(d["last_updated"]) if d.get("last_updated") else None,
            evidence_sources=d.get("evidence_sources", {}),
            sensitivity=sensitivity,
            quarantined=d.get("quarantined", False),
            quarantine_reason=d.get("quarantine_reason")
        )