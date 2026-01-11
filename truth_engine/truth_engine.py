"""
Truth Engine - Orchestrates the Probabilistic Dependency Graph

Manages player nodes, dependency edges, evidence processing, and diagnostic monitoring
to maintain live probabilistic truth for betting intelligence.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
import time

from .player_node import PlayerNode, Distribution
from .evidence import EvidenceBundle, EvidenceProcessor, EvidenceType, EvidenceSource, EvidenceSignal
from .dependency_edge import DependencyEdge, EdgeFactory
from .diagnostics import DiagnosticEngine, DiagnosticLevel, QuarantineReason


@dataclass
class GraphState:
    """Snapshot of the entire dependency graph state."""
    nodes: Dict[str, PlayerNode] = field(default_factory=dict)
    edges: Dict[str, DependencyEdge] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    version: str = "1.0"

    def save_to_file(self, path: Path):
        """Save graph state to JSON file."""
        state_dict = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": {k: v.to_dict() for k, v in self.edges.items()},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "version": self.version
        }

        with open(path, 'w') as f:
            json.dump(state_dict, f, indent=2)

    @classmethod
    def load_from_file(cls, path: Path) -> "GraphState":
        """Load graph state from JSON file."""
        if not path.exists():
            return cls()

        with open(path, 'r') as f:
            state_dict = json.load(f)

        nodes = {}
        for k, v in state_dict.get("nodes", {}).items():
            nodes[k] = PlayerNode.from_dict(v)

        edges = {}
        for k, v in state_dict.get("edges", {}).items():
            edges[k] = DependencyEdge.from_dict(v)

        timestamp = None
        if state_dict.get("timestamp"):
            timestamp = datetime.fromisoformat(state_dict["timestamp"])

        return cls(
            nodes=nodes,
            edges=edges,
            timestamp=timestamp,
            version=state_dict.get("version", "1.0")
        )


class TruthEngine:
    """
    Main orchestrator for the Dynamic Truth Engine.

    Manages the probabilistic graph, processes evidence, enforces constraints,
    and maintains system health through diagnostics.
    """

    def __init__(self, storage_path: Optional[Path] = None,
                 diagnostic_log_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("outputs/truth_engine")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Core components
        self.graph_state = GraphState()
        self.evidence_processor = EvidenceProcessor()
        self.diagnostic_engine = DiagnosticEngine(diagnostic_log_path)

        # Processing state
        self.is_processing = False
        self.last_update = None
        self.update_count = 0

        # Async processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.evidence_queue = asyncio.Queue()

        # Setup logging
        self.logger = logging.getLogger("TruthEngine")
        self.logger.setLevel(logging.INFO)

        # Load existing state if available
        self._load_state()

    def _load_state(self):
        """Load previous graph state and diagnostics."""
        graph_path = self.storage_path / "graph_state.json"
        if graph_path.exists():
            self.graph_state = GraphState.load_from_file(graph_path)
            self.logger.info(f"Loaded graph state with {len(self.graph_state.nodes)} nodes, {len(self.graph_state.edges)} edges")

        diag_path = self.storage_path / "diagnostics_state.json"
        if diag_path.exists():
            self.diagnostic_engine.load_state(diag_path)
            self.logger.info("Loaded diagnostic state")

    def _save_state(self):
        """Save current graph state and diagnostics."""
        graph_path = self.storage_path / "graph_state.json"
        self.graph_state.save_to_file(graph_path)

        diag_path = self.storage_path / "diagnostics_state.json"
        self.diagnostic_engine.save_state(diag_path)

    def add_player_node(self, node: PlayerNode):
        """Add a player node to the graph."""
        self.graph_state.nodes[node.player_id] = node
        self.logger.info(f"Added player node: {node.player_name} ({node.player_id})")

        # Run initial health check
        alerts = self.diagnostic_engine.check_node_health(node)
        if alerts:
            self.logger.warning(f"Health alerts for new node {node.player_id}: {len(alerts)} alerts")

    def add_dependency_edge(self, edge: DependencyEdge):
        """Add a dependency edge to the graph."""
        self.graph_state.edges[edge.edge_id] = edge
        self.logger.info(f"Added dependency edge: {edge.edge_id} ({edge.edge_type.value})")

        # Update node relationships
        if edge.player_a_id in self.graph_state.nodes:
            if edge.player_b_id not in self.graph_state.nodes[edge.player_a_id].teammate_nodes:
                if edge.edge_type.value.startswith('teammate'):
                    self.graph_state.nodes[edge.player_a_id].teammate_nodes.append(edge.player_b_id)
                elif edge.edge_type.value.startswith('opponent'):
                    self.graph_state.nodes[edge.player_a_id].opponent_nodes.append(edge.player_b_id)

        if edge.player_b_id in self.graph_state.nodes and edge.bidirectional:
            if edge.player_a_id not in self.graph_state.nodes[edge.player_b_id].teammate_nodes:
                if edge.edge_type.value.startswith('teammate'):
                    self.graph_state.nodes[edge.player_b_id].teammate_nodes.append(edge.player_a_id)
                elif edge.edge_type.value.startswith('opponent'):
                    self.graph_state.nodes[edge.player_b_id].opponent_nodes.append(edge.player_a_id)

    def submit_evidence(self, evidence_bundle: EvidenceBundle):
        """Submit evidence for processing."""
        if self.is_processing:
            # Queue for later processing
            asyncio.create_task(self.evidence_queue.put(evidence_bundle))
            self.logger.debug(f"Queued evidence for {evidence_bundle.player_id}")
        else:
            # Process immediately
            asyncio.create_task(self._process_evidence_bundle(evidence_bundle))

    async def _process_evidence_bundle(self, evidence_bundle: EvidenceBundle):
        """
        Process a single evidence bundle.

        Updates node state and propagates constraints.
        """
        try:
            self.is_processing = True

            player_id = evidence_bundle.player_id
            if player_id not in self.graph_state.nodes:
                self.logger.warning(f"Evidence for unknown player: {player_id}")
                return

            node = self.graph_state.nodes[player_id]

            # Update node with evidence
            node.update_from_evidence(evidence_bundle)

            # Propagate constraints to connected nodes
            await self._propagate_constraints(player_id)

            # Update diagnostics
            alerts = self.diagnostic_engine.check_node_health(node)
            if alerts:
                self.logger.warning(f"Generated {len(alerts)} alerts for {player_id}")

            # Update metrics
            evidence_stats = {"processed": 1, "rejected": 0}
            self.diagnostic_engine.update_health_metrics(
                list(self.graph_state.nodes.values()),
                list(self.graph_state.edges.values()),
                evidence_stats
            )

            self.update_count += 1
            self.last_update = datetime.now()

            self.logger.info(f"Processed evidence for {player_id}: integrity={evidence_bundle.integrity_score:.2f}")

        except Exception as e:
            self.logger.error(f"Error processing evidence for {player_id}: {e}")
            # Mark evidence as rejected in diagnostics
            evidence_stats = {"processed": 0, "rejected": 1}
            self.diagnostic_engine.update_health_metrics(
                list(self.graph_state.nodes.values()),
                list(self.graph_state.edges.values()),
                evidence_stats
            )
        finally:
            self.is_processing = False

            # Process queued evidence
            if not self.evidence_queue.empty():
                next_bundle = await self.evidence_queue.get()
                asyncio.create_task(self._process_evidence_bundle(next_bundle))

    async def _propagate_constraints(self, updated_player_id: str):
        """
        Propagate constraint effects to connected nodes.

        When one node updates, check all edges and update connected nodes.
        """
        affected_nodes = set()

        # Find all edges involving this player
        relevant_edges = [
            edge for edge in self.graph_state.edges.values()
            if edge.player_a_id == updated_player_id or edge.player_b_id == updated_player_id
        ]

        for edge in relevant_edges:
            if not edge.active:
                continue

            # Determine which node is the "other" node
            if edge.player_a_id == updated_player_id:
                other_player_id = edge.player_b_id
                is_player_a = True
            else:
                other_player_id = edge.player_a_id
                is_player_a = False

            if other_player_id not in self.graph_state.nodes:
                continue

            other_node = self.graph_state.nodes[other_player_id]
            updated_node = self.graph_state.nodes[updated_player_id]

            # Get current states for constraint evaluation
            player_a_state = {
                "performance_factor": 1.0,  # Simplified - would compute from projections
                "projected_minutes": updated_node.minutes_posterior or updated_node.minutes_prior,
                "fatigue_level": 1.0 - updated_node.fatigue_factor
            }

            player_b_state = {
                "performance_factor": 1.0,
                "projected_minutes": other_node.minutes_posterior or other_node.minutes_prior,
                "fatigue_level": 1.0 - other_node.fatigue_factor
            }

            # Evaluate constraints
            result = edge.evaluate(player_a_state, player_b_state)

            # Apply adjustments to the other node
            if is_player_a:
                # Updated node is A, adjust B
                adjustment_factor = result["player_b_adjustment"]
            else:
                # Updated node is B, adjust A
                adjustment_factor = result["player_a_adjustment"]

            # Apply adjustment (simplified - would adjust specific projections)
            if adjustment_factor != 1.0:
                other_node.confidence_score *= adjustment_factor
                affected_nodes.add(other_player_id)

                self.logger.debug(f"Applied {adjustment_factor:.2f} adjustment to {other_player_id} via {edge.edge_id}")

        # Recursively propagate if nodes were affected (prevent infinite loops)
        for affected_id in affected_nodes:
            if affected_id != updated_player_id:  # Avoid self-propagation
                await self._propagate_constraints(affected_id)

    def get_projection(self, player_id: str, stat_type: str, line: float, direction: str) -> Optional[Dict]:
        """
        Get live probability projection for a player stat.

        Returns None if player not found or node quarantined.
        """
        if player_id not in self.graph_state.nodes:
            return None

        node = self.graph_state.nodes[player_id]
        return node.get_projection(stat_type, line, direction)

    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health report."""
        return self.diagnostic_engine.generate_health_report()

    def get_active_alerts(self) -> List[Dict]:
        """Get all active diagnostic alerts."""
        alerts = self.diagnostic_engine.get_active_alerts()
        return [alert.to_dict() for alert in alerts]

    def quarantine_node(self, player_id: str, reason: QuarantineReason, duration_hours: int = 24):
        """Manually quarantine a node."""
        if player_id in self.graph_state.nodes:
            node = self.graph_state.nodes[player_id]
            node.quarantined = True
            node.quarantine_reason = reason.value

            self.diagnostic_engine.quarantine_component("node", player_id, reason, duration_hours)
            self.logger.warning(f"Manually quarantined node {player_id}: {reason.value}")

    def release_quarantine(self, player_id: str):
        """Release a quarantined node."""
        if player_id in self.graph_state.nodes:
            node = self.graph_state.nodes[player_id]
            node.quarantined = False
            node.quarantine_reason = None

            # Find and resolve related alerts
            for alert in self.diagnostic_engine.alerts:
                if (alert.component == "node" and
                    alert.component_id == player_id and
                    "quarantine" in alert.message.lower() and
                    not alert.resolved):
                    alert.resolve("Manual release")
                    break

            self.logger.info(f"Released quarantine for node {player_id}")

    async def run_diagnostic_cycle(self):
        """Run a full diagnostic cycle on all components."""
        self.logger.info("Starting diagnostic cycle")

        # Check all nodes
        for node in self.graph_state.nodes.values():
            alerts = self.diagnostic_engine.check_node_health(node)
            if alerts:
                self.logger.warning(f"Node {node.player_id} health alerts: {len(alerts)}")

        # Check all edges
        for edge in self.graph_state.edges.values():
            alerts = self.diagnostic_engine.check_edge_health(edge)
            if alerts:
                self.logger.warning(f"Edge {edge.edge_id} health alerts: {len(alerts)}")

        # Update health metrics
        evidence_stats = {"processed": self.update_count, "rejected": 0}  # Simplified
        self.diagnostic_engine.update_health_metrics(
            list(self.graph_state.nodes.values()),
            list(self.graph_state.edges.values()),
            evidence_stats
        )

        # Save state
        self._save_state()

        self.logger.info("Completed diagnostic cycle")

    def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """Create a timestamped backup of the current state."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = backup_name or f"backup_{timestamp}"

        backup_dir = self.storage_path / "backups" / backup_name
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Copy current state files
        import shutil
        graph_src = self.storage_path / "graph_state.json"
        diag_src = self.storage_path / "diagnostics_state.json"

        if graph_src.exists():
            shutil.copy2(graph_src, backup_dir / "graph_state.json")
        if diag_src.exists():
            shutil.copy2(diag_src, backup_dir / "diagnostics_state.json")

        # Create metadata
        metadata = {
            "backup_name": backup_name,
            "timestamp": datetime.now().isoformat(),
            "nodes_count": len(self.graph_state.nodes),
            "edges_count": len(self.graph_state.edges),
            "update_count": self.update_count,
            "system_health": self.get_system_health()["system_health_score"]
        }

        with open(backup_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)

        self.logger.info(f"Created backup: {backup_dir}")
        return backup_dir

    async def shutdown(self):
        """Gracefully shutdown the engine."""
        self.logger.info("Shutting down Truth Engine")

        # Process any remaining evidence
        while not self.evidence_queue.empty():
            try:
                bundle = await asyncio.wait_for(self.evidence_queue.get(), timeout=1.0)
                await self._process_evidence_bundle(bundle)
            except asyncio.TimeoutError:
                break

        # Final save
        self._save_state()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        self.logger.info("Truth Engine shutdown complete")


# Convenience functions for UFA integration

def update_truth(evidence_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for updating truth from evidence.

    This function integrates with the existing UFA pipeline.
    """
    # This would be a global or module-level engine instance
    # For now, return a placeholder response
    return {
        "status": "success",
        "message": "Truth engine update placeholder",
        "evidence_processed": len(evidence_data.get("bundles", [])),
        "nodes_updated": 0,
        "constraints_propagated": 0
    }


def get_live_projection(player_id: str, stat_type: str, line: float, direction: str) -> Optional[Dict]:
    """
    Get live probability projection.

    Integrates with existing UFA probability calculations.
    """
    # Placeholder - would query actual engine
    return {
        "player": player_id,
        "stat": stat_type,
        "line": line,
        "direction": direction,
        "probability": 0.5,  # Placeholder
        "confidence": 0.8,
        "source": "dynamic_truth_engine"
    }


def update_truth(evidence_bundle: EvidenceBundle) -> bool:
    """
    Update truth engine with new evidence.

    This is the main entry point for evidence integration.
    Returns True if evidence was accepted and processed.
    """
    # Placeholder - would submit to actual engine
    logger.info(f"Processing evidence for {evidence_bundle.player_id}")
    return True


def get_live_projection(player_id: str, stat_type: str, line: float, direction: str) -> Dict[str, Any]:
    """
    Get live probability projection for a player prop.

    Args:
        player_id: Player identifier
        stat_type: Type of stat (points, rebounds, etc.)
        line: The betting line
        direction: "higher" or "lower"

    Returns:
        Projection dict with probability, confidence, etc.
    """
    # Placeholder - would query actual engine
    return {
        "player": player_id,
        "stat": stat_type,
        "line": line,
        "direction": direction,
        "probability": 0.5,  # Placeholder
        "confidence": 0.8,
        "source": "dynamic_truth_engine"
    }


def get_system_status() -> Dict[str, Any]:
    """
    Get current system status for monitoring.

    Used by UFA dashboard and alerts.
    """
    return {
        "engine_status": "placeholder",
        "nodes_active": 0,
        "alerts_active": 0,
        "last_update": datetime.now().isoformat(),
        "system_health": 0.95
    }