"""
Feature ingestion and attachment utilities for the Specialist System.

This module maps raw box + tracking rows into the canonical specialist feature
schema, and attaches flattened fields onto a prop dict for downstream engines
(`core/stat_specialist_engine.py`, `stat_specialist_engine.py`) to consume.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from .feature_schema import (
    build_feature_bundle,
    GlobalFeatures,
    Shooting3PMFeatures,
    PickAndPopBigFeatures,
    MidrangeFeatures,
    BigPostRimRunnerFeatures,
    AssistSpecialistFeatures,
)


def _flatten_bundle_to_dict(bundle) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    gf: GlobalFeatures = bundle.global_features
    if gf:
        out.update(
            dict(
                minutes=gf.minutes,
                usage_rate=gf.usage_rate,
                assisted_fg_rate=gf.assisted_fg_rate,
                time_of_possession=gf.time_of_possession,
                avg_shot_distance=gf.avg_shot_distance,
                bench_minutes_rate=gf.bench_minutes_rate,
                usage_volatility=gf.usage_volatility,
            )
        )

    tp: Optional[Shooting3PMFeatures] = bundle.three_point
    if tp:
        out.update(
            dict(
                **{
                    "3pa": tp.three_pa,
                    "3pm": tp.three_pm,
                },
                assisted_3pa_rate=tp.assisted_3pa_rate,
                pullup_3pa_rate=tp.pullup_3pa_rate,
                dribbles_per_shot=tp.dribbles_per_shot,
                corner_3_rate=tp.corner_3_rate,
                shot_quality_3=tp.shot_quality_3,
            )
        )

    pp: Optional[PickAndPopBigFeatures] = bundle.pick_and_pop
    if pp:
        out.update(
            dict(
                position=pp.position,
                avg_3pa=pp.avg_3pa,
                pick_and_pop_rate=pp.pick_and_pop_rate,
                above_break_3_rate=pp.above_break_3_rate,
                trailer_3_rate=pp.trailer_3_rate,
            )
        )

    mr: Optional[MidrangeFeatures] = bundle.midrange
    if mr:
        out.update(
            dict(
                midrange_fga_rate=mr.midrange_fga_rate,
                rim_fga_rate=mr.rim_fga_rate,
                elbow_touch_rate=mr.elbow_touch_rate,
                shot_clock_usage_mid=mr.shot_clock_usage_mid,
            )
        )

    bp: Optional[BigPostRimRunnerFeatures] = bundle.big_post
    if bp:
        out.update(
            dict(
                post_touch_rate=bp.post_touch_rate,
                paint_fga_rate=bp.paint_fga_rate,
                roll_man_frequency=bp.roll_man_frequency,
                putback_rate=bp.putback_rate,
            )
        )

    asf: Optional[AssistSpecialistFeatures] = bundle.assist
    if asf:
        out.update(
            dict(
                potential_assists=asf.potential_assists,
                touches=asf.touches,
                passes_per_touch=asf.passes_per_touch,
                drive_and_kick_rate=asf.drive_and_kick_rate,
            )
        )

    return out


def attach_features_to_prop(prop: Dict[str, Any], box_row: Dict[str, Any], tracking_row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach specialist features to a prop dict.

    - Builds a typed feature bundle from raw rows
    - Flattens relevant fields onto the prop for existing specialist engines
    - Stores the full bundle under `specialist_features` for debugging
    """
    try:
        bundle = build_feature_bundle(
            player=str(prop.get("player", "")),
            team=prop.get("team"),
            box_row=box_row or {},
            tracking_row=tracking_row or {},
        )
        flat = _flatten_bundle_to_dict(bundle)
        # Attach flattened fields top-level for compatibility with existing engines
        for k, v in flat.items():
            if v is not None:
                prop[k] = v
        # Keep full bundle for diagnostics
        prop["specialist_features"] = flat
        return prop
    except Exception:
        return prop


def attach_features_to_props(props: list[Dict[str, Any]], box_by_player: Dict[str, Dict[str, Any]], tracking_by_player: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Batch attach features to a list of prop dicts.

    Looks up per-player box/tracking rows from provided maps.
    """
    out: list[Dict[str, Any]] = []
    for p in props:
        name = str(p.get("player", ""))
        box = box_by_player.get(name, {})
        track = tracking_by_player.get(name, {})
        out.append(attach_features_to_prop(p, box, track))
    return out
