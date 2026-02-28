"""
CBB Game Context Features — Enhanced
--------------------------------------
Context factors that affect player performance predictions.
Includes coach priors, ref bias, travel fatigue, and seed volatility.
"""

import json
import yaml
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


# Model prior paths
MODELS_DIR = Path(__file__).parent.parent / "models"


@dataclass
class CoachContext:
    """Coach-specific adjustments."""
    name: str = ""
    pace_mult: float = 1.0
    foul_rate_mult: float = 1.0


@dataclass 
class RefContext:
    """Referee-specific adjustments."""
    location: str = "HOME"  # HOME, AWAY, NEUTRAL
    foul_boost: float = 1.0
    free_throw_boost: float = 1.0
    variance_mult: float = 1.0
    crew_name: Optional[str] = None


@dataclass
class TravelContext:
    """Travel and fatigue context."""
    fatigue_type: str = "NONE"
    mean_mult: float = 1.0
    variance_mult: float = 1.0


@dataclass
class SeedContext:
    """Tournament seed volatility."""
    home_seed: Optional[int] = None
    away_seed: Optional[int] = None
    seed_gap: int = 0
    variance_mult: float = 1.0
    coach_seed_interaction: float = 1.0


@dataclass
class GameContext:
    """CBB game context for edge generation"""
    game_id: str
    home_team: str
    away_team: str
    game_date: str
    
    # Conference context
    is_conference_game: bool = False
    home_conference: str = ""
    away_conference: str = ""
    
    # Venue
    is_neutral_site: bool = False
    venue: str = ""
    event_name: str = ""
    
    # Lines
    spread: float = 0.0
    over_under: float = 0.0
    
    # Risk flags
    blowout_risk: bool = False
    blowout_probability: float = 0.0
    
    # Schedule context
    home_days_rest: int = 0
    away_days_rest: int = 0
    is_back_to_back_home: bool = False
    is_back_to_back_away: bool = False
    
    # Season context
    is_early_season: bool = False  # First 10 games
    is_tournament: bool = False
    
    # Enhanced context - coach priors
    home_coach: CoachContext = field(default_factory=CoachContext)
    away_coach: CoachContext = field(default_factory=CoachContext)
    
    # Enhanced context - ref bias
    ref_context: RefContext = field(default_factory=RefContext)
    
    # Enhanced context - travel fatigue
    home_fatigue: TravelContext = field(default_factory=TravelContext)
    away_fatigue: TravelContext = field(default_factory=TravelContext)
    
    # Enhanced context - seed volatility (tournament only)
    seed_context: SeedContext = field(default_factory=SeedContext)
    
    # Blocking
    is_blocked: bool = False
    block_reason: Optional[str] = None


def load_model_prior(name: str) -> dict:
    """Load model prior file."""
    yaml_path = MODELS_DIR / f"{name}.yaml"
    json_path = MODELS_DIR / f"{name}.json"
    
    if yaml_path.exists():
        with open(yaml_path) as f:
            return yaml.safe_load(f)
    elif json_path.exists():
        with open(json_path) as f:
            return json.load(f)
    return {}


def build_game_context(
    game: Dict,
    home_schedule: Optional[list] = None,
    away_schedule: Optional[list] = None,
    home_coach_name: Optional[str] = None,
    away_coach_name: Optional[str] = None,
    ref_crew: Optional[str] = None,
    home_seed: Optional[int] = None,
    away_seed: Optional[int] = None
) -> GameContext:
    """
    Build game context from game data and team schedules.
    
    Args:
        game: Game dictionary with basic info
        home_schedule: Recent games for home team
        away_schedule: Recent games for away team
        home_coach_name: Head coach name for home team
        away_coach_name: Head coach name for away team
        ref_crew: Ref crew identifier (if known)
        home_seed: Tournament seed (if applicable)
        away_seed: Tournament seed (if applicable)
        
    Returns:
        GameContext dataclass with all context flags
    """
    spread = abs(game.get("spread", 0))
    
    # Calculate blowout probability from spread
    blowout_prob = min(spread * 0.03, 0.75)
    
    is_neutral = game.get("neutral_site", False)
    is_tourney = game.get("tournament", False)
    
    context = GameContext(
        game_id=game.get("game_id", ""),
        home_team=game.get("home_team", ""),
        away_team=game.get("away_team", ""),
        game_date=game.get("date", ""),
        
        is_conference_game=game.get("is_conference", False),
        home_conference=game.get("home_conference", ""),
        away_conference=game.get("away_conference", ""),
        
        is_neutral_site=is_neutral,
        venue=game.get("venue", ""),
        event_name=game.get("event_name", ""),
        
        spread=game.get("spread", 0),
        over_under=game.get("over_under", 0),
        
        blowout_risk=spread > 15,
        blowout_probability=blowout_prob,
        
        is_early_season=game.get("game_number", 99) <= 10,
        is_tournament=is_tourney,
    )
    
    # Calculate rest days if schedule provided
    if home_schedule:
        context.home_days_rest = _calculate_days_rest(game.get("date"), home_schedule)
        context.is_back_to_back_home = context.home_days_rest == 0
    
    if away_schedule:
        context.away_days_rest = _calculate_days_rest(game.get("date"), away_schedule)
        context.is_back_to_back_away = context.away_days_rest == 0
    
    # Build coach context
    context.home_coach = _build_coach_context(home_coach_name)
    context.away_coach = _build_coach_context(away_coach_name)
    
    # Build ref context
    context.ref_context = _build_ref_context(
        is_neutral=is_neutral,
        is_tournament=is_tourney,
        crew_name=ref_crew
    )
    
    # Build travel/fatigue context
    context.home_fatigue = _build_fatigue_context(
        days_rest=context.home_days_rest,
        is_tournament=is_tourney,
        game_depth=game.get("tournament_round", 0)
    )
    context.away_fatigue = _build_fatigue_context(
        days_rest=context.away_days_rest,
        is_tournament=is_tourney,
        game_depth=game.get("tournament_round", 0)
    )
    
    # Build seed context (tournament only)
    if is_tourney and home_seed and away_seed:
        context.seed_context = _build_seed_context(
            home_seed=home_seed,
            away_seed=away_seed,
            home_coach_name=home_coach_name,
            away_coach_name=away_coach_name
        )
    
    # Apply context-based blocks
    context = apply_context_blocks(context)
    
    return context


def _build_coach_context(coach_name: Optional[str]) -> CoachContext:
    """Build coach context from priors."""
    if not coach_name:
        return CoachContext()
    
    priors = load_model_prior("coach_priors")
    default = priors.get("_default", {"pace_mult": 1.0, "foul_rate_mult": 1.0})
    
    coach_data = priors.get(coach_name, default)
    
    return CoachContext(
        name=coach_name,
        pace_mult=coach_data.get("pace_mult", 1.0),
        foul_rate_mult=coach_data.get("foul_rate_mult", 1.0)
    )


def _build_ref_context(
    is_neutral: bool,
    is_tournament: bool,
    crew_name: Optional[str]
) -> RefContext:
    """Build ref context from bias priors."""
    ref_bias = load_model_prior("ref_bias")
    ref_crews = load_model_prior("ref_crews")
    
    # Determine location
    if is_tournament or is_neutral:
        location = "NEUTRAL"
    else:
        location = "HOME"  # Will be overridden per-player based on their team
    
    # Get location-based bias
    loc_data = ref_bias.get(location, ref_bias.get("NEUTRAL", {}))
    
    context = RefContext(
        location=location,
        foul_boost=loc_data.get("foul_boost", 1.0),
        free_throw_boost=loc_data.get("free_throw_boost", 1.0),
        variance_mult=loc_data.get("variance_mult", 1.0),
        crew_name=crew_name
    )
    
    # Apply crew-specific adjustments if known
    if crew_name:
        crews = ref_crews.get("CREWS", {})
        crew_data = crews.get(crew_name, ref_crews.get("_unknown_crew_default", {}))
        context.foul_boost *= crew_data.get("foul_mult", 1.0)
        context.variance_mult *= crew_data.get("variance_mult", 1.0)
    
    return context


def _build_fatigue_context(
    days_rest: int,
    is_tournament: bool,
    game_depth: int = 0
) -> TravelContext:
    """Build travel/fatigue context from priors."""
    fatigue_priors = load_model_prior("travel_fatigue")
    
    # Determine fatigue type
    if is_tournament and game_depth >= 3:  # Sweet 16+
        fatigue_type = "TOURNAMENT_DEEP"
    elif is_tournament:
        fatigue_type = "TOURNAMENT_EARLY"
    elif days_rest == 0:
        fatigue_type = "BACK_TO_BACK"
    elif days_rest == 1:
        fatigue_type = "ONE_DAY_TURNAROUND"
    else:
        fatigue_type = "NONE"
    
    fatigue_data = fatigue_priors.get(fatigue_type, fatigue_priors.get("NONE", {}))
    
    return TravelContext(
        fatigue_type=fatigue_type,
        mean_mult=fatigue_data.get("mean_mult", 1.0),
        variance_mult=fatigue_data.get("variance_mult", 1.0)
    )


def _build_seed_context(
    home_seed: int,
    away_seed: int,
    home_coach_name: Optional[str],
    away_coach_name: Optional[str]
) -> SeedContext:
    """Build seed volatility context from priors."""
    seed_volatility = load_model_prior("seed_volatility")
    seed_coach = load_model_prior("seed_coach_matrix")
    
    seed_gap = abs(home_seed - away_seed)
    
    # Get base variance multiplier from seed gap
    if seed_gap <= 2:
        var_key = "SEED_GAP_1_2"
    elif seed_gap <= 4:
        var_key = "SEED_GAP_3_4"
    elif seed_gap <= 8:
        var_key = "SEED_GAP_5_8"
    elif seed_gap <= 12:
        var_key = "SEED_GAP_9_12"
    else:
        var_key = "SEED_GAP_13_PLUS"
    
    variance_mult = seed_volatility.get(var_key, 1.0)
    
    # Apply coach × seed interaction
    coach_seed_mult = 1.0
    coach_effects = seed_coach.get("COACH_SEED_EFFECTS", {})
    
    for coach_name in [home_coach_name, away_coach_name]:
        if coach_name and coach_name in coach_effects:
            effects = coach_effects[coach_name]
            # Determine if this coach's team is favored or underdog
            # Simplified: lower seed number = favored
            is_high_seed = True  # Placeholder - would need team context
            seed_type = "HIGH_SEED" if is_high_seed else "LOW_SEED"
            coach_seed_mult *= effects.get(seed_type, 1.0)
    
    return SeedContext(
        home_seed=home_seed,
        away_seed=away_seed,
        seed_gap=seed_gap,
        variance_mult=variance_mult,
        coach_seed_interaction=coach_seed_mult
    )


def _calculate_days_rest(game_date: str, schedule: list) -> int:
    """Calculate days since last game."""
    if not game_date or not schedule:
        return 3  # Default assumption
    
    try:
        target = datetime.strptime(game_date, "%Y-%m-%d")
        # Find most recent game before target
        for game in sorted(schedule, key=lambda x: x.get("date", ""), reverse=True):
            prev_date = datetime.strptime(game.get("date", ""), "%Y-%m-%d")
            if prev_date < target:
                return (target - prev_date).days - 1
    except (ValueError, TypeError):
        pass
    
    return 3


def apply_context_blocks(context: GameContext) -> GameContext:
    """
    Apply context-based blocking rules.
    
    Blocks:
    - High blowout probability games (for overs)
    - Early season games (reduced confidence)
    """
    from sports.cbb.config import CBB_EDGE_GATES
    
    # Block if blowout probability too high
    if context.blowout_probability > CBB_EDGE_GATES.max_blowout_probability:
        context.is_blocked = True
        context.block_reason = f"BLOWOUT_RISK ({context.blowout_probability:.1%})"
    
    return context


def get_combined_variance_mult(context: GameContext, is_home_team: bool) -> float:
    """
    Get combined variance multiplier from all context factors.
    
    Args:
        context: GameContext with all loaded priors
        is_home_team: Whether calculating for home team player
    
    Returns:
        Combined variance multiplier
    """
    mult = 1.0
    
    # Ref variance
    mult *= context.ref_context.variance_mult
    
    # Travel fatigue
    fatigue = context.home_fatigue if is_home_team else context.away_fatigue
    mult *= fatigue.variance_mult
    
    # Seed volatility (tournament only)
    if context.is_tournament and context.seed_context.seed_gap > 0:
        mult *= context.seed_context.variance_mult
        mult *= context.seed_context.coach_seed_interaction
    
    return mult


def get_combined_mean_mult(context: GameContext, is_home_team: bool) -> float:
    """
    Get combined mean multiplier from context factors.
    
    Args:
        context: GameContext with all loaded priors
        is_home_team: Whether calculating for home team player
    
    Returns:
        Combined mean multiplier
    """
    mult = 1.0
    
    # Travel fatigue affects mean
    fatigue = context.home_fatigue if is_home_team else context.away_fatigue
    mult *= fatigue.mean_mult
    
    return mult
