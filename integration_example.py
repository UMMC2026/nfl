"""Integration with existing cheatsheet generation.

This module shows how to plug ClientFocusedReporter into the
current injury gate and pick hydration pipeline.
"""

from datetime import datetime
from typing import Dict, List, Any

from reporter.client_focused_reporter import (
    ClientFocusedReporter,
    SystemStatus,
    SystemHealth,
    SubscriberTier,
    ReportFormatter,
)
from ufa.gates.injury_gate import get_injury_feed_health


def get_data_freshness() -> str:
    """Return a human-readable data freshness string.

    In production this should reflect when picks_hydrated.json or
    upstream stat feeds were last refreshed.
    """

    return "15 minutes ago"


def get_subscriber_tier() -> SubscriberTier:
    """Return subscriber tier.

    In production this would likely be loaded from a user profile
    or configuration store.
    """

    return SubscriberTier.PRO


def generate_enhanced_cheatsheet(
    picks_hydrated: List[Dict[str, Any]], output_format: str = "text"
) -> str:
    """Generate an enhanced client-focused cheatsheet.

    This function is intentionally side-effect free; callers can
    decide where to send the formatted output (console, email,
    web dashboard, etc.).
    """

    injury_health = get_injury_feed_health()

    if injury_health == "HEALTHY":
        system_status = SystemStatus(
            injury_feed=SystemHealth.HEALTHY,
            predictive_model=SystemHealth.HEALTHY,
            learning_system=SystemHealth.HEALTHY,
            parlay_builder=SystemHealth.HEALTHY,
            data_freshness=get_data_freshness(),
        )
    else:
        system_status = SystemStatus(
            injury_feed=SystemHealth.DEGRADED,
            predictive_model=SystemHealth.HEALTHY,
            learning_system=SystemHealth.DEGRADED,
            parlay_builder=SystemHealth.DEGRADED,
            data_freshness=get_data_freshness(),
            degraded_since=datetime.utcnow(),
            estimated_restoration="Monitoring NBA API",
        )

    subscriber_tier = get_subscriber_tier()

    reporter = ClientFocusedReporter(
        system_status=system_status,
        raw_picks=picks_hydrated,
        subscriber_tier=subscriber_tier,
    )

    report = reporter.generate_report()

    if output_format == "json":
        return ReportFormatter.format_json(report)
    if output_format == "html":
        return ReportFormatter.format_html(report)
    return ReportFormatter.format_text(report)
