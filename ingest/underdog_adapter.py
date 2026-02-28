"""Underdog → canonical prop adapter.

This module provides a single normalization+ingest entry point for
Underdog Pick'em props before they enter the truth engine.

Usage pattern (example):

    from parse_underdog_paste import parse_text
    from ingest.underdog_adapter import normalize_underdog_props_to_dicts

    raw_props = parse_text(paste_blob)  # list[dict] from website copy/paste
    props = normalize_underdog_props_to_dicts(raw_props, sport="NBA")

`props` can then be passed directly into the risk-first pipeline's
slate analyzers, schedule/roster gates, and Monte Carlo engine.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional

from schemas.prop_schemas import ExternalProp, PayoutProfile


# Map parse_underdog_paste stat keys → canonical internal market codes.
# This intentionally mirrors STATS_MASTER_LIST.md but stays small and
# focused on the most common props that the risk-first engine supports.
_STAT_TO_MARKET: Dict[str, str] = {
    # Core single stats
    "points": "PTS",
    "rebounds": "REB",
    "assists": "AST",

    # Combo stats
    "pra": "PRA",          # pts + rebs + asts
    "pts+reb": "PR",
    "pts+ast": "PA",
    "reb+ast": "RA",

    # Shooting
    "3pm": "3PM",
    "3-pointers made": "3PM",
    "3 pointers made": "3PM",

    # Defensive
    "steals": "STL",
    "blocks": "BLK",

    # Negative
    "turnovers": "TO",
}


def _normalize_market(stat_key: str) -> str:
    """Normalize a parsed stat key to internal market code.

    Falls back to an upper-cased token so unknown/experimental stats
    still flow through the pipeline in a predictable way, while
    allowing risk gates or render layers to decide how to treat them.
    """

    s = (stat_key or "").strip().lower()
    if not s:
        return "UNK"
    return _STAT_TO_MARKET.get(s, s.upper())


def _default_payout_profile() -> PayoutProfile:
    """Return a conservative default PayoutProfile for Underdog Pick'em.

    Detailed flex/power payout tables are handled elsewhere (e.g. ufa
    payouts module).  Here we only tag the product so downstream EV
    or portfolio logic can branch correctly.
    """

    return PayoutProfile(
        source="UNDERDOG",
        product="PICKEM",
        format="flex",   # baseline; specific entry may override
        min_legs=2,
        max_legs=6,
        notes="Default Underdog Pick'em payout profile (see payouts module for tables)",
    )


def normalize_underdog_props(
    raw_props: Iterable[Dict[str, Any]],
    *,
    sport: str = "NBA",
    payout_profile: Optional[PayoutProfile] = None,
    slate_id: Optional[str] = None,
) -> List[ExternalProp]:
    """Normalize raw Underdog props into ExternalProp objects.

    Parameters
    ----------
    raw_props:
        Iterable of dictionaries produced by `parse_underdog_paste` or
        other Underdog-specific ingestion scripts. Expected keys:
        `player`, `team`, `opponent`, `stat`, `line`, `direction`.

    sport:
        Sport tag to attach (e.g. "NBA", "TENNIS").

    payout_profile:
        Optional PayoutProfile describing how entries built from these
        props will pay out. If not provided, a conservative default is
        used for Underdog Pick'em.

    slate_id:
        Optional identifier tying all props in this batch to a single
        slate/run (useful for audit and reconciliation).
    """

    profile = payout_profile or _default_payout_profile()
    results: List[ExternalProp] = []

    for raw in raw_props:
        player = str(raw.get("player", "")).strip()
        if not player:
            continue

        raw_line = raw.get("line")
        try:
            line_val = float(raw_line)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue

        direction = str(raw.get("direction", "")).strip().lower()
        if direction not in {"higher", "lower"}:
            # Accept OVER/UNDER variants and normalize.
            if direction in {"over", "o"}:
                direction = "higher"
            elif direction in {"under", "u"}:
                direction = "lower"
            else:
                # If we truly don't know, skip rather than guess.
                continue

        stat_key = str(raw.get("stat", "")).strip()
        market = _normalize_market(stat_key)

        team = str(raw.get("team", "UNK")).strip() or "UNK"
        opponent = str(raw.get("opponent", "UNK")).strip() or "UNK"

        ext = ExternalProp(
            source="UNDERDOG",
            sport=sport,
            player=player,
            team=team,
            opponent=opponent,
            market=market,
            line=line_val,
            direction=direction,
            payout_profile=profile,
            raw=dict(raw),
            slate_id=slate_id,
            book_prop_id=str(raw.get("id")) if raw.get("id") is not None else None,
        )
        results.append(ext)

    return results


def normalize_underdog_props_to_dicts(
    raw_props: Iterable[Dict[str, Any]],
    *,
    sport: str = "NBA",
    payout_profile: Optional[PayoutProfile] = None,
    slate_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convenience wrapper returning plain dictionaries.

    This is helpful for legacy parts of the pipeline that expect
    dict-like objects instead of dataclasses.
    """

    objs = normalize_underdog_props(
        raw_props,
        sport=sport,
        payout_profile=payout_profile,
        slate_id=slate_id,
    )

    dicts: List[Dict[str, Any]] = []
    for o in objs:
        d = asdict(o)
        # Provide a "stat" alias for legacy code paths that still
        # expect a stat key instead of the canonical "market" field.
        d.setdefault("stat", d.get("market"))
        dicts.append(d)
    return dicts


__all__ = [
    "normalize_underdog_props",
    "normalize_underdog_props_to_dicts",
]
