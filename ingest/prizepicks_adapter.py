"""PrizePicks → canonical prop adapter.

Normalizes parsed PrizePicks props into the shared `ExternalProp` schema so
that Underdog, PrizePicks and Odds API lines can all flow into the same
truth engine and governance layer.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Iterable, List, Optional

from schemas.prop_schemas import ExternalProp, PayoutProfile
from ingest.underdog_adapter import _normalize_market  # reuse same stat→market mapping


def _default_payout_profile_prizepicks() -> PayoutProfile:
    """Conservative default payout profile for PrizePicks pick'em.

    Exact flex/power payout tables are handled elsewhere; here we only
    tag the product so downstream EV logic knows this came from
    PrizePicks pick'em-style markets.
    """

    return PayoutProfile(
        source="PRIZEPICKS",
        product="PICKEM",
        format="flex",
        min_legs=2,
        max_legs=6,
        notes="Default PrizePicks Pick'em payout profile",
    )


def normalize_prizepicks_props(
    raw_props: Iterable[Dict[str, Any]],
    *,
    sport: str = "NBA",
    payout_profile: Optional[PayoutProfile] = None,
    slate_id: Optional[str] = None,
) -> List[ExternalProp]:
    """Normalize raw PrizePicks props into ExternalProp objects.

    Expected input shape is similar to Underdog:
        {"player", "team", "opponent", "stat", "line", "direction", ...}

    Many of your existing PrizePicks parsers (NBA, tennis, soccer, golf)
    already emit this style of dict; this adapter sits on top and
    guarantees a unified schema.
    """

    profile = payout_profile or _default_payout_profile_prizepicks()
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

        # Allow per-prop sport override if parser already set it.
        sport_tag = str(raw.get("sport", sport) or sport).strip() or sport

        team = str(raw.get("team", "UNK")).strip() or "UNK"
        opponent = str(raw.get("opponent", "UNK")).strip() or "UNK"

        ext = ExternalProp(
            source="PRIZEPICKS",
            sport=sport_tag,
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


def normalize_prizepicks_props_to_dicts(
    raw_props: Iterable[Dict[str, Any]],
    *,
    sport: str = "NBA",
    payout_profile: Optional[PayoutProfile] = None,
    slate_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return normalized PrizePicks props as plain dicts.

    Useful for legacy dict-based pipelines.
    """

    objs = normalize_prizepicks_props(
        raw_props,
        sport=sport,
        payout_profile=payout_profile,
        slate_id=slate_id,
    )

    dicts: List[Dict[str, Any]] = []
    for o in objs:
        d = asdict(o)
        d.setdefault("stat", d.get("market"))
        dicts.append(d)
    return dicts


__all__ = [
    "normalize_prizepicks_props",
    "normalize_prizepicks_props_to_dicts",
]
