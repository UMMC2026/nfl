"""soccer/gates/soccer_gates.py

Hard governance gates for Soccer v1.0.

Failure of ANY hard gate => NO_PLAY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from soccer.config import SOCCER_GATES, ENABLED_LEAGUES


@dataclass
class GateResult:
    passed: bool
    gate: str
    reason: str = ""


def validate_match_gates(match: Dict) -> Tuple[bool, List[GateResult]]:
    """Validate a match payload against Soccer hard gates."""
    results: List[GateResult] = []

    league = (match.get("league") or "").strip().upper()
    if league not in ENABLED_LEAGUES:
        results.append(GateResult(False, "S1_COMPETITION", f"league_not_enabled:{league}"))
    else:
        results.append(GateResult(True, "S1_COMPETITION", "ok"))

    # Data sufficiency
    home_matches = int(match.get("home_matches", 0) or 0)
    away_matches = int(match.get("away_matches", 0) or 0)
    if home_matches < SOCCER_GATES.min_team_matches:
        results.append(GateResult(False, "S2_DATA", f"home_matches<{SOCCER_GATES.min_team_matches}"))
    if away_matches < SOCCER_GATES.min_team_matches:
        results.append(GateResult(False, "S2_DATA", f"away_matches<{SOCCER_GATES.min_team_matches}"))

    xg_sources = match.get("xg_sources") or []
    if not isinstance(xg_sources, list):
        xg_sources = [str(xg_sources)]
    if len(xg_sources) < SOCCER_GATES.min_xg_sources:
        results.append(GateResult(False, "S2_DATA", f"xg_sources<{SOCCER_GATES.min_xg_sources}"))

    # Match state
    state = (match.get("match_state") or "").strip().upper() or "PRE"
    if SOCCER_GATES.block_live and state == "LIVE":
        results.append(GateResult(False, "S3_STATE", "live_blocked"))
    else:
        results.append(GateResult(True, "S3_STATE", "ok"))

    # Odds format
    odds_fmt = (match.get("odds_format") or "decimal").strip().lower()
    if SOCCER_GATES.require_decimal_odds and odds_fmt != "decimal":
        results.append(GateResult(False, "S4_ODDS", f"odds_format={odds_fmt}"))
    else:
        results.append(GateResult(True, "S4_ODDS", "ok"))

    passed = all(r.passed for r in results)
    return passed, results
