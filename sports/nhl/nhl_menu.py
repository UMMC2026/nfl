"""
NHL INTERACTIVE MENU — v3.0
============================

Risk-first hockey analysis with goalie gate enforcement.

Usage:
    .venv\\Scripts\\python.exe sports/nhl/nhl_menu.py

Features:
    - Ingest Underdog slate (paste props)
    - Analyze SOG props (Player Shots Model)
    - Analyze Goalie Saves
    - Goals/Assists/Points Props (NEW v3.0)
    - Monte Carlo parlay optimizer (NEW v3.0)
    - Live Stats API integration (NEW v3.0)
    - Calibration tracking (NEW v3.0)
    - Goalie confirmation gate
    - Travel/Ref context adjustments
    - Opponent defense adjustments

GLOBAL ASSERTIONS:
    - unconfirmed_goalie_bets == 0
    - slam_count == 0
    - live_bets_per_game <= 1
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import logging
import unicodedata

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Import player stats module for real averages
try:
    from sports.nhl.player_stats import (
        get_player_stats,
        get_goalie_stats,
        get_lambda,
        get_sigma,
        SKATER_STATS_2026,
        GOALIE_STATS_2026,
    )
    STATS_LOADED = True
except ImportError:
    STATS_LOADED = False
    print("[!] Player stats module not loaded - using defaults")

# Import universal parser
try:
    from sports.nhl.universal_parser import (
        parse_universal,
        deduplicate_props as universal_dedupe,
        UniversalProp,
        convert_to_nhl_prop,
    )
    UNIVERSAL_PARSER_LOADED = True
except ImportError:
    UNIVERSAL_PARSER_LOADED = False
    print("[!] Universal parser not loaded - using standard parser only")

# === v3.0 IMPORTS ===
# Parlay Optimizer
try:
    from sports.nhl.parlay_optimizer import ParlayOptimizer, ParlayLeg
    PARLAY_OPTIMIZER_LOADED = True
except ImportError:
    PARLAY_OPTIMIZER_LOADED = False

# Calibration Tracker
try:
    from sports.nhl.calibration.tracker import NHLCalibrationTracker
    CALIBRATION_LOADED = True
except ImportError:
    CALIBRATION_LOADED = False

# Live Stats API
try:
    from sports.nhl.api.nhl_stats_api import NHLStatsAPI, get_lambda_live, get_sigma_live
    LIVE_API_LOADED = True
except ImportError:
    LIVE_API_LOADED = False

# Player Props Model
try:
    from sports.nhl.players.props_model import PlayerPropsModel, analyze_player_prop
    PROPS_MODEL_LOADED = True
except ImportError:
    PROPS_MODEL_LOADED = False

# ─────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────

VERSION = "3.0.0"
SPORT = "NHL"

# Slate persistence file
SLATE_CACHE_FILE = PROJECT_ROOT / "outputs" / "nhl" / ".nhl_slate_cache.json"

# Tier thresholds (NO SLAM in NHL)
TIERS = {
    "STRONG": (0.64, 0.67),
    "LEAN": (0.58, 0.63),
    "NO_PLAY": (0.0, 0.579),
}

# SOG-specific tiers (slightly different)
SOG_TIERS = {
    "STRONG": (0.62, 0.66),
    "LEAN": (0.58, 0.61),
    "NO_PLAY": (0.0, 0.579),
}

# Gates
MIN_TOI_MINUTES = 12.0
MAX_CV_PERCENT = 45.0
MIN_EDGE_PERCENT = 2.0

# Output directory
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "nhl"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────

@dataclass
class NHLProp:
    """Parsed NHL prop from Underdog."""
    player: str
    team: str
    position: str  # F, D, G
    opponent: str
    game_time: str
    stat: str  # SOG, Goals, Blocked Shots, Saves
    line: float
    direction: str  # More/Less or Over/Under
    trending: Optional[int] = None
    tag: Optional[str] = None  # Demon, Goblin, etc.
    
    # Analysis fields (filled after processing)
    model_prob: Optional[float] = None
    implied_prob: float = 0.50
    edge: Optional[float] = None
    tier: str = "PENDING"
    pick_state: str = "PENDING"
    risk_flags: List[str] = None
    
    def __post_init__(self):
        if self.risk_flags is None:
            self.risk_flags = []
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass 
class NHLSlate:
    """Collection of props for a slate."""
    date: str
    props: List[NHLProp]
    games: Dict[str, Dict]  # game_key -> game info
    
    # Goalie confirmations
    confirmed_goalies: Dict[str, str] = None  # team -> goalie name
    
    # Analysis summary
    total_props: int = 0
    playable_props: int = 0
    strong_picks: int = 0
    lean_picks: int = 0
    
    def __post_init__(self):
        if self.confirmed_goalies is None:
            self.confirmed_goalies = {}


# ─────────────────────────────────────────────────────────
# SLATE PERSISTENCE
# ─────────────────────────────────────────────────────────

def save_slate_cache(slate: NHLSlate) -> bool:
    """Save current slate to cache file for persistence."""
    try:
        SLATE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert props to dicts
        props_data = []
        for prop in slate.props:
            props_data.append(asdict(prop))
        
        cache_data = {
            "date": slate.date,
            "props": props_data,
            "games": slate.games,
            "confirmed_goalies": slate.confirmed_goalies,
            "total_props": slate.total_props,
            "playable_props": slate.playable_props,
            "strong_picks": slate.strong_picks,
            "lean_picks": slate.lean_picks,
            "cached_at": datetime.now().isoformat(),
        }
        
        with open(SLATE_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        return True
    except Exception as e:
        logger.warning(f"Failed to save slate cache: {e}")
        return False


def load_slate_cache() -> Optional[NHLSlate]:
    """Load slate from cache file if it exists and is from today."""
    try:
        if not SLATE_CACHE_FILE.exists():
            # Try fallback to latest picks JSON
            return _load_from_latest_picks_json()
        
        with open(SLATE_CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        
        # Check if cache is from today
        cache_date = cache_data.get("date", "")
        today = date.today().strftime("%Y-%m-%d")
        
        if cache_date != today:
            logger.info(f"Cache is stale ({cache_date}), trying picks JSON fallback")
            return _load_from_latest_picks_json()
        
        # Reconstruct props
        props = []
        for prop_data in cache_data.get("props", []):
            prop = NHLProp(
                player=prop_data.get("player", ""),
                team=prop_data.get("team", ""),
                position=prop_data.get("position", ""),
                opponent=prop_data.get("opponent", ""),
                game_time=prop_data.get("game_time", ""),
                stat=prop_data.get("stat", ""),
                line=prop_data.get("line", 0),
                direction=prop_data.get("direction", ""),
                trending=prop_data.get("trending", False),
                tag=prop_data.get("tag"),
                model_prob=prop_data.get("model_prob"),
                implied_prob=prop_data.get("implied_prob", 0.50),
                edge=prop_data.get("edge"),
                tier=prop_data.get("tier", "PENDING"),
                pick_state=prop_data.get("pick_state", "PENDING"),
                risk_flags=prop_data.get("risk_flags", []),
            )
            props.append(prop)
        
        slate = NHLSlate(
            date=cache_data["date"],
            props=props,
            games=cache_data.get("games", {}),
            confirmed_goalies=cache_data.get("confirmed_goalies", {}),
            total_props=cache_data.get("total_props", len(props)),
            playable_props=cache_data.get("playable_props", 0),
            strong_picks=cache_data.get("strong_picks", 0),
            lean_picks=cache_data.get("lean_picks", 0),
        )
        
        return slate
    
    except Exception as e:
        logger.warning(f"Failed to load slate cache: {e}")
        return _load_from_latest_picks_json()


def _load_from_latest_picks_json() -> Optional[NHLSlate]:
    """Fallback: Load from latest NHL_PICKS_*.json file if from today."""
    try:
        today = date.today().strftime("%Y%m%d")
        pattern = f"NHL_PICKS_{today}_*.json"
        
        # Find all matching files
        json_files = list(OUTPUT_DIR.glob(pattern))
        if not json_files:
            return None
        
        # Get the latest one
        latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
        logger.info(f"Loading from fallback: {latest_file.name}")
        
        with open(latest_file, 'r') as f:
            data = json.load(f)
        
        # Reconstruct props from picks JSON format
        props = []
        for pick in data.get("picks", []):
            prop = NHLProp(
                player=pick.get("player", ""),
                team=pick.get("team", ""),
                position=pick.get("position", ""),
                opponent=pick.get("opponent", ""),
                game_time=pick.get("game_time", ""),
                stat=pick.get("stat", ""),
                line=pick.get("line", 0),
                direction=pick.get("direction", ""),
                trending=pick.get("trending"),
                tag=pick.get("tag"),
                model_prob=pick.get("probability"),
                implied_prob=0.50,
                edge=pick.get("edge"),
                tier=pick.get("tier", "PENDING"),
                pick_state="OPTIMIZABLE" if pick.get("tier") in ["STRONG", "LEAN"] else "REJECTED",
                risk_flags=pick.get("risk_flags", []),
            )
            props.append(prop)
        
        summary = data.get("summary", {})
        slate = NHLSlate(
            date=data.get("date", date.today().strftime("%Y-%m-%d")),
            props=props,
            games={},
            confirmed_goalies={},
            total_props=summary.get("total_props", len(props)),
            playable_props=summary.get("playable", 0),
            strong_picks=summary.get("strong", 0),
            lean_picks=summary.get("lean", 0),
        )
        
        return slate
        
    except Exception as e:
        logger.warning(f"Failed to load from picks JSON: {e}")
        return None


# ─────────────────────────────────────────────────────────
# UNDERDOG PARSER
# ─────────────────────────────────────────────────────────

def parse_underdog_paste(text: str) -> List[NHLProp]:
    """
    Parse pasted Underdog NHL props.
    
    Handles NEW format (2025+):
        athlete or team avatar
        Tage Thompson
        BUF vs PIT - 6:00PM CST
        
        3.5
        Shots on Goal
        Higher
        1.06x
        Lower
        0.84x
        
    Also handles goalie format:
        Alex Lyon
        BUF vs PIT - 6:00PM CST
        25.5
        Saves
        Higher
        ...
    """
    props = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    
    # Stat type mapping (full name -> internal name)
    stat_map = {
        'shots on goal': 'SOG',
        'saves': 'Saves',
        'goals against': 'GA',
        'points': 'Points',
        'goals': 'Goals',
        'assists': 'Assists',
        'fantasy points': 'Fantasy',
        'power play points': 'PP Points',
        'faceoffs won': 'Faceoffs',
        'hits': 'Hits',
        'blocked shots': 'Blocked',
        'first goal scorer': 'First Goal',
        '1st period shots on goal': '1P SOG',
        '1st period saves': '1P Saves',
        '1st period goals against': '1P GA',
        'plus minus': 'Plus/Minus',
    }
    
    # Position detection from team line (will infer from stat if not available)
    goalie_stats = {'Saves', 'GA', '1P Saves', '1P GA'}
    
    i = 0
    current_player = None
    current_team = None
    current_opponent = None
    current_game_time = None
    
    while i < len(lines):
        line = lines[i]
        
        # Skip known junk lines
        if line.lower() in ('athlete or team avatar', 'fewer picks', 'trending', 'more', 'less'):
            i += 1
            continue
        
        # Skip multiplier values (e.g., "1.06x", "0.84x")
        if re.match(r'^[\d.]+x$', line):
            i += 1
            continue
        
        # Skip pure numbers that are trending counts
        if line.isdigit() and int(line) > 100:  # Trending counts are typically large
            i += 1
            continue
        
        # Check for game line: "TEAM vs TEAM - TIME" or "TEAM @ TEAM - TIME"
        game_match = re.match(r'^([A-Z]{2,3})\s*(vs|@)\s*([A-Z]{2,3})\s*-\s*(.+)$', line, re.IGNORECASE)
        if game_match:
            team1 = game_match.group(1).upper()
            vs_at = game_match.group(2)
            team2 = game_match.group(3).upper()
            current_game_time = game_match.group(4).strip()
            
            # Determine team/opponent based on vs/@
            if vs_at.lower() == 'vs':
                current_team = team1
                current_opponent = team2
            else:  # @
                current_team = team2  # Player's team listed second when @
                current_opponent = team1
            i += 1
            continue
        
        # Check if this is a player name (capitalized, not a stat/direction)
        # Player names: First Last, skip if it's a known stat or direction
        is_stat = line.lower() in stat_map
        is_direction = line.lower() in ('higher', 'lower')
        is_number = re.match(r'^[\d.]+$', line)
        
        if not is_stat and not is_direction and not is_number:
            # Check if it looks like a player name (at least 2 words, capitalized)
            words = line.split()
            if len(words) >= 2 and all(w[0].isupper() for w in words if len(w) > 0):
                # Remove any tag suffix
                tag = None
                player_name = line
                for t in ["Demon", "Goblin", "Fire", "Ice", "Taco"]:
                    if line.endswith(t):
                        tag = t
                        player_name = line[:-len(t)].strip()
                        break
                current_player = player_name
                i += 1
                continue
        
        # Check for line value (numeric like 3.5, 25.5, 0.5)
        if is_number and current_player:
            try:
                line_val = float(line)
                
                # Look ahead for stat type
                stat_type = None
                stat_internal = None
                direction = "Higher"
                
                # Next line should be stat
                if i + 1 < len(lines):
                    stat_line = lines[i + 1].lower()
                    # Sort by length to match longer strings first
                    for full_name, internal in sorted(stat_map.items(), key=lambda x: len(x[0]), reverse=True):
                        if full_name in stat_line:
                            stat_type = full_name
                            stat_internal = internal
                            break
                
                if stat_internal:
                    # Look for direction (Higher/Lower)
                    for j in range(i + 2, min(i + 5, len(lines))):
                        if lines[j].lower() == 'higher':
                            direction = "Higher"
                            break
                        elif lines[j].lower() == 'lower':
                            direction = "Lower"
                            break
                    
                    # Determine position based on stat
                    position = 'G' if stat_internal in goalie_stats else 'F'
                    
                    # Create prop
                    prop = NHLProp(
                        player=current_player,
                        team=current_team or "",
                        position=position,
                        opponent=current_opponent or "",
                        game_time=current_game_time or "",
                        stat=stat_internal,
                        line=line_val,
                        direction=direction,
                        trending=None,
                        tag=None,
                    )
                    props.append(prop)
                
            except ValueError:
                pass
        
        i += 1
    
    return props


def deduplicate_props(props: List[NHLProp]) -> List[NHLProp]:
    """Remove duplicate props (same player/stat/line)."""
    seen = set()
    unique = []
    
    for prop in props:
        key = (prop.player, prop.stat, prop.line, prop.direction)
        if key not in seen:
            seen.add(key)
            unique.append(prop)
    
    return unique


# ─────────────────────────────────────────────────────────
# ANALYSIS ENGINE
# ─────────────────────────────────────────────────────────

def get_player_baseline(player: str, stat: str, position: str = "F") -> Tuple[float, float]:
    """
    Get player's baseline stats (avg, std).
    Uses real 2025-26 season data when available.
    """
    # Try to get real stats from player_stats module
    if STATS_LOADED:
        avg = get_lambda(player, stat, position)
        std = get_sigma(player, stat, position)
        return (avg, std)
    
    # Fallback baselines by stat type
    baselines = {
        "SOG": (2.8, 1.2),
        "Goals": (0.35, 0.5),
        "Assists": (0.45, 0.6),
        "Points": (0.80, 0.9),
        "Blocked Shots": (1.2, 0.8),
        "Saves": (27.0, 5.0),
        "Goalie Saves": (27.0, 5.0),
        "Time On Ice": (16.5, 3.0),
    }
    
    return baselines.get(stat, (1.5, 1.0))


def calculate_poisson_prob(lambda_val: float, line: float, direction: str) -> float:
    """
    Calculate probability using Poisson distribution.
    """
    import math
    
    def poisson_pmf(k, lam):
        return (lam ** k) * math.exp(-lam) / math.factorial(k)
    
    def poisson_cdf(k, lam):
        return sum(poisson_pmf(i, lam) for i in range(k + 1))
    
    # For half-lines like 2.5, calculate P(X > 2.5) = P(X >= 3)
    if line == int(line):
        # Whole number line
        threshold = int(line)
        if direction.upper() in ("MORE", "OVER"):
            # P(X > line) = 1 - P(X <= line)
            prob = 1 - poisson_cdf(threshold, lambda_val)
        else:
            # P(X < line) = P(X <= line - 1)
            prob = poisson_cdf(threshold - 1, lambda_val)
    else:
        # Half-line (e.g., 2.5)
        threshold = int(line)
        if direction.upper() in ("MORE", "OVER"):
            # P(X > 2.5) = P(X >= 3) = 1 - P(X <= 2)
            prob = 1 - poisson_cdf(threshold, lambda_val)
        else:
            # P(X < 2.5) = P(X <= 2)
            prob = poisson_cdf(threshold, lambda_val)
    
    return max(0.01, min(0.99, prob))


def analyze_sog_prop(prop: NHLProp) -> NHLProp:
    """Analyze a Shots on Goal prop using real season stats."""
    avg, std = get_player_baseline(prop.player, "SOG", prop.position)
    
    # Log real stats if found
    if STATS_LOADED:
        stats = get_player_stats(prop.player)
        if stats:
            avg = stats.sog_avg
            std = stats.sog_std
    
    # Calculate probability
    prob = calculate_poisson_prob(avg, prop.line, prop.direction)
    
    # Apply gates
    cv = (std / avg * 100) if avg > 0 else 100
    
    if cv > MAX_CV_PERCENT:
        prop.risk_flags.append(f"HIGH_CV:{cv:.0f}%")
        prob = min(prob, 0.60)  # Cap at 60%
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    # Assign tier
    if prob >= SOG_TIERS["STRONG"][0]:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= SOG_TIERS["LEAN"][0]:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    # Edge gate
    if prop.edge < MIN_EDGE_PERCENT / 100:
        prop.risk_flags.append("LOW_EDGE")
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_goals_prop(prop: NHLProp) -> NHLProp:
    """Analyze a Goals prop using real season stats."""
    avg, std = get_player_baseline(prop.player, "Goals", prop.position)
    
    # Get real stats if available
    if STATS_LOADED:
        stats = get_player_stats(prop.player)
        if stats:
            avg = stats.goals_avg
            std = stats.goals_std
    
    # Goals are rare events - use Poisson
    prob = calculate_poisson_prob(avg, prop.line, prop.direction)
    
    # Goals props are inherently volatile
    prop.risk_flags.append("VOLATILE_STAT")
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    # Stricter tiers for goals
    if prob >= 0.60:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= 0.55:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_blocked_shots_prop(prop: NHLProp) -> NHLProp:
    """Analyze a Blocked Shots prop."""
    avg, std = get_player_baseline(prop.player, "Blocked Shots")
    
    # Defensemen block more
    if prop.position == "D":
        avg *= 1.3
    
    prob = calculate_poisson_prob(avg, prop.line, prop.direction)
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    # Standard tier assignment
    if prob >= 0.62:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= 0.58:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_toi_prop(prop: NHLProp) -> NHLProp:
    """Analyze Time on Ice (TOI) prop - uses normal distribution."""
    # Get player TOI baseline
    if STATS_LOADED:
        stats = get_player_stats(prop.player)
        if stats and stats.toi_avg > 0:
            avg = stats.toi_avg
            std = getattr(stats, 'toi_std', 0.0)
            if std <= 0:
                std = avg * 0.15  # Default: 15% of avg
        else:
            # Default based on position
            if prop.position == "D":
                avg = 22.0  # Defensemen play more
                std = 3.5
            elif prop.position == "F":
                avg = 17.0  # Forwards less
                std = 3.0
            else:
                avg = 18.0
                std = 3.0
    else:
        # Position-based defaults
        if prop.position == "D":
            avg = 22.0
            std = 3.5
        else:
            avg = 17.0
            std = 3.0
    
    # Use normal distribution for TOI (continuous variable)
    try:
        from scipy import stats as scipy_stats
        if prop.direction.lower() in ("more", "higher", "over"):
            prob = 1 - scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
        else:
            prob = scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
    except ImportError:
        # Fallback if scipy not available
        z = (prop.line - avg) / std if std > 0 else 0
        if prop.direction.lower() in ("more", "higher", "over"):
            prob = 0.5 - z * 0.3  # Rough approximation
        else:
            prob = 0.5 + z * 0.3
        prob = max(0.1, min(0.9, prob))
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    # TOI is fairly predictable
    if prob >= 0.65:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= 0.58:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_points_prop(prop: NHLProp) -> NHLProp:
    """Analyze Points prop."""
    # Points = Goals + Assists, use player baseline
    avg, std = get_player_baseline(prop.player, "Points", prop.position)
    
    # Most NHL players average 0.3-1.0 points per game
    if avg < 0.1:
        avg = 0.5 if prop.position == "F" else 0.3
    
    prob = calculate_poisson_prob(avg, prop.line, prop.direction)
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    # Points props tier assignment
    if prob >= 0.62:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= 0.55:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_assists_prop(prop: NHLProp) -> NHLProp:
    """Analyze Assists prop."""
    avg, std = get_player_baseline(prop.player, "Assists", prop.position)
    
    if avg < 0.1:
        avg = 0.4 if prop.position == "F" else 0.3
    
    prob = calculate_poisson_prob(avg, prop.line, prop.direction)
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    if prob >= 0.60:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= 0.55:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_saves_prop(prop: NHLProp) -> NHLProp:
    """
    Analyze Goalie Saves prop using NORMAL distribution.
    
    Saves follow a normal distribution (high-count, continuous-ish).
    Goalie saves are inherently volatile — apply stricter caps.
    
    Per governance:
        - SLAM tier DISABLED for NHL
        - Goalie confirmation MANDATORY (checked elsewhere)
        - Max confidence 85% (goalie variance)
    """
    # Get goalie baseline from stats
    if STATS_LOADED:
        try:
            goalie_stats = get_goalie_stats(prop.player)
            if goalie_stats:
                avg = goalie_stats.saves_avg
                std = goalie_stats.saves_std
            else:
                avg, std = 27.0, 5.0  # Default
        except:
            avg, std = 27.0, 5.0
    else:
        avg, std = get_player_baseline(prop.player, "Saves")
    
    # Calculate probability using NORMAL distribution (not Poisson!)
    try:
        from scipy import stats as scipy_stats
        if prop.direction.lower() in ("more", "higher", "over"):
            prob = 1 - scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
        else:
            prob = scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
    except ImportError:
        # Fallback z-score approximation
        z = (prop.line - avg) / std if std > 0 else 0
        if prop.direction.lower() in ("more", "higher", "over"):
            prob = max(0.01, 0.5 - z * 0.34)
        else:
            prob = min(0.99, 0.5 + z * 0.34)
    
    # HARD CAP: Goalie saves are volatile — max 85% confidence
    prob = min(prob, 0.85)
    
    # Mark as volatile (goalie-dependent)
    prop.risk_flags.append("GOALIE_VOLATILE")
    
    prop.model_prob = prob
    prop.edge = prob - prop.implied_prob
    
    # Tier assignment (stricter for saves due to goalie variance)
    if prob >= 0.64:
        prop.tier = "STRONG"
        prop.pick_state = "OPTIMIZABLE"
    elif prob >= 0.58:
        prop.tier = "LEAN"
        prop.pick_state = "OPTIMIZABLE"
    else:
        prop.tier = "NO_PLAY"
        prop.pick_state = "REJECTED"
    
    # Edge gate
    if prop.edge < MIN_EDGE_PERCENT / 100:
        prop.risk_flags.append("LOW_EDGE")
        prop.pick_state = "REJECTED"
    
    return prop


def analyze_prop(prop: NHLProp) -> NHLProp:
    """Route prop to appropriate analyzer."""
    stat = prop.stat.upper() if prop.stat else ""
    
    if stat == "SOG" or "SHOT" in stat:
        return analyze_sog_prop(prop)
    elif stat == "GOALS" or stat == "GOAL":
        return analyze_goals_prop(prop)
    elif stat in ("BLOCKED SHOTS", "BLOCKS", "BLOCKED"):
        return analyze_blocked_shots_prop(prop)
    elif stat in ("SAVES", "GOALIE SAVES", "SV", "GOALIE S"):
        return analyze_saves_prop(prop)
    elif stat == "TOI" or "TIME ON ICE" in stat.upper():
        return analyze_toi_prop(prop)
    elif stat == "POINTS" or stat == "PTS":
        return analyze_points_prop(prop)
    elif stat in ("ASSISTS", "AST"):
        return analyze_assists_prop(prop)
    elif stat == "PPP" or "POWER PLAY" in stat.upper():
        # Power play points - rare event
        avg = 0.25  # Most players average ~0.25 PPP
        prob = calculate_poisson_prob(avg, prop.line, prop.direction)
        prop.model_prob = prob
        prop.edge = prob - prop.implied_prob
        prop.tier = "LEAN" if prob >= 0.55 else "NO_PLAY"
        prop.pick_state = "OPTIMIZABLE" if prop.tier != "NO_PLAY" else "REJECTED"
        return prop
    elif stat == "FOW" or "FACEOFF" in stat.upper():
        # Faceoffs won - use normal distribution
        avg = 10.0  # Average center wins ~10 faceoffs
        std = 4.0
        from scipy import stats as scipy_stats
        try:
            if prop.direction.lower() in ("more", "higher", "over"):
                prob = 1 - scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
            else:
                prob = scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
        except:
            prob = 0.50
        prop.model_prob = prob
        prop.edge = prob - prop.implied_prob
        prop.tier = "LEAN" if prob >= 0.58 else "NO_PLAY"
        prop.pick_state = "OPTIMIZABLE" if prop.tier != "NO_PLAY" else "REJECTED"
        return prop
    elif stat in ("FPTS", "FANTASY POINTS"):
        # Fantasy points - use normal distribution
        avg = 10.0
        std = 5.0
        from scipy import stats as scipy_stats
        try:
            if prop.direction.lower() in ("more", "higher", "over"):
                prob = 1 - scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
            else:
                prob = scipy_stats.norm.cdf(prop.line, loc=avg, scale=std)
        except:
            prob = 0.50
        prop.model_prob = prob
        prop.edge = prob - prop.implied_prob
        prop.tier = "LEAN" if prob >= 0.55 else "NO_PLAY"
        prop.pick_state = "OPTIMIZABLE" if prop.tier != "NO_PLAY" else "REJECTED"
        return prop
    else:
        # Generic analysis
        avg, std = get_player_baseline(prop.player, prop.stat)
        prob = calculate_poisson_prob(avg, prop.line, prop.direction)
        prop.model_prob = prob
        prop.edge = prob - prop.implied_prob
        prop.tier = "LEAN" if prob >= 0.58 else "NO_PLAY"
        prop.pick_state = "OPTIMIZABLE" if prop.tier != "NO_PLAY" else "REJECTED"
        return prop


def analyze_slate(slate: NHLSlate) -> NHLSlate:
    """Analyze all props in a slate."""
    for i, prop in enumerate(slate.props):
        slate.props[i] = analyze_prop(prop)
    
    # Update summary
    slate.total_props = len(slate.props)
    slate.playable_props = sum(1 for p in slate.props if p.pick_state == "OPTIMIZABLE")
    slate.strong_picks = sum(1 for p in slate.props if p.tier == "STRONG")
    slate.lean_picks = sum(1 for p in slate.props if p.tier == "LEAN")
    
    return slate


# ─────────────────────────────────────────────────────────
# DISPLAY FUNCTIONS
# ─────────────────────────────────────────────────────────

def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print menu header."""
    print("\n" + "=" * 60)
    print(f"  NHL ANALYSIS MENU v{VERSION}")
    print(f"  Risk-First Hockey | NO SLAM TIER | Goalie Gate Required")
    print("=" * 60)


def print_prop_summary(prop: NHLProp, idx: int):
    """Print single prop summary."""
    tier_icons = {"STRONG": "🟢", "LEAN": "🟡", "NO_PLAY": "⚫", "PENDING": "⏳"}
    icon = tier_icons.get(prop.tier, "❓")
    
    tag_str = f" [{prop.tag}]" if prop.tag else ""
    prob_str = f"{prop.model_prob:.1%}" if prop.model_prob else "---"
    edge_str = f"{prop.edge:.1%}" if prop.edge else "---"
    
    print(f"  {idx:2d}. {icon} {prop.player}{tag_str} ({prop.team})")
    print(f"      {prop.stat} {prop.direction} {prop.line} vs {prop.opponent}")
    print(f"      Prob: {prob_str} | Edge: {edge_str} | Tier: {prop.tier}")
    
    if prop.risk_flags:
        print(f"      ⚠️  {', '.join(prop.risk_flags)}")
    print()


def print_slate_summary(slate: NHLSlate):
    """Print slate summary."""
    print(f"\n{'─' * 50}")
    print(f"  SLATE SUMMARY — {slate.date}")
    print(f"{'─' * 50}")
    print(f"  Total Props:    {slate.total_props}")
    print(f"  Playable:       {slate.playable_props}")
    print(f"  🟢 STRONG:      {slate.strong_picks}")
    print(f"  🟡 LEAN:        {slate.lean_picks}")
    print(f"{'─' * 50}\n")


def print_playable_picks(slate: NHLSlate):
    """Print only playable picks."""
    playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
    
    if not playable:
        print("\n  ⚠️  No playable picks found.\n")
        return
    
    # Sort by probability descending
    playable.sort(key=lambda x: x.model_prob or 0, reverse=True)
    
    print(f"\n{'=' * 50}")
    print(f"  PLAYABLE PICKS ({len(playable)})")
    print(f"{'=' * 50}\n")
    
    for i, prop in enumerate(playable, 1):
        print_prop_summary(prop, i)


# ─────────────────────────────────────────────────────────
# MENU ACTIONS
# ─────────────────────────────────────────────────────────

def _read_multiline_paste(end_markers: Tuple[str, ...] = ("END", "DONE")) -> str:
    """Read a multiline paste from stdin.

    IMPORTANT: Underdog pastes contain many blank lines. Using "press ENTER twice"
    as a terminator will often stop early and leave remaining paste lines in the
    input buffer. Those leftover lines then get interpreted as the next menu choice
    (e.g. "Lower" -> Invalid choice).

    This reader stops only when the user enters an explicit end marker on its own
    line (default: END/DONE) or sends EOF (Ctrl+Z then Enter on Windows).
    """
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break

        if line.strip().upper() in end_markers:
            break

        lines.append(line)

    # Preserve internal blank lines but trim leading/trailing whitespace/newlines.
    text = "\n".join(lines)
    return text.strip()

def action_ingest_slate() -> Optional[NHLSlate]:
    """Ingest slate from Underdog OR PrizePicks (auto-detected)."""
    print("\n" + "-" * 50)
    print("  UNIVERSAL SLATE INGEST")
    print("-" * 50)
    print("\n  [1] Paste props (finish with END or Ctrl+Z)")
    print("  [2] Load from file (nhl_slate.txt)")
    print("  [Q] Cancel")
    
    choice = input("\n  Choice: ").strip().upper()
    
    if choice == "Q":
        return None
    
    if choice == "2":
        # Load from file
        try:
            with open("nhl_slate.txt", "r", encoding="utf-8") as f:
                text = f.read()
            print(f"\n  [OK] Loaded {len(text)} chars from nhl_slate.txt")
        except FileNotFoundError:
            print("\n  [!] nhl_slate.txt not found. Save your props to this file first.")
            return None
    else:
        # Paste mode
        print("\n  Paste props below.")
        print("  When finished, type END on its own line and press Enter.")
        print("  (Alternative on Windows: press Ctrl+Z then Enter.)\n")

        text = _read_multiline_paste()

        if not text:
            print("\n  [!] No input received.\n")
            return None

        if os.environ.get("NHL_DEBUG_INGEST", "").strip() == "1":
            print(f"\n  [DEBUG] Received {len(text.splitlines())} lines of input")
    
    # Use universal parser if available
    if UNIVERSAL_PARSER_LOADED:
        uprops, metadata = parse_universal(text)
        
        if not uprops:
            # Fallback to standard parser
            props = parse_underdog_paste(text)
            props = deduplicate_props(props)
        else:
            # Convert UniversalProp to NHLProp
            props = []
            for up in uprops:
                nhl_prop = NHLProp(
                    player=up.player,
                    team=up.team,
                    position=up.position,
                    opponent=up.opponent,
                    game_time=up.game_time,
                    stat=up.stat,
                    line=up.line,
                    direction=up.direction,
                    trending=up.trending,
                    tag=up.tag,
                )
                props.append(nhl_prop)
            
            print(f"\n  [OK] Format detected: {', '.join(metadata['formats_detected'])}")
            if metadata.get('underdog_count'):
                print(f"       Underdog props: {metadata['underdog_count']}")
            if metadata.get('prizepicks_count'):
                print(f"       PrizePicks props: {metadata['prizepicks_count']}")
    else:
        # Standard parser
        props = parse_underdog_paste(text)
        props = deduplicate_props(props)
    
    if not props:
        print("\n  [!] No props parsed from input.\n")
        return None
    
    # Create slate
    slate = NHLSlate(
        date=date.today().strftime("%Y-%m-%d"),
        props=props,
        games={},
    )
    
    # Extract unique games
    for prop in props:
        game_key = f"{prop.team}_vs_{prop.opponent}"
        if game_key not in slate.games:
            slate.games[game_key] = {
                "home": prop.team if "vs" in prop.game_time.lower() else prop.opponent,
                "away": prop.opponent if "vs" in prop.game_time.lower() else prop.team,
                "time": prop.game_time,
            }
    
    print(f"\n  [OK] Parsed {len(props)} unique props from {len(slate.games)} games.\n")
    
    # Show breakdown by stat
    stat_counts = {}
    for p in props:
        stat_counts[p.stat] = stat_counts.get(p.stat, 0) + 1
    
    print("  Props by stat:")
    for stat, count in sorted(stat_counts.items(), key=lambda x: -x[1]):
        print(f"    {stat}: {count}")
    
    # Show source breakdown
    sources = {}
    if UNIVERSAL_PARSER_LOADED and 'metadata' in dir():
        for fmt in metadata.get('formats_detected', []):
            sources[fmt] = sources.get(fmt, 0) + 1
        if sources:
            print("\n  Sources:")
            for src, cnt in sources.items():
                print(f"    {src}")
    
    # Auto-save raw slate to cache
    save_slate_cache(slate)
    
    return slate


def _norm_player_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", str(name))
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return " ".join(n.split()).strip()


def action_auto_ingest_nhl():
    """🔌 Auto-ingest NHL props via Playwright (DK Pick6/PrizePicks/Underdog)."""
    print("\n" + "=" * 70)
    print("  🔌 AUTO-INGEST NHL PROPS (Playwright)")
    print("=" * 70)
    print("\n  This uses the universal Playwright scraper.")
    print("  Tip: Persistent profile mode keeps you logged in.")
    
    try:
        from ingestion.prop_ingestion_pipeline import interactive_browse_persistent, run_pipeline
    except Exception as e:
        print(f"\n  ❌ Could not import ingestion pipeline: {e}")
        print("     Expected: ingestion/prop_ingestion_pipeline.py")
        return None
    
    print("\n  Choose ingest mode:")
    print("    [1] Persistent browser (recommended) — login once, navigate to NHL props")
    print("    [2] Quick scrape all sites — may require logins each run")
    mode = input("\n  Select [1/2] (default 1): ").strip() or "1"
    
    try:
        if mode.strip() == "2":
            run_pipeline(sites=["draftkings", "prizepicks", "underdog"], headless=False)
        else:
            interactive_browse_persistent()
    except Exception as e:
        print(f"\n  ❌ Ingest failed: {e}")
        return None
    
    from pathlib import Path
    scraped_latest = Path("outputs/props_latest.json")
    
    if not scraped_latest.exists():
        print(f"\n  ❌ Missing scraped output: {scraped_latest}")
        return None
    
    try:
        import json
        data = json.loads(scraped_latest.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"\n  ❌ Could not read scraped props JSON: {e}")
        return None
    
    props = data.get("props") if isinstance(data, dict) else None
    if not isinstance(props, list) or not props:
        print("\n  ❌ No props found in scraped output.")
        return None
    
    print(f"\n  ✅ Successfully ingested {len(props)} NHL props!")
    print("\n  📁 Props saved to: outputs/props_latest.json")
    print("\n  ➡️ Next: Use [2] Analyze Slate to process these props")
    
    # Note: Actual slate parsing would need NHL-specific prop parser
    # For now, return None and let user manually analyze
    return None


def action_ingest_slate_odds_api() -> Optional[NHLSlate]:
    """Ingest NHL slate via The Odds API (no paste), then validate and load.

    This avoids paste/scrape workflows and keeps NHL state isolated inside the NHL menu.
    Requires ODDS_API_KEY (or ODDSAPI_KEY) in the repo root .env.
    """

    # Load .env (best-effort)
    try:
        from dotenv import load_dotenv  # type: ignore

        env_path = str((PROJECT_ROOT / ".env").resolve())
        load_dotenv(dotenv_path=env_path, override=False)
    except Exception:
        pass

    api_key = (os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY") or "").strip()
    if not api_key:
        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv(dotenv_path=str((PROJECT_ROOT / ".env").resolve()), override=True)
        except Exception:
            pass
        api_key = (os.getenv("ODDS_API_KEY") or os.getenv("ODDSAPI_KEY") or "").strip()

    if not api_key:
        print("\n  [!] Missing ODDS_API_KEY")
        print(f"      Set ODDS_API_KEY in: {(PROJECT_ROOT / '.env').resolve()}")
        return None

    print("\n" + "-" * 50)
    print("  NHL ODDS API INGEST (us_dfs) → VALIDATE → LOAD")
    print("-" * 50)

    # Stage 1: ingest
    try:
        from ingestion.prop_ingestion_pipeline import run_odds_api

        ingested = run_odds_api(sport="NHL")
        if not ingested:
            print("\n  [!] Odds API ingest returned 0 props")
            return None
        print(f"\n  [OK] Ingested {len(ingested)} raw props")
    except Exception as e:
        import traceback

        print(f"\n  [ERROR] Odds API ingest failed: {e}")
        traceback.print_exc()
        return None

    # Stage 2: validation gate
    try:
        from src.validation.validate_scraped_data import main as validate_main

        validate_main(["--sport", "NHL", "--allow-discrepancies", "--platforms", "oddsapi"])
        print("\n  [OK] Validation complete")
    except Exception as e:
        import traceback

        print(f"\n  [ERROR] Validation failed: {e}")
        traceback.print_exc()
        return None

    # Stage 3: load latest validated parquet and convert to NHLSlate
    try:
        import pandas as pd  # type: ignore

        processed = PROJECT_ROOT / "data" / "processed"
        files = sorted(processed.glob("validated_props_NHL_*.parquet"))
        if not files:
            print("\n  [!] No validated parquet found in data/processed")
            return None
        latest = files[-1]
        df = pd.read_parquet(latest)
        if df.empty:
            print("\n  [!] Validated parquet is empty")
            return None

        # Map validator-normalized stats to NHL menu internal stats
        stat_map = {
            "sog": "SOG",
            "saves": "Saves",
            "goals": "Goals",
            "assists": "Assists",
            "points": "Points",
            "pp_points": "PP Points",
            "blocked_shots": "Blocked Shots",
        }

        props: List[NHLProp] = []
        for _, row in df.iterrows():
            player = row.get("player_normalized") or row.get("player")
            stat = row.get("stat_normalized") or row.get("stat")
            line = row.get("line")
            direction = row.get("direction")

            if not player or not stat or line != line or not direction:
                continue

            stat_norm = str(stat).strip().lower()
            stat_internal = stat_map.get(stat_norm)
            if not stat_internal:
                continue

            dir_norm = str(direction).strip().lower()
            if dir_norm in ("higher", "over", "more"):
                dir_internal = "Higher"
            elif dir_norm in ("lower", "under", "less"):
                dir_internal = "Lower"
            else:
                continue

            # Best-effort game context (structured columns emitted by Odds API raw artifact)
            home = str(row.get("home_team") or "")
            away = str(row.get("away_team") or "")
            game_time = str(row.get("commence_time") or "")

            position = "G" if stat_internal in ("Saves",) else "F"
            team = home
            opponent = away

            props.append(
                NHLProp(
                    player=_norm_player_name(str(player)),
                    team=team,
                    position=position,
                    opponent=opponent,
                    game_time=game_time,
                    stat=stat_internal,
                    line=float(line),
                    direction=dir_internal,
                    trending=None,
                    tag=None,
                )
            )

        props = deduplicate_props(props)
        if not props:
            print("\n  [!] No NHL props could be built from validated data")
            return None

        slate = NHLSlate(
            date=date.today().strftime("%Y-%m-%d"),
            props=props,
            games={},
        )

        # Extract unique games (best-effort)
        for prop in props:
            if prop.team and prop.opponent:
                game_key = f"{prop.team}_vs_{prop.opponent}"
                if game_key not in slate.games:
                    slate.games[game_key] = {
                        "home": prop.team,
                        "away": prop.opponent,
                        "time": prop.game_time,
                    }

        print(f"\n  [OK] Loaded {len(props)} props from validated parquet")
        save_slate_cache(slate)
        return slate
    except Exception as e:
        import traceback

        print(f"\n  [ERROR] Failed to load validated props: {e}")
        traceback.print_exc()
        return None


def action_analyze_slate(slate: NHLSlate) -> NHLSlate:
    """Run full analysis on slate."""
    print("\n" + "─" * 50)
    print("  ANALYZING SLATE...")
    print("─" * 50 + "\n")
    
    slate = analyze_slate(slate)
    
    print_slate_summary(slate)
    print_playable_picks(slate)
    
    # === CROSS-SPORT DATABASE: Auto-save top 5 NHL picks ===
    try:
        from engine.daily_picks_db import save_top_picks
        playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
        if playable:
            # Sort by probability descending
            playable.sort(key=lambda x: x.model_prob or 0, reverse=True)
            nhl_edges = []
            for prop in playable[:10]:  # Take top 10 for selection
                nhl_edges.append({
                    "player": prop.player,
                    "stat": prop.stat,
                    "line": prop.line,
                    "direction": prop.direction.upper() if prop.direction else "OVER",
                    "probability": prop.model_prob or 0,
                    "tier": prop.tier,
                    "team": prop.team,
                })
            save_top_picks(nhl_edges, "NHL", top_n=5)
            print(f"\n  ✅ Cross-Sport DB: Saved top 5 NHL picks")
    except ImportError:
        pass  # Cross-sport module not available
    except Exception as e:
        print(f"\n  ⚠️ Cross-Sport DB save: {e}")
    
    # === AUTO-SAVE SLATE TO CACHE ===
    if save_slate_cache(slate):
        print(f"\n  ✅ Slate auto-saved to cache")
    
    return slate


def action_filter_by_stat(slate: NHLSlate, stat: str):
    """Filter and display props by stat type."""
    filtered = [p for p in slate.props if p.stat == stat]
    
    if not filtered:
        print(f"\n  No {stat} props found.\n")
        return
    
    print(f"\n{'=' * 50}")
    print(f"  {stat} PROPS ({len(filtered)})")
    print(f"{'=' * 50}\n")
    
    # Sort by probability
    filtered.sort(key=lambda x: x.model_prob or 0, reverse=True)
    
    for i, prop in enumerate(filtered, 1):
        print_prop_summary(prop, i)


def action_export_picks(slate: NHLSlate):
    """Export playable picks to JSON."""
    playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
    
    if not playable:
        print("\n  ⚠️  No playable picks to export.\n")
        return
    
    filename = f"nhl_picks_{slate.date}.json"
    filepath = OUTPUT_DIR / filename
    
    output = {
        "sport": "NHL",
        "date": slate.date,
        "generated_at": datetime.now().isoformat(),
        "version": VERSION,
        "summary": {
            "total_props": slate.total_props,
            "playable": len(playable),
            "strong": slate.strong_picks,
            "lean": slate.lean_picks,
        },
        "picks": [p.to_dict() for p in playable],
    }
    
    with open(filepath, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n  ✅ Exported {len(playable)} picks to:")
    print(f"     {filepath}\n")


def action_goalie_check():
    """Check goalie confirmations."""
    print("\n" + "─" * 50)
    print("  GOALIE CONFIRMATION CHECK")
    print("─" * 50)
    print("\n  ⚠️  GOALIE GATE IS MANDATORY")
    print("     Bets without confirmed goalies are REJECTED.\n")
    print("  Check these sources:")
    print("    1. DailyFaceoff.com")
    print("    2. Team beat reporters")
    print("    3. @NHLGoalieNews on Twitter\n")
    print("  Enter confirmed goalies (team:goalie), or 'done':\n")
    
    confirmations = {}
    while True:
        try:
            line = input("  > ").strip()
            if line.lower() == "done" or line == "":
                break
            
            if ":" in line:
                team, goalie = line.split(":", 1)
                confirmations[team.strip().upper()] = goalie.strip()
                print(f"    ✓ {team.strip().upper()}: {goalie.strip()}")
        except KeyboardInterrupt:
            break
    
    if confirmations:
        print(f"\n  ✅ {len(confirmations)} goalies confirmed.\n")
    
    return confirmations


def action_generate_report(slate: NHLSlate):
    """Generate professional report with Top 5 picks."""
    try:
        from sports.nhl.nhl_report import (
            generate_professional_report,
            save_report,
            save_picks_json,
            get_top_5_picks,
            apply_data_driven_adjustments,
        )
        
        print("\n  Generating professional report...")
        print("  Applying data-driven calibration (SDG)...\n")
        
        # Apply SDG adjustments
        slate.props = apply_data_driven_adjustments(slate.props)
        slate.playable_props = sum(1 for p in slate.props if p.pick_state == "OPTIMIZABLE")
        slate.strong_picks = sum(1 for p in slate.props if p.tier == "STRONG")
        slate.lean_picks = sum(1 for p in slate.props if p.tier == "LEAN")
        
        # Generate and print report
        report = generate_professional_report(slate, apply_sdg=False)  # Already applied
        print(report)
        
        # Save files
        report_path = save_report(report, slate)
        json_path = save_picks_json(slate)
        
        print(f"\n  [FILE] Report saved: {report_path}")
        print(f"  [FILE] JSON saved: {json_path}")
        
    except ImportError as e:
        print(f"\n  [ERROR] Report module not found: {e}")
    except Exception as e:
        print(f"\n  [ERROR] Report generation failed: {e}")


def action_show_top_5(slate: NHLSlate):
    """Show Top 5 picks summary."""
    try:
        from sports.nhl.nhl_report import get_top_5_picks, format_top_5_ascii
        from sports.nhl.player_stats import get_player_stats
        
        top_5 = get_top_5_picks(slate)
        
        if not top_5:
            print("\n  No picks meet minimum thresholds.\n")
            return
        
        print(format_top_5_ascii(top_5))
        
    except ImportError:
        # Fallback if report module not available
        playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
        playable.sort(key=lambda x: x.model_prob or 0, reverse=True)
        top_5 = playable[:5]
        
        print("\n" + "=" * 50)
        print("  TOP 5 NHL PICKS")
        print("=" * 50)
        
        for i, p in enumerate(top_5, 1):
            tier_icons = {"STRONG": "[STRONG]", "LEAN": "[LEAN]"}
            icon = tier_icons.get(p.tier, "[?]")
            print(f"\n  #{i} {icon} {p.player} ({p.team})")
            print(f"     {p.stat} {p.direction.upper()} {p.line}")
            print(f"     Confidence: {(p.model_prob or 0)*100:.1f}%")


def action_send_telegram(slate: NHLSlate):
    """Send Top 5 picks to Telegram."""
    try:
        from sports.nhl.nhl_report import (
            get_top_5_picks,
            push_nhl_telegram,
            can_send_telegram,
        )
        
        if not can_send_telegram():
            print("\n  [!] Telegram not configured.")
            print("      Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
            return
        
        top_5 = get_top_5_picks(slate)
        
        if not top_5:
            print("\n  [!] No picks to send.")
            return
        
        print("\n  Sending to Telegram...")
        success = push_nhl_telegram(top_5, slate)
        
        if success:
            print("  [OK] Telegram message sent!")
        else:
            print("  [!] Telegram send failed.")
            
    except ImportError as e:
        print(f"\n  [ERROR] Report module not found: {e}")
    except Exception as e:
        print(f"\n  [ERROR] Telegram send failed: {e}")


# ─────────────────────────────────────────────────────────
# v3.0 ACTIONS — Parlay Optimizer, Calibration, Live API
# ─────────────────────────────────────────────────────────

def action_parlay_optimizer(slate: NHLSlate):
    """Run Monte Carlo parlay optimizer on playable picks."""
    if not PARLAY_OPTIMIZER_LOADED:
        print("\n  [!] Parlay optimizer module not available.")
        print("      Check: sports/nhl/parlay_optimizer.py")
        return
    
    playable = [p for p in slate.props if p.pick_state == "OPTIMIZABLE"]
    
    if len(playable) < 2:
        print("\n  [!] Need at least 2 playable picks for parlays.")
        return
    
    print("\n" + "=" * 60)
    print("  NHL PARLAY OPTIMIZER — Monte Carlo Simulation")
    print("=" * 60)
    print(f"\n  Playable picks: {len(playable)}")
    print("  Running 2,000 simulations per combination...\n")
    
    optimizer = ParlayOptimizer(num_sims=2000)
    
    # Convert props to ParlayLeg format
    for p in playable:
        game_id = f"{min(p.team, p.opponent)}_{max(p.team, p.opponent)}"
        leg = ParlayLeg(
            player=p.player,
            team=p.team,
            opponent=p.opponent,
            game_id=game_id,
            stat=p.stat,
            line=p.line,
            direction=p.direction.upper(),
            probability=p.model_prob or 0.55,
            tier=p.tier,
        )
        optimizer.add_leg(leg)
    
    # Run optimization
    result = optimizer.optimize(min_legs=2, max_legs=4, top_n=10)
    optimizer.print_results(result)


def action_calibration_report():
    """Show calibration report."""
    if not CALIBRATION_LOADED:
        print("\n  [!] Calibration tracker not available.")
        print("      Check: sports/nhl/calibration/tracker.py")
        return
    
    tracker = NHLCalibrationTracker()
    report = tracker.generate_report()
    tracker.print_report(report)
    
    # Offer CSV export
    print("\n  Export to CSV? [Y/N]: ", end="")
    choice = input().strip().upper()
    if choice == "Y":
        csv_path = tracker.export_csv()
        print(f"  Exported to: {csv_path}")


def action_refresh_live_stats():
    """Refresh live stats from NHL API."""
    if not LIVE_API_LOADED:
        print("\n  [!] Live Stats API not available.")
        print("      Check: sports/nhl/api/nhl_stats_api.py")
        return
    
    print("\n" + "=" * 60)
    print("  NHL LIVE STATS API — Refreshing Data")
    print("=" * 60)
    
    api = NHLStatsAPI()
    
    print("\n  Fetching live player stats...")
    try:
        # Force cache refresh by clearing old data
        import os
        cache_dir = PROJECT_ROOT / "sports" / "nhl" / "cache"
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                try:
                    os.remove(f)
                    print(f"    Cleared: {f.name}")
                except:
                    pass
        
        print("\n  Fetching fresh data from NHL API...")
        print("  (This may take 30-60 seconds)")
        
        # Test fetch
        test_players = ["Connor McDavid", "Auston Matthews", "Nathan MacKinnon"]
        for player in test_players:
            stats = api.get_player_stats(player)
            if stats:
                print(f"    ✓ {player}: {stats.goals}G, {stats.assists}A, {stats.sog} SOG")
            else:
                print(f"    ✗ {player}: No data found")
        
        print("\n  ✅ Live stats refreshed!")
        
    except Exception as e:
        print(f"\n  [ERROR] API refresh failed: {e}")


def action_analyze_player_props(slate: NHLSlate):
    """Analyze player props for Goals/Assists/Points using v3.0 model."""
    if not PROPS_MODEL_LOADED:
        print("\n  [!] Player props model not available.")
        print("      Check: sports/nhl/players/props_model.py")
        return
    
    print("\n" + "=" * 60)
    print("  NHL PLAYER PROPS ANALYZER — Goals/Assists/Points")
    print("=" * 60)
    
    model = PlayerPropsModel()
    
    # Filter for scoring props only
    scoring_stats = {"goals", "assists", "points"}
    scoring_props = [
        p for p in slate.props 
        if p.stat.lower() in scoring_stats
    ]
    
    if not scoring_props:
        print("\n  No Goals/Assists/Points props found in slate.")
        print("  Try adding props with stat types: Goals, Assists, Points")
        return
    
    print(f"\n  Analyzing {len(scoring_props)} scoring props...\n")
    
    results = []
    for prop in scoring_props:
        try:
            result = model.analyze_prop(
                player=prop.player,
                stat=prop.stat,
                line=prop.line,
                direction=prop.direction,
                opponent=prop.opponent,
            )
            
            # Update the prop with new probabilities
            prop.model_prob = result.probability
            prop.tier = result.tier
            prop.edge = result.edge
            
            # Set pick state
            if result.tier == "STRONG":
                prop.pick_state = "OPTIMIZABLE"
            elif result.tier == "LEAN":
                prop.pick_state = "OPTIMIZABLE"
            else:
                prop.pick_state = "REJECTED"
            
            results.append((prop, result))
            
            tier_icon = "🟢" if result.tier == "STRONG" else ("🟡" if result.tier == "LEAN" else "⚫")
            print(f"  {tier_icon} {prop.player}: {prop.stat} {prop.direction} {prop.line}")
            print(f"      Prob: {result.probability*100:.1f}% | Edge: {result.edge*100:.1f}% | Tier: {result.tier}")
            
        except Exception as e:
            print(f"  [!] Error analyzing {prop.player}: {e}")
    
    # Summary
    playable = sum(1 for _, r in results if r.tier in ("STRONG", "LEAN"))
    print(f"\n  Total analyzed: {len(results)}")
    print(f"  Playable: {playable}")


def action_show_help():
    """Show help information."""
    print("\n" + "=" * 60)
    print("  NHL MENU HELP")
    print("=" * 60)
    print("""
  WORKFLOW:
    1. [1] Ingest slate by pasting Underdog props
    2. [2] Run analysis on the slate
    3. [5] Show Top 5 picks
    4. [R] Generate professional report
    5. [T] Send picks to Telegram
    6. [G] Confirm goalies (REQUIRED for totals/saves)

  NEW v3.0 FEATURES:
    [P] Player Props — Analyze Goals/Assists/Points
    [M] Monte Carlo — Parlay optimizer with correlation
    [C] Calibration — Track hit rates by stat/tier
    [L] Live Stats — Refresh from NHL API

  TIERS (NO SLAM IN NHL):
    [STRONG]: 62-66% probability
    [LEAN]:   58-61% probability
    [SKIP]:   <58% (rejected)

  DATA-DRIVEN CALIBRATION (SDG):
    - SOG props get slight boost (+5%)
    - Goals props penalized slightly (-10%)
    - Direction-specific adjustments applied

  GATES:
    - Goalie confirmation required for totals/saves
    - Minimum 2% edge required
    - High volatility caps at 60%

  STAT FILTERS:
    [S] SOG only
    [O] Goals only
    [B] Blocked shots only
""")
    input("  Press ENTER to continue...")


# ─────────────────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────────────────

def main():
    """Main menu loop."""
    slate: Optional[NHLSlate] = None
    
    # === AUTO-LOAD SLATE FROM CACHE ===
    cached_slate = load_slate_cache()
    if cached_slate:
        slate = cached_slate
        print(f"\n  ✅ Auto-loaded today's slate from cache ({slate.total_props} props, {slate.playable_props} playable)")
        input("  Press ENTER to continue...")
    
    while True:
        clear_screen()
        print_header()
        
        # Show current state
        if slate:
            print(f"\n  Current slate: {slate.date} ({slate.total_props} props)")
            if slate.playable_props > 0:
                print(f"     Playable: {slate.playable_props} ({slate.strong_picks} STRONG, {slate.lean_picks} LEAN)")
        else:
            print("\n  No slate loaded")
        
        print("\n" + "-" * 50)
        print("  MENU OPTIONS:")
        print("-" * 50)
        print("""
  [0] 🔌 Auto-Ingest (DK Pick6/PrizePicks/Underdog) ★NEW
      [A] Ingest Slate via Odds API (no paste)
  [1] Ingest Underdog Slate (paste props)
  [2] Analyze Slate
  [3] Show Playable Picks
  [5] Show TOP 5 PICKS
  
  [S] Filter: SOG Only
  [O] Filter: Goals Only
  [B] Filter: Blocked Shots Only
  [P] Analyze Player Props (Goals/Assists/Points) ★NEW
  
  [G] Goalie Confirmation Check
  [E] Export Picks (JSON)
  [R] GENERATE PROFESSIONAL REPORT
  [T] SEND TO TELEGRAM
  
  [M] MONTE CARLO PARLAY OPTIMIZER ★NEW
  [C] CALIBRATION REPORT ★NEW
  [L] REFRESH LIVE STATS ★NEW
  
  [H] Help
  [Q] Quit
""")
        
        choice = input("  Enter choice: ").strip().upper()

        if choice == "0":
            slate = action_auto_ingest_nhl()
            input("\n  Press ENTER to continue...")
            continue
        
        if choice == "A":
            slate = action_ingest_slate_odds_api()
            input("\n  Press ENTER to continue...")
            continue
        
        if choice == "1":
            slate = action_ingest_slate()
            input("\n  Press ENTER to continue...")
            
        elif choice == "2":
            if slate:
                slate = action_analyze_slate(slate)
            else:
                print("\n  [!] No slate loaded. Use [1] first.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "3":
            if slate:
                print_playable_picks(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
        
        elif choice == "5":
            if slate:
                action_show_top_5(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "S":
            if slate:
                action_filter_by_stat(slate, "SOG")
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "O":
            if slate:
                action_filter_by_stat(slate, "Goals")
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "B":
            if slate:
                action_filter_by_stat(slate, "Blocked Shots")
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "G":
            confirmations = action_goalie_check()
            if slate:
                slate.confirmed_goalies = confirmations
            input("\n  Press ENTER to continue...")
            
        elif choice == "E":
            if slate:
                action_export_picks(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
        
        elif choice == "R":
            if slate:
                action_generate_report(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
        
        elif choice == "T":
            if slate:
                action_send_telegram(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
        
        # === v3.0 OPTIONS ===
        elif choice == "P":
            if slate:
                action_analyze_player_props(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "M":
            if slate:
                action_parlay_optimizer(slate)
            else:
                print("\n  [!] No slate loaded.\n")
            input("\n  Press ENTER to continue...")
            
        elif choice == "C":
            action_calibration_report()
            input("\n  Press ENTER to continue...")
            
        elif choice == "L":
            action_refresh_live_stats()
            input("\n  Press ENTER to continue...")
            
        elif choice == "H":
            action_show_help()
            input("\n  Press ENTER to continue...")
            
        elif choice == "Q":
            print("\n  Goodbye!\n")
            break
        
        else:
            print("\n  [!] Invalid choice.\n")
            input("  Press ENTER to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye! 🏒\n")
