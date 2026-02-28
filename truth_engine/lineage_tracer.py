"""
Probability Lineage Tracer
==========================

Tracks the full audit trail of probability estimates through the system.
Every probability adjustment is logged with source, reason, and magnitude.

This is CRITICAL for:
1. Debugging unexpected outputs
2. Regulatory compliance
3. Model improvement through post-hoc analysis
4. Detecting calibration drift
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LineageSource(Enum):
    """Source of probability estimate or adjustment."""
    BASELINE = "baseline"              # Initial Monte Carlo estimate
    MATCHUP_MEMORY = "matchup_memory"  # Player vs opponent adjustment
    INJURY_REPORT = "injury_report"    # Injury status adjustment
    PACE = "pace"                      # Game pace adjustment
    REST_DAYS = "rest_days"            # Rest/fatigue adjustment
    HOME_AWAY = "home_away"            # Home/away split
    MINUTES = "minutes"                # Expected minutes adjustment
    USAGE = "usage"                    # Usage rate adjustment
    WEATHER = "weather"                # Weather conditions (outdoor sports)
    RECENCY = "recency"                # Recent form adjustment
    CORRELATION = "correlation"        # Correlated outcome adjustment
    GATE_CAP = "gate_cap"              # Probability cap applied
    MANUAL_OVERRIDE = "manual"         # Human override


@dataclass
class LineageEntry:
    """Single entry in the probability lineage chain."""
    timestamp: datetime
    source: LineageSource
    input_prob: float
    output_prob: float
    adjustment_factor: float
    confidence: float
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
            "input_prob": self.input_prob,
            "output_prob": self.output_prob,
            "adjustment_factor": self.adjustment_factor,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LineageEntry":
        return cls(
            timestamp=datetime.fromisoformat(d["timestamp"]),
            source=LineageSource(d["source"]),
            input_prob=d["input_prob"],
            output_prob=d["output_prob"],
            adjustment_factor=d["adjustment_factor"],
            confidence=d["confidence"],
            reason=d["reason"],
            metadata=d.get("metadata", {}),
        )


@dataclass
class ProbabilityLineage:
    """
    Complete lineage for a single probability estimate.
    
    Tracks the probability from initial Monte Carlo through all adjustments.
    """
    edge_id: str
    player_id: str
    stat_type: str
    line: float
    direction: str
    
    # The chain of transformations
    entries: List[LineageEntry] = field(default_factory=list)
    
    # Final values
    initial_prob: Optional[float] = None
    final_prob: Optional[float] = None
    total_adjustment: float = 1.0
    
    # Quality metrics
    adjustment_count: int = 0
    max_single_adjustment: float = 0.0
    avg_confidence: float = 0.0
    
    # Flags
    was_capped: bool = False
    cap_applied: Optional[float] = None
    has_manual_override: bool = False
    
    def add_entry(self, entry: LineageEntry):
        """Add a lineage entry and update metrics."""
        self.entries.append(entry)
        
        if self.initial_prob is None:
            self.initial_prob = entry.input_prob
        
        self.final_prob = entry.output_prob
        self.adjustment_count += 1
        
        # Track adjustment magnitude
        adj_magnitude = abs(entry.adjustment_factor - 1.0)
        self.max_single_adjustment = max(self.max_single_adjustment, adj_magnitude)
        
        # Update total adjustment
        self.total_adjustment *= entry.adjustment_factor
        
        # Running average of confidence
        total_conf = sum(e.confidence for e in self.entries)
        self.avg_confidence = total_conf / len(self.entries)
        
        # Check for cap
        if entry.source == LineageSource.GATE_CAP:
            self.was_capped = True
            self.cap_applied = entry.output_prob
        
        # Check for manual override
        if entry.source == LineageSource.MANUAL_OVERRIDE:
            self.has_manual_override = True
    
    def get_lineage_hash(self) -> str:
        """Generate unique hash for this lineage chain."""
        content = json.dumps([e.to_dict() for e in self.entries], sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "player_id": self.player_id,
            "stat_type": self.stat_type,
            "line": self.line,
            "direction": self.direction,
            "entries": [e.to_dict() for e in self.entries],
            "initial_prob": self.initial_prob,
            "final_prob": self.final_prob,
            "total_adjustment": self.total_adjustment,
            "adjustment_count": self.adjustment_count,
            "max_single_adjustment": self.max_single_adjustment,
            "avg_confidence": self.avg_confidence,
            "was_capped": self.was_capped,
            "cap_applied": self.cap_applied,
            "has_manual_override": self.has_manual_override,
            "lineage_hash": self.get_lineage_hash(),
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProbabilityLineage":
        lineage = cls(
            edge_id=d["edge_id"],
            player_id=d["player_id"],
            stat_type=d["stat_type"],
            line=d["line"],
            direction=d["direction"],
        )
        for entry_dict in d.get("entries", []):
            lineage.entries.append(LineageEntry.from_dict(entry_dict))
        lineage.initial_prob = d.get("initial_prob")
        lineage.final_prob = d.get("final_prob")
        lineage.total_adjustment = d.get("total_adjustment", 1.0)
        lineage.adjustment_count = d.get("adjustment_count", 0)
        lineage.max_single_adjustment = d.get("max_single_adjustment", 0.0)
        lineage.avg_confidence = d.get("avg_confidence", 0.0)
        lineage.was_capped = d.get("was_capped", False)
        lineage.cap_applied = d.get("cap_applied")
        lineage.has_manual_override = d.get("has_manual_override", False)
        return lineage


class ProbabilityLineageTracer:
    """
    Central tracer for all probability lineages in a session.
    
    Usage:
        tracer = ProbabilityLineageTracer()
        
        # Start tracking a probability
        tracer.start_lineage("edge_123", "lebron_james", "PTS", 25.5, "HIGHER")
        
        # Record baseline
        tracer.record_adjustment("edge_123", LineageSource.BASELINE, 0.0, 0.55, 
                                 1.0, 0.9, "Monte Carlo baseline")
        
        # Record matchup adjustment  
        tracer.record_adjustment("edge_123", LineageSource.MATCHUP_MEMORY, 0.55, 0.58,
                                 1.055, 0.7, "Favorable BOS matchup history")
        
        # Get final lineage
        lineage = tracer.get_lineage("edge_123")
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("outputs/lineage")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self._lineages: Dict[str, ProbabilityLineage] = {}
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def start_lineage(self, edge_id: str, player_id: str, stat_type: str,
                      line: float, direction: str) -> ProbabilityLineage:
        """Start tracking a new probability lineage."""
        lineage = ProbabilityLineage(
            edge_id=edge_id,
            player_id=player_id,
            stat_type=stat_type,
            line=line,
            direction=direction,
        )
        self._lineages[edge_id] = lineage
        return lineage
    
    def record_adjustment(
        self,
        edge_id: str,
        source: LineageSource,
        input_prob: float,
        output_prob: float,
        adjustment_factor: float,
        confidence: float,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[LineageEntry]:
        """Record a probability adjustment in the lineage."""
        if edge_id not in self._lineages:
            logger.warning(f"No lineage started for edge {edge_id}")
            return None
        
        entry = LineageEntry(
            timestamp=datetime.now(),
            source=source,
            input_prob=input_prob,
            output_prob=output_prob,
            adjustment_factor=adjustment_factor,
            confidence=confidence,
            reason=reason,
            metadata=metadata or {},
        )
        
        self._lineages[edge_id].add_entry(entry)
        return entry
    
    def get_lineage(self, edge_id: str) -> Optional[ProbabilityLineage]:
        """Get the full lineage for an edge."""
        return self._lineages.get(edge_id)
    
    def get_all_lineages(self) -> Dict[str, ProbabilityLineage]:
        """Get all tracked lineages."""
        return self._lineages
    
    def save_session(self, filename: Optional[str] = None):
        """Persist all lineages to disk."""
        if filename is None:
            filename = f"lineage_{self._session_id}.json"
        
        path = self.storage_path / filename
        data = {
            "session_id": self._session_id,
            "timestamp": datetime.now().isoformat(),
            "lineage_count": len(self._lineages),
            "lineages": {k: v.to_dict() for k, v in self._lineages.items()},
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved {len(self._lineages)} lineages to {path}")
        return path
    
    def load_session(self, filename: str):
        """Load lineages from a previous session."""
        path = self.storage_path / filename
        if not path.exists():
            logger.warning(f"Lineage file not found: {path}")
            return
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        self._session_id = data.get("session_id", self._session_id)
        self._lineages = {
            k: ProbabilityLineage.from_dict(v) 
            for k, v in data.get("lineages", {}).items()
        }
        
        logger.info(f"Loaded {len(self._lineages)} lineages from {path}")
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate summary statistics for all lineages."""
        if not self._lineages:
            return {"error": "No lineages tracked"}
        
        # Aggregate stats
        total_adjustments = sum(l.adjustment_count for l in self._lineages.values())
        avg_total_adj = sum(l.total_adjustment for l in self._lineages.values()) / len(self._lineages)
        capped_count = sum(1 for l in self._lineages.values() if l.was_capped)
        override_count = sum(1 for l in self._lineages.values() if l.has_manual_override)
        
        # Source breakdown
        source_counts: Dict[str, int] = {}
        for lineage in self._lineages.values():
            for entry in lineage.entries:
                source_counts[entry.source.value] = source_counts.get(entry.source.value, 0) + 1
        
        # Largest adjustments
        largest_adj = sorted(
            [(l.edge_id, l.max_single_adjustment) for l in self._lineages.values()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "session_id": self._session_id,
            "total_lineages": len(self._lineages),
            "total_adjustments": total_adjustments,
            "avg_adjustments_per_edge": total_adjustments / len(self._lineages),
            "avg_total_adjustment": avg_total_adj,
            "capped_count": capped_count,
            "capped_pct": capped_count / len(self._lineages) * 100,
            "override_count": override_count,
            "source_breakdown": source_counts,
            "largest_adjustments": largest_adj,
        }


# Convenience function for inline lineage recording
def record_lineage_step(
    tracer: Optional[ProbabilityLineageTracer],
    edge_id: str,
    source: LineageSource,
    input_prob: float,
    output_prob: float,
    confidence: float,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Record a lineage step if tracer is active, return output probability.
    
    This is designed for easy integration into existing code:
    
        prob = record_lineage_step(tracer, edge_id, LineageSource.BASELINE,
                                   0.0, 0.55, 0.9, "MC baseline")
        prob = record_lineage_step(tracer, edge_id, LineageSource.MATCHUP_MEMORY,
                                   prob, 0.58, 0.7, "BOS favorable")
    """
    if tracer is not None:
        factor = output_prob / input_prob if input_prob > 0 else 1.0
        tracer.record_adjustment(
            edge_id, source, input_prob, output_prob, factor, confidence, reason, metadata
        )
    return output_prob
