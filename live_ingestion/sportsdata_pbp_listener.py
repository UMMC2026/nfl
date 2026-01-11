"""
SportsDataIO PBP Source - Rate-limited, degradation-aware integration

Implements the free-tier rate-limit & degradation rules for SportsDataIO.
Provides dual-provider failover with ESPN as backup.
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Iterator
from datetime import datetime, timedelta, timezone
import requests
import json

from .pbp_schema import PBPEvent, PBPEventType, PBPGame
from .pbp_sources import PBPSource

logger = logging.getLogger(__name__)


@dataclass
class SportsDataIOConfig:
    """Configuration for SportsDataIO integration."""
    api_key: str
    base_url: str = "https://api.sportsdata.io/v2/json"
    daily_limit: int = 1000  # Conservative free tier assumption
    burst_limit: int = 10    # Calls per minute
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0


class RateLimiter:
    """Centralized rate controller for SportsDataIO."""

    def __init__(self, daily_limit: int, burst_limit: int):
        self.daily_limit = daily_limit
        self.burst_limit = burst_limit
        self.calls_today = 0
        self.calls_last_minute: List[float] = []
        self.last_reset = datetime.now(timezone.utc).date()

    def _reset_if_new_day(self):
        """Reset daily counter if it's a new day."""
        today = datetime.now(timezone.utc).date()
        if today != self.last_reset:
            self.calls_today = 0
            self.last_reset = today

    def _cleanup_old_calls(self):
        """Remove calls older than 1 minute."""
        cutoff = time.time() - 60
        self.calls_last_minute = [t for t in self.calls_last_minute if t > cutoff]

    def allow_call(self) -> tuple[bool, Optional[str]]:
        """Check if a call is allowed under rate limits."""
        self._reset_if_new_day()
        self._cleanup_old_calls()

        if self.calls_today >= self.daily_limit:
            return False, "DAILY_LIMIT_EXCEEDED"

        if len(self.calls_last_minute) >= self.burst_limit:
            return False, "BURST_LIMIT_EXCEEDED"

        return True, None

    def record_call(self):
        """Record a successful API call."""
        self.calls_today += 1
        self.calls_last_minute.append(time.time())

    def get_status(self) -> Dict[str, Any]:
        """Get current rate limit status."""
        return {
            "calls_today": self.calls_today,
            "daily_limit": self.daily_limit,
            "calls_last_minute": len(self.calls_last_minute),
            "burst_limit": self.burst_limit,
            "daily_remaining": max(0, self.daily_limit - self.calls_today),
            "burst_remaining": max(0, self.burst_limit - len(self.calls_last_minute))
        }


class CircuitBreaker:
    """Circuit breaker for API failure handling."""

    def __init__(self, failure_threshold: int = 3, timeout_minutes: int = 15):
        self.failure_threshold = failure_threshold
        self.timeout_minutes = timeout_minutes
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        """Record a successful call."""
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")

    def allow_call(self) -> bool:
        """Check if calls are allowed."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = datetime.now(timezone.utc) - self.last_failure_time
                if elapsed > timedelta(minutes=self.timeout_minutes):
                    self.state = "HALF_OPEN"
                    logger.info("Circuit breaker HALF_OPEN - testing connection")
                    return True
            return False

        # HALF_OPEN - allow one test call
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class SportsDataIOPBPListener:
    """SportsDataIO PBP listener with rate limiting and degradation."""

    def __init__(self, config: SportsDataIOConfig):
        self.config = config
        self.rate_limiter = RateLimiter(config.daily_limit, config.burst_limit)
        self.circuit_breaker = CircuitBreaker()
        self.session = requests.Session()
        self.session.headers.update({
            'Ocp-Apim-Subscription-Key': config.api_key,
            'Content-Type': 'application/json'
        })

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Make a rate-limited API request with circuit breaker."""
        # Check circuit breaker
        if not self.circuit_breaker.allow_call():
            logger.warning("Circuit breaker preventing API call")
            return None

        # Check rate limits
        allowed, reason = self.rate_limiter.allow_call()
        if not allowed:
            logger.warning(f"Rate limit exceeded: {reason}")
            return None

        url = f"{self.config.base_url}/{endpoint}"

        for attempt in range(self.config.retry_attempts):
            try:
                response = self.session.get(url, params=params, timeout=self.config.request_timeout)

                if response.status_code == 200:
                    self.rate_limiter.record_call()
                    self.circuit_breaker.record_success()
                    return response.json()

                elif response.status_code == 429:
                    logger.warning("Rate limit hit (HTTP 429)")
                    self.rate_limiter.record_call()  # Still counts as a call
                    return None

                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    if attempt == self.config.retry_attempts - 1:
                        self.circuit_breaker.record_failure()
                        return None

            except requests.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt == self.config.retry_attempts - 1:
                    self.circuit_breaker.record_failure()
                    return None

            # Exponential backoff
            time.sleep(self.config.retry_delay * (2 ** attempt))

        return None

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        """Fetch complete PBP for a game."""
        data = self._make_request(f"GamesBySeason/{datetime.now().year}")

        if not data:
            return None

        # Find the specific game
        game_data = None
        for game in data:
            if str(game.get('GameID')) == game_id:
                game_data = game
                break

        if not game_data:
            logger.warning(f"Game {game_id} not found")
            return None

        # Get play-by-play data
        pbp_data = self._make_request(f"PlayByPlay/{game_id}")

        if not pbp_data:
            return None

        # Convert to PBPGame
        events = []
        for play in pbp_data:
            event = self._parse_play(play)
            if event:
                events.append(event)

        return PBPGame(
            game_id=game_id,
            events=sorted(events, key=lambda e: e.timestamp)
        )

    def stream_live_events(self, game_id: str) -> Iterator[PBPEvent]:
        """Stream live events (polling-based for free tier)."""
        last_update = None

        while True:
            # Check if we can make calls
            if not self.circuit_breaker.allow_call():
                logger.info("Circuit breaker open - pausing live streaming")
                time.sleep(60)  # Wait before checking again
                continue

            allowed, reason = self.rate_limiter.allow_call()
            if not allowed:
                if reason == "DAILY_LIMIT_EXCEEDED":
                    logger.warning("Daily limit exceeded - switching to static mode")
                    break
                else:
                    logger.info(f"Burst limit hit - waiting")
                    time.sleep(60)
                    continue

            # Fetch latest data
            pbp_data = self._make_request(f"PlayByPlay/{game_id}")

            if pbp_data:
                new_events = []
                for play in pbp_data:
                    # Only process events newer than last update
                    play_time = datetime.fromisoformat(play['TimeOfPossession'].replace('Z', '+00:00'))
                    if last_update is None or play_time > last_update:
                        event = self._parse_play(play)
                        if event:
                            new_events.append(event)

                # Yield new events
                for event in sorted(new_events, key=lambda e: e.timestamp):
                    yield event

                # Update last update time
                if pbp_data:
                    last_update = max(
                        datetime.fromisoformat(play['TimeOfPossession'].replace('Z', '+00:00'))
                        for play in pbp_data
                    )

            # Poll every 30 seconds (free tier friendly)
            time.sleep(30)

    def _parse_play(self, play: Dict[str, Any]) -> Optional[PBPEvent]:
        """Parse SportsDataIO play data into PBPEvent."""
        try:
            event_type, player_id, team_id, metadata = self._classify_play(play)

            if not event_type:
                return None

            # Parse timestamp
            timestamp = datetime.fromisoformat(play['TimeOfPossession'].replace('Z', '+00:00'))

            # Calculate quarter and clock
            quarter = play.get('Quarter', 1)
            clock_seconds = self._parse_clock(play.get('TimeRemaining', '12:00'))

            return PBPEvent(
                event_id=f"sportsdata_{play['PlayID']}",
                game_id=str(play['GameID']),
                source="sportsdata",
                timestamp=timestamp,
                quarter=quarter,
                clock_seconds=clock_seconds,
                event_type=event_type,
                player_id=player_id,
                team_id=str(team_id) if team_id else None,
                metadata=metadata
            )

        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse play {play.get('PlayID', 'unknown')}: {e}")
            return None

    def _classify_play(self, play: Dict[str, Any]) -> tuple[Optional[PBPEventType], Optional[str], Optional[int], Dict[str, Any]]:
        """Classify play type and extract relevant data."""
        description = play.get('Description', '').lower()

        # Substitution
        if 'substitution' in description or 'enters' in description:
            player_id = str(play.get('PlayerID')) if play.get('PlayerID') else None
            team_id = play.get('TeamID')
            return PBPEventType.SUBSTITUTION_IN, player_id, team_id, {"sportsdata_description": play.get('Description')}

        # Foul
        elif 'foul' in description:
            player_id = str(play.get('PlayerID')) if play.get('PlayerID') else None
            team_id = play.get('TeamID')
            return PBPEventType.FOUL, player_id, team_id, {"sportsdata_description": play.get('Description')}

        # Shot made
        elif any(word in description for word in ['makes', 'scores']):
            player_id = str(play.get('PlayerID')) if play.get('PlayerID') else None
            team_id = play.get('TeamID')
            # Check for 3-point shots
            points = 3 if any(three_ind in description for three_ind in ['three', '3-pt', '3pt']) else 2
            return PBPEventType.SHOT_MADE, player_id, team_id, {
                "sportsdata_description": play.get('Description'),
                "score_value": points
            }

        # Shot missed
        elif 'misses' in description:
            player_id = str(play.get('PlayerID')) if play.get('PlayerID') else None
            team_id = play.get('TeamID')
            return PBPEventType.SHOT_MISSED, player_id, team_id, {"sportsdata_description": play.get('Description')}

        # Timeout
        elif 'timeout' in description:
            team_id = play.get('TeamID')
            return PBPEventType.TIMEOUT, None, team_id, {"sportsdata_description": play.get('Description')}

        # Quarter start/end
        elif any(word in description for word in ['quarter', 'period', 'half']):
            return PBPEventType.QUARTER_START if 'start' in description else PBPEventType.QUARTER_END, None, None, {"sportsdata_description": play.get('Description')}

        return None, None, None, {}

    def _parse_clock(self, clock_str: str) -> int:
        """Parse clock string (MM:SS) to seconds."""
        try:
            minutes, seconds = map(int, clock_str.split(':'))
            return minutes * 60 + seconds
        except (ValueError, AttributeError):
            return 720  # Default 12:00

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status."""
        return {
            "provider": "SportsDataIO",
            "rate_limiter": self.rate_limiter.get_status(),
            "circuit_breaker": self.circuit_breaker.get_status(),
            "config": {
                "daily_limit": self.config.daily_limit,
                "burst_limit": self.config.burst_limit,
                "timeout": self.config.request_timeout
            }
        }


class SportsDataIOPBPSource(PBPSource):
    """SportsDataIO PBP source wrapper."""

    def __init__(self, config: SportsDataIOConfig):
        self.listener = SportsDataIOPBPListener(config)

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        return self.listener.get_game_pbp(game_id)

    def stream_live_events(self, game_id: str) -> Iterator[PBPEvent]:
        return self.listener.stream_live_events(game_id)

    def get_source_name(self) -> str:
        return "sportsdata"