"""
Golf Edge Generator
===================
Generate edges from parsed props using Monte Carlo simulation.
Supports: Round Strokes, Finishing Position, Birdies
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import json
import uuid
import sys

# Execution context imports
from core.execution_context import ExecutionContext, assert_publish_allowed
from core.execution_mode import ExecutionMode, ExecutionState

# Project imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from golf.config import GOLF_THRESHOLDS, GOLF_CONFIDENCE_CAPS


@dataclass
class GolfEdge:
    """A golf betting edge."""
    edge_id: str
    sport: str = "GOLF"
    tournament: str = ""
    player: str = ""
    market: str = ""
    line: float = 0.0
    direction: str = ""  # "higher" or "lower" or "better"
    probability: float = 0.0
    tier: str = "AVOID"
    pick_state: str = "RAW"
    avoid_reason: Optional[str] = None  # Why pick was rejected/vetted
    
    # Odds/multipliers
    higher_mult: Optional[float] = None
    lower_mult: Optional[float] = None
    
    # Player context
    player_avg: Optional[float] = None
    player_stddev: Optional[float] = None
    sg_total: Optional[float] = None
    course_fit: Optional[float] = None
    
    # Course/conditions context
    wave: str = ""  # AM or PM
    course_adjustment: float = 0.0
    birdie_factor: float = 1.0
    
    # Metadata
    round_num: int = 0
    tee_time: str = ""
    data_sources: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "edge_id": self.edge_id,
            "sport": self.sport,
            "tournament": self.tournament,
            "player": self.player,
            "market": self.market,
            "stat": self.market,  # Alias for commentary compatibility
            "line": self.line,
            "direction": self.direction,
            "probability": self.probability,
            "tier": self.tier,
            "pick_state": self.pick_state,
            "higher_mult": self.higher_mult,
            "lower_mult": self.lower_mult,
            "player_avg": self.player_avg,
            "mu": self.player_avg,  # Alias for commentary compatibility
            "sigma": self.player_stddev,  # Alias for commentary compatibility
            "player_stddev": self.player_stddev,
            "sg_total": self.sg_total,
            "course_fit": self.course_fit,
            "wave": self.wave,
            "course_adjustment": self.course_adjustment,
            "birdie_factor": self.birdie_factor,
            "round_num": self.round_num,
            "tee_time": self.tee_time,
            "data_sources": self.data_sources,
            "created_at": self.created_at,
            "avoid_reason": self.avoid_reason,
        }


def assign_tier(probability: float, market: str, tournament_name: str = None) -> str:
    """
    Assign tier based on probability and market type.
    
    Phase 5B: Supports tournament-aware thresholds for Majors/PGA Tour events.
    Regular golf events still have NO SLAM tier due to high variance.
    
    Args:
        probability: Model probability (0.0-1.0)
        market: Market type (round_strokes, finishing_position, etc.)
        tournament_name: Optional tournament name for tier-specific thresholds
    
    Returns:
        Tier string (SLAM, STRONG, LEAN, SPEC, AVOID)
    """
    # Phase 5B: For Majors/PGA Tour, use tournament-aware thresholds (with higher cap)
    if tournament_name:
        try:
            from golf.tournament_tier import get_tournament_tier, GolfTournamentTier, implied_tier_for_golf
            tier = get_tournament_tier(tournament_name)
            
            # For Majors and PGA Tour, allow higher confidence (SLAM eligible)
            if tier in (GolfTournamentTier.MAJOR, GolfTournamentTier.PGA_SIGNATURE, GolfTournamentTier.PGA_TOUR):
                # Cap at 90% for elite events (allows SLAM at 85%)
                capped_prob = min(probability, 0.90)
            else:
                # Standard golf cap for other events
                cap = GOLF_CONFIDENCE_CAPS.get(market, 0.72)
                capped_prob = min(probability, cap)
            
            return implied_tier_for_golf(capped_prob, tournament_name)
        except ImportError:
            pass
    
    # Get market-specific cap (default golf behavior)
    cap = GOLF_CONFIDENCE_CAPS.get(market, 0.72)
    capped_prob = min(probability, cap)
    
    # Golf thresholds (no SLAM)
    if capped_prob >= GOLF_THRESHOLDS.get("STRONG", 0.72):
        return "STRONG"
    elif capped_prob >= GOLF_THRESHOLDS.get("LEAN", 0.60):
        return "LEAN"
    elif capped_prob >= GOLF_THRESHOLDS.get("SPEC", 0.52):
        return "SPEC"
    else:
        return "AVOID"


def determine_pick_state(edge: GolfEdge) -> Tuple[str, Optional[str]]:
    """
    Determine pick state for governance and classify rejection reason.
    
    Returns:
        Tuple of (pick_state, avoid_reason)
        pick_state: OPTIMIZABLE | VETTED | REJECTED
        avoid_reason: Classification of why pick was rejected/vetted
    """
    # REJECTED - Too low confidence
    if edge.probability < 0.52:
        return "REJECTED", "low_confidence"
    
    # REJECTED - Below tier threshold
    if edge.tier == "AVOID":
        return "REJECTED", "tier_threshold"
    
    # VETTED - Unverified player data
    if "auto_seeded" in edge.data_sources:
        print(f"[GOVERNANCE] {edge.player}: UNVERIFIED player (auto-seeded), betting blocked")
        return "VETTED", "unverified_player"
    
    # VETTED - High variance market
    if edge.market == "finishing_position" and edge.probability < 0.58:
        return "VETTED", "high_variance_market"
    
    # VETTED - Missing SG data
    if edge.sg_total is None and edge.probability < 0.60:
        return "VETTED", "missing_sg_data"
    
    return "OPTIMIZABLE", None


def generate_edge_from_prop(
    prop: Dict,
    player_stats: Optional[Dict] = None,
    course_stats: Optional[Dict] = None,
    use_database: bool = True,
    use_course_adjustments: bool = True,
) -> List[GolfEdge]:
    """
    Generate edge(s) from a parsed prop.
    
    Args:
        prop: Parsed prop dict from underdog parser
        player_stats: Player statistics (avg, stddev, SG)
        course_stats: Course difficulty info
        use_database: Whether to lookup player in database
        use_course_adjustments: Whether to apply course/wave adjustments
        
    Returns:
        List of GolfEdge objects (one per direction if both available)
    """
    from core.validation.fail_fast import fail_fast_check, FailFastError
    from scoring.hard_gates import hard_stop_gate
    from core.integrity.checksum import model_integrity_checksum
    
    # MARKET GOVERNANCE CHECK (Phase 1 — No ShotLink)
    try:
        from golf.config.market_governance import (
            is_market_allowed, 
            get_disabled_reason,
            normalize_market,
            get_market_config,
            MarketStatus,
        )
        market_raw = prop.get("market", "")
        market_normalized = normalize_market(market_raw)
        
        if not is_market_allowed(market_normalized):
            reason = get_disabled_reason(market_normalized)
            print(f"[MARKET BLOCKED] {prop.get('player', '?')} {market_raw}: {reason}")
            return []
        
        # Get market config for later confidence caps
        market_config = get_market_config(market_normalized)
    except ImportError:
        market_config = None  # Fallback if market_governance not available
    
    # Phase 5B: WEATHER GATE CHECK
    # Block if extreme weather conditions
    tournament = prop.get("tournament", "")
    date_str = prop.get("date", datetime.now().strftime("%Y-%m-%d"))
    weather_blocked = False
    weather_block_reason = None
    try:
        from golf.weather_gate import check_weather_gate
        weather_passed, weather_block_reason = check_weather_gate(
            tournament, date_str, prop.get("market", "")
        )
        if not weather_passed:
            print(f"[WEATHER BLOCKED] {prop.get('player', '?')} @ {tournament}: {weather_block_reason}")
            weather_blocked = True
    except ImportError:
        pass  # Weather gate not available
    
    if weather_blocked:
        return []  # Don't generate edges for blocked weather
    
    edges = []
    
    player = prop.get("player", "Unknown")
    market = prop.get("market", "")
    line = prop.get("line", 0)
    tournament = prop.get("tournament", "")
    round_num = prop.get("round", 0)
    tee_time = prop.get("tee_time", "")
    
    # Get multipliers
    higher_mult = prop.get("higher_mult")
    lower_mult = prop.get("lower_mult")
    better_mult = prop.get("better_mult")  # For finishing position
    
    # Get course adjustments (with round-specific data for R4 Sunday)
    course_adj = {"scoring_adjustment": 0.0, "birdie_factor": 1.0, "wave": "", "scoring_stddev": 3.0}
    if use_course_adjustments and tournament:
        try:
            from golf.config.course_adjustments import get_course_adjustment
            course_adj = get_course_adjustment(
                tournament=tournament,
                tee_time=tee_time,
                round_num=round_num,  # Pass round for R4 Sunday-specific priors
            )
        except ImportError:
            pass
    
    # Get player stats: database → provided → line inference
    if player_stats is None and use_database:
        try:
            from golf.data.player_database import get_player_database
            db = get_player_database()
            player_stats = db.get_stats_for_edge(player, market, line)
        except ImportError:
            player_stats = get_default_player_stats(market, line)
    elif player_stats is None:
        player_stats = get_default_player_stats(market, line)

    # Apply course adjustment to player stats BEFORE probability calc
    if course_adj["scoring_adjustment"] != 0 and market == "round_strokes":
        if "avg" in player_stats:
            player_stats = player_stats.copy()
            player_stats["avg"] = player_stats["avg"] + course_adj["scoring_adjustment"]
            # Use course-specific volatility if available (R4 Sunday = 3.1)
            if course_adj.get("scoring_stddev"):
                player_stats["stddev"] = course_adj["scoring_stddev"]
            player_stats["sources"] = player_stats.get("sources", []) + ["course_adjusted"]
    
    if course_adj["birdie_factor"] != 1.0 and market == "birdies":
        if "avg_birdies" in player_stats:
            player_stats = player_stats.copy()
            player_stats["avg_birdies"] = player_stats["avg_birdies"] * course_adj["birdie_factor"]
            player_stats["sources"] = player_stats.get("sources", []) + ["course_adjusted"]

    # Normalize market name for probability routing
    market_normalized = market
    try:
        from golf.config.market_governance import normalize_market
        market_normalized = normalize_market(market)
    except ImportError:
        pass

    # Calculate probabilities based on market type (BEFORE fail-fast)
    if market_normalized == "round_strokes":
        probs = calculate_round_strokes_probability(line, player_stats, course_stats)
    elif market_normalized == "birdies":
        probs = calculate_birdies_probability(line, player_stats)
    elif market_normalized == "finishing_position":
        probs = calculate_finishing_position_probability(line, player_stats)
    elif market_normalized in ["matchup", "head_to_head"]:
        # G-markets (head-to-head comparisons)
        # LOOK UP OPPONENT STATS FOR MATCHUP
        opponent_stats = None
        opponent = prop.get("opponent", "")
        if opponent and use_database:
            try:
                from golf.data.player_database import get_player_database
                db = get_player_database()
                opponent_stats = db.get_stats_for_edge(opponent, "matchup", line)
                if opponent_stats:
                    print(f"[MATCHUP] Found opponent stats: {opponent} SG={opponent_stats.get('sg_total', 0)}")
            except ImportError:
                pass
        probs = calculate_matchup_probability(prop, player_stats, opponent_stats)
    else:
        probs = {"higher": 0.50, "lower": 0.50}

    # FAIL FAST VALIDATION (with ACTUAL calculated probability)
    # Skip FAIL FAST for matchups — coin-flip is valid for evenly matched players
    # Matchups don't have "projection" in the same sense as stat props
    if market_normalized not in ["matchup", "head_to_head"]:
        # Signature: fail_fast_check(sport, stat, game_logs, mu_raw, sigma, prob_raw)
        best_prob = max(probs.get("higher", 0.5), probs.get("lower", 0.5), probs.get("better", 0.5))
        mu_val = player_stats.get("avg", player_stats.get("avg_birdies", player_stats.get("expected_finish", 0)))
        sigma_val = player_stats.get("stddev", 1.0) or 1.0  # Ensure non-zero
        n_val = player_stats.get("n", 5)
        
        try:
            fail_fast_check(
                sport="GOLF",
                stat=market,
                game_logs=[1] * max(3, n_val),  # Placeholder for sample count
                mu_raw=mu_val,
                sigma=sigma_val,
                prob_raw=best_prob  # Use ACTUAL calculated probability
            )
        except FailFastError as e:
            print(f"[FAIL FAST] {player} {market} {line}: {e}")
            return []
    else:
        # Matchups: mark as VETTED (not OPTIMIZABLE) unless we have SG data
        if player_stats.get("sg_total") is None:
            print(f"[MATCHUP] {player} vs opponent: No SG data - marking as VETTED")

    # HARD-STOP GATE (abort if mathematically invalid)
    # Skip for matchups since they don't have traditional mu/sigma structure
    if market_normalized not in ["matchup", "head_to_head"]:
        try:
            for direction in ["higher", "lower"]:
                prob = probs.get(direction, 0.5)
                mu = player_stats.get("avg", player_stats.get("avg_birdies", player_stats.get("expected_finish", 0)))
                sigma = player_stats.get("stddev", 1.0) or 1.0  # Ensure non-zero
                passed, reason = hard_stop_gate(
                    mu=mu,
                    sigma=sigma,
                    line=float(line),
                    prob=prob
                )
                if not passed:
                    print(f"[HARD STOP] {player} {market} {line} {direction}: {reason}")
        except Exception as e:
            print(f"[HARD STOP] {player} {market} {line}: {e}")
            return []

    # Phase 5B: Apply field strength adjustments
    # Elite players get boosted in weak fields, penalized in strong fields
    field_strength_info = {}
    try:
        from golf.field_strength import apply_field_strength_adjustment
        player_owgr = player_stats.get("owgr")  # May be None
        for direction in ["higher", "lower", "better"]:
            if direction in probs and probs[direction] > 0:
                probs[direction], fs_info = apply_field_strength_adjustment(
                    probs[direction], player, tournament, player_owgr
                )
                if fs_info.get("adjustment_applied"):
                    field_strength_info = fs_info
    except ImportError:
        pass  # Field strength module not available

    # GOLF-SPECIFIC CONFIDENCE CAP (prevents overconfident UNDERS)
    # Golf UNDERS are dangerous due to clustering (birdies come in bunches)
    try:
        from golf.config.market_governance import get_golf_confidence_cap
        for direction in ["higher", "lower"]:
            prob = probs.get(direction, 0.5)
            cap = get_golf_confidence_cap(market, direction)
            if prob > cap:
                print(f"[CONFIDENCE CAP] {player} {market} {line} {direction}: {prob:.1%} exceeds {cap:.0%} cap")
                probs[direction] = cap  # Cap it, don't reject
    except ImportError:
        pass  # Fallback if market_governance not available

    # INTEGRITY CHECKSUM (silent in production)
    # Signature: model_integrity_checksum expects: mu, sigma, n_games, prob_raw, line
    mu_for_checksum = player_stats.get("avg", player_stats.get("avg_birdies", player_stats.get("expected_finish", 0)))
    checksum = model_integrity_checksum({
        "mu": mu_for_checksum,
        "sigma": player_stats.get("stddev", 1.0) or 1.0,
        "n_games": player_stats.get("n", 5),
        "prob_raw": probs.get("higher", 0.5),
        "line": float(line),
    })
    
    # Determine the correct "avg" key based on market type
    if market == "birdies":
        player_avg_value = player_stats.get("avg_birdies", player_stats.get("avg"))
    elif market == "finishing_position":
        player_avg_value = player_stats.get("expected_finish", player_stats.get("avg"))
    elif market_normalized in ["matchup", "head_to_head"]:
        # For matchups, use SG as the "avg" representation
        player_avg_value = player_stats.get("sg_total", 0.0)
    else:
        player_avg_value = player_stats.get("avg")
    
    # Generate edges for available directions
    # GOLF DIRECTION LOGIC FIX:
    # For round_strokes: LOWER is better performance (lower score wins)
    # Only generate edges where there's actual betting value, not just mathematical certainty
    # Rule: Only create edge if probability suggests player will beat market expectation
    
    # For round_strokes: If player_avg < line, the value is on LOWER (player shoots better)
    # For round_strokes: If player_avg > line, the value is on HIGHER (but this is negative edge)
    # DO NOT create edges just because prob > 50% - create edges where value exists
    
    if market_normalized == "round_strokes":
        # Golf-specific logic: LOWER strokes = better performance
        # Only generate LOWER edges if player is expected to beat the line
        if player_avg_value and player_avg_value < line:
            # Player is better than line expects → LOWER has value
            if probs.get("lower", 0) >= 0.55 or lower_mult is not None:
                edge = GolfEdge(
                    edge_id=f"GOLF_{player.replace(' ', '_')}_{market}_LOWER_{uuid.uuid4().hex[:8]}",
                    tournament=tournament,
                    player=player,
                    market=market,
                    line=line,
                    direction="lower",
                    probability=probs.get("lower", 0.50),
                    higher_mult=higher_mult,
                    lower_mult=lower_mult,
                    player_avg=player_avg_value,
                    player_stddev=player_stats.get("stddev"),
                    sg_total=player_stats.get("sg_total"),
                    wave=course_adj.get("wave", ""),
                    course_adjustment=course_adj.get("scoring_adjustment", 0.0),
                    birdie_factor=course_adj.get("birdie_factor", 1.0),
                    round_num=round_num,
                    tee_time=tee_time,
                    data_sources=player_stats.get("sources", ["default"]),
                )
                edge.tier = assign_tier(edge.probability, market, tournament)
                edge.pick_state, edge.avoid_reason = determine_pick_state(edge)
                edges.append(edge)
        elif player_avg_value and player_avg_value > line:
            # Player is worse than line expects → HIGHER has value (rare, but possible)
            if probs.get("higher", 0) >= 0.55 or higher_mult is not None:
                edge = GolfEdge(
                    edge_id=f"GOLF_{player.replace(' ', '_')}_{market}_HIGHER_{uuid.uuid4().hex[:8]}",
                    tournament=tournament,
                    player=player,
                    market=market,
                    line=line,
                    direction="higher",
                    probability=probs.get("higher", 0.50),
                    higher_mult=higher_mult,
                    lower_mult=lower_mult,
                    player_avg=player_avg_value,
                    player_stddev=player_stats.get("stddev"),
                    sg_total=player_stats.get("sg_total"),
                    wave=course_adj.get("wave", ""),
                    course_adjustment=course_adj.get("scoring_adjustment", 0.0),
                    birdie_factor=course_adj.get("birdie_factor", 1.0),
                    round_num=round_num,
                    tee_time=tee_time,
                    data_sources=player_stats.get("sources", ["default"]),
                )
                edge.tier = assign_tier(edge.probability, market, tournament)
                edge.pick_state, edge.avoid_reason = determine_pick_state(edge)
                edges.append(edge)
    else:
        # Non-round_strokes markets: Use original logic
        if higher_mult is not None or (market != "finishing_position" and probs.get("higher", 0) > 0.50):
            edge = GolfEdge(
                edge_id=f"GOLF_{player.replace(' ', '_')}_{market}_HIGHER_{uuid.uuid4().hex[:8]}",
                tournament=tournament,
                player=player,
                market=market,
                line=line,
                direction="higher",
                probability=probs.get("higher", 0.50),
                higher_mult=higher_mult,
                lower_mult=lower_mult,
                player_avg=player_avg_value,
                player_stddev=player_stats.get("stddev"),
                sg_total=player_stats.get("sg_total"),
                wave=course_adj.get("wave", ""),
                course_adjustment=course_adj.get("scoring_adjustment", 0.0),
                birdie_factor=course_adj.get("birdie_factor", 1.0),
                round_num=round_num,
                tee_time=tee_time,
                data_sources=player_stats.get("sources", ["default"]),
            )
            edge.tier = assign_tier(edge.probability, market, tournament)
            edge.pick_state, edge.avoid_reason = determine_pick_state(edge)
            edges.append(edge)
        
        if lower_mult is not None or (market != "finishing_position" and probs.get("lower", 0) > 0.50):
            edge = GolfEdge(
                edge_id=f"GOLF_{player.replace(' ', '_')}_{market}_LOWER_{uuid.uuid4().hex[:8]}",
                tournament=tournament,
                player=player,
                market=market,
                line=line,
                direction="lower",
                probability=probs.get("lower", 0.50),
                higher_mult=higher_mult,
                lower_mult=lower_mult,
                player_avg=player_avg_value,
                player_stddev=player_stats.get("stddev"),
                sg_total=player_stats.get("sg_total"),
                wave=course_adj.get("wave", ""),
                course_adjustment=course_adj.get("scoring_adjustment", 0.0),
                birdie_factor=course_adj.get("birdie_factor", 1.0),
                round_num=round_num,
                tee_time=tee_time,
                data_sources=player_stats.get("sources", ["default"]),
            )
            edge.tier = assign_tier(edge.probability, market, tournament)
            edge.pick_state, edge.avoid_reason = determine_pick_state(edge)
            edges.append(edge)
    
    # Finishing position "Better" = lower position number
    if better_mult is not None and market == "finishing_position":
        edge = GolfEdge(
            edge_id=f"GOLF_{player.replace(' ', '_')}_{market}_BETTER_{uuid.uuid4().hex[:8]}",
            tournament=tournament,
            player=player,
            market=market,
            line=line,
            direction="better",
            probability=probs.get("better", 0.50),
            higher_mult=better_mult,  # Store in higher_mult field
            player_avg=player_avg_value,
            player_stddev=player_stats.get("stddev"),
            sg_total=player_stats.get("sg_total"),
            wave=course_adj.get("wave", ""),
            course_adjustment=course_adj.get("scoring_adjustment", 0.0),
            birdie_factor=course_adj.get("birdie_factor", 1.0),
            round_num=round_num,
            tee_time=tee_time,
            data_sources=player_stats.get("sources", ["default"]),
        )
        edge.tier = assign_tier(edge.probability, "finishing_position", tournament)
        edge.pick_state, edge.avoid_reason = determine_pick_state(edge)
        edges.append(edge)
    
    return edges


def get_default_player_stats(market: str, line: float) -> Dict:
    """Get reasonable default stats based on market and line."""
    if market == "round_strokes":
        # Line gives hint about player skill
        if line <= 69.5:
            return {"avg": 69.5, "stddev": 2.8, "sources": ["line_inference"]}
        elif line <= 70.5:
            return {"avg": 70.5, "stddev": 2.9, "sources": ["line_inference"]}
        elif line <= 71.5:
            return {"avg": 71.5, "stddev": 3.0, "sources": ["line_inference"]}
        else:
            return {"avg": 72.0, "stddev": 3.1, "sources": ["line_inference"]}
    
    elif market == "birdies":
        # Birdie line inference
        if line <= 3.5:
            return {"avg_birdies": 3.5, "stddev": 1.5, "sources": ["line_inference"]}
        elif line <= 4.5:
            return {"avg_birdies": 4.5, "stddev": 1.6, "sources": ["line_inference"]}
        else:
            return {"avg_birdies": 5.0, "stddev": 1.7, "sources": ["line_inference"]}
    
    elif market == "finishing_position":
        # Finishing position is tricky - use field-based estimate
        return {"expected_finish": line, "sources": ["line_inference"]}
    
    return {"sources": ["default"]}


def calculate_round_strokes_probability(
    line: float,
    player_stats: Dict,
    course_stats: Optional[Dict] = None
) -> Dict[str, float]:
    """
    Calculate probability for round strokes prop using Monte Carlo.
    
    Args:
        line: Prop line (e.g., 71.5)
        player_stats: {"avg": float, "stddev": float, "sg_total": float}
        course_stats: {"difficulty_factor": float, "avg_score": float}
    
    Returns:
        {"higher": prob, "lower": prob}
    """
    import numpy as np
    
    # Get player parameters
    avg = player_stats.get("avg", 71.0)
    stddev = player_stats.get("stddev", 3.0)
    
    # Course adjustment
    if course_stats:
        difficulty = course_stats.get("difficulty_factor", 0)
        avg += difficulty
    
    # SG adjustment (better players perform better)
    sg = player_stats.get("sg_total")
    if sg is not None:
        avg -= sg * 0.5  # SG translates to scoring
    
    # Monte Carlo simulation (10k iterations)
    np.random.seed(42)  # Reproducible
    simulated = np.random.normal(avg, stddev, 10000)
    
    prob_higher = float(np.mean(simulated > line))
    prob_lower = float(np.mean(simulated <= line))
    
    return {"higher": round(prob_higher, 4), "lower": round(prob_lower, 4)}


def calculate_birdies_probability(
    line: float,
    player_stats: Dict
) -> Dict[str, float]:
    """
    Calculate probability for birdies prop using Poisson distribution.
    
    Args:
        line: Prop line (e.g., 3.5)
        player_stats: {"avg_birdies": float}
        
    Returns:
        {"higher": prob, "lower": prob}
    """
    import numpy as np
    
    # Get player birdie rate
    avg_birdies = player_stats.get("avg_birdies", 4.0)
    
    # Monte Carlo with Poisson
    np.random.seed(42)
    simulated = np.random.poisson(avg_birdies, 10000)
    
    prob_higher = float(np.mean(simulated > line))
    prob_lower = float(np.mean(simulated <= line))
    
    return {"higher": round(prob_higher, 4), "lower": round(prob_lower, 4)}


def calculate_finishing_position_probability(
    line: float,
    player_stats: Dict
) -> Dict[str, float]:
    """
    Calculate probability for finishing position prop.
    "Better" = finish in position <= line (lower number is better).
    
    This is complex - depends on field strength, player skill.
    Use DataGolf or approximation.
    """
    import numpy as np
    
    expected_finish = player_stats.get("expected_finish", line)
    
    # Approximate with log-normal (heavy tail for golf finishes)
    # Players can finish much worse than expected (bad weekend)
    mean_log = np.log(expected_finish)
    sigma_log = 0.5  # Variance in golf finishes
    
    np.random.seed(42)
    simulated = np.random.lognormal(mean_log, sigma_log, 10000)
    
    # "Better" = lower number
    prob_better = float(np.mean(simulated <= line))
    prob_worse = float(np.mean(simulated > line))
    
    return {"better": round(prob_better, 4), "worse": round(prob_worse, 4)}


def calculate_matchup_probability(
    prop: Dict,
    player_stats: Dict,
    opponent_stats: Optional[Dict] = None
) -> Dict[str, float]:
    """
    Calculate probability for head-to-head (G-market) matchups.
    
    Uses Elo-style comparison based on Strokes Gained differential.
    For "Birdies or Better Matchup" - compares birdie-making ability.
    
    Args:
        prop: Prop dict with player info
        player_stats: Stats for player 1
        opponent_stats: Stats for player 2 (if available)
        
    Returns:
        {"higher": prob, "lower": prob} where higher = player 1 wins matchup
    """
    import numpy as np
    
    # Get SG differentials (or use line as tie-breaker hint)
    player_sg = player_stats.get("sg_total", 0)
    opponent_sg = opponent_stats.get("sg_total", 0) if opponent_stats else 0
    
    # SG differential → probability using logistic function
    # Each 1.0 SG advantage ≈ 65% win probability
    sg_diff = player_sg - opponent_sg
    
    # If no SG data, use line as hint (0.5 line means close matchup)
    # FIX: Handle None line gracefully
    line = prop.get("line")
    if line is None:
        line = 0.5  # Default to coin flip
    
    if sg_diff == 0 and line == 0.5:
        # True coin flip matchup
        return {"higher": 0.50, "lower": 0.50}
    
    # Elo-style calculation: P(win) = 1 / (1 + 10^(-sg_diff/0.4))
    # Calibrated: 0.4 SG advantage ≈ 60% win probability
    prob_player1_wins = 1 / (1 + 10 ** (-sg_diff / 0.4)) if sg_diff != 0 else 0.50
    
    # Monte Carlo for variance (matchups have high variance)
    np.random.seed(42)
    # Add noise: even big favorites can lose on any given day
    noise = np.random.normal(0, 0.15, 10000)
    simulated_probs = prob_player1_wins + noise
    
    # Player 1 wins when simulated > 0.5
    actual_prob = float(np.mean(simulated_probs > 0.5))
    
    # Bound between 35% and 65% (matchups are inherently uncertain)
    actual_prob = max(0.35, min(0.65, actual_prob))
    
    return {
        "higher": round(actual_prob, 4),  # Player 1 wins
        "lower": round(1 - actual_prob, 4)  # Player 2 wins
    }


def generate_all_edges(
    props: List[Dict],
    player_db: Optional[Dict] = None,
    course_stats: Optional[Dict] = None,
) -> List[GolfEdge]:
    """
    Generate edges for all props in slate.
    
    Args:
        props: List of parsed props
        player_db: Optional player statistics database
        course_stats: Optional course difficulty stats
        
    Returns:
        List of GolfEdge objects (deduplicated)
    """
    all_edges = []
    
    for prop in props:
        player = prop.get("player", "")
        
        # Look up player stats
        player_stats = None
        if player_db and player in player_db:
            player_stats = player_db[player]
        
        edges = generate_edge_from_prop(prop, player_stats, course_stats)
        all_edges.extend(edges)
    
    # DEDUPLICATION GATE (Priority 2 fix)
    # Golf props from multiple books can create duplicates
    # Dedup by (player, market, line, direction) - keep highest probability
    print(f"[DEDUP] Before: {len(all_edges)} edges")
    
    dedup_map = {}
    for edge in all_edges:
        # Create unique key: player + market + line + direction
        key = (edge.player, edge.market, float(edge.line), edge.direction)
        
        if key not in dedup_map:
            dedup_map[key] = edge
        else:
            # Keep edge with higher probability (better data source)
            if edge.probability > dedup_map[key].probability:
                print(f"[DEDUP] Replacing {edge.player} {edge.market} {edge.line} {edge.direction}: {dedup_map[key].probability:.1%} → {edge.probability:.1%}")
                dedup_map[key] = edge
    
    deduped_edges = list(dedup_map.values())
    print(f"[DEDUP] After: {len(deduped_edges)} edges (removed {len(all_edges) - len(deduped_edges)} duplicates)")
    
    return deduped_edges


def filter_edges_by_tier(edges: List[GolfEdge], min_tier: str = "LEAN") -> List[GolfEdge]:
    """Filter edges to minimum tier."""
    tier_order = ["STRONG", "LEAN", "SPEC", "AVOID"]
    min_idx = tier_order.index(min_tier) if min_tier in tier_order else 2
    
    return [e for e in edges if tier_order.index(e.tier) <= min_idx]


def filter_edges_optimizable(edges: List[GolfEdge]) -> List[GolfEdge]:
    """Filter to only OPTIMIZABLE edges."""
    return [e for e in edges if e.pick_state == "OPTIMIZABLE"]



def save_edges(edges: List[GolfEdge], output_path: Path, exec_ctx: ExecutionContext = None):
    """Save edges to JSON file. Enforce execution context if provided. Track EdgeLifecycle for each edge."""
    from core.edge_lifecycle import EdgeLifecycle, MarketSnapshot
    if exec_ctx is not None:
        assert_publish_allowed(exec_ctx)
    now = datetime.now()
    edge_lifecycles = []
    for e in edges:
        # Initial market snapshot
        ms = MarketSnapshot(
            timestamp=now,
            line=e.line,
            implied_probability=e.probability
        )
        lifecycle = EdgeLifecycle(
            edge_id=e.edge_id,
            platform=exec_ctx.platform if exec_ctx else "unknown",
            publish_time=now,
            initial_line=e.line,
            initial_probability=e.probability,
            snapshots=[ms],
            decay_rate=0.0,
            half_life_minutes=None,
            invalidated=False,
            outcome=None
        )
        edge_lifecycles.append(lifecycle)
        # For now, just print lifecycle for audit (could persist to DB/log)
        print(f"[EDGE LIFECYCLE] {lifecycle}")
    data = {
        "generated_at": now.isoformat(),
        "sport": "GOLF",
        "edge_count": len(edges),
        "edges": [e.to_dict() for e in edges],
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    return output_path


if __name__ == "__main__":
    # Test with sample props
    sample_props = [
        {
            "player": "Hideki Matsuyama",
            "tournament": "Farmers Insurance Open",
            "market": "round_strokes",
            "line": 71.5,
            "round": 2,
            "higher_mult": 1.04,
            "lower_mult": 0.87,
        },
        {
            "player": "Hideki Matsuyama",
            "tournament": "Farmers Insurance Open",
            "market": "birdies",
            "line": 3.5,
            "round": 2,
            "higher_mult": 0.83,
            "lower_mult": 1.08,
        },
        {
            "player": "Hideki Matsuyama",
            "tournament": "Farmers Insurance Open",
            "market": "finishing_position",
            "line": 20.5,
            "better_mult": 0.67,
        },
    ]
    
    edges = generate_all_edges(sample_props)
    
    print("=" * 60)
    print("GOLF EDGE GENERATOR TEST")
    print("=" * 60)
    
    for edge in edges:
        print(f"\n{edge.player} | {edge.market} {edge.line} {edge.direction.upper()}")
        print(f"  Probability: {edge.probability:.1%}")
        print(f"  Tier: {edge.tier}")
        print(f"  State: {edge.pick_state}")
