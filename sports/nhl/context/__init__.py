"""NHL Context Module — Referee Bias + Travel Fatigue v2.0"""
from sports.nhl.context.ref_bias import (
    RefereeProfile,
    TeamPPProfile,
    RefBiasAdjustment,
    RefTendency,
    RefereeBiasCalculator,
    calculate_ref_bias_for_game,
    get_referee_profile,
    SAMPLE_REFEREES,
)
from sports.nhl.context.travel_fatigue import (
    TravelSchedule,
    FatigueAdjustment,
    HomeIceAdvantage,
    TravelFatigueCalculator,
    calculate_travel_adjustment,
    get_distance,
    get_timezone_crossing,
    get_altitude,
)

__all__ = [
    # Referee bias
    "RefereeProfile",
    "TeamPPProfile",
    "RefBiasAdjustment",
    "RefTendency",
    "RefereeBiasCalculator",
    "calculate_ref_bias_for_game",
    "get_referee_profile",
    "SAMPLE_REFEREES",
    # Travel fatigue
    "TravelSchedule",
    "FatigueAdjustment",
    "HomeIceAdvantage",
    "TravelFatigueCalculator",
    "calculate_travel_adjustment",
    "get_distance",
    "get_timezone_crossing",
    "get_altitude",
]
