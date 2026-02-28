"""Canonical schemas for external (book) props.

This module defines small, explicit data structures that sit *between*
external markets (e.g. Underdog) and the internal truth engine.

These are pre-truth: they describe *what the book is offering*, not
our probabilities, tiers, or governance state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class PayoutProfile:
    """Describes how a book pays out entries built from these props.

    This does *not* encode our opinion of EV; it only mirrors the
    product structure (flex vs power, min/max legs, etc.).  Detailed
    payout tables live in sport- or product-specific modules.
    """

    source: str = "UNDERDOG"          # e.g. "UNDERDOG", "PRIZEPICKS"
    product: str = "PICKEM"           # e.g. "PICKEM", "PICK6"
    format: str = "flex"              # "flex" or "power" (or vendor-specific)
    min_legs: int = 2
    max_legs: int = 6
    notes: str = ""                   # free-form description / version tag
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalProp:
    """Canonical representation of a *single* external prop line.

    This is the hand-off format that normalization/ingest layers
    should produce before the pick enters the truth engine.

    Required fields closely match how the rest of the system
    thinks about edges and picks, while remaining book-agnostic.
    """

    # Where this prop came from
    source: str                # e.g. "UNDERDOG"
    sport: str                 # e.g. "NBA", "TENNIS"

    # Entity and market
    player: str                # display name as used internally
    team: str                  # normalized team code (e.g. "HOU") or "UNK"
    opponent: str              # opponent team code or "UNK"
    market: str                # canonical stat/market key (e.g. "PTS", "3PM", "PRA")

    # Line as posted by the book
    line: float
    direction: str             # "higher" / "lower" (pre-normalized)

    # How the book will pay entries built from this prop
    payout_profile: PayoutProfile

    # Raw book payload for traceability / audit
    raw: Dict[str, Any] = field(default_factory=dict)

    # Optional hook for downstream correlation / slate grouping
    slate_id: Optional[str] = None
    book_prop_id: Optional[str] = None


__all__ = ["PayoutProfile", "ExternalProp"]
