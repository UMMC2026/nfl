"""
Specialist feature schema and ingestion stubs.

Defines typed containers for global and specialist-specific tracking fields,
plus helper signatures for deriving features from raw tracking/box data.

This is the canonical place to declare required fields for the specialist system.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class StatSpecialistType(Enum):
    GENERIC = "GENERIC"
    CATCH_AND_SHOOT_3PM = "CATCH_AND_SHOOT_3PM"
    PICK_AND_POP_BIG = "PICK_AND_POP_BIG"
    MIDRANGE_SPECIALIST = "MIDRANGE_SPECIALIST"
    BIG_POST_RIM_RUNNER = "BIG_POST_RIM_RUNNER"
    ASSIST_SPECIALIST = "ASSIST_SPECIALIST"


@dataclass
class GlobalFeatures:
    minutes: Optional[float] = None
    usage_rate: Optional[float] = None
    assisted_fg_rate: Optional[float] = None
    time_of_possession: Optional[float] = None
    avg_shot_distance: Optional[float] = None
    bench_minutes_rate: Optional[float] = None
    usage_volatility: Optional[float] = None  # rolling σ


@dataclass
class Shooting3PMFeatures:
    three_pa: Optional[float] = None
    three_pm: Optional[float] = None
    assisted_3pa_rate: Optional[float] = None
    pullup_3pa_rate: Optional[float] = None
    dribbles_per_shot: Optional[float] = None
    corner_3_rate: Optional[float] = None
    shot_quality_3: Optional[float] = None  # expected value quality score


@dataclass
class PickAndPopBigFeatures:
    position: Optional[str] = None
    avg_3pa: Optional[float] = None
    pick_and_pop_rate: Optional[float] = None
    above_break_3_rate: Optional[float] = None
    trailer_3_rate: Optional[float] = None


@dataclass
class MidrangeFeatures:
    midrange_fga_rate: Optional[float] = None
    rim_fga_rate: Optional[float] = None
    elbow_touch_rate: Optional[float] = None
    shot_clock_usage_mid: Optional[float] = None


@dataclass
class BigPostRimRunnerFeatures:
    post_touch_rate: Optional[float] = None
    paint_fga_rate: Optional[float] = None
    roll_man_frequency: Optional[float] = None
    putback_rate: Optional[float] = None


@dataclass
class AssistSpecialistFeatures:
    potential_assists: Optional[float] = None
    touches: Optional[float] = None
    passes_per_touch: Optional[float] = None
    drive_and_kick_rate: Optional[float] = None


@dataclass
class SpecialistFeatureBundle:
    player: str
    team: Optional[str]
    global_features: GlobalFeatures
    three_point: Optional[Shooting3PMFeatures] = None
    pick_and_pop: Optional[PickAndPopBigFeatures] = None
    midrange: Optional[MidrangeFeatures] = None
    big_post: Optional[BigPostRimRunnerFeatures] = None
    assist: Optional[AssistSpecialistFeatures] = None


def derive_global_features(box_row: Dict[str, Any], tracking_row: Dict[str, Any]) -> GlobalFeatures:
    """Derive global features from box + tracking.

    Expected keys (examples):
      - box_row: {"minutes": ..., "usage_rate": ..., "bench_minutes_rate": ...}
      - tracking_row: {"assisted_fg_rate": ..., "time_of_possession": ..., "avg_shot_distance": ...}

    usage_volatility is a rolling σ computed upstream and passed in tracking_row.
    """
    return GlobalFeatures(
        minutes=box_row.get("minutes"),
        usage_rate=box_row.get("usage_rate"),
        assisted_fg_rate=tracking_row.get("assisted_fg_rate"),
        time_of_possession=tracking_row.get("time_of_possession"),
        avg_shot_distance=tracking_row.get("avg_shot_distance"),
        bench_minutes_rate=box_row.get("bench_minutes_rate"),
        usage_volatility=tracking_row.get("usage_volatility"),
    )


def derive_three_point_features(tracking_row: Dict[str, Any]) -> Shooting3PMFeatures:
    return Shooting3PMFeatures(
        three_pa=tracking_row.get("3pa"),
        three_pm=tracking_row.get("3pm"),
        assisted_3pa_rate=tracking_row.get("assisted_3pa_rate"),
        pullup_3pa_rate=tracking_row.get("pullup_3pa_rate"),
        dribbles_per_shot=tracking_row.get("dribbles_per_shot"),
        corner_3_rate=tracking_row.get("corner_3_rate"),
        shot_quality_3=tracking_row.get("shot_quality_3"),
    )


def derive_pick_and_pop_features(tracking_row: Dict[str, Any]) -> PickAndPopBigFeatures:
    return PickAndPopBigFeatures(
        position=tracking_row.get("position"),
        avg_3pa=tracking_row.get("avg_3pa"),
        pick_and_pop_rate=tracking_row.get("pick_and_pop_rate"),
        above_break_3_rate=tracking_row.get("above_break_3_rate"),
        trailer_3_rate=tracking_row.get("trailer_3_rate"),
    )


def derive_midrange_features(tracking_row: Dict[str, Any]) -> MidrangeFeatures:
    return MidrangeFeatures(
        midrange_fga_rate=tracking_row.get("midrange_fga_rate"),
        rim_fga_rate=tracking_row.get("rim_fga_rate"),
        elbow_touch_rate=tracking_row.get("elbow_touch_rate"),
        shot_clock_usage_mid=tracking_row.get("shot_clock_usage_mid"),
    )


def derive_big_post_features(tracking_row: Dict[str, Any]) -> BigPostRimRunnerFeatures:
    return BigPostRimRunnerFeatures(
        post_touch_rate=tracking_row.get("post_touch_rate"),
        paint_fga_rate=tracking_row.get("paint_fga_rate"),
        roll_man_frequency=tracking_row.get("roll_man_frequency"),
        putback_rate=tracking_row.get("putback_rate"),
    )


def derive_assist_features(tracking_row: Dict[str, Any]) -> AssistSpecialistFeatures:
    return AssistSpecialistFeatures(
        potential_assists=tracking_row.get("potential_assists"),
        touches=tracking_row.get("touches"),
        passes_per_touch=tracking_row.get("passes_per_touch"),
        drive_and_kick_rate=tracking_row.get("drive_and_kick_rate"),
    )


def build_feature_bundle(player: str, team: Optional[str], box_row: Dict[str, Any], tracking_row: Dict[str, Any]) -> SpecialistFeatureBundle:
    """Build a complete feature bundle for a player.

    All sub-features are optional; populate the ones your pipeline supports.
    """
    return SpecialistFeatureBundle(
        player=player,
        team=team,
        global_features=derive_global_features(box_row, tracking_row),
        three_point=derive_three_point_features(tracking_row) if tracking_row else None,
        pick_and_pop=derive_pick_and_pop_features(tracking_row) if tracking_row else None,
        midrange=derive_midrange_features(tracking_row) if tracking_row else None,
        big_post=derive_big_post_features(tracking_row) if tracking_row else None,
        assist=derive_assist_features(tracking_row) if tracking_row else None,
    )
