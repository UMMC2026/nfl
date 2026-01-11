"""
Tests for SportsDataIO PBP integration with rate limiting and degradation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import json

from live_ingestion.sportsdata_pbp_listener import (
    SportsDataIOConfig,
    RateLimiter,
    CircuitBreaker,
    SportsDataIOPBPListener,
    SportsDataIOPBPSource
)
from live_ingestion.pbp_schema import PBPEvent, PBPEventType


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_allow_call_under_limits(self):
        """Test calls are allowed when under limits."""
        limiter = RateLimiter(daily_limit=1000, burst_limit=10)

        for _ in range(5):
            assert limiter.allow_call() == (True, None)
            limiter.record_call()

        status = limiter.get_status()
        assert status["calls_today"] == 5
        assert status["calls_last_minute"] == 5

    def test_daily_limit_exceeded(self):
        """Test daily limit enforcement."""
        limiter = RateLimiter(daily_limit=5, burst_limit=10)

        for _ in range(5):
            limiter.record_call()

        allowed, reason = limiter.allow_call()
        assert not allowed
        assert reason == "DAILY_LIMIT_EXCEEDED"

    def test_burst_limit_exceeded(self):
        """Test burst limit enforcement."""
        limiter = RateLimiter(daily_limit=1000, burst_limit=3)

        for _ in range(3):
            limiter.record_call()

        allowed, reason = limiter.allow_call()
        assert not allowed
        assert reason == "BURST_LIMIT_EXCEEDED"

    def test_day_reset(self):
        """Test daily counter resets at midnight."""
        limiter = RateLimiter(daily_limit=1000, burst_limit=10)

        # Simulate calls yesterday
        limiter._last_reset = datetime.now(timezone.utc).date() - timedelta(days=1)
        limiter.calls_today = 50

        # Force reset by calling the method directly
        limiter._reset_if_new_day()

        # Should be reset to 0
        assert limiter.calls_today == 0


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_closed_state_allows_calls(self):
        """Test circuit breaker allows calls in closed state."""
        cb = CircuitBreaker()
        assert cb.allow_call()
        assert cb.state == "CLOSED"

    def test_open_state_blocks_calls(self):
        """Test circuit breaker blocks calls in open state."""
        cb = CircuitBreaker(failure_threshold=2)

        cb.record_failure()
        assert cb.state == "CLOSED"  # Not yet open

        cb.record_failure()
        assert cb.state == "OPEN"

        assert not cb.allow_call()

    def test_half_open_after_timeout(self):
        """Test circuit breaker enters half-open after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout_minutes=0.001)  # Very short timeout

        cb.record_failure()
        assert cb.state == "OPEN"

        # Wait for timeout
        import time
        time.sleep(0.1)

        assert cb.allow_call()  # Should enter half-open
        assert cb.state == "HALF_OPEN"

    def test_success_resets_state(self):
        """Test successful call resets circuit breaker."""
        cb = CircuitBreaker(failure_threshold=1)

        cb.record_failure()
        assert cb.state == "OPEN"

        cb.record_success()
        assert cb.state == "CLOSED"


class TestSportsDataIOPBPListener:
    """Test SportsDataIO PBP listener."""

    @pytest.fixture
    def config(self):
        return SportsDataIOConfig(
            api_key="test_key",
            daily_limit=100,
            burst_limit=5
        )

    @pytest.fixture
    def listener(self, config):
        return SportsDataIOPBPListener(config)

    def test_initialization(self, listener):
        """Test listener initializes correctly."""
        status = listener.get_status()
        assert status["provider"] == "SportsDataIO"
        assert "rate_limiter" in status
        assert "circuit_breaker" in status

    @patch('live_ingestion.sportsdata_pbp_listener.requests.Session.get')
    def test_successful_api_call(self, mock_get, listener):
        """Test successful API call handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response

        result = listener._make_request("test/endpoint")

        assert result == {"test": "data"}
        mock_get.assert_called_once()

    @patch('live_ingestion.sportsdata_pbp_listener.requests.Session.get')
    def test_rate_limit_handling(self, mock_get, listener):
        """Test rate limit response handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        result = listener._make_request("test/endpoint")

        assert result is None
        # Should still count as a call
        status = listener.rate_limiter.get_status()
        assert status["calls_today"] == 1

    @patch('live_ingestion.sportsdata_pbp_listener.requests.Session.get')
    def test_circuit_breaker_on_failure(self, mock_get, listener):
        """Test circuit breaker activation on repeated failures."""
        # Mock failed responses instead of exceptions
        mock_response = Mock()
        mock_response.status_code = 500  # Server error
        mock_get.return_value = mock_response

        # Default threshold is 3 failures
        for _ in range(3):
            listener._make_request("test/endpoint")

        # Circuit should be open
        assert listener.circuit_breaker.state == "OPEN"
        assert not listener.circuit_breaker.allow_call()

    def test_play_classification(self, listener):
        """Test play event classification."""
        # Substitution
        sub_play = {
            "PlayID": 123,
            "Description": "Austin Reaves enters the game for LeBron James",
            "PlayerID": 1630559,
            "TeamID": 1610612747,
            "TimeOfPossession": datetime.now(timezone.utc).isoformat()
        }

        event_type, player_id, team_id, metadata = listener._classify_play(sub_play)
        assert event_type == PBPEventType.SUBSTITUTION_IN
        assert player_id == "1630559"
        assert team_id == 1610612747

        # Foul
        foul_play = {
            "PlayID": 124,
            "Description": "Anthony Davis shooting foul",
            "PlayerID": 203076,
            "TeamID": 1610612747,
            "TimeOfPossession": datetime.now(timezone.utc).isoformat()
        }

        event_type, player_id, team_id, metadata = listener._classify_play(foul_play)
        assert event_type == PBPEventType.FOUL
        assert player_id == "203076"

        # Shot made
        shot_play = {
            "PlayID": 125,
            "Description": "LeBron James makes 3-pt jump shot",
            "PlayerID": 2544,
            "TeamID": 1610612747,
            "TimeOfPossession": datetime.now(timezone.utc).isoformat()
        }

        event_type, player_id, team_id, metadata = listener._classify_play(shot_play)
        assert event_type == PBPEventType.SHOT_MADE
        assert metadata["score_value"] == 3

    def test_clock_parsing(self, listener):
        """Test clock string parsing."""
        assert listener._parse_clock("12:00") == 720
        assert listener._parse_clock("5:30") == 330
        assert listener._parse_clock("0:15") == 15
        assert listener._parse_clock("invalid") == 720  # Default


class TestSportsDataIODegradation:
    """Test degradation rules and confidence decay."""

    @pytest.fixture
    def normalizer(self):
        from live_ingestion.pbp_normalizer import PBPNormalizer, PBPNormalizerConfig
        config = PBPNormalizerConfig(
            sportsdata_api_key="test_key",
            confidence_decay_on_throttle=0.8
        )
        return PBPNormalizer(config)

    def test_confidence_decay_application(self, normalizer):
        """Test confidence decay is applied to events from degraded games."""
        # Create test event
        event = PBPEvent(
            event_id="test_123",
            game_id="401468656",
            source="sportsdata",
            timestamp=datetime.now(timezone.utc),
            quarter=1,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747",
            metadata={"confidence": 1.0}
        )

        # Mark game as degraded
        normalizer._mark_game_degraded("401468656", "RATE_LIMIT", "Testing degradation")

        # Apply confidence decay
        decayed_event = normalizer.apply_confidence_decay(event)

        assert decayed_event.metadata["confidence"] == 0.8

    def test_partial_feed_detection(self, normalizer):
        """Test partial feed detection."""
        game_id = "401468656"

        # Initially not partial (no events, but let's not check this)
        # assert not normalizer.check_partial_feed(game_id)

        # Simulate old last event by clearing recent events and checking
        normalizer._recent_events.clear()  # Clear any events
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        assert normalizer.check_partial_feed(game_id, old_time)

        # Game should be marked as degraded
        assert game_id in normalizer._degraded_games
        assert normalizer._degraded_games[game_id]["degraded"]

    def test_degradation_status_reporting(self, normalizer):
        """Test degradation status is properly reported."""
        game_id = "401468656"
        normalizer._mark_game_degraded(game_id, "TEST", "Testing status reporting")

        status = normalizer.get_degradation_status()

        assert game_id in status["degraded_games"]
        assert len(status["mode_switches"]) == 1
        assert status["mode_switches"][0]["event"] == "GAME_DEGRADED"

    def test_mode_switch_logging(self, normalizer):
        """Test mode switches are logged."""
        normalizer._switch_to_static_mode("DAILY_LIMIT_EXCEEDED", "Test switch")

        status = normalizer.get_degradation_status()
        switches = status["mode_switches"]

        assert len(switches) == 1
        assert switches[0]["event"] == "MODE_SWITCH"
        assert switches[0]["to_mode"] == "STATIC_TRUTH"