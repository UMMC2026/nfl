"""
ESPN PBP Listener - Fetches live play-by-play data from ESPN's public APIs

Converts ESPN's format to canonical PBPEvent schema.
Handles rate limiting, error recovery, and data validation.
"""

import json
import ssl
import time
import urllib.request
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Iterator
from datetime import datetime, timedelta
import logging

from .pbp_schema import PBPEvent, PBPEventType, PBPGame

logger = logging.getLogger(__name__)

# SSL context for compatibility
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


@dataclass
class ESPNPBPConfig:
    """Configuration for ESPN PBP fetching."""
    base_url: str = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
    request_timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class ESPNPBPListener:
    """
    Fetches and normalizes live PBP data from ESPN.

    Converts ESPN's play-by-play format to canonical PBPEvent objects.
    """

    def __init__(self, config: Optional[ESPNPBPConfig] = None):
        self.config = config or ESPNPBPConfig()
        self._last_request_time = 0
        self._rate_limit_delay = 1.0  # Minimum delay between requests

    def _fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from ESPN API with error handling."""
        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)

        for attempt in range(self.config.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": self.config.user_agent}
                )

                with urllib.request.urlopen(
                    req,
                    context=_ssl_ctx,
                    timeout=self.config.request_timeout
                ) as resp:
                    self._last_request_time = time.time()
                    return json.loads(resp.read())

            except Exception as e:
                logger.warning(f"ESPN API request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff

        return None

    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        """
        Fetch complete play-by-play for a game.

        Args:
            game_id: ESPN game ID (e.g., "401468656")

        Returns:
            PBPGame with all events, or None if fetch fails
        """
        url = f"{self.config.base_url}/playbyplay?event={game_id}"
        data = self._fetch_json(url)

        if not data:
            return None

        game = PBPGame(game_id=game_id)
        events = self._parse_pbp_data(data, game_id)

        for event in events:
            game.add_event(event)

        return game

    def get_live_pbp_stream(self, game_id: str) -> Iterator[PBPEvent]:
        """
        Stream live PBP events for a game.

        Yields new events as they occur. Continues until game ends.
        """
        seen_event_ids = set()
        last_update = None

        while True:
            try:
                game = self.get_game_pbp(game_id)
                if not game:
                    logger.warning(f"Failed to fetch PBP for game {game_id}")
                    time.sleep(30)  # Wait before retry
                    continue

                # Get new events since last update
                new_events = []
                for event in game.events:
                    if event.event_id not in seen_event_ids:
                        new_events.append(event)
                        seen_event_ids.add(event.event_id)

                # Yield new events in chronological order
                for event in sorted(new_events, key=lambda e: e.timestamp):
                    yield event

                # Check if game is over
                if game.events and game.events[-1].event_type == PBPEventType.GAME_END:
                    logger.info(f"Game {game_id} ended, stopping stream")
                    break

                # Wait before next poll
                time.sleep(15)  # Poll every 15 seconds for live games

            except Exception as e:
                logger.error(f"Error in PBP stream for game {game_id}: {e}")
                time.sleep(30)

    def _parse_pbp_data(self, data: Dict[str, Any], game_id: str) -> List[PBPEvent]:
        """Parse ESPN PBP JSON into canonical PBPEvent objects."""
        events = []

        # ESPN structure: data["plays"] contains the play-by-play
        plays = data.get("plays", [])
        if not plays:
            logger.warning(f"No plays found in ESPN data for game {game_id}")
            return events

        for play in plays:
            try:
                event = self._parse_single_play(play, game_id)
                if event:
                    events.append(event)
            except Exception as e:
                logger.warning(f"Failed to parse play {play.get('id', 'unknown')}: {e}")
                continue

        return events

    def _parse_single_play(self, play: Dict[str, Any], game_id: str) -> Optional[PBPEvent]:
        """Parse a single ESPN play into a PBPEvent."""
        play_id = str(play.get("id", ""))
        if not play_id:
            return None

        # Extract timing information
        period = play.get("period", {}).get("number", 1)
        clock_str = play.get("clock", {}).get("displayValue", "12:00")

        # Parse clock (MM:SS format)
        try:
            minutes, seconds = map(int, clock_str.split(":"))
            clock_seconds = minutes * 60 + seconds
        except (ValueError, AttributeError):
            clock_seconds = 720  # Default to 12:00

        # Parse timestamp
        timestamp_str = play.get("timestamp", "")
        if timestamp_str:
            try:
                # ESPN timestamps are ISO format
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                timestamp = datetime.utcnow()
        else:
            timestamp = datetime.utcnow()

        # Determine event type and extract relevant data
        event_type, player_id, team_id, metadata = self._classify_play(play)

        if not event_type:
            return None  # Skip unrecognized plays

        return PBPEvent(
            event_id=f"espn_{play_id}",
            game_id=game_id,
            source="espn",
            timestamp=timestamp,
            quarter=period,
            clock_seconds=clock_seconds,
            event_type=event_type,
            player_id=player_id,
            team_id=team_id,
            metadata=metadata
        )

    def _classify_play(self, play: Dict[str, Any]) -> tuple[Optional[PBPEventType], Optional[str], str, Dict[str, Any]]:
        """
        Classify ESPN play type and extract relevant information.

        Returns:
            (event_type, player_id, team_id, metadata)
        """
        text = play.get("text", "").lower()
        type_text = play.get("type", {}).get("text", "").lower()

        # Extract team and player info
        team_id = play.get("team", {}).get("id", "")
        team_id = str(team_id) if team_id else ""

        participants = play.get("participants", [])
        player_id = None
        if participants:
            # Take first participant (usually the primary player)
            player = participants[0].get("athlete", {})
            player_id = str(player.get("id", "")) if player.get("id") else None

        metadata = {
            "espn_play_text": play.get("text", ""),
            "espn_type_text": type_text,
            "espn_play_type": play.get("type", {}).get("id", ""),
            "scoring_play": play.get("scoringPlay", False),
            "score_value": play.get("scoreValue", 0)
        }

        # Classification logic based on ESPN play types and text
        if "substitution" in type_text or "sub" in text:
            if "enters" in text or "in" in text:
                return PBPEventType.SUBSTITUTION_IN, player_id, team_id, metadata
            elif "exits" in text or "out" in text:
                return PBPEventType.SUBSTITUTION_OUT, player_id, team_id, metadata

        elif "foul" in type_text or "foul" in text:
            return PBPEventType.FOUL, player_id, team_id, metadata

        elif "turnover" in type_text or "turnover" in text:
            return PBPEventType.TURNOVER, player_id, team_id, metadata

        elif "shot" in type_text or any(word in text for word in ["makes", "misses", "shot"]):
            if "makes" in text or play.get("scoringPlay", False):
                return PBPEventType.SHOT_MADE, player_id, team_id, metadata
            else:
                return PBPEventType.SHOT_MISSED, player_id, team_id, metadata

        elif "rebound" in type_text or "rebound" in text:
            return PBPEventType.REBOUND, player_id, team_id, metadata

        elif "steal" in type_text or "steal" in text:
            return PBPEventType.STEAL, player_id, team_id, metadata

        elif "block" in type_text or "block" in text:
            return PBPEventType.BLOCK, player_id, team_id, metadata

        elif "timeout" in type_text or "timeout" in text:
            return PBPEventType.TIMEOUT, None, team_id, metadata

        elif "period" in type_text:
            if "start" in type_text or "begin" in text:
                return PBPEventType.PERIOD_START, None, "", metadata
            elif "end" in type_text or "final" in text:
                return PBPEventType.PERIOD_END, None, "", metadata

        # Skip unrecognized plays
        return None, None, "", metadata

    def get_game_status(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get current game status and basic info."""
        url = f"{self.config.base_url}/summary?event={game_id}"
        data = self._fetch_json(url)

        if not data:
            return None

        # Extract basic game info
        game_info = {
            "game_id": game_id,
            "status": data.get("status", {}).get("type", {}).get("name", "unknown"),
            "period": data.get("status", {}).get("period", 0),
            "clock": data.get("status", {}).get("displayClock", ""),
            "home_team": data.get("header", {}).get("competitions", [{}])[0].get("competitors", [{}, {}])[0].get("team", {}).get("abbreviation", ""),
            "away_team": data.get("header", {}).get("competitions", [{}])[0].get("competitors", [{}, {}])[1].get("team", {}).get("abbreviation", ""),
            "home_score": data.get("header", {}).get("competitions", [{}])[0].get("competitors", [{}, {}])[0].get("score", ""),
            "away_score": data.get("header", {}).get("competitions", [{}])[0].get("competitors", [{}, {}])[1].get("score", ""),
        }

        return game_info