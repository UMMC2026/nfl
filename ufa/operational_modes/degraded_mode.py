"""Degraded Data Operating Mode (SOP 2.2.1).

Central place to reason about whether the system is operating in a
"normal" or "degraded" data state and to expose simple hooks for
confidence caps, parlay eligibility and star-player filtering.

This module is intentionally lightweight for now: it focuses on the
injury feed health signal, which is currently the most fragile and
highest-impact dependency. Additional data sources (primary stats,
secondary verification, market feeds) can be wired into
``DataSourceStatus`` and ``DegradedModeManager`` over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional

from ufa.gates.injury_gate import get_injury_feed_health


class DegradedModeLevel(Enum):
    """Coarse-grained degraded mode level.

    Values are designed to map cleanly onto SOP 2.2.1:

    - NORMAL:   All critical feeds healthy.
    - LEVEL_1:  Single critical source degraded (e.g. injury feed).
    - LEVEL_2:  Multiple sources degraded (stats + injury, etc.).
    - LEVEL_3:  Critical failure / system halt.
    """

    NORMAL = "normal"
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"


@dataclass
class DataSourceStatus:
    """Status of a single data source (injury, stats, etc.)."""

    source_name: str
    is_healthy: bool
    last_success: datetime
    latency_seconds: float
    error_rate: float


class DegradedModeManager:
    """Manages degraded data operating mode per SOP 2.2.1.

    In this first implementation we primarily look at the injury feed
    health and treat any non-OK status as a LEVEL_1 degraded state.
    The class is structured so additional sources can be registered
    later without changing callers.
    """

    def __init__(self) -> None:
        self.current_level: DegradedModeLevel = DegradedModeLevel.NORMAL
        self.activated_at: Optional[datetime] = None
        self.source_statuses: Dict[str, DataSourceStatus] = {}

        self.thresholds = {
            "max_latency": timedelta(minutes=15),
            "max_outage": timedelta(minutes=5),
            "max_error_rate": 0.10,
        }

        # Confidence caps per level (used as *global* ceilings in
        # addition to any per-pick caps such as injury downgrades).
        self.confidence_caps: Dict[DegradedModeLevel, float] = {
            DegradedModeLevel.NORMAL: 1.0,
            DegradedModeLevel.LEVEL_1: 0.70,  # Injury feed only
            DegradedModeLevel.LEVEL_2: 0.60,  # Multiple sources
            DegradedModeLevel.LEVEL_3: 0.50,  # System halt / diagnostics only
        }

    # ------------------------------------------------------------------
    # Source registration / health assessment
    # ------------------------------------------------------------------

    def update_from_injury_feed(self) -> None:
        """Populate the injury_feed status from get_injury_feed_health()."""

        health = get_injury_feed_health()
        healthy = health in {"OK", "HEALTHY"}

        now = datetime.now(timezone.utc)
        self.source_statuses["injury_feed"] = DataSourceStatus(
            source_name="injury_feed",
            is_healthy=healthy,
            last_success=now if healthy else now - self.thresholds["max_outage"],
            latency_seconds=0.0,
            error_rate=0.0,
        )

    def _is_source_healthy(self, status: DataSourceStatus) -> bool:
        """Check if a data source meets basic health criteria."""

        # Latency / outage window
        if datetime.now(timezone.utc) - status.last_success > self.thresholds["max_latency"]:
            return False

        if status.error_rate > self.thresholds["max_error_rate"]:
            return False

        return status.is_healthy

    def assess_system_health(self) -> DegradedModeLevel:
        """Assess overall system health and return the degraded level."""

        unhealthy_sources = [
            name
            for name, status in self.source_statuses.items()
            if not self._is_source_healthy(status)
        ]

        if not unhealthy_sources:
            level = DegradedModeLevel.NORMAL
        elif len(unhealthy_sources) == 1:
            # For now any single unhealthy critical source → LEVEL_1.
            level = DegradedModeLevel.LEVEL_1
        elif len(unhealthy_sources) == 2:
            level = DegradedModeLevel.LEVEL_2
        else:
            level = DegradedModeLevel.LEVEL_3

        if level != self.current_level:
            self._transition_to_level(level)

        return self.current_level

    def _transition_to_level(self, new_level: DegradedModeLevel) -> None:
        self.current_level = new_level
        self.activated_at = datetime.now(timezone.utc) if new_level != DegradedModeLevel.NORMAL else None

    # ------------------------------------------------------------------
    # Public helpers used by callers
    # ------------------------------------------------------------------

    def apply_confidence_cap(self, raw_confidence: float) -> float:
        """Apply a *global* confidence cap for the current degraded level."""

        cap = self.confidence_caps.get(self.current_level, 1.0)
        return min(raw_confidence, cap)

    def is_parlay_allowed(self) -> bool:
        """Whether parlays are allowed in the current mode.

        As per SOP 2.2.1, any degraded mode level disables parlays.
        """

        return self.current_level == DegradedModeLevel.NORMAL

    def filter_star_players(self, plays: List[dict]) -> List[dict]:
        """Filter out star players in degraded mode per SOP.

        In NORMAL mode this is a no-op.
        """

        if self.current_level == DegradedModeLevel.NORMAL:
            return plays

        star_players = _load_star_player_list()
        return [p for p in plays if p.get("player") not in star_players]

    def get_operating_instructions(self) -> Dict[str, Optional[str]]:
        """Return a small status dict for dashboards/menus."""

        return {
            "current_level": self.current_level.value,
            "confidence_cap": f"{self.confidence_caps.get(self.current_level, 1.0):.2f}",
            "parlays_allowed": str(self.is_parlay_allowed()),
            "star_players_allowed": str(self.current_level == DegradedModeLevel.NORMAL),
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
        }


def _load_star_player_list() -> List[str]:
    """Static star player list for degraded-mode exclusion.

    In a more complete implementation this would be driven by a
    contract-value or usage-based feed. For now we seed it with an
    intentionally small, conservative list of obvious franchise
    players so that degraded mode errs on the side of caution.
    """

    return [
        "Giannis Antetokounmpo",
        "Joel Embiid",
        "Nikola Jokic",
        "Stephen Curry",
        "Kevin Durant",
        "LeBron James",
        "Luka Doncic",
        "Jayson Tatum",
        "Shai Gilgeous-Alexander",
        "Anthony Davis",
    ]


def get_current_degraded_level() -> DegradedModeLevel:
    """Convenience helper: infer degraded level from current signals.

    Today this is a thin wrapper around injury feed health; it is
    defined as a separate function so additional sources can be wired
    in later without touching callers.
    """

    manager = DegradedModeManager()
    manager.update_from_injury_feed()
    return manager.assess_system_health()
