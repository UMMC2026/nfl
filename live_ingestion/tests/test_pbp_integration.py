"""
Integration tests for PBP ingestion pipeline.

Tests end-to-end scenarios like "Substitution → Minutes Update".
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

from live_ingestion.pbp_schema import PBPEvent, PBPEventType
from live_ingestion.pbp_normalizer import PBPNormalizer


class TestPBPIntegration:
    """Integration tests for PBP pipeline."""

    @pytest.fixture
    def normalizer(self):
        """Create normalizer for testing."""
        return PBPNormalizer()

    def test_substitution_event_creation(self, normalizer):
        """Test that substitution events are properly normalized."""
        # Mock ESPN play data for substitution
        play_data = {
            "id": "401468656123",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period": {"number": 2},
            "clock": {"displayValue": "8:30"},
            "type": {"id": "8", "text": "Substitution"},
            "text": "Austin Reaves enters the game for LeBron James",
            "team": {"id": "1610612747"},
            "participants": [
                {"athlete": {"id": "1630559", "displayName": "Austin Reaves"}},  # Entering
                {"athlete": {"id": "2544", "displayName": "LeBron James"}}       # Exiting
            ],
            "scoringPlay": False,
            "scoreValue": 0
        }

        # Test the classification logic
        event_type, player_id, team_id, metadata = normalizer.sources["espn"].listener._classify_play(play_data)

        assert event_type == PBPEventType.SUBSTITUTION_IN
        assert player_id == "1630559"  # Austin Reaves entering
        assert team_id == "1610612747"
        assert metadata["espn_play_text"] == play_data["text"]

    def test_foul_event_creation(self, normalizer):
        """Test that foul events are properly normalized."""
        play_data = {
            "id": "401468656124",
            "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            "period": {"number": 3},
            "clock": {"displayValue": "5:45"},
            "type": {"id": "4", "text": "Foul"},
            "text": "Anthony Davis shooting foul (Drew Crawford)",
            "team": {"id": "1610612747"},
            "participants": [
                {"athlete": {"id": "203076", "displayName": "Anthony Davis"}}
            ],
            "scoringPlay": False,
            "scoreValue": 0
        }

        event_type, player_id, team_id, metadata = normalizer.sources["espn"].listener._classify_play(play_data)

        assert event_type == PBPEventType.FOUL
        assert player_id == "203076"  # Anthony Davis
        assert team_id == "1610612747"

    def test_shot_event_creation(self, normalizer):
        """Test that shot events are properly classified."""
        # Made shot
        made_shot_data = {
            "id": "401468656125",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period": {"number": 1},
            "clock": {"displayValue": "10:15"},
            "type": {"id": "2", "text": "Made Shot"},
            "text": "LeBron James makes 3-pt jump shot",
            "team": {"id": "1610612747"},
            "participants": [
                {"athlete": {"id": "2544", "displayName": "LeBron James"}}
            ],
            "scoringPlay": True,
            "scoreValue": 3
        }

        event_type, player_id, team_id, metadata = normalizer.sources["espn"].listener._classify_play(made_shot_data)

        assert event_type == PBPEventType.SHOT_MADE
        assert player_id == "2544"
        assert metadata["score_value"] == 3

    def test_event_stream_deduplication(self, normalizer):
        """Test that duplicate events are properly deduplicated."""
        event = PBPEvent(
            event_id="test_123",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc),
            quarter=1,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747"
        )

        # First occurrence should not be duplicate
        assert not normalizer._is_duplicate(event)

        # Mark as processed
        normalizer._mark_event(event)

        # Second occurrence should be duplicate
        assert normalizer._is_duplicate(event)

        # Different event (different player) should not be duplicate
        different_event = PBPEvent(
            event_id="test_124",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc),
            quarter=1,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="203076",  # Different player (Anthony Davis)
            team_id="1610612747"
        )

        assert not normalizer._is_duplicate(different_event)

    def test_source_failover_integration(self, normalizer):
        """Test that source failover works in integration."""
        # Mock primary source failure
        with patch.object(normalizer.sources["espn"], 'get_game_pbp', return_value=None):
            # Mock fallback success
            mock_game = Mock()
            mock_game.game_id = "401468656"
            mock_game.events = []

            with patch.object(normalizer.sources["nba_api"], 'get_game_pbp', return_value=mock_game):
                result = normalizer.get_game_pbp("401468656")

                assert result is not None
                assert result.game_id == "401468656"

    def test_event_age_validation(self, normalizer):
        """Test that events are validated for age."""
        # Recent event should pass
        recent_event = PBPEvent(
            event_id="recent",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=30),
            quarter=1,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747"
        )

        assert normalizer._validate_event(recent_event)

        # Old event should fail
        old_event = PBPEvent(
            event_id="old",
            game_id="401468656",
            source="espn",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=12),  # Too old
            quarter=1,
            clock_seconds=600,
            event_type=PBPEventType.FOUL,
            player_id="2544",
            team_id="1610612747"
        )

        assert not normalizer._validate_event(old_event)