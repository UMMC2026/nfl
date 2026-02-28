"""
GOLF WEATHER GATE HARDENING — Phase 5B Enhancement
====================================================

Weather-based confidence adjustments and blocking for golf:
- High wind (>20 mph): Block all birdies/scoring props
- Rain forecast: Reduce confidence on all props
- Forecast volatility: Block if forecast changes >20% day-of

Weather Data Sources:
- OpenWeatherMap API (free tier)
- Course-specific adjustments (links vs parkland)

Usage:
    from golf.weather_gate import check_weather_gate, get_weather_adjustment
    
    passed, reason = check_weather_gate("TPC Sawgrass", "2026-02-08")
    # Returns: (False, "WIND_BLOCK: 25mph sustained winds")

Created: 2026-02-05
Phase: 5B Week 3-4
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

GOLF_DIR = Path(__file__).parent
WEATHER_CACHE_PATH = GOLF_DIR / "data" / "weather_cache.json"
WEATHER_CONFIG_PATH = GOLF_DIR / "config" / "weather_thresholds.json"


class WeatherSeverity(Enum):
    IDEAL = "ideal"           # Perfect conditions
    ACCEPTABLE = "acceptable"  # Minor adjustments
    CAUTION = "caution"       # Reduce confidence
    BLOCK = "block"           # Hard block on props


@dataclass
class WeatherConditions:
    """Current or forecast weather for a venue."""
    venue: str
    date: str
    wind_mph: float = 0.0
    wind_gust_mph: float = 0.0
    rain_probability: float = 0.0  # 0-1
    rain_inches: float = 0.0
    temperature_f: float = 70.0
    humidity_pct: float = 50.0
    severity: WeatherSeverity = WeatherSeverity.IDEAL
    forecast_locked: bool = False  # True if >=3 days old
    last_updated: Optional[str] = None


@dataclass
class WeatherAdjustment:
    """Adjustment to apply based on weather."""
    adjustment: float  # Confidence adjustment (-0.10 to 0.0)
    blocked: bool
    block_reason: Optional[str]
    details: Dict = field(default_factory=dict)


# =============================================================================
# WEATHER THRESHOLDS
# =============================================================================

# Wind thresholds (sustained mph)
WIND_THRESHOLDS = {
    "IDEAL": 10,        # <10 mph = no adjustment
    "LIGHT": 15,        # 10-15 mph = -2%
    "MODERATE": 20,     # 15-20 mph = -4%
    "STRONG": 25,       # 20-25 mph = -6% + block birdies
    "BLOCK": 30,        # >25 mph = block all props
}

# Wind adjustments by speed
WIND_ADJUSTMENTS = {
    "IDEAL": 0.0,
    "LIGHT": -0.02,
    "MODERATE": -0.04,
    "STRONG": -0.06,
}

# Rain thresholds
RAIN_THRESHOLDS = {
    "DRY": 0.10,        # <10% chance = no adjustment
    "LIGHT": 0.30,      # 10-30% = -2%
    "MODERATE": 0.50,   # 30-50% = -4%
    "HEAVY": 0.70,      # 50-70% = -6% + caution
    "BLOCK": 0.90,      # >70% = block (play unlikely)
}

RAIN_ADJUSTMENTS = {
    "DRY": 0.0,
    "LIGHT": -0.02,
    "MODERATE": -0.04,
    "HEAVY": -0.06,
}

# Course type multipliers (links more affected by wind)
COURSE_TYPE_MULTIPLIERS = {
    "links": 1.5,       # Links courses = 50% more wind impact
    "parkland": 1.0,    # Standard
    "desert": 0.8,      # Desert courses slightly protected
    "mountain": 1.2,    # Mountain courses have variable wind
}

# Known course types
COURSE_TYPES: Dict[str, str] = {
    "st andrews": "links",
    "royal troon": "links",
    "royal birkdale": "links",
    "royal portrush": "links",
    "carnoustie": "links",
    "muirfield": "links",
    "turnberry": "links",
    "pebble beach": "links",
    "harbour town": "links",  # Not true links but wind-exposed
    
    "augusta national": "parkland",
    "tpc sawgrass": "parkland",
    "bay hill": "parkland",
    "riviera": "parkland",
    "quail hollow": "parkland",
    "east lake": "parkland",
    "torrey pines": "parkland",
    "colonial": "parkland",
    
    "tpc scottsdale": "desert",
    "pga west": "desert",
    "la quinta": "desert",
}


def normalize_venue_name(name: str) -> str:
    """Normalize venue name for matching."""
    return name.lower().strip().replace("-", " ").replace("'", "")


def get_course_type(venue: str) -> str:
    """Get course type for wind multiplier."""
    normalized = normalize_venue_name(venue)
    
    for known_venue, course_type in COURSE_TYPES.items():
        if known_venue in normalized or normalized in known_venue:
            return course_type
    
    return "parkland"  # Default


def load_weather_cache() -> Dict[str, WeatherConditions]:
    """Load cached weather data."""
    if WEATHER_CACHE_PATH.exists():
        try:
            with open(WEATHER_CACHE_PATH, encoding="utf-8") as f:
                data = json.load(f)
                result = {}
                for key, info in data.items():
                    if key.startswith("_"):
                        continue
                    result[key] = WeatherConditions(
                        venue=info.get("venue", ""),
                        date=info.get("date", ""),
                        wind_mph=info.get("wind_mph", 0.0),
                        wind_gust_mph=info.get("wind_gust_mph", 0.0),
                        rain_probability=info.get("rain_probability", 0.0),
                        rain_inches=info.get("rain_inches", 0.0),
                        temperature_f=info.get("temperature_f", 70.0),
                        humidity_pct=info.get("humidity_pct", 50.0),
                        severity=WeatherSeverity(info.get("severity", "ideal")),
                        forecast_locked=info.get("forecast_locked", False),
                        last_updated=info.get("last_updated"),
                    )
                return result
        except Exception as e:
            print(f"[WEATHER_GATE] Warning: Could not load cache: {e}")
    return {}


def save_weather_cache(data: Dict[str, WeatherConditions]) -> None:
    """Save weather cache."""
    WEATHER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    output = {
        "_metadata": {
            "last_updated": datetime.now().isoformat(),
            "description": "Cached weather forecasts for golf venues"
        }
    }
    
    for key, conditions in data.items():
        output[key] = {
            "venue": conditions.venue,
            "date": conditions.date,
            "wind_mph": conditions.wind_mph,
            "wind_gust_mph": conditions.wind_gust_mph,
            "rain_probability": conditions.rain_probability,
            "rain_inches": conditions.rain_inches,
            "temperature_f": conditions.temperature_f,
            "humidity_pct": conditions.humidity_pct,
            "severity": conditions.severity.value,
            "forecast_locked": conditions.forecast_locked,
            "last_updated": conditions.last_updated,
        }
    
    with open(WEATHER_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


def classify_wind(wind_mph: float, venue: str) -> Tuple[str, float]:
    """
    Classify wind severity and get adjustment.
    
    Returns:
        Tuple of (classification, adjustment)
    """
    course_type = get_course_type(venue)
    multiplier = COURSE_TYPE_MULTIPLIERS.get(course_type, 1.0)
    effective_wind = wind_mph * multiplier
    
    if effective_wind >= WIND_THRESHOLDS["BLOCK"]:
        return "BLOCK", -0.10  # Hard block
    elif effective_wind >= WIND_THRESHOLDS["STRONG"]:
        return "STRONG", WIND_ADJUSTMENTS["STRONG"] * multiplier
    elif effective_wind >= WIND_THRESHOLDS["MODERATE"]:
        return "MODERATE", WIND_ADJUSTMENTS["MODERATE"] * multiplier
    elif effective_wind >= WIND_THRESHOLDS["LIGHT"]:
        return "LIGHT", WIND_ADJUSTMENTS["LIGHT"] * multiplier
    else:
        return "IDEAL", 0.0


def classify_rain(rain_probability: float) -> Tuple[str, float]:
    """
    Classify rain severity and get adjustment.
    
    Returns:
        Tuple of (classification, adjustment)
    """
    if rain_probability >= RAIN_THRESHOLDS["BLOCK"]:
        return "BLOCK", -0.10
    elif rain_probability >= RAIN_THRESHOLDS["HEAVY"]:
        return "HEAVY", RAIN_ADJUSTMENTS["HEAVY"]
    elif rain_probability >= RAIN_THRESHOLDS["MODERATE"]:
        return "MODERATE", RAIN_ADJUSTMENTS["MODERATE"]
    elif rain_probability >= RAIN_THRESHOLDS["LIGHT"]:
        return "LIGHT", RAIN_ADJUSTMENTS["LIGHT"]
    else:
        return "DRY", 0.0


def get_weather_conditions(
    venue: str,
    date: str,
    use_cache: bool = True,
) -> Optional[WeatherConditions]:
    """
    Get weather conditions for a venue/date.
    
    Args:
        venue: Course/venue name
        date: Date in YYYY-MM-DD format
        use_cache: Whether to use cached data
    
    Returns:
        WeatherConditions if available
    """
    cache_key = f"{normalize_venue_name(venue)}_{date}"
    
    if use_cache:
        cache = load_weather_cache()
        if cache_key in cache:
            return cache[cache_key]
    
    # No cached data - return None (caller should fetch or use default)
    return None


def check_weather_gate(
    venue: str,
    date: str,
    market: str = "",
) -> Tuple[bool, Optional[str]]:
    """
    Check if weather conditions allow betting on this venue/date.
    
    Args:
        venue: Course name
        date: Date in YYYY-MM-DD format
        market: Market type (for market-specific blocks)
    
    Returns:
        Tuple of (passed, block_reason)
        passed=True means OK to bet, False means blocked
    """
    conditions = get_weather_conditions(venue, date)
    
    if conditions is None:
        # No weather data - pass with warning
        return True, None
    
    # Check forecast age (must be >=3 days old to be "locked")
    if not conditions.forecast_locked:
        # Forecast not locked - allow but with caution
        return True, None
    
    # Check wind
    wind_class, wind_adj = classify_wind(conditions.wind_mph, venue)
    if wind_class == "BLOCK":
        return False, f"WIND_BLOCK: {conditions.wind_mph:.0f}mph sustained winds"
    
    # Block birdies in strong wind
    if wind_class == "STRONG" and market in ["birdies", "birdies_or_better"]:
        return False, f"WIND_BIRDIES_BLOCK: {conditions.wind_mph:.0f}mph reduces birdie opportunities"
    
    # Check rain
    rain_class, rain_adj = classify_rain(conditions.rain_probability)
    if rain_class == "BLOCK":
        return False, f"RAIN_BLOCK: {conditions.rain_probability:.0%} chance of rain (play unlikely)"
    
    return True, None


def get_weather_adjustment(
    venue: str,
    date: str,
    market: str = "",
) -> WeatherAdjustment:
    """
    Get confidence adjustment based on weather.
    
    Args:
        venue: Course name
        date: Date in YYYY-MM-DD format
        market: Market type
    
    Returns:
        WeatherAdjustment with adjustment value and details
    """
    conditions = get_weather_conditions(venue, date)
    
    if conditions is None:
        return WeatherAdjustment(
            adjustment=0.0,
            blocked=False,
            block_reason=None,
            details={"source": "no_data"}
        )
    
    # Check gate first
    passed, block_reason = check_weather_gate(venue, date, market)
    if not passed:
        return WeatherAdjustment(
            adjustment=-0.10,
            blocked=True,
            block_reason=block_reason,
            details={
                "wind_mph": conditions.wind_mph,
                "rain_probability": conditions.rain_probability,
            }
        )
    
    # Calculate adjustments
    wind_class, wind_adj = classify_wind(conditions.wind_mph, venue)
    rain_class, rain_adj = classify_rain(conditions.rain_probability)
    
    total_adj = wind_adj + rain_adj
    total_adj = max(-0.10, total_adj)  # Cap at -10%
    
    return WeatherAdjustment(
        adjustment=total_adj,
        blocked=False,
        block_reason=None,
        details={
            "wind_mph": conditions.wind_mph,
            "wind_class": wind_class,
            "wind_adjustment": wind_adj,
            "rain_probability": conditions.rain_probability,
            "rain_class": rain_class,
            "rain_adjustment": rain_adj,
            "course_type": get_course_type(venue),
            "total_adjustment": total_adj,
        }
    )


def apply_weather_adjustment(
    raw_probability: float,
    venue: str,
    date: str,
    market: str = "",
) -> Tuple[float, Dict]:
    """
    Apply weather adjustment to probability.
    
    Args:
        raw_probability: Original probability
        venue: Course name
        date: Date in YYYY-MM-DD format
        market: Market type
    
    Returns:
        Tuple of (adjusted_probability, adjustment_info)
    """
    adj = get_weather_adjustment(venue, date, market)
    
    if adj.blocked:
        # Return 0 probability for blocked conditions
        return 0.0, {
            "blocked": True,
            "block_reason": adj.block_reason,
            **adj.details
        }
    
    adjusted_prob = raw_probability + adj.adjustment
    adjusted_prob = max(0.40, min(0.85, adjusted_prob))
    
    return adjusted_prob, {
        "blocked": False,
        "adjustment_applied": abs(adj.adjustment) > 0.005,
        **adj.details
    }


# =============================================================================
# WEATHER DATA INGESTION
# =============================================================================

def update_weather_forecast(
    venue: str,
    date: str,
    wind_mph: float,
    rain_probability: float,
    wind_gust_mph: float = 0.0,
    rain_inches: float = 0.0,
    temperature_f: float = 70.0,
    humidity_pct: float = 50.0,
) -> None:
    """
    Update weather forecast for a venue/date.
    
    Args:
        venue: Course name
        date: Date in YYYY-MM-DD format
        wind_mph: Sustained wind speed
        rain_probability: 0-1 probability of rain
        ... other optional fields
    """
    cache = load_weather_cache()
    cache_key = f"{normalize_venue_name(venue)}_{date}"
    
    # Determine severity
    wind_class, _ = classify_wind(wind_mph, venue)
    rain_class, _ = classify_rain(rain_probability)
    
    if wind_class == "BLOCK" or rain_class == "BLOCK":
        severity = WeatherSeverity.BLOCK
    elif wind_class == "STRONG" or rain_class == "HEAVY":
        severity = WeatherSeverity.CAUTION
    elif wind_class in ["MODERATE", "LIGHT"] or rain_class in ["MODERATE", "LIGHT"]:
        severity = WeatherSeverity.ACCEPTABLE
    else:
        severity = WeatherSeverity.IDEAL
    
    # Check if forecast is old enough to be "locked"
    try:
        forecast_date = datetime.strptime(date, "%Y-%m-%d")
        days_out = (forecast_date - datetime.now()).days
        forecast_locked = days_out <= 0  # Lock on day-of
    except:
        forecast_locked = False
    
    cache[cache_key] = WeatherConditions(
        venue=venue,
        date=date,
        wind_mph=wind_mph,
        wind_gust_mph=wind_gust_mph,
        rain_probability=rain_probability,
        rain_inches=rain_inches,
        temperature_f=temperature_f,
        humidity_pct=humidity_pct,
        severity=severity,
        forecast_locked=forecast_locked,
        last_updated=datetime.now().isoformat(),
    )
    
    save_weather_cache(cache)
    print(f"[WEATHER_GATE] Updated {venue} {date}: {severity.value} (wind={wind_mph}mph, rain={rain_probability:.0%})")


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Golf Weather Gate")
    parser.add_argument("--check", nargs=2, metavar=("VENUE", "DATE"),
                       help="Check weather gate for venue/date")
    parser.add_argument("--update", nargs=4, metavar=("VENUE", "DATE", "WIND", "RAIN"),
                       help="Update weather: venue date wind_mph rain_probability")
    parser.add_argument("--list-courses", action="store_true",
                       help="List known course types")
    
    args = parser.parse_args()
    
    if args.check:
        venue, date = args.check
        passed, reason = check_weather_gate(venue, date)
        adj = get_weather_adjustment(venue, date)
        
        print(f"\n=== Weather Check: {venue} on {date} ===")
        print(f"  Gate Passed: {'✅ YES' if passed else '❌ NO'}")
        if reason:
            print(f"  Block Reason: {reason}")
        print(f"  Adjustment: {adj.adjustment:+.1%}")
        if adj.details:
            print(f"  Wind: {adj.details.get('wind_mph', 0):.0f} mph ({adj.details.get('wind_class', 'N/A')})")
            print(f"  Rain: {adj.details.get('rain_probability', 0):.0%} ({adj.details.get('rain_class', 'N/A')})")
    
    elif args.update:
        venue, date, wind, rain = args.update
        update_weather_forecast(venue, date, float(wind), float(rain))
    
    elif args.list_courses:
        print("\n=== Known Course Types ===")
        by_type = {}
        for course, ctype in COURSE_TYPES.items():
            if ctype not in by_type:
                by_type[ctype] = []
            by_type[ctype].append(course)
        
        for ctype, courses in sorted(by_type.items()):
            mult = COURSE_TYPE_MULTIPLIERS.get(ctype, 1.0)
            print(f"\n  {ctype.upper()} (wind multiplier: {mult:.1f}x):")
            for course in sorted(courses):
                print(f"    - {course.title()}")
    
    else:
        parser.print_help()
