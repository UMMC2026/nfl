"""
Evidence System - Handles live data updates and Bayesian evidence processing

Evidence comes from multiple sources (PBP, commentary, tracking) with different
confidence levels and decay characteristics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import json
from enum import Enum


class EvidenceType(Enum):
    """Types of evidence that can update player nodes."""
    PLAY_BY_PLAY = "pbp"
    COMMENTARY = "commentary"
    TRACKING = "tracking"
    INJURY_REPORT = "injury"
    LINEUP_CHANGE = "lineup"
    STAT_UPDATE = "stat_update"


class EvidenceSource(Enum):
    """Sources of evidence data."""
    ESPN = "espn"
    NBA_API = "nba_api"
    OFFICIAL_FEED = "official"
    ANALYST = "analyst"
    TRACKING_SYSTEM = "tracking"


@dataclass
class EvidenceSignal:
    """
    Individual signal within evidence bundle.

    Represents a specific measurement or observation.
    """
    value: Union[float, int, str, bool]
    confidence: float  # 0.0 to 1.0
    strength: float  # How strongly to weight this signal (0.0 to 1.0)
    timestamp: datetime
    source: EvidenceSource
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_stale(self, max_age_minutes: int = 30) -> bool:
        """Check if evidence is too old to be useful."""
        return (datetime.now() - self.timestamp) > timedelta(minutes=max_age_minutes)

    def decayed_confidence(self, decay_rate: float = 0.1) -> float:
        """
        Apply time-based decay to confidence.

        decay_rate: How much confidence drops per minute
        """
        age_minutes = (datetime.now() - self.timestamp).total_seconds() / 60.0
        decay_factor = max(0.0, 1.0 - (decay_rate * age_minutes))
        return self.confidence * decay_factor


@dataclass
class EvidenceBundle:
    """
    Collection of related evidence signals for a player.

    Bundles maintain integrity and can be validated as a unit.
    """
    player_id: str
    evidence_type: EvidenceType
    timestamp: datetime

    # Core signals
    minutes_signal: Optional[EvidenceSignal] = None
    usage_signal: Optional[EvidenceSignal] = None
    fatigue_signal: Optional[EvidenceSignal] = None
    foul_signal: Optional[EvidenceSignal] = None
    injury_signal: Optional[EvidenceSignal] = None

    # Additional context
    game_context: Dict[str, Any] = field(default_factory=dict)  # quarter, score, etc.
    source_confidences: Dict[str, float] = field(default_factory=dict)

    # Integrity and validation
    integrity_score: float = 1.0
    validation_errors: List[str] = field(default_factory=list)

    def validate_integrity(self) -> bool:
        """
        Validate the integrity of this evidence bundle.

        Returns True if bundle should be processed.
        """
        errors = []

        # Check for conflicting signals
        if self.minutes_signal and self.minutes_signal.value < 0:
            errors.append("Invalid minutes value")

        if self.usage_signal and self.usage_signal.value < 0:
            errors.append("Invalid usage value")

        # Check signal consistency
        if self.fatigue_signal and self.fatigue_signal.value > 1.0:
            errors.append("Fatigue signal out of bounds")

        # Check for stale data
        signals = [self.minutes_signal, self.usage_signal, self.fatigue_signal,
                  self.foul_signal, self.injury_signal]
        for signal in signals:
            if signal and signal.is_stale():
                errors.append(f"Stale {signal} signal")

        # Calculate integrity score
        self.validation_errors = errors
        self.integrity_score = max(0.0, 1.0 - (len(errors) * 0.2))

        return self.integrity_score >= 0.5

    def get_effective_signals(self) -> Dict[str, EvidenceSignal]:
        """
        Get signals with decayed confidence applied.

        Only returns signals that pass integrity checks.
        """
        if not self.validate_integrity():
            return {}

        signals = {}
        decay_rate = 0.05  # 5% confidence loss per minute

        if self.minutes_signal:
            self.minutes_signal.confidence = self.minutes_signal.decayed_confidence(decay_rate)
            signals["minutes"] = self.minutes_signal

        if self.usage_signal:
            self.usage_signal.confidence = self.usage_signal.decayed_confidence(decay_rate)
            signals["usage"] = self.usage_signal

        if self.fatigue_signal:
            self.fatigue_signal.confidence = self.fatigue_signal.decayed_confidence(decay_rate)
            signals["fatigue"] = self.fatigue_signal

        if self.foul_signal:
            self.foul_signal.confidence = self.foul_signal.decayed_confidence(decay_rate)
            signals["foul"] = self.foul_signal

        if self.injury_signal:
            self.injury_signal.confidence = self.injury_signal.decayed_confidence(decay_rate)
            signals["injury"] = self.injury_signal

        return signals

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "player_id": self.player_id,
            "evidence_type": self.evidence_type.value,
            "timestamp": self.timestamp.isoformat(),
            "minutes_signal": self.minutes_signal.__dict__ if self.minutes_signal else None,
            "usage_signal": self.usage_signal.__dict__ if self.usage_signal else None,
            "fatigue_signal": self.fatigue_signal.__dict__ if self.fatigue_signal else None,
            "foul_signal": self.foul_signal.__dict__ if self.foul_signal else None,
            "injury_signal": self.injury_signal.__dict__ if self.injury_signal else None,
            "game_context": self.game_context,
            "source_confidences": self.source_confidences,
            "integrity_score": self.integrity_score,
            "validation_errors": self.validation_errors
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvidenceBundle":
        """Deserialize from dict."""
        # Helper to recreate signals
        def signal_from_dict(signal_dict):
            if not signal_dict:
                return None
            return EvidenceSignal(
                value=signal_dict["value"],
                confidence=signal_dict["confidence"],
                strength=signal_dict["strength"],
                timestamp=datetime.fromisoformat(signal_dict["timestamp"]),
                source=EvidenceSource(signal_dict["source"]),
                metadata=signal_dict.get("metadata", {})
            )

        return cls(
            player_id=d["player_id"],
            evidence_type=EvidenceType(d["evidence_type"]),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            minutes_signal=signal_from_dict(d.get("minutes_signal")),
            usage_signal=signal_from_dict(d.get("usage_signal")),
            fatigue_signal=signal_from_dict(d.get("fatigue_signal")),
            foul_signal=signal_from_dict(d.get("foul_signal")),
            injury_signal=signal_from_dict(d.get("injury_signal")),
            game_context=d.get("game_context", {}),
            source_confidences=d.get("source_confidences", {}),
            integrity_score=d.get("integrity_score", 1.0),
            validation_errors=d.get("validation_errors", [])
        )


class EvidenceProcessor:
    """
    Processes raw data into evidence bundles.

    Handles different data sources and formats.
    """

    def __init__(self):
        self.source_confidence_map = {
            EvidenceSource.ESPN: 0.9,
            EvidenceSource.NBA_API: 0.85,
            EvidenceSource.OFFICIAL_FEED: 0.95,
            EvidenceSource.ANALYST: 0.6,
            EvidenceSource.TRACKING_SYSTEM: 0.8
        }

    def process_pbp_data(self, pbp_events: List[Dict], player_id: str) -> EvidenceBundle:
        """
        Process play-by-play data into evidence.

        Extracts minutes played, usage patterns, fatigue indicators.
        """
        bundle = EvidenceBundle(
            player_id=player_id,
            evidence_type=EvidenceType.PLAY_BY_PLAY,
            timestamp=datetime.now()
        )

        # Analyze PBP for player activity
        player_events = [e for e in pbp_events if e.get("player_id") == player_id]

        if not player_events:
            bundle.integrity_score = 0.0
            bundle.validation_errors.append("No player events found")
            return bundle

        # Calculate minutes from timestamps
        timestamps = [datetime.fromisoformat(e["timestamp"]) for e in player_events if "timestamp" in e]
        if timestamps:
            minutes_played = (max(timestamps) - min(timestamps)).total_seconds() / 60.0
            bundle.minutes_signal = EvidenceSignal(
                value=minutes_played,
                confidence=self.source_confidence_map[EvidenceSource.ESPN],
                strength=0.8,
                timestamp=datetime.now(),
                source=EvidenceSource.ESPN
            )

        # Analyze usage patterns (simplified)
        action_counts = {}
        for event in player_events:
            action = event.get("action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1

        # Estimate usage from actions
        total_actions = sum(action_counts.values())
        if total_actions > 0:
            usage_estimate = min(100.0, (total_actions / 10.0) * 100)  # Rough heuristic
            bundle.usage_signal = EvidenceSignal(
                value=usage_estimate,
                confidence=0.7,
                strength=0.6,
                timestamp=datetime.now(),
                source=EvidenceSource.ESPN
            )

        # Fatigue indicators (consecutive actions without rest)
        fatigue_score = self._calculate_fatigue_from_pbp(player_events)
        if fatigue_score > 0:
            bundle.fatigue_signal = EvidenceSignal(
                value=fatigue_score,
                confidence=0.6,
                strength=0.5,
                timestamp=datetime.now(),
                source=EvidenceSource.ESPN
            )

        bundle.source_confidences["pbp_analysis"] = 0.8
        return bundle

    def process_commentary_data(self, commentary: str, player_id: str) -> EvidenceBundle:
        """
        Process analyst commentary into evidence.

        Uses NLP to extract player status indicators.
        """
        bundle = EvidenceBundle(
            player_id=player_id,
            evidence_type=EvidenceType.COMMENTARY,
            timestamp=datetime.now()
        )

        # Simple keyword analysis (can be enhanced with NLP)
        commentary_lower = commentary.lower()

        # Fatigue indicators
        fatigue_keywords = ["tired", "fatigued", "winded", "struggling", "heavy legs"]
        fatigue_score = sum(1 for kw in fatigue_keywords if kw in commentary_lower) * 0.2

        if fatigue_score > 0:
            bundle.fatigue_signal = EvidenceSignal(
                value=min(1.0, fatigue_score),
                confidence=0.5,  # Analyst commentary is subjective
                strength=0.4,
                timestamp=datetime.now(),
                source=EvidenceSource.ANALYST
            )

        # Injury indicators
        injury_keywords = ["injury", "limp", "favoring", "soreness", "questionable"]
        injury_score = sum(1 for kw in injury_keywords if kw in commentary_lower) * 0.3

        if injury_score > 0:
            bundle.injury_signal = EvidenceSignal(
                value=min(1.0, injury_score),
                confidence=0.6,
                strength=0.7,  # Injuries are serious
                timestamp=datetime.now(),
                source=EvidenceSource.ANALYST
            )

        bundle.source_confidences["commentary_analysis"] = 0.6
        return bundle

    def process_tracking_data(self, tracking_data: Dict, player_id: str) -> EvidenceBundle:
        """
        Process advanced tracking data into evidence.

        Includes biomechanical and performance metrics.
        """
        bundle = EvidenceBundle(
            player_id=player_id,
            evidence_type=EvidenceType.TRACKING,
            timestamp=datetime.now()
        )

        # Extract relevant metrics
        if "biomechanics" in tracking_data:
            bio = tracking_data["biomechanics"]

            # Fatigue from movement efficiency
            if "movement_efficiency" in bio:
                efficiency = bio["movement_efficiency"]
                fatigue_score = max(0, 1.0 - efficiency)  # Lower efficiency = more fatigue
                bundle.fatigue_signal = EvidenceSignal(
                    value=fatigue_score,
                    confidence=self.source_confidence_map[EvidenceSource.TRACKING_SYSTEM],
                    strength=0.7,
                    timestamp=datetime.now(),
                    source=EvidenceSource.TRACKING_SYSTEM
                )

        bundle.source_confidences["tracking_analysis"] = 0.8
        return bundle

    def _calculate_fatigue_from_pbp(self, events: List[Dict]) -> float:
        """
        Calculate fatigue score from PBP patterns.

        Looks for decreased activity or efficiency over time.
        """
        if len(events) < 5:
            return 0.0

        # Sort by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        # Simple heuristic: fatigue increases with consecutive high-intensity actions
        fatigue_score = 0.0
        consecutive_high_intensity = 0

        for event in sorted_events:
            action = event.get("action", "").lower()
            if any(word in action for word in ["drive", "dunk", "block", "steal"]):
                consecutive_high_intensity += 1
                if consecutive_high_intensity > 3:
                    fatigue_score += 0.1
            else:
                consecutive_high_intensity = 0

        return min(1.0, fatigue_score)