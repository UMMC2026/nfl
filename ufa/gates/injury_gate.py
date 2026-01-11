"""Pre-game injury availability gate.

This module centralizes injury-based availability logic. It is designed
as a **read-only, side-effect-free** component that other parts of the
system can call when deciding whether a prop is eligible or should be
confidence-downgraded.

Current implementation intentionally keeps the data fetch stub simple so
that wiring and semantics are stable even before a real injury feed is
integrated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

INJURY_FRESHNESS_HOURS = 12


_injury_report_cache = None  # type: ignore[var-annotated]
_injury_report_season: Optional[str] = None
_injury_report_fetched_at: Optional[datetime] = None

# Coarse-grained injury feed health flag. We intentionally keep this
# simple: if any attempt to load the league-wide injury report fails
# hard (e.g. missing nba_api, network error, empty frames), we mark the
# feed as "DEGRADED" for the remainder of the process. Callers that
# care about learning / verification integrity can treat this as a
# fail-closed signal, while day-of generation can still operate in a
# fail-open-but-flagged mode.
_injury_feed_degraded: bool = False


@dataclass
class InjuryGateResult:
    """Result of the injury availability gate for a single player.

    Attributes
    ----------
    allowed:
        Whether the pick is allowed to be shown as eligible.
    downgraded:
        True when the player is available but should have their
        confidence tier reduced (e.g. QUESTIONABLE).
    injury_status:
        Normalized injury string, e.g. "OUT", "DOUBTFUL",
        "QUESTIONABLE", "PROBABLE", "ACTIVE", "UNKNOWN".
    injury_source:
        Human-readable source identifier (e.g. "ESPN", "nba_api").
    injury_last_checked_at:
        When this status was last confirmed, in UTC.
    injury_fresh:
        Whether the status is considered fresh according to
        INJURY_FRESHNESS_HOURS.
    block_reason:
        Optional machine-readable reason explaining why a pick was
        blocked. None when ``allowed`` is True.
    confidence_multiplier:
        Multiplier to apply to model confidence when ``downgraded`` is
        True. Always 1.0 when no downgrade is requested.
    """

    allowed: bool
    downgraded: bool
    injury_status: str
    injury_source: str
    injury_last_checked_at: datetime
    injury_fresh: bool
    block_reason: Optional[str] = None
    confidence_multiplier: float = 1.0


def injury_availability_gate(
    *,
    player: str,
    team: str,
    league: str = "NBA",
    game_time_utc: Optional[datetime] = None,
    now_utc: Optional[datetime] = None,
) -> InjuryGateResult:
    """Pre-game injury availability gate.

    Parameters
    ----------
    player:
        Player name (display string used throughout the system).
    team:
        Team abbreviation (e.g. "NYK", "LAL").
    league:
        League code (e.g. "NBA", "NFL"). Currently unused but kept for
        future extension when league-specific injury feeds are wired in.
    game_time_utc:
        Scheduled game start time in UTC. Not required for the current
        placeholder implementation but included for future use
        (e.g. freshness windows that depend on tipoff time).
    now_utc:
        Override for "current" time, mainly for tests.

    Notes
    -----
    - For NBA, this function uses ``nba_api``'s ``InjuryReports``
      endpoint to derive availability. Players listed as OUT or
      DOUBTFUL are **blocked**. QUESTIONABLE players are allowed but
      downgraded via a confidence multiplier.
        - If the injury report cannot be fetched at all (network / missing
            dependency), we mark the feed as **degraded** and return an
            ``UNKNOWN`` status with a downgrade recommendation. Day-of
            generation can treat this as fail-open-with-warnings, while
            learning / verification code should treat the slate as
            **injury-unverified** and block accordingly.
    - For non-NBA leagues, the gate currently treats players as ACTIVE
      but still returns a structured result, so future league-specific
      feeds can plug in without changing callers.
    """

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    league_norm = league.upper()

    # Non-NBA leagues: currently pass-through ACTIVE until a dedicated
    # feed is wired. We still emit a result so callers can rely on the
    # same structure.
    if league_norm != "NBA":
        return InjuryGateResult(
            allowed=True,
            downgraded=False,
            injury_status="ACTIVE",
            injury_source="PLACEHOLDER",
            injury_last_checked_at=now_utc,
            injury_fresh=True,
        )

    # Determine NBA season string, e.g. "2024-25".
    season_dt = game_time_utc or now_utc
    season_str = _season_from_date(season_dt)

    try:
        status, source, checked_at, fresh = _fetch_nba_injury_status(
            player=player,
            team=team,
            season=season_str,
            now_utc=now_utc,
        )
    except Exception:
        # If we cannot fetch injury data at all, mark the feed as
        # degraded and return an UNKNOWN status. This allows day-of
        # cheatsheet generation to continue in a fail-open mode while
        # still surfacing the problem loudly. Learning / verification
        # code should treat this as "injury unverified" and block.
        global _injury_feed_degraded
        _injury_feed_degraded = True

        return InjuryGateResult(
            allowed=True,
            downgraded=True,
            injury_status="UNKNOWN",
            injury_source="NONE",
            injury_last_checked_at=now_utc,
            injury_fresh=False,
            block_reason="NO_INJURY_DATA",
            confidence_multiplier=0.75,
        )

    # Freshness check (normally always True because we refresh the
    # report when it exceeds INJURY_FRESHNESS_HOURS).
    if not fresh:
        return InjuryGateResult(
            allowed=False,
            downgraded=False,
            injury_status=status,
            injury_source=source,
            injury_last_checked_at=checked_at,
            injury_fresh=False,
            block_reason="INJURY_STATUS_STALE",
        )

    norm = status.upper()

    if norm in {"OUT", "DOUBTFUL"}:
        return InjuryGateResult(
            allowed=False,
            downgraded=False,
            injury_status=norm,
            injury_source=source,
            injury_last_checked_at=checked_at,
            injury_fresh=True,
            block_reason="PLAYER_INACTIVE",
        )

    if norm == "QUESTIONABLE":
        return InjuryGateResult(
            allowed=True,
            downgraded=True,
            injury_status=norm,
            injury_source=source,
            injury_last_checked_at=checked_at,
            injury_fresh=True,
            confidence_multiplier=0.70,
        )

    # ACTIVE / PROBABLE / UNKNOWN → allowed, no downgrade.
    return InjuryGateResult(
        allowed=True,
        downgraded=False,
        injury_status=norm or "ACTIVE",
        injury_source=source,
        injury_last_checked_at=checked_at,
        injury_fresh=True,
    )


def _season_from_date(dt: datetime) -> str:
    """Derive NBA season string (e.g. "2024-25") from a datetime.

    NBA seasons start in October and end the following year, so dates
    in Jan–Sep map to the previous start year.
    """

    year = dt.year
    if dt.month >= 10:  # Oct, Nov, Dec → season start of this year
        start_year = year
        end_year = year + 1
    else:  # Jan–Sep → season started last year
        start_year = year - 1
        end_year = year

    return f"{start_year}-{str(end_year)[-2:]}"


def _load_injury_report_df(season: str, now_utc: datetime):
    """Load and cache the league-wide injury report for a season.

    Uses nba_api.stats.endpoints.InjuryReports and caches the first
    DataFrame for up to INJURY_FRESHNESS_HOURS to avoid hammering the
    API.
    """

    global _injury_report_cache, _injury_report_season, _injury_report_fetched_at

    if (
        _injury_report_cache is not None
        and _injury_report_season == season
        and _injury_report_fetched_at is not None
        and (now_utc - _injury_report_fetched_at) <= timedelta(hours=INJURY_FRESHNESS_HOURS)
    ):
        return _injury_report_cache

    try:
        from nba_api.stats.endpoints import injuryreports  # type: ignore[import]
    except Exception as e:  # pragma: no cover - environment/config issue
        raise RuntimeError(
            "nba_api injuryreports endpoint not available. Install extras: "
            "pip install -r requirements-extras.txt"
        ) from e

    reports = injuryreports.InjuryReports(season=season)
    frames = reports.get_data_frames()
    if not frames:
        raise RuntimeError("nba_api InjuryReports returned no data frames")

    df = frames[0]
    _injury_report_cache = df
    _injury_report_season = season
    _injury_report_fetched_at = now_utc
    return df


def _normalize_status(raw_status: str) -> str:
    """Normalize free-form injury status text into coarse buckets."""

    if not raw_status:
        return "ACTIVE"

    s = raw_status.strip().upper()

    if "OUT" in s:
        return "OUT"
    if "DOUBTFUL" in s:
        return "DOUBTFUL"
    if "QUESTIONABLE" in s or "GAME TIME" in s:
        return "QUESTIONABLE"
    if "PROBABLE" in s or "AVAILABLE" in s:
        return "PROBABLE"

    return "ACTIVE"


def _fetch_nba_injury_status(
    *,
    player: str,
    team: str,
    season: str,
    now_utc: datetime,
) -> tuple[str, str, datetime, bool]:
    """Fetch and interpret NBA injury status for a single player.

    Returns (status, source, injury_last_checked_at, injury_fresh).

    Semantics:
    - If the player is **not** present in the league injury report,
      they are treated as ACTIVE.
    - If present, we normalise the reported status string.
    - Freshness is tied to the injury report fetch time; we refresh the
      league report when older than INJURY_FRESHNESS_HOURS.
    """

    df = _load_injury_report_df(season=season, now_utc=now_utc)

    if "PLAYER_NAME" not in df.columns:
        raise RuntimeError("InjuryReports DataFrame missing PLAYER_NAME column")

    name_series = df["PLAYER_NAME"].astype(str).str.lower()
    mask = name_series == player.lower()

    team_col = None
    for candidate in ("TEAM_ABBREVIATION", "TEAM_ABBREVIATION_x", "TEAM_ABBREVIATION_y"):
        if candidate in df.columns:
            team_col = candidate
            break

    if team_col is not None:
        mask &= df[team_col].astype(str).str.upper() == team.upper()

    subset = df[mask]

    if subset.empty:
        # Not on the injury report → assume ACTIVE.
        return "ACTIVE", "nba_api", now_utc, True

    # Use the most recent row; InjuryReports is typically per-day, so
    # one row per player/team is common.
    row = subset.iloc[-1]

    raw_status = str(row.get("INJURY_STATUS") or row.get("STATUS") or "")
    status = _normalize_status(raw_status)

    # We treat the fetch time as the "last checked" moment. More
    # granular timestamps can be incorporated later if exposed by the
    # endpoint.
    checked_at = now_utc
    fresh = True

    return status, "nba_api", checked_at, fresh


def get_injury_feed_health() -> str:
    """Return the coarse-grained health of the injury feed.

    Values
    ------
    - "OK":      Injury report fetches have not failed in this process.
    - "DEGRADED": At least one league-wide injury report fetch failed;
                  callers should treat injury status as *unverified*
                  for learning / verification purposes.
    """

    return "DEGRADED" if _injury_feed_degraded else "OK"
