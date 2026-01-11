"""Slate-level data verification for learning readiness.

This module performs diagnostic checks to determine whether a slate is
"safe to learn from". It is intentionally read-only and has **no side
effects** on calibration_history.csv, outcomes, or governance rules.

Current implementation focuses on wiring, structure, and reporting. The
actual data fetchers for box scores and league APIs are thin stubs that
can be upgraded later without touching the CLI surface.

Design principles
-----------------
- Fail closed: treat missing / incomplete data as **blocked**.
- No retries or mutation inside this module.
- Per-game results are always logged into a machine-readable summary
  structure which the CLI then writes to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ufa.gates.injury_gate import get_injury_feed_health


@dataclass
class VerificationGameResult:
    """Per-game verification outcome.

    This mirrors the JSON schema described in the PM blueprint while
    keeping types convenient for Python code.
    """

    game_id: str
    home_team: str
    away_team: str

    game_status: str = "UNKNOWN"
    final_confirmed_at: Optional[str] = None  # ISO8601 or None
    minutes_since_final: Optional[int] = None

    sources_checked: Dict[str, str] = field(default_factory=dict)

    # Simple stat agreement summary; concrete fields can be extended
    # once real data fetchers are wired in.
    stat_check: Dict[str, Any] = field(default_factory=dict)

    overtime: bool = False
    correction_risk: bool = False

    # Optional high-level injury / availability notes. These are
    # intentionally coarse and game-level; detailed per-player checks
    # (e.g. late scratches) can still map to a single slate-level
    # block_reason such as "LATE_SCRATCH_OR_IN_GAME_REMOVAL".
    injury_notes: Dict[str, Any] = field(default_factory=dict)

    learning_gate_passed: bool = False
    block_reason: Optional[str] = None


@dataclass
class VerificationSummary:
    """Slate-level verification summary for a single league/date."""

    slate_date: str
    league: str
    generated_at: str
    games: List[VerificationGameResult]

    @property
    def games_checked(self) -> int:
        return len(self.games)

    @property
    def safe_games(self) -> int:
        return sum(1 for g in self.games if g.learning_gate_passed and not g.block_reason)

    @property
    def blocked_games(self) -> int:
        return self.games_checked - self.safe_games

    @property
    def safe_to_learn(self) -> bool:
        """A conservative "safe to learn" flag.

        We only consider a slate safe when **all** games have passed
        verification and at least one game was checked.
        """

        return self.games_checked > 0 and self.blocked_games == 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_verification(league: str, slate_date: str) -> VerificationSummary:
    """Run verification for a given league and slate date.

    Args:
        league: League identifier, e.g. "NBA" or "NFL" (case-insensitive).
        slate_date: Slate date in ``YYYY-MM-DD`` format.

    Returns:
        VerificationSummary describing per-game results. Callers are
        responsible for writing this to disk in any desired format.
    """

    league_norm = league.upper()
    generated_at = datetime.now(timezone.utc).isoformat()

    games = _resolve_games_for_slate(league_norm, slate_date)

    results: List[VerificationGameResult] = []
    for game in games:
        result = verify_game(game_id=game["id"], home_team=game["home_team"], away_team=game["away_team"], league=league_norm)
        results.append(result)

    # If the injury feed is degraded for this process, we conservatively
    # treat the entire slate as injury-unverified from a learning
    # perspective. Structural gates may all pass, but we still mark
    # games as blocked so they never contaminate calibration.
    if get_injury_feed_health() == "DEGRADED":
        for result in results:
            result.learning_gate_passed = False
            if not result.block_reason:
                result.block_reason = "INJURY_FEED_UNAVAILABLE"

    return VerificationSummary(
        slate_date=slate_date,
        league=league_norm,
        generated_at=generated_at,
        games=results,
    )


# ---------------------------------------------------------------------------
# Core per-game verification logic
# ---------------------------------------------------------------------------


def verify_game(*, game_id: str, home_team: str, away_team: str, league: str) -> VerificationGameResult:
    """Run verification checks for a single game.

    This function is intentionally self-contained and has **no side
    effects**. It does not touch calibration history, outcomes, or any
    persistent store. All results are returned via the
    ``VerificationGameResult`` structure.
    """

    now_utc = datetime.now(timezone.utc)

    result = VerificationGameResult(
        game_id=game_id,
        home_team=home_team,
        away_team=away_team,
    )

    # Fetch source data. These helpers are intentionally thin and can be
    # upgraded later to use real ESPN / league APIs.
    espn_data = _fetch_espn_box_score(game_id=game_id, league=league)
    league_data = _fetch_league_api_stats(game_id=game_id, league=league)

    # Record which sources we attempted.
    result.sources_checked["espn_box"] = "OK" if espn_data else "MISSING"
    result.sources_checked["league_api"] = "OK" if league_data else "MISSING"

    if not espn_data:
        result.block_reason = "DATA_UNAVAILABLE_ESPn"
        return result

    # Gate 1 — FINAL status
    status = str(espn_data.get("game_status", "")).upper() or "UNKNOWN"
    result.game_status = status

    if status != "FINAL":
        result.block_reason = "GAME_NOT_FINAL"
        return result

    # Gate 2 — SLA: at least 15 minutes since final confirmation
    final_ts_raw = espn_data.get("final_confirmed_at")
    if not final_ts_raw:
        result.block_reason = "MISSING_FINAL_CONFIRMED_AT"
        return result

    final_dt = _parse_iso_like(final_ts_raw)
    if final_dt is None:
        result.block_reason = "FINAL_CONFIRMED_AT_UNPARSABLE"
        return result

    # normalise to naive UTC
    if final_dt.tzinfo is not None:
        final_dt = final_dt.astimezone(timezone.utc).replace(tzinfo=None)
    now_naive = now_utc.replace(tzinfo=None)

    minutes_since_final = int((now_naive - final_dt).total_seconds() // 60)
    result.minutes_since_final = max(minutes_since_final, 0)
    result.final_confirmed_at = final_dt.replace(tzinfo=timezone.utc).isoformat()

    if minutes_since_final < 15:
        result.block_reason = "SLA_NOT_MET"
        return result

    # Gate 3 — cross-source stat agreement (if league API data is present)
    if league_data:
        stat_check = _compare_stats(espn_data, league_data)
        result.stat_check = stat_check

        max_delta = stat_check.get("max_delta")
        if max_delta is None:
            # Could not compute deltas; treat as blocked until logic is
            # upgraded.
            result.block_reason = "STAT_CHECK_INCOMPLETE"
            return result

        if max_delta > 0.1:
            result.block_reason = "STAT_MISMATCH"
            return result

    else:
        # No league-api mirror available yet → be conservative and mark
        # as blocked for learning, but still include this game in the
        # report for visibility.
        result.block_reason = "LEAGUE_API_UNAVAILABLE"
        return result

    # At this point, all core structural gates have passed. Before we
    # mark the game as safe for learning, we allow for injury-based
    # integrity checks (e.g. late scratches) when the upstream data
    # sources expose enough detail. These checks are intentionally
    # conservative and only *further* restrict learning.

    # Example (future wiring):
    # - espn_data["pregame_injury_status"][player_id]
    # - league_data["minutes_played"][player_id]
    # For now, we look for a simple boolean hint that a late scratch or
    # in-game removal was detected by an upstream process.
    late_scratch_flag = bool(espn_data.get("late_scratch_or_removal", False))
    if late_scratch_flag:
        result.injury_notes["late_scratch_or_removal"] = True
        result.learning_gate_passed = False
        result.block_reason = "LATE_SCRATCH_OR_IN_GAME_REMOVAL"
    else:
        result.learning_gate_passed = True
        result.block_reason = None

    # Optional flags — callers can extend espn_data/league_data to
    # include richer context later (overtime, correction risk, etc.).
    result.overtime = bool(espn_data.get("overtime", False))
    result.correction_risk = bool(espn_data.get("correction_risk", False))

    return result


# ---------------------------------------------------------------------------
# Helpers for game resolution and stat comparison
# ---------------------------------------------------------------------------


def _resolve_games_for_slate(league: str, slate_date: str) -> List[Dict[str, str]]:
    """Resolve games for a league/date.

    The current implementation is intentionally conservative: it returns
    an empty list, which means **no games are considered safe to learn**
    by default. This is preferable to guessing.

    Once a canonical slate source is chosen (e.g. ESPN scoreboard for
    NFL, league schedule for NBA), this function can be expanded to
    return real game identifiers while keeping the public API stable.
    """

    # Placeholder: no automatic game discovery yet.
    return []


def _fetch_espn_box_score(*, game_id: str, league: str) -> Dict[str, Any]:
    """Fetch a minimal box score structure from ESPN (stub).

    The structure is expected to include at least:

    - ``game_status``: "FINAL" when complete
    - ``final_confirmed_at``: timestamp string
    - optional: ``overtime`` and ``correction_risk`` booleans

    Until wired to real APIs, this returns an empty dict, which causes
    ``verify_game`` to conservatively block the game from learning.
    """

    _ = game_id, league  # unused for now
    return {}


def _fetch_league_api_stats(*, game_id: str, league: str) -> Dict[str, Any]:
    """Fetch league-official stats (stub).

    Expected to mirror the ESPN box score at the stat level so that
    ``_compare_stats`` can compute deltas.
    """

    _ = game_id, league
    return {}


def _compare_stats(espn_data: Dict[str, Any], league_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compare ESPN and league stats and compute simple deltas.

    The exact shape of the input dicts is intentionally loose for now.
    This function looks for a small set of conventional keys and falls
    back to an empty result when it cannot compute a meaningful delta.
    """

    # Placeholder keys; when wiring real data, adapt this mapping.
    stat_keys = ["points", "rebounds", "assists"]

    max_delta: Optional[float] = None
    per_stat: Dict[str, Dict[str, Optional[float]]] = {}

    for key in stat_keys:
        espn_val = espn_data.get(key)
        league_val = league_data.get(key)

        if espn_val is None or league_val is None:
            per_stat[key] = {"espn": espn_val, "league": league_val, "delta": None}
            continue

        try:
            delta = float(espn_val) - float(league_val)
        except (TypeError, ValueError):
            per_stat[key] = {"espn": espn_val, "league": league_val, "delta": None}
            continue

        per_stat[key] = {"espn": float(espn_val), "league": float(league_val), "delta": delta}
        abs_delta = abs(delta)
        if max_delta is None or abs_delta > max_delta:
            max_delta = abs_delta

    return {"per_stat": per_stat, "max_delta": max_delta}


def _parse_iso_like(value: Any) -> Optional[datetime]:
    """Parse a loose ISO-8601-like timestamp into a datetime.

    Accepts several common formats so that upstream callers can emit
    reasonably formatted strings without being overly strict here.
    """

    if not isinstance(value, str):
        return None

    txt = value.strip()
    # Try the most permissive variant first
    try:
        return datetime.fromisoformat(txt.replace("Z", "+00:00"))
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(txt, fmt)
        except ValueError:
            continue

    return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def summary_to_dict(summary: VerificationSummary) -> Dict[str, Any]:
    """Convert a VerificationSummary into a JSON-serialisable dict."""

    return {
        "slate_date": summary.slate_date,
        "league": summary.league,
        "generated_at": summary.generated_at,
        "games": [asdict(g) for g in summary.games],
    }


def format_human_report(summary: VerificationSummary) -> str:
    """Render a human-readable verification report for a slate."""

    lines: List[str] = []
    header = f"DATA VERIFICATION REPORT — {summary.league} — {summary.slate_date}"
    lines.append("=" * len(header))
    lines.append(header)
    lines.append("=" * len(header))
    lines.append("")

    lines.append(f"Games checked: {summary.games_checked}")
    lines.append(f"Safe to learn: {summary.safe_games}")
    lines.append(f"Blocked: {summary.blocked_games}")
    lines.append("")

    if summary.blocked_games:
        lines.append("BLOCKED GAMES")
        lines.append("-------------")
        for g in summary.games:
            if not g.block_reason:
                continue
            label = f"{g.away_team} @ {g.home_team}" if g.home_team or g.away_team else g.game_id
            detail = g.block_reason
            if g.block_reason == "SLA_NOT_MET" and g.minutes_since_final is not None:
                detail += f" (finalized {g.minutes_since_final} min ago)"
            lines.append(f"• {label} — {detail}")
        lines.append("")

    safe_games = [g for g in summary.games if g.learning_gate_passed and not g.block_reason]
    if safe_games:
        lines.append("SAFE GAMES")
        lines.append("----------")
        for g in safe_games:
            label = f"{g.away_team} @ {g.home_team}" if g.home_team or g.away_team else g.game_id
            ot_suffix = ", OT flagged" if g.overtime else ""
            lines.append(f"• {label} — FINAL, verified{ot_suffix}")
        lines.append("")

    status_line = "Learning status: ✅ SAFE" if summary.safe_to_learn else "Learning status: ❌ NOT SAFE"
    if not summary.games:
        status_line += " (no games verified)"
    elif summary.blocked_games:
        status_line += " (blocked games exist)"

    lines.append(status_line)

    lines.append("=" * len(header))

    return "\n".join(lines)
