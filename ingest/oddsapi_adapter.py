"""Odds API → canonical prop adapter.

Bridges the The Odds API client (`src/sources/odds_api.py`) into the
shared `ExternalProp` schema so reference lines from multiple books
(Underdog, PrizePicks, pick6, etc. via Odds API) can be compared
against your truth engine.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from schemas.prop_schemas import ExternalProp, PayoutProfile
from ingest.underdog_adapter import _normalize_market

try:
    from src.sources.odds_api import (
        OddsApiError,
        oddsapi_fetch_player_props,
    )
except Exception as _e:  # pragma: no cover
    OddsApiError = RuntimeError  # type: ignore
    oddsapi_fetch_player_props = None  # type: ignore
    _oddsapi_import_err = _e


def _default_payout_profile_reference() -> PayoutProfile:
    """Default profile for Odds API reference lines.

    These are not DFS pick'em slips by themselves; they represent
    single-market prices.  We tag them as a "REFERENCE" product so
    downstream code can treat them differently from DFS entries.
    """

    return PayoutProfile(
        source="ODDS_API",
        product="REFERENCE",
        format="single",
        min_legs=1,
        max_legs=1,
        notes="Reference lines from The Odds API (per-book, per-market)",
    )


def normalize_oddsapi_props(
    raw_props: Iterable[Dict[str, Any]],
    *,
    sport: str = "NBA",
    payout_profile: Optional[PayoutProfile] = None,
    slate_id: Optional[str] = None,
) -> List[ExternalProp]:
    """Normalize pre-fetched Odds API props into ExternalProp objects.

    Expects dicts shaped like those returned by
    `src.sources.odds_api._odds_event_to_props` / `oddsapi_fetch_player_props`:

        {"player", "stat", "line", "direction", "sport", "raw", ...}

    Team/opponent are left as "UNK"; your existing team resolvers can
    refine that later if desired.
    """

    profile = payout_profile or _default_payout_profile_reference()
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
            if direction in {"over", "o", "more"}:
                direction = "higher"
            elif direction in {"under", "u", "less"}:
                direction = "lower"
            else:
                continue

        stat_key = str(raw.get("stat", "")).strip()
        market = _normalize_market(stat_key)

        # Prefer explicit sport tag from Odds API if present.
        sport_tag = str(raw.get("sport", sport) or sport).strip() or sport

        ext = ExternalProp(
            source="ODDS_API",
            sport=sport_tag,
            player=player,
            team="UNK",
            opponent="UNK",
            market=market,
            line=line_val,
            direction=direction,
            payout_profile=profile,
            raw=dict(raw),
            slate_id=slate_id,
            book_prop_id=None,
        )
        results.append(ext)

    return results


def fetch_and_normalize_oddsapi_props(
    *,
    sport: str = "NBA",
    sport_key: str = "basketball_nba",
    regions: str = "us_dfs",
    markets: Iterable[str] = ("player_points",),
    bookmakers: Optional[Iterable[str]] = ("betr_us_dfs", "pick6", "prizepicks", "underdog"),
    max_events: Optional[int] = None,
    payout_profile: Optional[PayoutProfile] = None,
    slate_id: Optional[str] = None,
) -> Tuple[List[ExternalProp], Dict[str, Any]]:
    """Fetch player props via The Odds API and normalize to ExternalProp.

    Returns (props, metadata) where `props` is a list[ExternalProp] and
    `metadata` contains quota and diagnostic information from the
    underlying client.
    """

    if oddsapi_fetch_player_props is None:  # pragma: no cover
        raise OddsApiError(f"Odds API adapter not available: {_oddsapi_import_err}")

    props_raw, meta = oddsapi_fetch_player_props(
        sport=sport,
        sport_key=sport_key,
        regions=regions,
        markets=markets,
        bookmakers=bookmakers,
        max_events=max_events,
    )

    norm = normalize_oddsapi_props(
        props_raw,
        sport=sport,
        payout_profile=payout_profile,
        slate_id=slate_id,
    )
    return norm, meta


def fetch_and_normalize_oddsapi_props_to_dicts(
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Wrapper returning dicts instead of dataclasses.

    Accepts the same keyword arguments as `fetch_and_normalize_oddsapi_props`.
    """
    props, meta = fetch_and_normalize_oddsapi_props(**kwargs)

    dicts: List[Dict[str, Any]] = []
    for p in props:
        d = asdict(p)
        d.setdefault("stat", d.get("market"))
        dicts.append(d)
    return dicts, meta


__all__ = [
    "normalize_oddsapi_props",
    "fetch_and_normalize_oddsapi_props",
    "fetch_and_normalize_oddsapi_props_to_dicts",
]
