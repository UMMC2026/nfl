"""
UNDERDOG FANTASY - ENHANCED ANALYSIS WITH REAL-WORLD CONTEXT
=============================================================
Layers of Analysis:
1. Base Stats (Season Averages)
2. Matchup Context (Opponent Defense Rankings)
3. Game Script Prediction (Score, Pace, Play Volume)
4. Recent Form (Last 3 Games Trend)
5. Situational Factors (Home/Away, Weather, Injuries)
6. Consistency Rating (How often they hit the line)
7. Risk Assessment Score

PIT @ CLE  |  JAX @ IND
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from datetime import datetime

console = Console()

# ============================================================================
# DEFENSIVE RANKINGS (2024 Season - Lower = Better Defense)
# ============================================================================
DEFENSE_RANKINGS = {
    "PIT": {
        "overall": 5,
        "rush_def": 3,      # Excellent run D
        "pass_def": 8,
        "sacks_allowed": 28,  # O-line gives up sacks
        "ppg_allowed": 18.2,
        "rush_ypg_allowed": 98.5,
        "pass_ypg_allowed": 195.2,
        "red_zone_def": 6,
        "notes": "Elite front 7, Watt disrupts everything"
    },
    "CLE": {
        "overall": 18,
        "rush_def": 20,     # Weak run D
        "pass_def": 15,
        "sacks_allowed": 42,  # Poor O-line protection
        "ppg_allowed": 25.6,
        "rush_ypg_allowed": 125.8,
        "pass_ypg_allowed": 228.5,
        "red_zone_def": 22,
        "notes": "Garrett elite but D falls apart around him"
    },
    "JAX": {
        "overall": 25,
        "rush_def": 22,
        "pass_def": 26,
        "sacks_allowed": 38,
        "ppg_allowed": 25.6,
        "rush_ypg_allowed": 128.5,
        "pass_ypg_allowed": 245.2,
        "red_zone_def": 28,
        "notes": "Porous secondary, Walker/Hines-Allen get pressure"
    },
    "IND": {
        "overall": 14,
        "rush_def": 18,
        "pass_def": 12,
        "sacks_allowed": 32,
        "ppg_allowed": 22.8,
        "rush_ypg_allowed": 118.2,
        "pass_ypg_allowed": 215.5,
        "red_zone_def": 15,
        "notes": "Bend don't break, improved secondary"
    }
}

# ============================================================================
# GAME SCRIPT PREDICTIONS
# ============================================================================
GAME_SCRIPTS = {
    "PIT_CLE": {
        "spread": -7.5,  # PIT favored
        "total": 42.5,
        "predicted_score": {"PIT": 24, "CLE": 17},
        "game_flow": "PIT CONTROL",
        "pace": "SLOW",  # Low total, run-heavy
        "blowout_risk": 35,  # % chance of 14+ margin
        "notes": [
            "PIT likely to run clock with lead",
            "CLE will need to throw to keep up",
            "Jameis turnover potential high",
            "Low-scoring, physical game expected"
        ],
        "pit_adjustments": {
            "rush_boost": 1.10,  # +10% rush with lead
            "pass_reduction": 0.92,  # Less need to throw
            "garbage_time": False
        },
        "cle_adjustments": {
            "rush_reduction": 0.85,  # Abandoning run when behind
            "pass_boost": 1.15,  # Throwing more to catch up
            "garbage_time": True  # Possible garbage time stats
        }
    },
    "JAX_IND": {
        "spread": -3.5,  # IND favored
        "total": 45.5,
        "predicted_score": {"IND": 27, "JAX": 21},
        "game_flow": "COMPETITIVE",
        "pace": "MODERATE",
        "blowout_risk": 20,
        "notes": [
            "Closer game, both teams run-first",
            "IND will lean heavily on JT",
            "JAX QB situation murky (Lawrence questionable)",
            "Higher scoring than PIT/CLE"
        ],
        "ind_adjustments": {
            "rush_boost": 1.15,  # JT featured heavily
            "pass_reduction": 0.95,
            "garbage_time": False
        },
        "jax_adjustments": {
            "rush_boost": 0.90,  # May need to throw
            "pass_boost": 1.05,
            "garbage_time": True
        }
    }
}

# ============================================================================
# PLAYER CONTEXT & RECENT FORM
# ============================================================================
PLAYER_CONTEXT = {
    # PITTSBURGH
    "Russell Wilson": {
        "recent_3": [185, 242, 212],  # Last 3 games pass yards
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 100,
        "matchup_history": "N/A",
        "risk_factors": ["Age (36)", "Cold weather impact"],
        "opportunity_score": 75,
        "consistency": 68  # % of games hitting typical lines
    },
    "Najee Harris": {
        "recent_3": [72, 55, 68],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 62,
        "matchup_history": "89 yds vs CLE last meeting",
        "risk_factors": ["Splits carries with Warren"],
        "opportunity_score": 70,
        "consistency": 55
    },
    "Jaylen Warren": {
        "recent_3": [42, 28, 38],
        "trend": "UP",
        "health": "HEALTHY", 
        "snap_pct": 38,
        "matchup_history": "45 yds vs CLE last meeting",
        "risk_factors": ["RB2, game-flow dependent"],
        "opportunity_score": 60,
        "consistency": 62
    },
    "George Pickens": {
        "recent_3": [85, 62, 78],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 95,
        "matchup_history": "92 yds vs CLE last year",
        "risk_factors": ["Drops", "Focus issues"],
        "opportunity_score": 90,
        "consistency": 72
    },
    "Pat Freiermuth": {
        "recent_3": [45, 32, 28],
        "trend": "DOWN",
        "health": "HEALTHY",
        "snap_pct": 85,
        "risk_factors": ["Red zone only sometimes"],
        "opportunity_score": 65,
        "consistency": 58
    },
    "T.J. Watt": {
        "recent_3": [1.0, 0.5, 1.5],  # Sacks
        "trend": "UP",
        "health": "HEALTHY",
        "snap_pct": 92,
        "matchup_history": "2.0 sacks vs CLE last year",
        "risk_factors": ["Sometimes doubled"],
        "opportunity_score": 95,
        "consistency": 75
    },
    
    # CLEVELAND
    "Jameis Winston": {
        "recent_3": [268, 235, 275],
        "trend": "VOLATILE",
        "health": "HEALTHY",
        "snap_pct": 100,
        "matchup_history": "First game vs PIT D",
        "risk_factors": ["TURNOVER PRONE - 1.25 INT/game", "Reckless throws"],
        "opportunity_score": 80,
        "consistency": 45  # Very inconsistent
    },
    "Nick Chubb": {
        "recent_3": [38, 42, 28],
        "trend": "DOWN",
        "health": "LIMITED",  # Returning from major injury
        "snap_pct": 35,  # Heavily limited
        "matchup_history": "Had 75 yds vs PIT when healthy",
        "risk_factors": ["POST-INJURY", "Pitch count likely", "Judkins taking work"],
        "opportunity_score": 40,
        "consistency": 35
    },
    "Quinshon Judkins": {
        "recent_3": [62, 48, 55],
        "trend": "UP",
        "health": "HEALTHY",
        "snap_pct": 55,
        "risk_factors": ["Rookie learning curve"],
        "opportunity_score": 70,
        "consistency": 58
    },
    "Jerry Jeudy": {
        "recent_3": [72, 55, 68],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 92,
        "matchup_history": "First year with CLE",
        "risk_factors": ["Winston's accuracy issues"],
        "opportunity_score": 85,
        "consistency": 65
    },
    "David Njoku": {
        "recent_3": [58, 42, 55],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 88,
        "risk_factors": ["Red zone dependent"],
        "opportunity_score": 75,
        "consistency": 70
    },
    "Myles Garrett": {
        "recent_3": [1.0, 1.5, 0.5],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 90,
        "matchup_history": "1.5 sacks vs PIT last year",
        "risk_factors": ["Gets doubled often"],
        "opportunity_score": 95,
        "consistency": 78
    },
    
    # JACKSONVILLE
    "Trevor Lawrence": {
        "recent_3": [195, 188, 215],
        "trend": "DOWN",
        "health": "QUESTIONABLE",  # Check status
        "snap_pct": 100,
        "matchup_history": "225 yds vs IND last year",
        "risk_factors": ["INJURY CONCERN", "No weapons", "Poor protection"],
        "opportunity_score": 65,
        "consistency": 52
    },
    "Travis Etienne": {
        "recent_3": [32, 42, 28],
        "trend": "DOWN",
        "health": "HEALTHY",
        "snap_pct": 45,  # REDUCED - Bigsby taking over
        "matchup_history": "62 yds vs IND last year",
        "risk_factors": ["LOST STARTING JOB", "Bigsby preferred", "May be benched"],
        "opportunity_score": 35,  # Very low now
        "consistency": 28  # Rarely hits old lines anymore
    },
    "Tank Bigsby": {
        "recent_3": [55, 62, 48],
        "trend": "UP",
        "health": "HEALTHY",
        "snap_pct": 55,  # Now the lead back
        "risk_factors": ["Goal line vulture potential"],
        "opportunity_score": 75,
        "consistency": 65
    },
    "Brian Thomas": {
        "recent_3": [82, 68, 95],
        "trend": "UP",
        "health": "HEALTHY",
        "snap_pct": 95,
        "matchup_history": "First year - rookie sensation",
        "risk_factors": ["QB play limits ceiling", "Gets double-teamed"],
        "opportunity_score": 90,
        "consistency": 72
    },
    "Travon Walker": {
        "recent_3": [0.5, 1.0, 0.5],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 88,
        "risk_factors": ["Inconsistent"],
        "opportunity_score": 70,
        "consistency": 58
    },
    
    # INDIANAPOLIS
    "Joe Flacco": {
        "recent_3": [235, 210, 245],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 100,
        "matchup_history": "Veteran knows how to manage",
        "risk_factors": ["Age (39)", "Limited mobility"],
        "opportunity_score": 70,
        "consistency": 65
    },
    "Jonathan Taylor": {
        "recent_3": [112, 95, 128],
        "trend": "HOT",
        "health": "HEALTHY",
        "snap_pct": 75,
        "matchup_history": "138 yds vs JAX last year",
        "risk_factors": ["Heavy workload fatigue late season"],
        "opportunity_score": 98,  # ELITE
        "consistency": 85  # Very consistent
    },
    "Michael Pittman Jr.": {
        "recent_3": [55, 48, 62],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 92,
        "matchup_history": "72 yds vs JAX last year",
        "risk_factors": ["Target competition"],
        "opportunity_score": 75,
        "consistency": 68
    },
    "Alec Pierce": {
        "recent_3": [72, 55, 48],
        "trend": "VOLATILE",
        "health": "HEALTHY",
        "snap_pct": 85,
        "risk_factors": ["Boom/bust deep threat"],
        "opportunity_score": 65,
        "consistency": 55
    },
    "Tyler Warren": {
        "recent_3": [52, 48, 55],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 90,
        "risk_factors": ["TE can be game-flow dependent"],
        "opportunity_score": 70,
        "consistency": 72
    },
    "Zaire Franklin": {
        "recent_3": [8, 7, 9],
        "trend": "STABLE",
        "health": "HEALTHY",
        "snap_pct": 100,
        "risk_factors": ["Tackle machine, very consistent"],
        "opportunity_score": 85,
        "consistency": 82
    }
}

# ============================================================================
# ENHANCED PROPS WITH FULL CONTEXT
# ============================================================================
ENHANCED_PROPS = [
    # PIT PLAYERS
    {
        "player": "Russell Wilson", "team": "PIT", "opp": "CLE",
        "stat": "Pass Yards", "line": 215.5, "season_avg": 215.0,
        "matchup_factor": 1.05,  # CLE pass D is mediocre (#15)
        "game_script_factor": 0.92,  # May not need to throw much
        "weather_factor": 0.95,  # Cold December game
    },
    {
        "player": "Najee Harris", "team": "PIT", "opp": "CLE",
        "stat": "Rush Yards", "line": 55.5, "season_avg": 61.3,
        "matchup_factor": 1.15,  # CLE rush D is weak (#20)
        "game_script_factor": 1.10,  # Run clock with lead
        "weather_factor": 1.05,  # Cold = more runs
    },
    {
        "player": "Jaylen Warren", "team": "PIT", "opp": "CLE",
        "stat": "Rush Yards", "line": 30.5, "season_avg": 35.2,
        "matchup_factor": 1.15,  # Weak CLE run D
        "game_script_factor": 1.10,
        "weather_factor": 1.05,
    },
    {
        "player": "George Pickens", "team": "PIT", "opp": "CLE",
        "stat": "Rec Yards", "line": 60.5, "season_avg": 72.8,
        "matchup_factor": 1.08,  # CLE CB room is average
        "game_script_factor": 0.95,  # Less pass volume
        "weather_factor": 0.95,
    },
    {
        "player": "Pat Freiermuth", "team": "PIT", "opp": "CLE",
        "stat": "Rec Yards", "line": 30.5, "season_avg": 36.4,
        "matchup_factor": 1.12,  # CLE struggles vs TEs
        "game_script_factor": 0.95,
        "weather_factor": 0.98,
    },
    {
        "player": "T.J. Watt", "team": "PIT", "opp": "CLE",
        "stat": "Sacks", "line": 0.5, "season_avg": 0.72,
        "matchup_factor": 1.25,  # CLE O-line is BAD (42 sacks allowed)
        "game_script_factor": 1.15,  # CLE throwing when behind
        "weather_factor": 1.0,
    },
    
    # CLE PLAYERS
    {
        "player": "Jameis Winston", "team": "CLE", "opp": "PIT",
        "stat": "Pass Yards", "line": 245.5, "season_avg": 251.5,
        "matchup_factor": 0.88,  # PIT has elite pass D (#8)
        "game_script_factor": 1.15,  # Throwing to catch up
        "weather_factor": 0.95,
    },
    {
        "player": "Jameis Winston", "team": "CLE", "opp": "PIT",
        "stat": "INTs", "line": 0.5, "season_avg": 1.25,
        "matchup_factor": 1.30,  # PIT ballhawks, Fitzpatrick
        "game_script_factor": 1.20,  # Forcing throws when behind
        "weather_factor": 1.05,  # Cold hands
    },
    {
        "player": "Nick Chubb", "team": "CLE", "opp": "PIT",
        "stat": "Rush Yards", "line": 45.5, "season_avg": 35.0,
        "matchup_factor": 0.75,  # PIT elite run D (#3)
        "game_script_factor": 0.80,  # Abandoning run when behind
        "weather_factor": 1.0,
    },
    {
        "player": "Jerry Jeudy", "team": "CLE", "opp": "PIT",
        "stat": "Rec Yards", "line": 45.5, "season_avg": 58.6,
        "matchup_factor": 0.90,  # Tough PIT secondary
        "game_script_factor": 1.15,  # More targets when trailing
        "weather_factor": 0.95,
    },
    {
        "player": "David Njoku", "team": "CLE", "opp": "PIT",
        "stat": "Rec Yards", "line": 35.5, "season_avg": 48.7,
        "matchup_factor": 0.92,  # PIT covers TEs well
        "game_script_factor": 1.10,
        "weather_factor": 0.98,
    },
    {
        "player": "Myles Garrett", "team": "CLE", "opp": "PIT",
        "stat": "Sacks", "line": 0.5, "season_avg": 0.89,
        "matchup_factor": 1.10,  # PIT O-line decent but not elite
        "game_script_factor": 0.95,  # PIT will run, less pass rush opps
        "weather_factor": 1.0,
    },
    
    # JAX PLAYERS
    {
        "player": "Trevor Lawrence", "team": "JAX", "opp": "IND",
        "stat": "Pass Yards", "line": 246.5, "season_avg": 204.5,
        "matchup_factor": 0.95,  # IND pass D is decent (#12)
        "game_script_factor": 1.05,  # May need to throw
        "weather_factor": 1.0,  # Dome game
    },
    {
        "player": "Travis Etienne", "team": "JAX", "opp": "IND",
        "stat": "Rush Yards", "line": 67.5, "season_avg": 37.2,
        "matchup_factor": 0.92,  # IND run D is decent
        "game_script_factor": 0.85,  # Trailing = less runs
        "weather_factor": 1.0,
    },
    {
        "player": "Travis Etienne", "team": "JAX", "opp": "IND",
        "stat": "Rush+Rec Yards", "line": 85.5, "season_avg": 54.1,
        "matchup_factor": 0.92,
        "game_script_factor": 0.85,
        "weather_factor": 1.0,
    },
    {
        "player": "Tank Bigsby", "team": "JAX", "opp": "IND",
        "stat": "Rush Yards", "line": 45.5, "season_avg": 47.9,
        "matchup_factor": 1.05,  # IND run D is exploitable
        "game_script_factor": 1.0,
        "weather_factor": 1.0,
    },
    {
        "player": "Brian Thomas", "team": "JAX", "opp": "IND",
        "stat": "Rec Yards", "line": 65.5, "season_avg": 75.4,
        "matchup_factor": 1.08,  # Can beat IND corners deep
        "game_script_factor": 1.05,  # Primary target
        "weather_factor": 1.0,
    },
    {
        "player": "Travon Walker", "team": "JAX", "opp": "IND",
        "stat": "Sacks", "line": 0.5, "season_avg": 0.62,
        "matchup_factor": 1.10,  # IND O-line has issues
        "game_script_factor": 1.0,
        "weather_factor": 1.0,
    },
    
    # IND PLAYERS
    {
        "player": "Joe Flacco", "team": "IND", "opp": "JAX",
        "stat": "Pass Yards", "line": 205.5, "season_avg": 220.0,
        "matchup_factor": 1.15,  # JAX has AWFUL pass D (#26)
        "game_script_factor": 0.92,  # JT will dominate, less need to throw
        "weather_factor": 1.0,
    },
    {
        "player": "Jonathan Taylor", "team": "IND", "opp": "JAX",
        "stat": "Rush Yards", "line": 70.5, "season_avg": 99.3,
        "matchup_factor": 1.18,  # JAX run D is weak (#22)
        "game_script_factor": 1.15,  # Featured in game plan
        "weather_factor": 1.0,
    },
    {
        "player": "Jonathan Taylor", "team": "IND", "opp": "JAX",
        "stat": "TDs", "line": 0.5, "season_avg": 1.27,
        "matchup_factor": 1.20,  # JAX red zone D is awful (#28)
        "game_script_factor": 1.15,
        "weather_factor": 1.0,
    },
    {
        "player": "Michael Pittman Jr.", "team": "IND", "opp": "JAX",
        "stat": "Rec Yards", "line": 44.5, "season_avg": 50.5,
        "matchup_factor": 1.12,  # JAX CBs are beatable
        "game_script_factor": 0.95,
        "weather_factor": 1.0,
    },
    {
        "player": "Alec Pierce", "team": "IND", "opp": "JAX",
        "stat": "Rec Yards", "line": 50.5, "season_avg": 58.1,
        "matchup_factor": 1.15,  # Deep shot opportunities vs JAX
        "game_script_factor": 0.95,
        "weather_factor": 1.0,
    },
    {
        "player": "Tyler Warren", "team": "IND", "opp": "JAX",
        "stat": "Rec Yards", "line": 48.5, "season_avg": 49.9,
        "matchup_factor": 1.10,  # JAX struggles vs TEs
        "game_script_factor": 0.98,
        "weather_factor": 1.0,
    },
    {
        "player": "Zaire Franklin", "team": "IND", "opp": "JAX",
        "stat": "Tackles", "line": 6.5, "season_avg": 7.2,
        "matchup_factor": 1.05,  # JAX will run, more tackling opps
        "game_script_factor": 1.0,
        "weather_factor": 1.0,
    },
]


def calculate_adjusted_projection(prop):
    """Calculate projection with all context factors"""
    base = prop["season_avg"]
    matchup = prop.get("matchup_factor", 1.0)
    script = prop.get("game_script_factor", 1.0)
    weather = prop.get("weather_factor", 1.0)
    
    # Get player context for additional adjustments
    player_ctx = PLAYER_CONTEXT.get(prop["player"], {})
    
    # Trend adjustment
    trend = player_ctx.get("trend", "STABLE")
    if trend == "HOT":
        trend_mult = 1.08
    elif trend == "UP":
        trend_mult = 1.05
    elif trend == "DOWN":
        trend_mult = 0.92
    elif trend == "VOLATILE":
        trend_mult = 1.0  # Neutral but high variance
    else:
        trend_mult = 1.0
    
    # Health adjustment
    health = player_ctx.get("health", "HEALTHY")
    if health == "QUESTIONABLE":
        health_mult = 0.85
    elif health == "LIMITED":
        health_mult = 0.75
    else:
        health_mult = 1.0
    
    # Calculate adjusted projection
    adjusted = base * matchup * script * weather * trend_mult * health_mult
    
    return adjusted


def calculate_risk_score(prop):
    """Calculate risk score (1-10, higher = more risky)"""
    player_ctx = PLAYER_CONTEXT.get(prop["player"], {})
    
    risk = 5  # Base risk
    
    # Consistency impacts risk
    consistency = player_ctx.get("consistency", 50)
    if consistency < 50:
        risk += 2
    elif consistency < 65:
        risk += 1
    elif consistency > 80:
        risk -= 1
    
    # Health impacts risk
    if player_ctx.get("health") == "QUESTIONABLE":
        risk += 2
    elif player_ctx.get("health") == "LIMITED":
        risk += 3
    
    # Volatile trend increases risk
    if player_ctx.get("trend") == "VOLATILE":
        risk += 1
    
    # Low opportunity score increases risk
    opp_score = player_ctx.get("opportunity_score", 70)
    if opp_score < 50:
        risk += 2
    elif opp_score < 65:
        risk += 1
    
    return min(10, max(1, risk))


def calculate_confidence(prop, adjusted_proj):
    """Calculate confidence score with all factors"""
    line = prop["line"]
    player_ctx = PLAYER_CONTEXT.get(prop["player"], {})
    
    # Base edge
    edge = adjusted_proj - line
    edge_pct = (edge / line) * 100 if line > 0 else 0
    
    # Start with edge-based confidence
    if edge_pct > 0:
        confidence = min(95, 50 + (edge_pct * 1.5))
    else:
        confidence = max(5, 50 + (edge_pct * 1.5))
    
    # Adjust for consistency
    consistency = player_ctx.get("consistency", 50)
    consistency_adj = (consistency - 50) / 100 * 10
    confidence += consistency_adj
    
    # Adjust for opportunity
    opp_score = player_ctx.get("opportunity_score", 70)
    opp_adj = (opp_score - 70) / 100 * 8
    confidence += opp_adj
    
    return min(98, max(2, confidence))


def analyze_enhanced_prop(prop):
    """Full enhanced analysis of a prop"""
    player = prop["player"]
    line = prop["line"]
    season_avg = prop["season_avg"]
    player_ctx = PLAYER_CONTEXT.get(player, {})
    
    # Calculate adjusted projection
    adjusted = calculate_adjusted_projection(prop)
    
    # Calculate edge
    edge = adjusted - line
    
    # Calculate risk and confidence
    risk = calculate_risk_score(prop)
    confidence = calculate_confidence(prop, adjusted)
    
    # Determine play
    if edge > 0 and confidence > 70:
        if confidence > 85:
            play = "STRONG OVER"
        else:
            play = "OVER"
    elif edge < 0 and confidence < 30:
        if confidence < 15:
            play = "STRONG UNDER"
        else:
            play = "UNDER"
    else:
        play = "HOLD"
    
    return {
        "player": player,
        "team": prop["team"],
        "opp": prop["opp"],
        "stat": prop["stat"],
        "line": line,
        "season_avg": season_avg,
        "adjusted_proj": adjusted,
        "edge": edge,
        "risk": risk,
        "confidence": confidence,
        "play": play,
        "trend": player_ctx.get("trend", "STABLE"),
        "health": player_ctx.get("health", "HEALTHY"),
        "consistency": player_ctx.get("consistency", 50),
        "risk_factors": player_ctx.get("risk_factors", [])
    }


def print_game_analysis(game_key, game_data, props):
    """Print enhanced analysis for a game"""
    
    # Game header with script info
    script = GAME_SCRIPTS[game_key]
    teams = game_key.split("_")
    
    console.print(Panel.fit(
        f"[bold white]{teams[0]} @ {teams[1]}[/bold white]\n"
        f"[cyan]Spread: {teams[1]} {script['spread']} | Total: {script['total']}[/cyan]\n"
        f"[yellow]Predicted: {teams[0]} {script['predicted_score'][teams[0]]} - {teams[1]} {script['predicted_score'][teams[1]]}[/yellow]\n"
        f"[dim]Game Flow: {script['game_flow']} | Pace: {script['pace']} | Blowout Risk: {script['blowout_risk']}%[/dim]",
        border_style="cyan"
    ))
    
    # Script notes
    console.print("[bold]Game Script Notes:[/bold]")
    for note in script["notes"]:
        console.print(f"  • {note}")
    console.print("")
    
    # Analyze props for each team
    for team in teams:
        team_def = DEFENSE_RANKINGS[team]
        opp = teams[1] if team == teams[0] else teams[0]
        opp_def = DEFENSE_RANKINGS[opp]
        
        console.print(Panel.fit(
            f"[bold]{team}[/bold] vs [dim]{opp} Defense (Rank #{opp_def['overall']})[/dim]\n"
            f"[dim]Opp Rush D: #{opp_def['rush_def']} | Opp Pass D: #{opp_def['pass_def']}[/dim]\n"
            f"[dim]{opp_def['notes']}[/dim]",
            border_style="yellow" if team in ["PIT", "IND"] else "red"
        ))
        
        # Get team props
        team_props = [p for p in props if p["team"] == team]
        
        # Create enhanced table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Player", width=16)
        table.add_column("Stat", width=12)
        table.add_column("Line", justify="center", width=6)
        table.add_column("Avg", justify="center", width=6)
        table.add_column("Adj", justify="center", width=6)
        table.add_column("Edge", justify="center", width=6)
        table.add_column("Trend", justify="center", width=6)
        table.add_column("Risk", justify="center", width=5)
        table.add_column("Conf", justify="center", width=5)
        table.add_column("Play", width=12)
        
        strong_plays = []
        
        for prop in team_props:
            result = analyze_enhanced_prop(prop)
            
            # Color coding
            if "STRONG" in result["play"]:
                play_style = "bold green" if "OVER" in result["play"] else "bold red"
                strong_plays.append(result)
            elif result["play"] != "HOLD":
                play_style = "green" if "OVER" in result["play"] else "red"
            else:
                play_style = "dim"
            
            # Trend indicator
            trend_map = {"HOT": "🔥", "UP": "📈", "DOWN": "📉", "STABLE": "➡️", "VOLATILE": "⚡"}
            trend_icon = trend_map.get(result["trend"], "➡️")
            
            # Risk color
            risk_style = "green" if result["risk"] <= 4 else ("yellow" if result["risk"] <= 6 else "red")
            
            # Health indicator
            health_icon = "✓" if result["health"] == "HEALTHY" else ("?" if result["health"] == "QUESTIONABLE" else "⚠")
            
            table.add_row(
                f"{result['player'][:15]} {health_icon}",
                result["stat"][:12],
                str(result["line"]),
                f"{result['season_avg']:.1f}",
                f"{result['adjusted_proj']:.1f}",
                f"{result['edge']:+.1f}",
                trend_icon,
                Text(str(result["risk"]), style=risk_style),
                f"{result['confidence']:.0f}%",
                Text(result["play"], style=play_style)
            )
        
        console.print(table)
        
        # Print strong plays with context
        if strong_plays:
            console.print(f"\n[bold green]💎 {team} STRONG PLAYS:[/bold green]")
            for sp in strong_plays:
                direction = "OVER" if "OVER" in sp["play"] else "UNDER"
                console.print(f"  [bold]{sp['player']}[/bold] {sp['stat']} {direction} {sp['line']}")
                console.print(f"    Adj Proj: {sp['adjusted_proj']:.1f} | Edge: {sp['edge']:+.1f}")
                console.print(f"    Confidence: {sp['confidence']:.0f}% | Risk: {sp['risk']}/10")
                if sp["risk_factors"]:
                    console.print(f"    ⚠️ Risks: {', '.join(sp['risk_factors'][:2])}")
                console.print("")
        
        console.print("")


def print_final_rankings():
    """Print final rankings across all games"""
    
    console.print("\n" + "="*70)
    console.print("[bold magenta]📊 FINAL RISK-ADJUSTED RANKINGS[/bold magenta]")
    console.print("="*70)
    
    # Analyze all props
    all_results = []
    for prop in ENHANCED_PROPS:
        result = analyze_enhanced_prop(prop)
        if result["play"] != "HOLD":
            # Calculate value score: confidence * (10 - risk) / 10
            value_score = result["confidence"] * (10 - result["risk"]) / 10
            result["value_score"] = value_score
            all_results.append(result)
    
    # Sort by value score
    all_results.sort(key=lambda x: x["value_score"], reverse=True)
    
    # Top plays table
    console.print("\n[bold green]🏆 TOP 10 VALUE PLAYS (Confidence × Safety)[/bold green]\n")
    
    table = Table(show_header=True, header_style="bold white")
    table.add_column("#", width=3)
    table.add_column("Player", width=18)
    table.add_column("Team", width=5)
    table.add_column("Prop", width=14)
    table.add_column("Line", justify="center", width=6)
    table.add_column("Adj Proj", justify="center", width=8)
    table.add_column("Play", justify="center", width=10)
    table.add_column("Conf", justify="center", width=5)
    table.add_column("Risk", justify="center", width=5)
    table.add_column("Value", justify="center", width=6)
    
    for i, r in enumerate(all_results[:10], 1):
        play_style = "green" if "OVER" in r["play"] else "red"
        risk_style = "green" if r["risk"] <= 4 else ("yellow" if r["risk"] <= 6 else "red")
        
        table.add_row(
            str(i),
            r["player"],
            r["team"],
            r["stat"],
            str(r["line"]),
            f"{r['adjusted_proj']:.1f}",
            Text(r["play"].replace("STRONG ", ""), style=play_style),
            f"{r['confidence']:.0f}%",
            Text(str(r["risk"]), style=risk_style),
            f"{r['value_score']:.1f}"
        )
    
    console.print(table)
    
    # Riskiest plays
    high_risk = [r for r in all_results if r["risk"] >= 7]
    if high_risk:
        console.print("\n[bold red]⚠️ HIGH-RISK PLAYS (Proceed with Caution):[/bold red]")
        for r in high_risk[:5]:
            console.print(f"  • {r['player']} {r['stat']} - Risk: {r['risk']}/10")
            console.print(f"    Reasons: {', '.join(r['risk_factors'][:2])}")
    
    # Lock of the day
    if all_results:
        lock = all_results[0]
        console.print(f"\n[bold green]🔒 LOCK OF THE DAY:[/bold green]")
        console.print(f"   [bold]{lock['player']}[/bold] ({lock['team']}) {lock['stat']}")
        direction = "OVER" if "OVER" in lock['play'] else "UNDER"
        console.print(f"   {direction} {lock['line']} (Proj: {lock['adjusted_proj']:.1f})")
        console.print(f"   Confidence: {lock['confidence']:.0f}% | Risk: {lock['risk']}/10 | Value: {lock['value_score']:.1f}")


def main():
    console.print(Panel.fit(
        "[bold cyan]🏈 UNDERDOG - ENHANCED ANALYSIS[/bold cyan]\n"
        "[white]With Matchup Context, Game Script & Risk Assessment[/white]\n"
        f"[dim]Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]",
        border_style="cyan"
    ))
    
    console.print("""
[bold]ANALYSIS LAYERS:[/bold]
  1. 📊 Season Averages (Base)
  2. 🎯 Matchup Factors (Opponent Defense Rankings)
  3. 📈 Game Script (Spread, Pace, Blowout Risk)
  4. 🌡️ Weather & Situational
  5. 🔥 Recent Form (Last 3 Games Trend)
  6. ⚕️ Health Status
  7. 📉 Consistency Rating
  8. ⚠️ Risk Assessment (1-10)
  9. 💎 Value Score (Confidence × Safety)
""")
    
    # Analyze Game 1
    console.print("\n" + "="*70)
    console.print("[bold white]GAME 1: PITTSBURGH STEELERS @ CLEVELAND BROWNS[/bold white]")
    console.print("="*70 + "\n")
    
    pit_cle_props = [p for p in ENHANCED_PROPS if p["team"] in ["PIT", "CLE"]]
    print_game_analysis("PIT_CLE", GAME_SCRIPTS["PIT_CLE"], pit_cle_props)
    
    # Analyze Game 2
    console.print("\n" + "="*70)
    console.print("[bold white]GAME 2: JACKSONVILLE JAGUARS @ INDIANAPOLIS COLTS[/bold white]")
    console.print("="*70 + "\n")
    
    jax_ind_props = [p for p in ENHANCED_PROPS if p["team"] in ["JAX", "IND"]]
    print_game_analysis("JAX_IND", GAME_SCRIPTS["JAX_IND"], jax_ind_props)
    
    # Final rankings
    print_final_rankings()
    
    console.print("\n[dim]⚠️ Always verify injury reports before game time![/dim]\n")


if __name__ == "__main__":
    main()
