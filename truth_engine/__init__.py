"""
Dynamic Truth Engine - Probabilistic Dependency Graph for Live Betting Intelligence

This package implements a node-based system for maintaining probabilistic truth
about player performance, with real-time evidence updates and constraint propagation.
"""

from .truth_engine import TruthEngine, update_truth, get_live_projection, get_system_status
from .player_node import PlayerNode, Distribution
from .evidence import EvidenceBundle, EvidenceProcessor, EvidenceType, EvidenceSource, EvidenceSignal
from .dependency_edge import DependencyEdge, EdgeFactory, EdgeType, ConstraintType
from .diagnostics import DiagnosticEngine, DiagnosticLevel, QuarantineReason

__version__ = "1.0.0"
__all__ = [
    # Main engine
    "TruthEngine",
    "update_truth",
    "get_live_projection",
    "get_system_status",

    # Core components
    "PlayerNode",
    "Distribution",
    "EvidenceBundle",
    "EvidenceProcessor",
    "EvidenceType",
    "EvidenceSource",
    "DependencyEdge",
    "EdgeFactory",
    "EdgeType",
    "ConstraintType",

    # Diagnostics
    "DiagnosticEngine",
    "DiagnosticLevel",
    "QuarantineReason"
]