"""
HOME ICE + TRAVEL FATIGUE SPLINE — NHL v2.0 Module
===================================================

NHL fatigue is nonlinear (especially West→East, altitude, B2B).

Features modeled:
- Miles traveled (rolling 7 days)
- Time zone crossings
- Rest differential
- Altitude (DEN, COL special)

Effect:
- Applies to shot rate and xGA, not raw goals directly

Gates:
- T1: Travel <300 miles → ignore
- T2: Fatigue penalty cap −6%
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────

# Gate thresholds
MIN_TRAVEL_MILES = 300
MAX_FATIGUE_PENALTY = 0.06  # 6% cap

# Time zone definitions (hours from ET)
TIMEZONE_MAP = {
    # Eastern
    "BOS": 0, "BUF": 0, "CAR": 0, "CBJ": 0, "DET": 0,
    "FLA": 0, "MTL": 0, "NJD": 0, "NYI": 0, "NYR": 0,
    "OTT": 0, "PHI": 0, "PIT": 0, "TBL": 0, "TOR": 0, "WSH": 0,
    # Central
    "CHI": -1, "COL": -1, "DAL": -1, "MIN": -1, "NSH": -1,
    "STL": -1, "WPG": -1, "ARI": -1, "UTA": -1,
    # Mountain
    "CGY": -1, "EDM": -1,
    # Pacific
    "ANA": -3, "LAK": -3, "SJS": -3, "SEA": -3, "VAN": -3, "VGK": -3,
}

# Arena altitudes (feet above sea level)
ALTITUDE_MAP = {
    "COL": 5280,  # Denver - Mile High
    "UTA": 4226,  # Utah (formerly ARI)
    "ARI": 4226,  # Arizona (if still used)
    "CGY": 3438,  # Calgary
    "EDM": 2116,  # Edmonton
    # All others are near sea level
}
DEFAULT_ALTITUDE = 100

# Distance matrix (miles between arenas - simplified)
# Full matrix would have all 32x32 combinations
SAMPLE_DISTANCES = {
    ("BOS", "NYR"): 215,
    ("BOS", "MTL"): 315,
    ("BOS", "TOR"): 550,
    ("BOS", "CHI"): 983,
    ("BOS", "DAL"): 1769,
    ("BOS", "COL"): 1960,
    ("BOS", "LAK"): 2984,
    ("BOS", "SEA"): 2993,
    ("NYR", "PHI"): 97,
    ("NYR", "WSH"): 229,
    ("NYR", "PIT"): 371,
    ("NYR", "CHI"): 790,
    ("NYR", "DAL"): 1552,
    ("NYR", "LAK"): 2777,
    ("CHI", "COL"): 1017,
    ("CHI", "DAL"): 917,
    ("CHI", "LAK"): 2015,
    ("DAL", "COL"): 780,
    ("DAL", "LAK"): 1436,
    ("COL", "LAK"): 1023,
    ("COL", "SEA"): 1315,
    ("LAK", "SJS"): 345,
    ("LAK", "SEA"): 1137,
    ("LAK", "VAN"): 1278,
    ("VAN", "CGY"): 675,
    ("VAN", "EDM"): 816,
    ("CGY", "EDM"): 299,
}


def get_distance(team_a: str, team_b: str) -> int:
    """Get distance between two arenas."""
    if team_a == team_b:
        return 0
    
    # Check both orderings
    key = (team_a, team_b)
    if key in SAMPLE_DISTANCES:
        return SAMPLE_DISTANCES[key]
    
    key = (team_b, team_a)
    if key in SAMPLE_DISTANCES:
        return SAMPLE_DISTANCES[key]
    
    # Default estimate based on timezone difference
    tz_diff = abs(TIMEZONE_MAP.get(team_a, 0) - TIMEZONE_MAP.get(team_b, 0))
    return 300 + (tz_diff * 800)  # Rough estimate


def get_timezone_crossing(team_a: str, team_b: str) -> int:
    """Get number of timezone crossings."""
    tz_a = TIMEZONE_MAP.get(team_a, 0)
    tz_b = TIMEZONE_MAP.get(team_b, 0)
    return abs(tz_a - tz_b)


def get_altitude(team: str) -> int:
    """Get arena altitude in feet."""
    return ALTITUDE_MAP.get(team, DEFAULT_ALTITUDE)


# ─────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────

@dataclass
class TravelSchedule:
    """Recent travel history for a team."""
    team: str
    current_location: str
    
    # Rolling 7-day travel
    total_miles_7d: int
    games_played_7d: int
    timezone_changes_7d: int
    
    # Recent rest
    days_since_last_game: int
    is_back_to_back: bool
    
    # Current trip
    games_on_road_trip: int = 0
    
    @property
    def is_heavy_travel(self) -> bool:
        """Team has significant recent travel."""
        return self.total_miles_7d > 3000
    
    @property
    def is_fatigued(self) -> bool:
        """Team is likely fatigued."""
        return (
            self.is_back_to_back or 
            self.games_played_7d >= 4 or
            self.timezone_changes_7d >= 3
        )


@dataclass
class FatigueAdjustment:
    """Result of travel fatigue calculation."""
    team: str
    
    # Inputs
    travel_miles: int
    timezone_crossings: int
    rest_days: int
    is_b2b: bool
    altitude_change: int
    
    # Components (pre-cap)
    distance_penalty: float
    timezone_penalty: float
    rest_bonus: float
    b2b_penalty: float
    altitude_penalty: float
    
    # Final adjustment (capped)
    raw_total: float
    final_adjustment: float
    is_capped: bool
    
    # Application
    is_applicable: bool      # Passes T1 gate
    affected_metrics: List[str]
    risk_tag: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "team": self.team,
            "travel_miles": self.travel_miles,
            "timezone_crossings": self.timezone_crossings,
            "rest_days": self.rest_days,
            "is_b2b": self.is_b2b,
            "distance_penalty": round(self.distance_penalty, 4),
            "timezone_penalty": round(self.timezone_penalty, 4),
            "rest_bonus": round(self.rest_bonus, 4),
            "b2b_penalty": round(self.b2b_penalty, 4),
            "altitude_penalty": round(self.altitude_penalty, 4),
            "raw_total": round(self.raw_total, 4),
            "final_adjustment": round(self.final_adjustment, 4),
            "is_capped": self.is_capped,
            "is_applicable": self.is_applicable,
            "affected_metrics": self.affected_metrics,
            "risk_tag": self.risk_tag,
        }


# ─────────────────────────────────────────────────────────
# FATIGUE CALCULATOR
# ─────────────────────────────────────────────────────────

class TravelFatigueCalculator:
    """
    Calculates performance adjustment based on travel fatigue.
    
    Uses a spline-like approach where penalties increase
    nonlinearly with distance and timezone changes.
    """
    
    # Penalty coefficients
    DISTANCE_COEF = 0.00001      # Per mile
    TIMEZONE_COEF = 0.008        # Per timezone crossed
    B2B_PENALTY = 0.025          # Back-to-back penalty
    REST_BONUS_PER_DAY = 0.005   # Bonus per rest day (max 3 days)
    ALTITUDE_COEF = 0.000005     # Per foot of altitude change
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate(
        self,
        team: str,
        origin: str,
        destination: str,
        rest_days: int,
        is_b2b: bool,
        games_in_7d: int = 0,
        total_miles_7d: int = 0,
    ) -> FatigueAdjustment:
        """
        Calculate fatigue adjustment for a team.
        
        Args:
            team: Team abbreviation
            origin: Where team is coming from
            destination: Arena for this game
            rest_days: Days since last game
            is_b2b: Is this a back-to-back?
            games_in_7d: Games played in last 7 days
            total_miles_7d: Total miles traveled in 7 days
        
        Returns:
            FatigueAdjustment with penalties/bonuses
        """
        # Get travel metrics
        travel_miles = get_distance(origin, destination)
        timezone_crossings = get_timezone_crossing(origin, destination)
        altitude_change = abs(get_altitude(destination) - get_altitude(origin))
        
        # GATE T1: Minimum travel threshold
        if travel_miles < MIN_TRAVEL_MILES:
            self.logger.debug(f"T1 GATE: Travel {travel_miles} mi < {MIN_TRAVEL_MILES} threshold")
            return FatigueAdjustment(
                team=team,
                travel_miles=travel_miles,
                timezone_crossings=timezone_crossings,
                rest_days=rest_days,
                is_b2b=is_b2b,
                altitude_change=altitude_change,
                distance_penalty=0.0,
                timezone_penalty=0.0,
                rest_bonus=0.0,
                b2b_penalty=0.0,
                altitude_penalty=0.0,
                raw_total=0.0,
                final_adjustment=0.0,
                is_capped=False,
                is_applicable=False,
                affected_metrics=[],
                risk_tag=None,
            )
        
        # Calculate component penalties
        
        # Distance: Nonlinear (sqrt) to model diminishing marginal fatigue
        distance_penalty = math.sqrt(travel_miles) * self.DISTANCE_COEF * 10
        
        # Timezone: More impactful for east-to-west
        timezone_penalty = timezone_crossings * self.TIMEZONE_COEF
        
        # Rest bonus (capped at 3 days)
        effective_rest = min(rest_days, 3)
        rest_bonus = effective_rest * self.REST_BONUS_PER_DAY if rest_days > 1 else 0.0
        
        # B2B penalty
        b2b_penalty = self.B2B_PENALTY if is_b2b else 0.0
        
        # Altitude: Only significant for high altitude destinations
        altitude_penalty = 0.0
        if altitude_change > 3000:  # Significant altitude change
            altitude_penalty = altitude_change * self.ALTITUDE_COEF
        
        # Heavy schedule multiplier
        schedule_multiplier = 1.0
        if games_in_7d >= 4:
            schedule_multiplier = 1.15
        elif games_in_7d >= 3:
            schedule_multiplier = 1.05
        
        # Calculate raw total (negative = penalty)
        raw_total = -(
            (distance_penalty + timezone_penalty + b2b_penalty + altitude_penalty) 
            * schedule_multiplier
        ) + rest_bonus
        
        # GATE T2: Cap at maximum penalty
        is_capped = False
        final_adjustment = raw_total
        
        if final_adjustment < -MAX_FATIGUE_PENALTY:
            final_adjustment = -MAX_FATIGUE_PENALTY
            is_capped = True
        
        # Determine risk tag
        risk_tag = None
        if is_b2b and travel_miles > 1000:
            risk_tag = "HEAVY_B2B_TRAVEL"
        elif timezone_crossings >= 3:
            risk_tag = "CROSS_COUNTRY_TRAVEL"
        elif altitude_change > 4000:
            risk_tag = "HIGH_ALTITUDE_TRAVEL"
        elif final_adjustment < -0.03:
            risk_tag = "TRAVEL_FATIGUE"
        
        return FatigueAdjustment(
            team=team,
            travel_miles=travel_miles,
            timezone_crossings=timezone_crossings,
            rest_days=rest_days,
            is_b2b=is_b2b,
            altitude_change=altitude_change,
            distance_penalty=distance_penalty,
            timezone_penalty=timezone_penalty,
            rest_bonus=rest_bonus,
            b2b_penalty=b2b_penalty,
            altitude_penalty=altitude_penalty,
            raw_total=raw_total,
            final_adjustment=final_adjustment,
            is_capped=is_capped,
            is_applicable=True,
            affected_metrics=["shot_rate", "xga"],
            risk_tag=risk_tag,
        )


def calculate_travel_adjustment(
    team: str,
    origin: str,
    destination: str,
    rest_days: int,
    is_b2b: bool = False,
) -> FatigueAdjustment:
    """
    Convenience function to calculate travel fatigue.
    
    Args:
        team: Team abbreviation
        origin: Previous game location
        destination: Current game location
        rest_days: Days since last game
        is_b2b: Is back-to-back?
    
    Returns:
        FatigueAdjustment
    """
    calculator = TravelFatigueCalculator()
    return calculator.calculate(
        team=team,
        origin=origin,
        destination=destination,
        rest_days=rest_days,
        is_b2b=is_b2b,
    )


# ─────────────────────────────────────────────────────────
# HOME ICE ADVANTAGE
# ─────────────────────────────────────────────────────────

@dataclass
class HomeIceAdvantage:
    """Home ice advantage calculation."""
    team: str
    base_advantage: float = 0.035  # 3.5% base
    
    # Modifiers
    altitude_boost: float = 0.0
    travel_opponent_penalty: float = 0.0
    
    # Final
    total_advantage: float = 0.0
    
    def calculate(
        self,
        opponent_fatigue: Optional[FatigueAdjustment] = None,
    ) -> float:
        """
        Calculate total home ice advantage.
        
        Args:
            opponent_fatigue: Opponent's travel fatigue adjustment
        
        Returns:
            Total home ice advantage multiplier
        """
        self.total_advantage = self.base_advantage
        
        # Altitude boost (for COL, UTA)
        altitude = get_altitude(self.team)
        if altitude > 4000:
            self.altitude_boost = 0.015  # Extra 1.5% for high altitude
            self.total_advantage += self.altitude_boost
        
        # Opponent travel penalty adds to home advantage
        if opponent_fatigue and opponent_fatigue.is_applicable:
            # Convert opponent penalty to home advantage
            self.travel_opponent_penalty = abs(opponent_fatigue.final_adjustment) * 0.5
            self.total_advantage += self.travel_opponent_penalty
        
        return self.total_advantage


# ─────────────────────────────────────────────────────────
# DEMO / SELF-TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "=" * 60)
    print("TRAVEL FATIGUE MODULE — NHL v2.0 DEMO")
    print("=" * 60)
    
    # Demo 1: Cross-country road trip
    print("\n--- SCENARIO 1: Cross-Country Trip ---")
    adj1 = calculate_travel_adjustment(
        team="BOS",
        origin="LAK",
        destination="SEA",
        rest_days=0,
        is_b2b=True,
    )
    
    print(f"Team: {adj1.team}")
    print(f"Travel: {adj1.travel_miles} miles")
    print(f"Timezone crossings: {adj1.timezone_crossings}")
    print(f"B2B: {adj1.is_b2b}")
    print(f"Components:")
    print(f"  Distance penalty: {adj1.distance_penalty:+.4f}")
    print(f"  Timezone penalty: {adj1.timezone_penalty:+.4f}")
    print(f"  B2B penalty: {adj1.b2b_penalty:+.4f}")
    print(f"  Altitude penalty: {adj1.altitude_penalty:+.4f}")
    print(f"  Rest bonus: {adj1.rest_bonus:+.4f}")
    print(f"Final adjustment: {adj1.final_adjustment:+.4f}")
    print(f"Capped: {adj1.is_capped}")
    print(f"Risk tag: {adj1.risk_tag}")
    
    # Demo 2: Short trip (should be ignored)
    print("\n--- SCENARIO 2: Short Trip (T1 Gate) ---")
    adj2 = calculate_travel_adjustment(
        team="NYR",
        origin="NJD",
        destination="PHI",
        rest_days=2,
        is_b2b=False,
    )
    
    print(f"Travel: {adj2.travel_miles} miles")
    print(f"Applicable: {adj2.is_applicable}")
    print(f"Final adjustment: {adj2.final_adjustment:+.4f}")
    
    # Demo 3: High altitude destination
    print("\n--- SCENARIO 3: High Altitude (COL) ---")
    adj3 = calculate_travel_adjustment(
        team="FLA",
        origin="FLA",
        destination="COL",
        rest_days=1,
        is_b2b=False,
    )
    
    print(f"Travel: {adj3.travel_miles} miles")
    print(f"Altitude change: {adj3.altitude_change} ft")
    print(f"Altitude penalty: {adj3.altitude_penalty:+.4f}")
    print(f"Final adjustment: {adj3.final_adjustment:+.4f}")
    print(f"Risk tag: {adj3.risk_tag}")
    
    # Demo 4: Home ice advantage with fatigued opponent
    print("\n--- SCENARIO 4: Home Ice Advantage ---")
    home_ice = HomeIceAdvantage(team="COL")
    total_hia = home_ice.calculate(opponent_fatigue=adj3)
    
    print(f"Base advantage: {home_ice.base_advantage:.3f}")
    print(f"Altitude boost: {home_ice.altitude_boost:.3f}")
    print(f"Opponent fatigue bonus: {home_ice.travel_opponent_penalty:.3f}")
    print(f"Total home ice: {home_ice.total_advantage:.3f} ({home_ice.total_advantage*100:.1f}%)")
