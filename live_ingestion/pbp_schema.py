"""
PBP Schema - Canonical event definitions for live play-by-play ingestion

All PBP sources (ESPN, NBA API, etc.) are normalized to this schema.
This ensures consistent processing regardless of data source.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum


class PBPEventType(Enum):
    """Canonical event types that affect player projections."""

    # Player-specific events
    SHOT_MADE = "shot_made"
    SHOT_MISSED = "shot_missed"
    FOUL = "foul"
    TURNOVER = "turnover"
    SUBSTITUTION_IN = "sub_in"
    SUBSTITUTION_OUT = "sub_out"

    # Game flow events
    TIMEOUT = "timeout"
    PERIOD_START = "period_start"
    PERIOD_END = "period_end"
    GAME_START = "game_start"
    GAME_END = "game_end"

    # Contextual events (low weight)
    REBOUND = "rebound"
    STEAL = "steal"
    BLOCK = "block"


@dataclass
class PBPEvent:
    """
    Canonical PBP event - all sources normalized to this format.

    This is the single source of truth for live game events.
    """

    # Identity
    event_id: str  # Unique across all games/sources
    game_id: str   # ESPN game ID or equivalent
    source: str    # "espn", "nba_api", "boxscore"

    # Timing
    timestamp: datetime  # When event occurred
    quarter: int         # 1-4 for NBA
    clock_seconds: int   # Seconds remaining in quarter

    # Event details
    event_type: PBPEventType
    player_id: Optional[str] = None  # NBA player ID if applicable
    team_id: str = ""                # NBA team ID

    # Additional context
    metadata: Dict[str, Any] = None  # Source-specific details

    def __post_init__(self):
        """Validate event after creation."""
        if self.metadata is None:
            self.metadata = {}

        # Validate required fields
        if not self.event_id or not self.game_id:
            raise ValueError("event_id and game_id are required")

        if self.quarter < 1 or self.quarter > 4:
            raise ValueError("quarter must be 1-4")

        if self.clock_seconds < 0 or self.clock_seconds > 720:  # 12 minutes
            raise ValueError("clock_seconds must be 0-720")

        # Player events require player_id
        player_events = {
            PBPEventType.SHOT_MADE, PBPEventType.SHOT_MISSED,
            PBPEventType.FOUL, PBPEventType.TURNOVER,
            PBPEventType.SUBSTITUTION_IN, PBPEventType.SUBSTITUTION_OUT,
            PBPEventType.REBOUND, PBPEventType.STEAL, PBPEventType.BLOCK
        }

        if self.event_type in player_events and not self.player_id:
            raise ValueError(f"{self.event_type.value} events require player_id")

    @property
    def is_player_event(self) -> bool:
        """Check if this event affects a specific player."""
        return self.player_id is not None

    @property
    def is_game_flow_event(self) -> bool:
        """Check if this event affects game flow."""
        return self.event_type in {
            PBPEventType.TIMEOUT, PBPEventType.PERIOD_START,
            PBPEventType.PERIOD_END, PBPEventType.GAME_START,
            PBPEventType.GAME_END
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "game_id": self.game_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "quarter": self.quarter,
            "clock_seconds": self.clock_seconds,
            "event_type": self.event_type.value,
            "player_id": self.player_id,
            "team_id": self.team_id,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PBPEvent':
        """Create from dictionary."""
        # Convert timestamp
        timestamp = datetime.fromisoformat(data["timestamp"])

        # Convert event_type
        event_type = PBPEventType(data["event_type"])

        return cls(
            event_id=data["event_id"],
            game_id=data["game_id"],
            source=data["source"],
            timestamp=timestamp,
            quarter=data["quarter"],
            clock_seconds=data["clock_seconds"],
            event_type=event_type,
            player_id=data.get("player_id"),
            team_id=data.get("team_id", ""),
            metadata=data.get("metadata", {})
        )


@dataclass
class PBPGame:
    """
    Container for all events in a game.

    Maintains chronological order and provides lookup methods.
    """

    game_id: str
    events: list[PBPEvent] = None
    last_updated: Optional[datetime] = None

    def __post_init__(self):
        """Initialize events list."""
        if self.events is None:
            self.events = []

    def add_event(self, event: PBPEvent) -> None:
        """Add event and maintain chronological order."""
        if event.game_id != self.game_id:
            raise ValueError(f"Event game_id {event.game_id} != game game_id {self.game_id}")

        # Insert in chronological order
        insert_idx = 0
        for i, existing in enumerate(self.events):
            if event.timestamp > existing.timestamp:
                insert_idx = i + 1
            elif event.timestamp == existing.timestamp:
                # Same timestamp - maintain event_id order for determinism
                if event.event_id > existing.event_id:
                    insert_idx = i + 1
                else:
                    break
            else:
                break

        self.events.insert(insert_idx, event)
        self.last_updated = event.timestamp

    def get_player_events(self, player_id: str) -> list[PBPEvent]:
        """Get all events for a specific player."""
        return [e for e in self.events if e.player_id == player_id]

    def get_recent_events(self, minutes: int = 5) -> list[PBPEvent]:
        """Get events from the last N minutes."""
        if not self.last_updated:
            return []

        cutoff = self.last_updated - timedelta(minutes=minutes)
        return [e for e in self.events if e.timestamp >= cutoff]

    def get_current_state(self) -> Dict[str, Any]:
        """Get current game state summary."""
        if not self.events:
            return {"status": "not_started"}

        latest = self.events[-1]

        # Count events by type
        event_counts = {}
        for event in self.events:
            event_counts[event.event_type.value] = event_counts.get(event.event_type.value, 0) + 1

        return {
            "game_id": self.game_id,
            "last_event": latest.timestamp.isoformat(),
            "quarter": latest.quarter,
            "clock_seconds": latest.clock_seconds,
            "total_events": len(self.events),
            "event_counts": event_counts
        }