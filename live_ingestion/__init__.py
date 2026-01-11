"""
Live Play-by-Play Ingestion Package

Converts real-time game events into structured evidence for the Truth Engine.
"""

from .pbp_schema import PBPEvent, PBPEventType, PBPGame
from .espn_pbp_listener import ESPNPBPListener, ESPNPBPConfig
from .sportsdata_pbp_listener import (
    SportsDataIOPBPListener,
    SportsDataIOConfig,
    SportsDataIOPBPSource,
    RateLimiter,
    CircuitBreaker
)
from .pbp_sources import PBPSource
from .pbp_normalizer import PBPNormalizer, PBPNormalizerConfig

__all__ = [
    # Schema
    "PBPEvent",
    "PBPEventType",
    "PBPGame",

    # ESPN Listener
    "ESPNPBPListener",
    "ESPNPBPConfig",

    # SportsDataIO Listener (Rate-Limited)
    "SportsDataIOPBPListener",
    "SportsDataIOConfig",
    "SportsDataIOPBPSource",
    "RateLimiter",
    "CircuitBreaker",

    # Normalizer
    "PBPNormalizer",
    "PBPNormalizerConfig",
    "PBPSource",
]