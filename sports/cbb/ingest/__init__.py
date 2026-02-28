"""
CBB Data Ingestion Module

Sources:
- Primary: SportsReference / NCAA stats
- Secondary: ESPN team box scores

RULE: Only ingest FINAL games for learning.
"""
from .game_stats import ingest_game_stats
from .player_stats import ingest_player_stats
from .schedule import fetch_schedule

__all__ = ["ingest_game_stats", "ingest_player_stats", "fetch_schedule"]
