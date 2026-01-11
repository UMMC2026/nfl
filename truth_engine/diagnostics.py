"""
Diagnostic Layer - Monitors system health and prevents cascading failures

Provides confidence scoring, sensitivity analysis, and quarantine mechanisms
to maintain system stability during live updates.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from pathlib import Path


class DiagnosticLevel(Enum):
    """Severity levels for diagnostic alerts."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class QuarantineReason(Enum):
    """Reasons for quarantining a node or edge."""
    LOW_CONFIDENCE = "low_confidence"
    STALE_DATA = "stale_data"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    SYSTEMIC_FAILURE = "systemic_failure"
    HIGH_SENSITIVITY = "high_sensitivity"
    INTEGRITY_FAILURE = "integrity_failure"


@dataclass
class DiagnosticAlert:
    """Individual diagnostic alert or warning."""
    alert_id: str
    level: DiagnosticLevel
    component: str  # "node", "edge", "evidence", "system"
    component_id: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None

    def resolve(self, resolution_note: str = ""):
        """Mark alert as resolved."""
        self.resolved = True
        self.resolution_timestamp = datetime.now()
        self.metadata["resolution_note"] = resolution_note

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "level": self.level.value,
            "component": self.component,
            "component_id": self.component_id,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "resolved": self.resolved,
            "resolution_timestamp": self.resolution_timestamp.isoformat() if self.resolution_timestamp else None
        }


@dataclass
class SensitivityProfile:
    """Sensitivity analysis for a component."""
    component_id: str
    component_type: str  # "node", "edge"

    # Sensitivity metrics
    evidence_sensitivity: float = 0.0  # How much projections change with evidence
    dependency_sensitivity: float = 0.0  # How much affected by other components
    time_sensitivity: float = 0.0  # How quickly projections decay

    # Risk assessment
    cascade_risk: float = 0.0  # Risk of triggering chain reactions
    failure_impact: float = 0.0  # Impact if this component fails

    # Scenarios tested
    scenarios_run: List[str] = field(default_factory=list)
    last_analysis: Optional[datetime] = None

    def calculate_overall_risk(self) -> float:
        """Calculate overall risk score (0.0 to 1.0)."""
        # Weighted combination of sensitivities and risks
        risk = (
            (self.evidence_sensitivity * 0.3) +
            (self.dependency_sensitivity * 0.3) +
            (self.time_sensitivity * 0.2) +
            (self.cascade_risk * 0.1) +
            (self.failure_impact * 0.1)
        )
        return min(1.0, max(0.0, risk))

    def should_quarantine(self) -> bool:
        """Determine if component should be quarantined based on sensitivity."""
        return self.calculate_overall_risk() > 0.7

    def to_dict(self) -> dict:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type,
            "evidence_sensitivity": self.evidence_sensitivity,
            "dependency_sensitivity": self.dependency_sensitivity,
            "time_sensitivity": self.time_sensitivity,
            "cascade_risk": self.cascade_risk,
            "failure_impact": self.failure_impact,
            "scenarios_run": self.scenarios_run,
            "last_analysis": self.last_analysis.isoformat() if self.last_analysis else None
        }


@dataclass
class HealthMetrics:
    """System-wide health metrics."""
    total_nodes: int = 0
    active_nodes: int = 0
    quarantined_nodes: int = 0

    total_edges: int = 0
    active_edges: int = 0
    inactive_edges: int = 0

    evidence_processed: int = 0
    evidence_rejected: int = 0

    average_confidence: float = 1.0
    average_integrity: float = 1.0

    last_updated: Optional[datetime] = None

    def update_from_nodes(self, nodes: List['PlayerNode']):
        """Update metrics from current node states."""
        self.total_nodes = len(nodes)
        self.active_nodes = sum(1 for n in nodes if not n.quarantined)
        self.quarantined_nodes = sum(1 for n in nodes if n.quarantined)

        if nodes:
            self.average_confidence = sum(n.confidence_score for n in nodes) / len(nodes)
            self.average_integrity = sum(n.data_integrity_score for n in nodes) / len(nodes)

        self.last_updated = datetime.now()

    def get_system_health_score(self) -> float:
        """Calculate overall system health (0.0 to 1.0)."""
        if self.total_nodes == 0:
            return 0.0

        # Component health
        node_health = self.active_nodes / self.total_nodes
        confidence_health = self.average_confidence
        integrity_health = self.average_integrity

        # Evidence processing health
        total_evidence = self.evidence_processed + self.evidence_rejected
        evidence_health = 1.0
        if total_evidence > 0:
            evidence_health = self.evidence_processed / total_evidence

        # Weighted average
        health = (
            (node_health * 0.4) +
            (confidence_health * 0.3) +
            (integrity_health * 0.2) +
            (evidence_health * 0.1)
        )

        return min(1.0, max(0.0, health))

    def to_dict(self) -> dict:
        return {
            "total_nodes": self.total_nodes,
            "active_nodes": self.active_nodes,
            "quarantined_nodes": self.quarantined_nodes,
            "total_edges": self.total_edges,
            "active_edges": self.active_edges,
            "inactive_edges": self.inactive_edges,
            "evidence_processed": self.evidence_processed,
            "evidence_rejected": self.evidence_rejected,
            "average_confidence": self.average_confidence,
            "average_integrity": self.average_integrity,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None
        }


class DiagnosticEngine:
    """
    Central diagnostic system for monitoring and maintaining system health.
    """

    def __init__(self, log_path: Optional[Path] = None):
        self.alerts: List[DiagnosticAlert] = []
        self.sensitivity_profiles: Dict[str, SensitivityProfile] = {}
        self.health_metrics = HealthMetrics()
        self.quarantine_rules = self._load_quarantine_rules()

        # Setup logging
        self.logger = logging.getLogger("DiagnosticEngine")
        if log_path:
            handler = logging.FileHandler(log_path)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _load_quarantine_rules(self) -> Dict[str, Dict]:
        """Load quarantine rules configuration."""
        return {
            "low_confidence": {
                "threshold": 0.4,
                "auto_quarantine": True,
                "max_duration_hours": 24
            },
            "stale_data": {
                "max_age_hours": 6,
                "auto_quarantine": True,
                "max_duration_hours": 12
            },
            "high_sensitivity": {
                "risk_threshold": 0.7,
                "auto_quarantine": True,
                "max_duration_hours": 48
            },
            "integrity_failure": {
                "threshold": 0.5,
                "auto_quarantine": True,
                "max_duration_hours": 24
            }
        }

    def check_node_health(self, node: 'PlayerNode') -> List[DiagnosticAlert]:
        """
        Check health of a player node and generate alerts.

        Returns list of alerts generated.
        """
        alerts = []

        # Confidence check
        if node.confidence_score < self.quarantine_rules["low_confidence"]["threshold"]:
            alert = DiagnosticAlert(
                alert_id=f"node_confidence_{node.player_id}_{datetime.now().timestamp()}",
                level=DiagnosticLevel.WARNING,
                component="node",
                component_id=node.player_id,
                message=f"Low confidence score: {node.confidence_score:.2f}",
                timestamp=datetime.now(),
                metadata={"confidence_score": node.confidence_score}
            )
            alerts.append(alert)
            self.alerts.append(alert)

            # Auto-quarantine if enabled
            if self.quarantine_rules["low_confidence"]["auto_quarantine"]:
                node.quarantined = True
                node.quarantine_reason = QuarantineReason.LOW_CONFIDENCE.value

        # Stale data check
        if node.last_updated:
            age_hours = (datetime.now() - node.last_updated).total_seconds() / 3600
            max_age = self.quarantine_rules["stale_data"]["max_age_hours"]
            if age_hours > max_age:
                alert = DiagnosticAlert(
                    alert_id=f"node_stale_{node.player_id}_{datetime.now().timestamp()}",
                    level=DiagnosticLevel.WARNING,
                    component="node",
                    component_id=node.player_id,
                    message=f"Stale data: {age_hours:.1f} hours old",
                    timestamp=datetime.now(),
                    metadata={"age_hours": age_hours, "max_age": max_age}
                )
                alerts.append(alert)
                self.alerts.append(alert)

        # Integrity check
        if node.data_integrity_score < self.quarantine_rules["integrity_failure"]["threshold"]:
            alert = DiagnosticAlert(
                alert_id=f"node_integrity_{node.player_id}_{datetime.now().timestamp()}",
                level=DiagnosticLevel.ERROR,
                component="node",
                component_id=node.player_id,
                message=f"Data integrity failure: {node.data_integrity_score:.2f}",
                timestamp=datetime.now(),
                metadata={"integrity_score": node.data_integrity_score}
            )
            alerts.append(alert)
            self.alerts.append(alert)

        return alerts

    def check_edge_health(self, edge: 'DependencyEdge') -> List[DiagnosticAlert]:
        """
        Check health of a dependency edge.

        Returns list of alerts generated.
        """
        alerts = []

        # Health score check
        health_score = edge.get_health_score()
        if health_score < 0.5:
            alert = DiagnosticAlert(
                alert_id=f"edge_health_{edge.edge_id}_{datetime.now().timestamp()}",
                level=DiagnosticLevel.WARNING,
                component="edge",
                component_id=edge.edge_id,
                message=f"Low edge health score: {health_score:.2f}",
                timestamp=datetime.now(),
                metadata={"health_score": health_score}
            )
            alerts.append(alert)
            self.alerts.append(alert)

        # Evaluation frequency check
        if edge.evaluation_count == 0:
            alert = DiagnosticAlert(
                alert_id=f"edge_unused_{edge.edge_id}_{datetime.now().timestamp()}",
                level=DiagnosticLevel.INFO,
                component="edge",
                component_id=edge.edge_id,
                message="Edge has never been evaluated",
                timestamp=datetime.now()
            )
            alerts.append(alert)
            self.alerts.append(alert)

        return alerts

    def run_sensitivity_analysis(self, component_id: str, component_type: str,
                               scenarios: List[Dict]) -> SensitivityProfile:
        """
        Run sensitivity analysis on a component.

        Returns sensitivity profile with risk assessment.
        """
        profile = SensitivityProfile(
            component_id=component_id,
            component_type=component_type
        )

        # Run each scenario and measure impact
        for scenario in scenarios:
            scenario_name = scenario["name"]
            profile.scenarios_run.append(scenario_name)

            # Simulate scenario impact (simplified - would need actual component)
            impact = scenario.get("impact", 0.0)
            profile.evidence_sensitivity += impact * 0.3
            profile.dependency_sensitivity += impact * 0.4
            profile.time_sensitivity += impact * 0.3

        profile.last_analysis = datetime.now()

        # Store profile
        self.sensitivity_profiles[component_id] = profile

        # Check if quarantine needed
        if profile.should_quarantine():
            alert = DiagnosticAlert(
                alert_id=f"sensitivity_quarantine_{component_id}_{datetime.now().timestamp()}",
                level=DiagnosticLevel.WARNING,
                component=component_type,
                component_id=component_id,
                message=f"High sensitivity risk: {profile.calculate_overall_risk():.2f}",
                timestamp=datetime.now(),
                metadata={"risk_score": profile.calculate_overall_risk()}
            )
            self.alerts.append(alert)

        return profile

    def update_health_metrics(self, nodes: List['PlayerNode'],
                            edges: List['DependencyEdge'],
                            evidence_stats: Dict[str, int]):
        """Update system-wide health metrics."""
        self.health_metrics.update_from_nodes(nodes)

        self.health_metrics.total_edges = len(edges)
        self.health_metrics.active_edges = sum(1 for e in edges if e.active)
        self.health_metrics.inactive_edges = len(edges) - self.health_metrics.active_edges

        self.health_metrics.evidence_processed = evidence_stats.get("processed", 0)
        self.health_metrics.evidence_rejected = evidence_stats.get("rejected", 0)

    def get_active_alerts(self, level: Optional[DiagnosticLevel] = None) -> List[DiagnosticAlert]:
        """Get active (unresolved) alerts, optionally filtered by level."""
        alerts = [a for a in self.alerts if not a.resolved]
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts

    def quarantine_component(self, component_type: str, component_id: str,
                           reason: QuarantineReason, duration_hours: int = 24):
        """
        Quarantine a component for a specified duration.

        This is a high-level action that should trigger appropriate quarantine logic.
        """
        alert = DiagnosticAlert(
            alert_id=f"quarantine_{component_type}_{component_id}_{datetime.now().timestamp()}",
            level=DiagnosticLevel.CRITICAL,
            component=component_type,
            component_id=component_id,
            message=f"Component quarantined: {reason.value}",
            timestamp=datetime.now(),
            metadata={
                "quarantine_reason": reason.value,
                "duration_hours": duration_hours,
                "auto_release": datetime.now() + timedelta(hours=duration_hours)
            }
        )
        self.alerts.append(alert)

        self.logger.warning(f"Quarantined {component_type} {component_id}: {reason.value}")

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report."""
        critical_alerts = len(self.get_active_alerts(DiagnosticLevel.CRITICAL))
        warning_alerts = len(self.get_active_alerts(DiagnosticLevel.WARNING))
        error_alerts = len(self.get_active_alerts(DiagnosticLevel.ERROR))

        high_risk_components = [
            pid for pid, profile in self.sensitivity_profiles.items()
            if profile.calculate_overall_risk() > 0.7
        ]

        return {
            "timestamp": datetime.now().isoformat(),
            "system_health_score": self.health_metrics.get_system_health_score(),
            "alerts": {
                "critical": critical_alerts,
                "warning": warning_alerts,
                "error": error_alerts,
                "total_active": critical_alerts + warning_alerts + error_alerts
            },
            "components": {
                "nodes": {
                    "total": self.health_metrics.total_nodes,
                    "active": self.health_metrics.active_nodes,
                    "quarantined": self.health_metrics.quarantined_nodes
                },
                "edges": {
                    "total": self.health_metrics.total_edges,
                    "active": self.health_metrics.active_edges,
                    "inactive": self.health_metrics.inactive_edges
                }
            },
            "evidence_processing": {
                "processed": self.health_metrics.evidence_processed,
                "rejected": self.health_metrics.evidence_rejected,
                "success_rate": (
                    self.health_metrics.evidence_processed /
                    max(1, self.health_metrics.evidence_processed + self.health_metrics.evidence_rejected)
                )
            },
            "risk_assessment": {
                "high_risk_components": len(high_risk_components),
                "component_ids": high_risk_components[:5]  # First 5 for brevity
            },
            "metrics": self.health_metrics.to_dict()
        }

    def save_state(self, path: Path):
        """Save diagnostic state to disk."""
        state = {
            "alerts": [a.to_dict() for a in self.alerts],
            "sensitivity_profiles": {k: v.to_dict() for k, v in self.sensitivity_profiles.items()},
            "health_metrics": self.health_metrics.to_dict(),
            "saved_at": datetime.now().isoformat()
        }

        with open(path, 'w') as f:
            json.dump(state, f, indent=2)

    def load_state(self, path: Path):
        """Load diagnostic state from disk."""
        if not path.exists():
            return

        with open(path, 'r') as f:
            state = json.load(f)

        # Restore alerts
        self.alerts = []
        for a_dict in state.get("alerts", []):
            alert = DiagnosticAlert(
                alert_id=a_dict["alert_id"],
                level=DiagnosticLevel(a_dict["level"]),
                component=a_dict["component"],
                component_id=a_dict["component_id"],
                message=a_dict["message"],
                timestamp=datetime.fromisoformat(a_dict["timestamp"]),
                metadata=a_dict.get("metadata", {}),
                resolved=a_dict.get("resolved", False),
                resolution_timestamp=datetime.fromisoformat(a_dict["resolution_timestamp"]) if a_dict.get("resolution_timestamp") else None
            )
            self.alerts.append(alert)

        # Restore sensitivity profiles
        self.sensitivity_profiles = {}
        for k, v in state.get("sensitivity_profiles", {}).items():
            profile = SensitivityProfile(
                component_id=v["component_id"],
                component_type=v["component_type"],
                evidence_sensitivity=v.get("evidence_sensitivity", 0.0),
                dependency_sensitivity=v.get("dependency_sensitivity", 0.0),
                time_sensitivity=v.get("time_sensitivity", 0.0),
                cascade_risk=v.get("cascade_risk", 0.0),
                failure_impact=v.get("failure_impact", 0.0),
                scenarios_run=v.get("scenarios_run", []),
                last_analysis=datetime.fromisoformat(v["last_analysis"]) if v.get("last_analysis") else None
            )
            self.sensitivity_profiles[k] = profile

        # Restore health metrics
        hm_dict = state.get("health_metrics", {})
        self.health_metrics = HealthMetrics(
            total_nodes=hm_dict.get("total_nodes", 0),
            active_nodes=hm_dict.get("active_nodes", 0),
            quarantined_nodes=hm_dict.get("quarantined_nodes", 0),
            total_edges=hm_dict.get("total_edges", 0),
            active_edges=hm_dict.get("active_edges", 0),
            inactive_edges=hm_dict.get("inactive_edges", 0),
            evidence_processed=hm_dict.get("evidence_processed", 0),
            evidence_rejected=hm_dict.get("evidence_rejected", 0),
            average_confidence=hm_dict.get("average_confidence", 1.0),
            average_integrity=hm_dict.get("average_integrity", 1.0),
            last_updated=datetime.fromisoformat(hm_dict["last_updated"]) if hm_dict.get("last_updated") else None
        )