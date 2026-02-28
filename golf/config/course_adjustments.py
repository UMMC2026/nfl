"""
Golf Course Adjustments
=======================
Course-specific scoring adjustments for Monte Carlo simulations.
Supports both hardcoded Python config (legacy) and external JSON config.
"""

import sys
import json
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

# Ensure project root is in path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# =============================================================================
# JSON CONFIG LOADER (allows real-time updates without code deployment)
# =============================================================================

_CONFIG_DIR = Path(__file__).parent
_COURSES_JSON = _CONFIG_DIR / "courses.json"
_cached_json_config: Optional[Dict] = None
_json_load_time: Optional[datetime] = None
_JSON_CACHE_TTL_SECONDS = 300  # Reload JSON every 5 minutes


def load_course_config_from_json() -> Dict[str, Any]:
    """
    Load course config from external JSON file.
    Caches result and auto-reloads if file is stale.
    
    Returns:
        Dict with course configurations or empty dict if file not found
    """
    global _cached_json_config, _json_load_time
    
    # Check if we have a valid cached config
    if _cached_json_config is not None and _json_load_time is not None:
        age = (datetime.now() - _json_load_time).total_seconds()
        if age < _JSON_CACHE_TTL_SECONDS:
            return _cached_json_config
    
    # Load from JSON
    if not _COURSES_JSON.exists():
        print(f"[COURSE_CONFIG] JSON config not found at {_COURSES_JSON}, using hardcoded")
        return {}
    
    try:
        with open(_COURSES_JSON, "r") as f:
            config = json.load(f)
        _cached_json_config = config
        _json_load_time = datetime.now()
        print(f"[COURSE_CONFIG] Loaded JSON config: {len(config.get('courses', {}))} courses")
        return config
    except Exception as e:
        print(f"[COURSE_CONFIG] Error loading JSON: {e}")
        return {}


def get_course_from_json(
    tournament: str,
    course: str = None,
    round_num: int = 0,
    wave: str = None
) -> Optional[Dict[str, Any]]:
    """
    Get course adjustment from JSON config.
    
    Args:
        tournament: Tournament name (matched against aliases in JSON)
        course: Specific course variant (e.g., "south", "north")
        round_num: Round number for round-specific adjustments
        wave: "AM" or "PM" for tee-time adjustments
        
    Returns:
        Dict with course adjustments or None if not found in JSON
    """
    config = load_course_config_from_json()
    if not config or "courses" not in config:
        return None
    
    tournament_lower = tournament.lower() if tournament else ""
    
    # Find matching course by alias
    for course_key, course_data in config["courses"].items():
        aliases = [a.lower() for a in course_data.get("aliases", [])]
        if any(alias in tournament_lower for alias in aliases):
            # Found match - now get round-specific data
            rounds = course_data.get("rounds", {})
            
            # Sunday (R4) gets specific config if available
            round_key = "sunday" if round_num == 4 and "sunday" in rounds else "default"
            round_data = rounds.get(round_key, rounds.get("default", {}))
            
            # Build result
            result = {
                "scoring_adjustment": round_data.get("difficulty_adjustment", 0.0),
                "birdie_factor": round_data.get("birdie_factor", 1.0),
                "bogey_factor": round_data.get("bogey_factor", 1.0),
                "scoring_stddev": round_data.get("scoring_stddev", 3.0),
                "course_notes": round_data.get("notes", ""),
                "difficulty_rank": round_data.get("difficulty_rank"),
                "course_name": course_data.get("name", course_key),
                "source": "json",
            }
            
            # Apply wave adjustment
            if wave:
                wave_adj = course_data.get("wave_adjustments", {}).get(wave, {})
                result["scoring_adjustment"] += wave_adj.get("scoring_adjustment", 0)
                result["wave"] = wave
            
            return result
    
    return None

# =============================================================================
# TORREY PINES (FARMERS INSURANCE OPEN) - SPECIFIC DATA
# =============================================================================

TORREY_PINES_ADJUSTMENTS = {
    "south_course": {
        "par": 72,
        "scoring_avg": 72.8,  # Plays 0.8 over par on average
        "difficulty_adjustment": +0.8,  # Add to player avg
        "birdie_factor": 0.85,  # Reduce birdie rate by 15%
        "bogey_factor": 1.20,  # Increase bogey rate by 20%
        "notes": "Long, punishing rough, Poa annua greens",
    },
    "south_course_sunday": {
        # 2026 R4 SUNDAY-SPECIFIC DATA (CDI = Course Difficulty Index)
        # Based on R1-R3 performance + historical Sunday priors
        "par": 72,
        "scoring_avg": 73.25,  # +1.25 over par - Sunday spike
        "difficulty_adjustment": +1.25,  # "Torrey Tax" for R4
        "birdie_factor": 0.75,  # Field birdie rate 14.2% (below tour avg)
        "bogey_factor": 1.35,  # Field bogey+ rate 21.8%
        "scoring_stddev": 3.1,  # High volatility
        "difficulty_rank": 2,  # 2nd toughest non-major on 2026 schedule
        "notes": "Sunday pins, firm greens, 21.8% bogey rate, punishing rough",
    },
    "north_course": {
        "par": 72,
        "scoring_avg": 71.2,  # Plays 0.8 under typical
        "difficulty_adjustment": -0.3,
        "birdie_factor": 1.10,  # 10% more birdies
        "bogey_factor": 0.95,
        "notes": "Shorter, more scorable",
    },
}

# =============================================================================
# AM/PM WAVE ADJUSTMENTS
# =============================================================================

WAVE_ADJUSTMENTS = {
    # Morning wave typically gets better conditions
    "AM": {
        "scoring_adjustment": -0.3,  # ~0.3 strokes better
        "wind_factor": 0.85,
        "notes": "Less wind, softer greens",
    },
    # Afternoon wave faces afternoon winds
    "PM": {
        "scoring_adjustment": +0.4,  # ~0.4 strokes worse
        "wind_factor": 1.25,
        "notes": "Afternoon winds, firmer greens",
    },
}

# Coastal courses have bigger wave splits
COASTAL_WAVE_MULTIPLIER = {
    "torrey_pines": 1.5,  # 50% bigger wave effect
    "pebble_beach": 1.8,
    "riviera": 1.2,
    "tpc_scottsdale": 0.8,  # Desert = less wind variation
}


def get_wave_from_tee_time(tee_time: str) -> str:
    """
    Determine AM/PM wave from tee time string.
    
    Args:
        tee_time: String like "11:32AM CST" or "2:15PM EST"
        
    Returns:
        "AM" or "PM"
    """
    if not tee_time:
        return "AM"  # Default
    
    tee_time_upper = tee_time.upper()
    
    if "PM" in tee_time_upper:
        # Check if it's early PM (before 2pm = still morning wave usually)
        try:
            hour = int(tee_time_upper.split(":")[0])
            if hour == 12 or hour < 2:
                return "AM"  # Early PM is often still morning wave
        except:
            pass
        return "PM"
    
    return "AM"


def get_course_adjustment(
    tournament: str,
    course: str = None,
    wave: str = None,
    tee_time: str = None,
    round_num: int = 0,
) -> Dict[str, float]:
    """
    Get course-specific adjustments.
    Tries JSON config first, falls back to hardcoded Python config.
    
    Args:
        tournament: Tournament name (e.g., "Farmers Insurance Open")
        course: Specific course if multi-course (e.g., "south", "north")
        wave: "AM" or "PM" (optional, can derive from tee_time)
        tee_time: Tee time string to derive wave
        round_num: Round number (1-4) for round-specific adjustments
        
    Returns:
        Dict with scoring_adjustment, birdie_factor, bogey_factor
    """
    # Derive wave from tee time if not provided
    if wave is None and tee_time:
        wave = get_wave_from_tee_time(tee_time)
    
    # TRY JSON CONFIG FIRST (allows real-time updates)
    json_result = get_course_from_json(tournament, course, round_num, wave)
    if json_result:
        print(f"[COURSE_ADJ] Using JSON config for {tournament} R{round_num}")
        return json_result
    
    # FALLBACK TO HARDCODED CONFIG
    result = {
        "scoring_adjustment": 0.0,
        "birdie_factor": 1.0,
        "bogey_factor": 1.0,
        "scoring_stddev": 3.0,
        "wave": wave or "AM",
        "course_notes": "",
        "difficulty_rank": None,
        "source": "hardcoded",
    }
    
    # Detect tournament
    tournament_lower = tournament.lower() if tournament else ""
    
    # Farmers Insurance Open (Torrey Pines)
    if "farmers" in tournament_lower or "torrey" in tournament_lower:
        # Round 4 Sunday = use Sunday-specific data
        if round_num == 4:
            adj = TORREY_PINES_ADJUSTMENTS["south_course_sunday"]
            result["scoring_stddev"] = adj.get("scoring_stddev", 3.1)
            result["difficulty_rank"] = adj.get("difficulty_rank")
        elif course and "north" in course.lower():
            adj = TORREY_PINES_ADJUSTMENTS["north_course"]
        else:
            adj = TORREY_PINES_ADJUSTMENTS["south_course"]
        
        result["scoring_adjustment"] = adj["difficulty_adjustment"]
        result["birdie_factor"] = adj["birdie_factor"]
        result["bogey_factor"] = adj["bogey_factor"]
        result["course_notes"] = adj["notes"]
        
        # Wave adjustment (bigger at Torrey)
        if wave is None and tee_time:
            wave = get_wave_from_tee_time(tee_time)
        
        if wave:
            wave_adj = WAVE_ADJUSTMENTS.get(wave, {})
            wave_mult = COASTAL_WAVE_MULTIPLIER.get("torrey_pines", 1.0)
            
            result["scoring_adjustment"] += wave_adj.get("scoring_adjustment", 0) * wave_mult
            result["wave"] = wave
    
    return result


# =============================================================================
# ROUND-SPECIFIC ADJUSTMENTS
# =============================================================================

ROUND_ADJUSTMENTS = {
    1: {
        "variance_multiplier": 1.1,  # R1 has more variance (rust, nerves)
        "notes": "First round jitters, field not separated",
    },
    2: {
        "variance_multiplier": 1.0,  # Normal
        "notes": "Standard round",
    },
    3: {
        "variance_multiplier": 0.95,  # Moving day, pros attack
        "birdie_boost": 0.05,
        "notes": "Moving day, aggressive play",
    },
    4: {
        "variance_multiplier": 0.90,  # Finals, tighter play
        "notes": "Final round pressure, conservative for some",
    },
}


def get_round_adjustment(round_num: int) -> Dict[str, float]:
    """Get round-specific adjustments."""
    return ROUND_ADJUSTMENTS.get(round_num, ROUND_ADJUSTMENTS[2])


# =============================================================================
# WEATHER INTEGRATION
# =============================================================================

def get_weather_adjustment(
    wind_mph: float = 0,
    rain: bool = False,
    temperature_f: float = 70,
) -> Dict[str, float]:
    """
    Calculate weather-based adjustments.
    
    Args:
        wind_mph: Wind speed in MPH
        rain: Whether rain is expected
        temperature_f: Temperature in Fahrenheit
        
    Returns:
        Dict with scoring_adjustment, birdie_factor
    """
    result = {
        "scoring_adjustment": 0.0,
        "birdie_factor": 1.0,
    }
    
    # Wind adjustment
    if wind_mph < 5:
        wind_cat = "calm"
    elif wind_mph < 10:
        wind_cat = "light"
    elif wind_mph < 15:
        wind_cat = "moderate"
    elif wind_mph < 20:
        wind_cat = "strong"
    elif wind_mph < 25:
        wind_cat = "very_strong"
    else:
        wind_cat = "extreme"
    
    # Import wind factors
    from golf.config.golf_config import WIND_ADJUSTMENT_FACTORS, WIND_BOGEY_MULTIPLIER
    
    result["scoring_adjustment"] -= WIND_ADJUSTMENT_FACTORS.get(wind_cat, 0)
    result["birdie_factor"] /= WIND_BOGEY_MULTIPLIER.get(wind_cat, 1.0)
    
    # Rain adjustment
    if rain:
        result["scoring_adjustment"] += 0.5  # Half stroke harder
        result["birdie_factor"] *= 0.90  # 10% fewer birdies
    
    # Temperature (cold = harder)
    if temperature_f < 50:
        result["scoring_adjustment"] += 0.3
    elif temperature_f > 90:
        result["scoring_adjustment"] += 0.2  # Heat fatigue
    
    return result


if __name__ == "__main__":
    # Test
    print("=== TORREY PINES ADJUSTMENTS ===")
    
    adj = get_course_adjustment(
        tournament="Farmers Insurance Open",
        course="south",
        tee_time="11:32AM CST"
    )
    print(f"AM Wave, South Course: {adj}")
    
    adj = get_course_adjustment(
        tournament="Farmers Insurance Open",
        course="south",
        tee_time="2:15PM CST"
    )
    print(f"PM Wave, South Course: {adj}")
    
    print("\n=== WEATHER ADJUSTMENTS ===")
    weather = get_weather_adjustment(wind_mph=15, rain=False, temperature_f=65)
    print(f"15mph wind: {weather}")
