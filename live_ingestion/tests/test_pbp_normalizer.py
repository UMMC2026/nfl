"""
Tests for PBP Normalizer - Validates event normalization and source handling
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from live_ingestion.pbp_schema import PBPEvent, PBPEventType, PBPGame
from live_ingestion.pbp_normalizer import PBPNormalizer, PBPNormalizerConfig, ESPNPBPSource
from live_ingestion.espn_pbp_listener import ESPNPBPListener


class TestPBPNormalizer:
    """Test PBP normalization functionality."""

    @pytest.fixture
    def normalizer(self):
        """Create normalizer with test config."""
        config = PBPNormalizerConfig(validation_enabled=True)
        return PBPNormalizer(config)

    @pytest.fixture
    def mock_espn_data(self) -> Dict[str, Any]:
        """Mock ESPN PBP API response."""
        return {
            "plays": [
                {
                    "id": "401468656001",
                    "timestamp": "2024-01-15T19:30:00Z",
                    "period": {"number": 1},
                    "clock": {"displayValue": "11:45"},
                    "type": {"id": "2", "text": "Made Shot"},
                    "text": "LeBron James makes 2-pt jump shot",
                    "team": {"id": "1610612747"},
                    "participants": [
                        {"athlete": {"id": "2544", "displayName": "LeBron James"}}
                    ],
                    "scoringPlay": True,
                    "scoreValue": 2
                },
                {
                    "id": "401468656002",
                    "timestamp": "2024-01-15T19:31:00Z",
                    "period": {"number": 1},
                    "clock": {"displayValue": "11:30"},
                    "type": {"id": "4", "text": "Foul"},
                    "text": "Anthony Davis shooting foul (Drew Crawford)",
                    "team": {"id": "1610612747"},
                    "participants": [
                        {"athlete": {"id": "203076", "displayName": "Anthony Davis"}}
                    ],
                    "scoringPlay": False,
                    "scoreValue": 0
                },
                {
                    "id": "401468656003",
                    "timestamp": "2024-01-15T19:32:00Z",
                    "period": {"number": 1},
                    "clock": {"displayValue": "11:15"},
                    "type": {"id": "8", "text": "Substitution"},
                    "text": "Austin Reaves enters the game for LeBron James",
                    "team": {"id": "1610612747"},
                    "participants": [
                        {"athlete": {"id": "1630559", "displayName": "Austin Reaves"}},
                        {"athlete": {"id": "2544", "displayName": "LeBron James"}}
                    ],
                    "scoringPlay": False,
                    "scoreValue": 0
                }
            ]
        }

    def test_normalizer_initialization(self, normalizer):
        """Test normalizer initializes with correct sources."""
        assert "espn" in normalizer.sources
        assert "nba_api" in normalizer.sources
        assert "boxscore" in normalizer.sources

        status = normalizer.get_source_status()
        assert status["primary_source"] == "espn"
        assert "espn" in status["sources"]

    @patch.object(ESPNPBPSource, 'get_game_pbp')
    def test_get_game_pbp_success(self, mock_get_pbp, normalizer, mock_espn_data):
        """Test successful PBP fetching and normalization."""
        # Create expected events with recent timestamp
        events = [
            PBPEvent(
                event_id="espn_401468656001",
                game_id="401468656",
                source="espn",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),  # Recent event
                quarter=1,
                clock_seconds=705,  # 11:45 = 11*60 + 45
                event_type=PBPEventType.SHOT_MADE,
                player_id="2544",
                team_id="1610612747",
                metadata={"scoring_play": True}
            )
        ]

        # Create mock game with events
        mock_game = PBPGame(game_id="401468656")
        for event in events:
            mock_game.add_event(event)

        mock_get_pbp.return_value = mock_game

        result = normalizer.get_game_pbp("401468656")

        assert result is not None
        assert result.game_id == "401468656"
        assert len(result.events) == 1
        assert result.events[0].event_type == PBPEventType.SHOT_MADE

    def test_event_validation(self, normalizer):
        """Test event validation logic."""
        # Valid event
        valid_event = PBPEvent(
            event_id="test_123",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc),
            quarter=2,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747"
        )

        assert normalizer._validate_event(valid_event)

        # Invalid event - future timestamp
        future_event = PBPEvent(
            event_id="test_future",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
            quarter=2,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747"
        )

        assert not normalizer._validate_event(future_event)

    def test_event_normalization(self, normalizer):
        """Test event normalization."""
        # Create event bypassing validation (since we want to test normalization of invalid values)
        raw_event = PBPEvent.__new__(PBPEvent)
        raw_event.event_id = "123"
        raw_event.game_id = "401468656"
        raw_event.source = "espn"
        raw_event.timestamp = datetime(2024, 1, 15, 19, 30, 0)  # No timezone
        raw_event.quarter = 1
        raw_event.clock_seconds = 750  # Over 720
        raw_event.event_type = PBPEventType.SHOT_MADE
        raw_event.player_id = "2544"
        raw_event.team_id = "1610612747"
        raw_event.metadata = {}

        normalized = normalizer._normalize_event(raw_event)

        assert normalized is not None
        assert normalized.event_id == "espn_123"
        assert normalized.timestamp.tzinfo is not None  # Should have timezone
        assert normalized.clock_seconds == 720  # Capped at max

    def test_deduplication(self, normalizer):
        """Test event deduplication."""
        event1 = PBPEvent(
            event_id="test_1",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc),
            quarter=1,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747"
        )

        # First event should not be duplicate
        assert not normalizer._is_duplicate(event1)

        # Mark as processed
        normalizer._mark_event(event1)

        # Same event should be duplicate
        event2 = event1  # Same event
        assert normalizer._is_duplicate(event2)

    def test_source_failover(self, normalizer):
        """Test source failover when primary fails."""
        # Mock primary source failure
        with patch.object(normalizer.sources["espn"], 'get_game_pbp', return_value=None):
            # Mock fallback success
            mock_fallback_game = PBPGame(game_id="401468656")
            with patch.object(normalizer.sources["nba_api"], 'get_game_pbp', return_value=mock_fallback_game):
                result = normalizer.get_game_pbp("401468656")

                # Should get result from fallback
                assert result is not None
                assert result.game_id == "401468656"