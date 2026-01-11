"""
PBP Source abstractions - shared base classes for all PBP data sources.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Optional
from .pbp_schema import PBPGame


class PBPSource(ABC):
    """Abstract base class for PBP data sources."""

    @abstractmethod
    def get_game_pbp(self, game_id: str) -> Optional[PBPGame]:
        """Fetch complete PBP for a game."""
        pass

    @abstractmethod
    def stream_live_events(self, game_id: str) -> Iterator[PBPGame.events]:
        """Stream live events for a game."""
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Return source identifier."""
        pass