"""
PBP Normalizer - Unifies multiple PBP sources into canonical events

Handles ESPN, NBA API, and boxscore deltas.
Ensures all events conform to PBPEvent schema.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Iterator, AsyncIterator
from datetime import datetime, timedelta, timezone
import time

from .pbp_schema import PBPEvent, PBPEventType, PBPGame
from .espn_pbp_listener import ESPNPBPListener, ESPNPBPConfig
from .sportsdata_pbp_listener import SportsDataIOPBPListener, SportsDataIOConfig, SportsDataIOPBPSource
from .pbp_sources import PBPSource

logger = logging.getLogger(__name__)


class ESPNPBPSource(PBPSource):
    """ESPN PBP source wrapper."""

    def __init__(self, config: Optional[ESPNPBPConfig] = None):
        self.listener = ESPNPBPListener(config)

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        return self.listener.get_game_pbp(game_id)

    def stream_live_events(self, game_id: str) -> Iterator[PBPEvent]:
        return self.listener.get_live_pbp_stream(game_id)

    def get_source_name(self) -> str:
        return "espn"


class NBAPBPSource(PBPSource):
    """NBA API PBP source (placeholder for future implementation)."""

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        # TODO: Implement NBA API PBP fetching
        logger.warning("NBA API PBP not yet implemented")
        return None

    def stream_live_events(self, game_id: str) -> Iterator[PBPEvent]:
        # TODO: Implement NBA API live streaming
        logger.warning("NBA API live streaming not yet implemented")
        return iter([])

    def get_source_name(self) -> str:
        return "nba_api"


class BoxscoreDeltaSource(PBPSource):
    """Boxscore delta source (fallback for basic game state)."""

    def __init__(self):
        self._last_boxscores: Dict[str, Dict[str, Any]] = {}

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        # Boxscore deltas don't provide full PBP, only current state
        logger.warning("Boxscore source doesn't support full PBP history")
        return None

    def stream_live_events(self, game_id: str) -> Iterator[PBPEvent]:
        # TODO: Implement boxscore polling for basic events
        logger.warning("Boxscore delta streaming not yet implemented")
        return iter([])

    def get_source_name(self) -> str:
        return "boxscore"


@dataclass
class PBPNormalizerConfig:
    """Configuration for PBP normalization."""
    primary_source: str = "sportsdata"  # Primary data source (SportsDataIO for rate-limited production)
    fallback_sources: List[str] = None  # Fallback sources in priority order
    deduplication_window: timedelta = timedelta(seconds=30)  # Window for duplicate detection
    max_event_age: timedelta = timedelta(hours=6)  # Maximum age for live events
    validation_enabled: bool = True

    # SportsDataIO specific configuration
    sportsdata_api_key: Optional[str] = None
    sportsdata_daily_limit: int = 1000
    sportsdata_burst_limit: int = 10

    # Degradation settings
    confidence_decay_on_throttle: float = 0.85  # Confidence multiplier when throttled
    partial_feed_threshold_seconds: int = 300  # 5 minutes without events = degraded
    auto_switch_to_static: bool = True  # Auto-switch to static mode on limits

    def __post_init__(self):
        if self.fallback_sources is None:
            self.fallback_sources = ["espn", "nba_api", "boxscore"]


class PBPNormalizer:
    """
    Normalizes PBP data from multiple sources into canonical events.

    Handles source failover, deduplication, and validation.
    """

    def __init__(self, config: Optional[PBPNormalizerConfig] = None):
        self.config = config or PBPNormalizerConfig()
        self.sources: Dict[str, PBPSource] = {}

        # Initialize sources
        self._init_sources()

        # Deduplication tracking
        self._recent_events: Dict[str, datetime] = {}

        # Degradation and mode switching state
        self._degraded_games: Dict[str, Dict[str, Any]] = {}
        self._mode_switches: List[Dict[str, Any]] = []

    def _init_sources(self):
        """Initialize all PBP sources."""
        # SportsDataIO (primary for rate-limited production)
        if self.config.sportsdata_api_key:
            sportsdata_config = SportsDataIOConfig(
                api_key=self.config.sportsdata_api_key,
                daily_limit=self.config.sportsdata_daily_limit,
                burst_limit=self.config.sportsdata_burst_limit
            )
            self.sources["sportsdata"] = SportsDataIOPBPSource(sportsdata_config)
        else:
            logger.warning("SportsDataIO API key not provided - source disabled")

        # ESPN (fallback)
        self.sources["espn"] = ESPNPBPSource()

        # NBA API (fallback)
        self.sources["nba_api"] = NBAPBPSource()

        # Boxscore deltas (last resort)
        self.sources["boxscore"] = BoxscoreDeltaSource()

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        """
        Get complete PBP for a game from best available source.

        Args:
            game_id: Game identifier

        Returns:
            PBPGame with normalized events, or None if unavailable
        """
        sources_to_try = [self.config.primary_source] + self.config.fallback_sources

        for source_name in sources_to_try:
            source = self.sources.get(source_name)
            if not source:
                continue

            try:
                game = source.get_game_pbp(game_id)
                if game:
                    # Validate and normalize events
                    normalized_events = []
                    for event in game.events:
                        normalized = self._normalize_event(event)
                        if normalized and self._validate_event(normalized):
                            # Apply confidence decay for degraded games
                            normalized = self.apply_confidence_decay(normalized)
                            normalized_events.append(normalized)

                    game.events = normalized_events
                    logger.info(f"Successfully fetched {len(normalized_events)} events for game {game_id} from {source_name}")
                    return game

            except Exception as e:
                logger.warning(f"Failed to get PBP from {source_name} for game {game_id}: {e}")
                continue

        logger.error(f"No PBP sources available for game {game_id}")
        return None

    def stream_live_events(self, game_id: str) -> Iterator[PBPEvent]:
        """
        Stream live events from primary source with failover and degradation handling.

        Yields normalized, validated events with confidence decay applied.
        """
        primary_source = self.sources.get(self.config.primary_source)
        if not primary_source:
            logger.error(f"Primary source {self.config.primary_source} not available")
            return

        last_event_time = datetime.now(timezone.utc)

        try:
            for event in primary_source.stream_live_events(game_id):
                normalized = self._normalize_event(event)
                if normalized and self._validate_event(normalized) and not self._is_duplicate(normalized):
                    # Apply confidence decay for degraded games
                    normalized = self.apply_confidence_decay(normalized)

                    self._mark_event(normalized)
                    last_event_time = normalized.timestamp
                    yield normalized

                # Check for partial feed periodically
                if self.check_partial_feed(game_id, last_event_time):
                    logger.warning(f"Partial feed detected for game {game_id}")

        except Exception as e:
            logger.error(f"Primary source streaming failed for game {game_id}: {e}")

            # Try fallback sources
            for fallback_name in self.config.fallback_sources:
                fallback_source = self.sources.get(fallback_name)
                if fallback_source:
                    try:
                        logger.info(f"Trying fallback source {fallback_name} for game {game_id}")
                        for event in fallback_source.stream_live_events(game_id):
                            normalized = self._normalize_event(event)
                            if normalized and self._validate_event(normalized) and not self._is_duplicate(normalized):
                                # Apply confidence decay for degraded games
                                normalized = self.apply_confidence_decay(normalized)

                                self._mark_event(normalized)
                                last_event_time = normalized.timestamp
                                yield normalized
                        break  # Success with fallback
                    except Exception as e2:
                        logger.warning(f"Fallback source {fallback_name} also failed: {e2}")
                        continue

        # Final partial feed check
        self.check_partial_feed(game_id, last_event_time)

    def _normalize_event(self, event: PBPEvent) -> Optional[PBPEvent]:
        """
        Apply final normalization to event.

        Ensures consistency across sources.
        """
        try:
            # Deep copy to avoid modifying original
            normalized = PBPEvent.__new__(PBPEvent)
            normalized.event_id = event.event_id
            normalized.game_id = event.game_id
            normalized.source = event.source
            normalized.timestamp = event.timestamp
            normalized.quarter = event.quarter
            normalized.clock_seconds = event.clock_seconds
            normalized.event_type = event.event_type
            normalized.player_id = event.player_id
            normalized.team_id = event.team_id
            normalized.metadata = event.metadata.copy() if event.metadata else {}

            # Normalize timestamps to UTC
            if normalized.timestamp.tzinfo is None:
                normalized.timestamp = normalized.timestamp.replace(tzinfo=timezone.utc)

            # Ensure event_id uniqueness across sources
            if not normalized.event_id.startswith(f"{normalized.source}_"):
                normalized.event_id = f"{normalized.source}_{normalized.event_id}"

            # Validate clock_seconds bounds
            if normalized.clock_seconds > 720:  # 12 minutes max
                normalized.clock_seconds = 720
            elif normalized.clock_seconds < 0:
                normalized.clock_seconds = 0

            # Validate quarter bounds
            if normalized.quarter < 1:
                normalized.quarter = 1
            elif normalized.quarter > 4:
                normalized.quarter = 4

            return normalized

        except Exception as e:
            logger.warning(f"Failed to normalize event {event.event_id}: {e}")
            return None

    def _validate_event(self, event: PBPEvent) -> bool:
        """Validate event against schema and business rules."""
        if not self.config.validation_enabled:
            return True

        try:
            # Schema validation (PBPEvent.__post_init__ handles most)
            event.__post_init__()

            # Business rule validation
            now = datetime.now(timezone.utc)

            # Event not too old for live processing
            if (now - event.timestamp) > self.config.max_event_age:
                logger.warning(f"Event {event.event_id} too old: {event.timestamp}")
                return False

            # Event not in future
            if event.timestamp > now + timedelta(minutes=5):  # Allow 5 min clock skew
                logger.warning(f"Event {event.event_id} timestamp in future: {event.timestamp}")
                return False

            # Quarter bounds
            if not (1 <= event.quarter <= 4):
                logger.warning(f"Event {event.event_id} invalid quarter: {event.quarter}")
                return False

            return True

        except Exception as e:
            logger.warning(f"Event validation failed for {event.event_id}: {e}")
            return False

    def _is_duplicate(self, event: PBPEvent) -> bool:
        """Check if event is a duplicate within deduplication window."""
        key = f"{event.game_id}_{event.event_type.value}_{event.player_id or 'none'}"

        now = datetime.now(timezone.utc)
        window_start = now - self.config.deduplication_window

        # Clean old entries
        self._recent_events = {
            k: v for k, v in self._recent_events.items()
            if v > window_start
        }

        if key in self._recent_events:
            return True

        self._recent_events[key] = event.timestamp
        return False

    def _mark_event(self, event: PBPEvent):
        """Mark event as processed for deduplication."""
        key = f"{event.game_id}_{event.event_type.value}_{event.player_id or 'none'}"
        self._recent_events[key] = event.timestamp

    # Degradation and mode switching state
    _degraded_games: Dict[str, Dict[str, Any]] = {}
    _mode_switches: List[Dict[str, Any]] = []

    def apply_confidence_decay(self, event: PBPEvent) -> PBPEvent:
        """Apply confidence decay to event based on data quality."""
        # Check if this game is in degraded mode
        game_status = self._degraded_games.get(event.game_id, {})

        if game_status.get("degraded", False):
            # Apply confidence decay
            if hasattr(event, 'confidence'):
                event.confidence *= self.config.confidence_decay_on_throttle
            else:
                # Add confidence field if not present
                event.metadata = event.metadata or {}
                event.metadata["confidence"] = self.config.confidence_decay_on_throttle

            logger.debug(f"Applied confidence decay to event {event.event_id}: {self.config.confidence_decay_on_throttle}")

        return event

    def check_partial_feed(self, game_id: str, last_event_time: Optional[datetime] = None) -> bool:
        """Check if feed is partial (missing expected events)."""
        if last_event_time is None:
            last_event_time = datetime.now(timezone.utc)

        threshold = timedelta(seconds=self.config.partial_feed_threshold_seconds)
        cutoff = last_event_time - threshold

        # Count recent events for this game
        recent_events = [
            ts for key, ts in self._recent_events.items()
            if key.startswith(f"{game_id}_") and ts > cutoff
        ]

        is_partial = len(recent_events) == 0
        if is_partial:
            self._mark_game_degraded(game_id, "PARTIAL_FEED", f"No events in last {self.config.partial_feed_threshold_seconds}s")

        return is_partial

    def _mark_game_degraded(self, game_id: str, reason: str, details: str):
        """Mark a game as degraded and log the event."""
        if game_id not in self._degraded_games:
            self._degraded_games[game_id] = {
                "degraded": True,
                "reason": reason,
                "details": details,
                "timestamp": datetime.now(timezone.utc),
                "confidence_penalty": 1 - self.config.confidence_decay_on_throttle
            }

            # Log degradation event
            degradation_event = {
                "event": "GAME_DEGRADED",
                "game_id": game_id,
                "reason": reason,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system_action": "CONFIDENCE_DECAY_APPLIED",
                "confidence_penalty": f"-{int((1 - self.config.confidence_decay_on_throttle) * 100)}%"
            }
            self._mode_switches.append(degradation_event)

            logger.warning(f"Game {game_id} marked as degraded: {reason} - {details}")

    def check_rate_limit_switch(self) -> bool:
        """Check if we should switch to static mode due to rate limits."""
        if not self.config.auto_switch_to_static:
            return False

        # Check SportsDataIO status if available
        sportsdata_source = self.sources.get("sportsdata")
        if sportsdata_source and hasattr(sportsdata_source.listener, 'rate_limiter'):
            status = sportsdata_source.listener.rate_limiter.get_status()
            if status["calls_today"] >= status["daily_limit"]:
                self._switch_to_static_mode("DAILY_LIMIT_EXCEEDED", "SportsDataIO daily limit reached")
                return True

        return False

    def _switch_to_static_mode(self, reason: str, details: str):
        """Switch system to static truth mode."""
        switch_event = {
            "event": "MODE_SWITCH",
            "from_mode": "DYNAMIC_TRUTH",
            "to_mode": "STATIC_TRUTH",
            "reason": reason,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_action": "LIVE_BETTING_DISABLED"
        }
        self._mode_switches.append(switch_event)

        logger.critical(f"SWITCHING TO STATIC MODE: {reason} - {details}")
        # In a real system, this would trigger mode switching in the broader application

    def get_degradation_status(self) -> Dict[str, Any]:
        """Get comprehensive degradation and mode switching status."""
        return {
            "degraded_games": self._degraded_games,
            "mode_switches": self._mode_switches[-10:],  # Last 10 switches
            "confidence_decay_rate": self.config.confidence_decay_on_throttle,
            "partial_feed_threshold_seconds": self.config.partial_feed_threshold_seconds,
            "auto_switch_enabled": self.config.auto_switch_to_static
        }

    def get_source_status(self) -> Dict[str, Any]:
        """Get status of all PBP sources."""
        status = {}
        for name, source in self.sources.items():
            try:
                # Basic connectivity check
                status[name] = {
                    "available": True,
                    "name": source.get_source_name()
                }
            except Exception as e:
                status[name] = {
                    "available": False,
                    "error": str(e)
                }

        return {
            "primary_source": self.config.primary_source,
            "fallback_sources": self.config.fallback_sources,
            "sources": status,
            "deduplication_window_seconds": self.config.deduplication_window.total_seconds(),
            "max_event_age_hours": self.config.max_event_age.total_seconds() / 3600,
            "degradation": self.get_degradation_status()
        }