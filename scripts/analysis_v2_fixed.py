"""
UNDERDOG FANTASY ANALYSIS SYSTEM v2.0
======================================
Strategic Upgrade Implementation - CORRECTED

Features:
1. Matchup Context Engine - Opponent defense adjustments
2. Volatility & Consistency Scoring - Hit rates, std dev, trends
3. Correlation Awareness System - Interdependent pick detection
4. Recency-Weighted Projections - 40% season, 60% recent
5. Value Score Algorithm - Composite prioritization

PIT @ CLE  |  JAX @ IND
December 28, 2025
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
import statistics

console = Console()

# ============================================================================
# DEFENSIVE RANKINGS (1-32, Lower = Better Defense)
# ============================================================================
DEFENSE_RANKINGS = {
    "PIT": {"rush": 3, "pass": 8, "overall": 5, "red_zone": 6, "sacks_allowed": 28},
    "CLE": {"rush": 20, "pass": 15, "overall": 18, "red_zone": 22, "sacks_allowed": 42},
    "JAX": {"rush": 28, "pass": 26, "overall": 25, "red_zone": 28, "sacks_allowed": 38},
    "IND": {"rush": 18, "pass": 12, "overall": 14, "red_zone": 15, "sacks_allowed": 32},
}

# ============================================================================
# PLAYER DATA WITH GAME-BY-GAME STATS (CORRECTED STRUCTURE)
# ============================================================================
PLAYER_DATA = {
    # PITTSBURGH STEELERS
    "Russell Wilson": {
        "team": "PIT", "opp": "CLE", "pos": "QB",
        "props": [
            {
                "stat": "Pass Yards", "line": 215.5, "type": "pass",
                "game_logs": [215, 242, 185, 228, 195, 232, 210, 198, 225, 220]
            },
            {
                "stat": "Pass TDs", "line": 1.5, "type": "pass_td",
                "game_logs": [2, 1, 2, 2, 1, 2, 1, 2, 2, 1]
            },
        ]
    },
    "Najee Harris": {
        "team": "PIT", "opp": "CLE", "pos": "RB",
        "props": [
            {
                "stat": "Rush Yards", "line": 55.5, "type": "rush",
                "game_logs": [55, 72, 48, 68, 62, 58, 75, 45, 68, 55, 72, 62, 58, 48, 65]
            },
        ]
    },
    "Jaylen Warren": {
        "team": "PIT", "opp": "CLE", "pos": "RB",
        "props": [
            {
                "stat": "Rush Yards", "line": 30.5, "type": "rush",
                "game_logs": [42, 28, 38, 35, 45, 32, 28, 42, 35, 38, 28, 42, 35, 45]
            },
        ]
    },
    "George Pickens": {
        "team": "PIT", "opp": "CLE", "pos": "WR",
        "props": [
            {
                "stat": "Rec Yards", "line": 60.5, "type": "rec",
                "game_logs": [85, 62, 78, 92, 55, 88, 45, 95, 68, 72, 82, 58, 75, 68]
            },
            {
                "stat": "Receptions", "line": 4.5, "type": "rec_count",
                "game_logs": [5, 4, 6, 5, 4, 5, 3, 6, 5, 4, 5, 4, 5, 4]
            },
        ]
    },
    "Pat Freiermuth": {
        "team": "PIT", "opp": "CLE", "pos": "TE",
        "props": [
            {
                "stat": "Rec Yards", "line": 30.5, "type": "rec",
                "game_logs": [45, 32, 28, 42, 38, 35, 28, 45, 32, 38, 42, 35, 28, 38, 42]
            },
        ]
    },
    "T.J. Watt": {
        "team": "PIT", "opp": "CLE", "pos": "DE",
        "props": [
            {
                "stat": "Sacks", "line": 0.5, "type": "sack",
                "game_logs": [1.0, 0.5, 1.5, 0, 1.0, 0.5, 1.0, 0, 1.5, 0.5, 1.0, 0, 1.5, 0.5]
            },
        ]
    },
    
    # CLEVELAND BROWNS
    "Jameis Winston": {
        "team": "CLE", "opp": "PIT", "pos": "QB",
        "props": [
            {
                "stat": "Pass Yards", "line": 245.5, "type": "pass",
                "game_logs": [268, 235, 275, 195, 285, 220, 255, 310]
            },
            {
                "stat": "INTs", "line": 0.5, "type": "int",
                "game_logs": [1, 2, 1, 0, 2, 1, 1, 2]
            },
        ]
    },
    "Nick Chubb": {
        "team": "CLE", "opp": "PIT", "pos": "RB",
        "injury": "LIMITED - Post knee surgery",
        "props": [
            {
                "stat": "Rush Yards", "line": 45.5, "type": "rush",
                "game_logs": [38, 42, 28, 35, 32, 45, 22]
            },
        ]
    },
    "Quinshon Judkins": {
        "team": "CLE", "opp": "PIT", "pos": "RB",
        "props": [
            {
                "stat": "Rush Yards", "line": 55.5, "type": "rush",
                "game_logs": [62, 48, 55, 42, 58, 45, 52, 65, 48, 55, 42, 58, 62, 48, 55, 52]
            },
        ]
    },
    "Jerry Jeudy": {
        "team": "CLE", "opp": "PIT", "pos": "WR",
        "props": [
            {
                "stat": "Rec Yards", "line": 55.5, "type": "rec",
                "game_logs": [72, 55, 68, 48, 75, 42, 62, 58, 72, 55, 48, 65, 58, 72]
            },
        ]
    },
    "David Njoku": {
        "team": "CLE", "opp": "PIT", "pos": "TE",
        "props": [
            {
                "stat": "Rec Yards", "line": 45.5, "type": "rec",
                "game_logs": [58, 42, 55, 48, 62, 38, 52, 45, 58, 42, 55, 48, 52, 45, 58]
            },
        ]
    },
    "Myles Garrett": {
        "team": "CLE", "opp": "PIT", "pos": "DE",
        "props": [
            {
                "stat": "Sacks", "line": 0.5, "type": "sack",
                "game_logs": [1.0, 1.5, 0.5, 2.0, 0, 1.0, 1.5, 0.5, 1.0, 0, 1.5, 1.0, 0.5, 1.0]
            },
        ]
    },
    
    # JACKSONVILLE JAGUARS
    "Trevor Lawrence": {
        "team": "JAX", "opp": "IND", "pos": "QB",
        "injury": "QUESTIONABLE - Shoulder",
        "props": [
            {
                "stat": "Pass Yards", "line": 246.5, "type": "pass",
                "game_logs": [195, 188, 215, 225, 178, 210, 195, 235, 185, 220]
            },
            {
                "stat": "Pass TDs", "line": 1.5, "type": "pass_td",
                "game_logs": [1, 0, 2, 1, 1, 1, 1, 2, 0, 1]
            },
        ]
    },
    "Travis Etienne": {
        "team": "JAX", "opp": "IND", "pos": "RB",
        "role_change": "REDUCED - Bigsby now lead back",
        "props": [
            {
                "stat": "Rush Yards", "line": 67.5, "type": "rush",
                "game_logs": [62, 55, 42, 48, 35, 28, 42, 32, 38, 28, 42, 32, 45, 28, 35]
            },
            {
                "stat": "Rush+Rec Yards", "line": 85.5, "type": "rush_rec",
                "game_logs": [75, 68, 55, 62, 48, 38, 52, 42, 48, 35, 52, 42, 55, 38, 45]
            },
            {
                "stat": "Receptions", "line": 2.5, "type": "rec_count",
                "game_logs": [3, 2, 3, 2, 4, 2, 3, 2, 3, 2, 3, 2, 3, 2]
            },
        ]
    },
    "Tank Bigsby": {
        "team": "JAX", "opp": "IND", "pos": "RB",
        "props": [
            {
                "stat": "Rush Yards", "line": 55.5, "type": "rush",
                "game_logs": [42, 55, 48, 62, 45, 58, 42, 52, 48, 55, 62, 75, 68, 72, 58, 65]
            },
        ]
    },
    "Brian Thomas": {
        "team": "JAX", "opp": "IND", "pos": "WR",
        "props": [
            {
                "stat": "Rec Yards", "line": 65.5, "type": "rec",
                "game_logs": [82, 68, 95, 72, 88, 65, 78, 92, 75, 68, 85, 72, 95, 78, 82, 75, 88]
            },
            {
                "stat": "Receptions", "line": 4.5, "type": "rec_count",
                "game_logs": [5, 4, 6, 5, 5, 4, 5, 6, 5, 4, 5, 5, 6, 5, 5, 4, 5]
            },
        ]
    },
    "Travon Walker": {
        "team": "JAX", "opp": "IND", "pos": "DE",
        "props": [
            {
                "stat": "Sacks", "line": 0.5, "type": "sack",
                "game_logs": [0.5, 1.0, 0.5, 0, 1.0, 0.5, 1.0, 0, 0.5, 1.5, 0.5, 1.0, 0, 0.5, 1.0, 0.5, 1.0]
            },
        ]
    },
    "Foyesade Oluokun": {
        "team": "JAX", "opp": "IND", "pos": "LB",
        "props": [
            {
                "stat": "Tackles", "line": 7.5, "type": "tackles",
                "game_logs": [8, 9, 7, 10, 8, 6, 9, 11, 7, 8, 10, 7, 9]
            },
        ]
    },
    
    # INDIANAPOLIS COLTS
    "Joe Flacco": {
        "team": "IND", "opp": "JAX", "pos": "QB",
        "props": [
            {
                "stat": "Pass Yards", "line": 215.5, "type": "pass",
                "game_logs": [235, 210, 245, 195, 228, 215, 242, 198, 225, 218]
            },
            {
                "stat": "Pass TDs", "line": 1.5, "type": "pass_td",
                "game_logs": [2, 1, 2, 1, 2, 1, 2, 1, 2, 1]
            },
        ]
    },
    "Jonathan Taylor": {
        "team": "IND", "opp": "JAX", "pos": "RB",
        "props": [
            {
                "stat": "Rush Yards", "line": 70.5, "type": "rush",
                "game_logs": [112, 95, 128, 85, 115, 92, 105, 135, 88, 118, 95, 125, 102, 98, 95]
            },
            {
                "stat": "Rush+Rec TDs", "line": 0.5, "type": "td",
                "game_logs": [1, 0, 2, 1, 1, 0, 1, 2, 0, 1, 1, 1, 0, 1, 1]
            },
            {
                "stat": "Rush Attempts", "line": 18.5, "type": "rush_att",
                "game_logs": [22, 18, 25, 17, 21, 19, 23, 24, 16, 22, 19, 24, 20, 18, 20]
            },
        ]
    },
    "Michael Pittman Jr.": {
        "team": "IND", "opp": "JAX", "pos": "WR",
        "props": [
            {
                "stat": "Rec Yards", "line": 54.5, "type": "rec",
                "game_logs": [55, 48, 62, 42, 58, 45, 52, 65, 48, 55, 42, 58, 52, 48, 55]
            },
        ]
    },
    "Alec Pierce": {
        "team": "IND", "opp": "JAX", "pos": "WR",
        "props": [
            {
                "stat": "Rec Yards", "line": 50.5, "type": "rec",
                "game_logs": [72, 35, 85, 28, 95, 42, 68, 25, 82, 38, 75, 32, 88, 45, 72]
            },
        ]
    },
    "Zaire Franklin": {
        "team": "IND", "opp": "JAX", "pos": "LB",
        "props": [
            {
                "stat": "Tackles", "line": 6.5, "type": "tackles",
                "game_logs": [8, 7, 9, 6, 8, 7, 9, 6, 8, 7, 8, 6, 7, 8, 7]
            },
        ]
    },
}

# ============================================================================
# CORRELATION GROUPS - Interdependent Picks
# ============================================================================
CORRELATION_GROUPS = [
    {
        "name": "Pittsburgh Passing Attack",
        "players": ["Russell Wilson", "George Pickens", "Pat Freiermuth"],
        "dependency": "All depend on Wilson having time to throw",
        "props": ["Pass Yards", "Rec Yards"]
    },
    {
        "name": "Cleveland Passing Attack",
        "players": ["Jameis Winston", "Jerry Jeudy", "David Njoku"],
        "dependency": "All depend on Winston's volatile performance",
        "props": ["Pass Yards", "Rec Yards"]
    },
    {
        "name": "Jacksonville Passing Attack",
        "players": ["Trevor Lawrence", "Brian Thomas"],
        "dependency": "Thomas production tied to Lawrence health/performance",
        "props": ["Pass Yards", "Rec Yards"]
    },
    {
        "name": "Pittsburgh Rush Attack",
        "players": ["Najee Harris", "Jaylen Warren"],
        "dependency": "Carries split - one thriving may limit other",
        "props": ["Rush Yards"]
    },
    {
        "name": "Jacksonville Rush Committee",
        "players": ["Travis Etienne", "Tank Bigsby"],
        "dependency": "Zero-sum - Bigsby taking Etienne's work",
        "props": ["Rush Yards"]
    },
    {
        "name": "PIT Defense vs CLE Pressure",
        "players": ["T.J. Watt", "Jameis Winston"],
        "dependency": "Watt sacks correlate with Winston INTs/pressure",
        "props": ["Sacks", "INTs"]
    },
]


def calculate_matchup_adjustment(opp, prop_type):
    """Apply matchup adjustment based on opponent defensive rankings"""
    opp_def = DEFENSE_RANKINGS[opp]
    
    if prop_type in ["rush", "rush_rec", "rush_att"]:
        rank = opp_def["rush"]
    elif prop_type in ["pass", "rec", "rec_count"]:
        rank = opp_def["pass"]
    elif prop_type == "sack":
        rank = 33 - (opp_def["sacks_allowed"] / 2)
    elif prop_type in ["td", "pass_td"]:
        rank = opp_def["red_zone"]
    elif prop_type == "int":
        return 1.15  # Vs PIT - more likely to throw INTs
    elif prop_type == "tackles":
        return 1.0  # Neutral
    else:
        rank = opp_def["overall"]
    
    # Convert rank to multiplier (1-32 → 0.85-1.15)
    if rank <= 10:
        return 0.85 + (rank * 0.005)
    elif rank >= 25:
        return 1.10 + ((rank - 25) * 0.015)
    else:
        return 1.0 + ((rank - 16) * 0.01)


def calculate_recency_weighted_avg(game_logs):
    """Calculate weighted average: 40% season, 60% last 4 games"""
    if len(game_logs) < 4:
        return sum(game_logs) / len(game_logs)
    
    season_avg = sum(game_logs) / len(game_logs)
    recent_avg = sum(game_logs[-4:]) / 4
    
    return (season_avg * 0.4) + (recent_avg * 0.6)


def calculate_volatility_metrics(game_logs, line):
    """Calculate volatility, hit rate, and trend"""
    if len(game_logs) < 3:
        return {"std_dev": 0, "hit_rate": 0, "trend": "STABLE", "consistency": "UNKNOWN"}
    
    std_dev = statistics.stdev(game_logs)
    mean = statistics.mean(game_logs)
    cv = (std_dev / mean) * 100 if mean > 0 else 0
    
    hits = sum(1 for g in game_logs if g > line)
    hit_rate = (hits / len(game_logs)) * 100
    
    season_avg = sum(game_logs) / len(game_logs)
    recent_avg = sum(game_logs[-4:]) / 4 if len(game_logs) >= 4 else season_avg
    
    if recent_avg > season_avg * 1.10:
        trend = "HOT"
    elif recent_avg > season_avg * 1.05:
        trend = "UP"
    elif recent_avg < season_avg * 0.90:
        trend = "DOWN"
    elif recent_avg < season_avg * 0.95:
        trend = "COOLING"
    else:
        trend = "STABLE"
    
    if cv < 20:
        consistency = "HIGH"
    elif cv < 35:
        consistency = "MODERATE"
    else:
        consistency = "LOW"
    
    return {
        "std_dev": std_dev,
        "hit_rate": hit_rate,
        "trend": trend,
        "consistency": consistency,
        "cv": cv,
        "recent_avg": recent_avg,
        "season_avg": season_avg
    }


def calculate_value_score(edge_pct, hit_rate, consistency, matchup_boost, volatility_penalty):
    """
    Value Score = 
      (Edge Size × 2.0) +
      (Hit Rate × 0.5) +
      (Consistency Score × 3.0) -
      (Volatility Penalty × 4.0) +
      (Matchup Boost × 1.5)
    """
    consistency_score = {"HIGH": 10, "MODERATE": 5, "LOW": 0, "UNKNOWN": 3}.get(consistency, 3)
    
    value = (
        (edge_pct * 2.0) +
        (hit_rate * 0.5) +
        (consistency_score * 3.0) -
        (volatility_penalty * 4.0) +
        (matchup_boost * 1.5)
    )
    
    return max(0, min(100, value))


def get_visual_indicators(cv, trend, consistency):
    """Get visual indicators for display"""
    if consistency == "HIGH":
        cons_icon = "🔒🔒🔒"
    elif consistency == "MODERATE":
        cons_icon = "🔒🔒"
    else:
        cons_icon = "⚡"
    
    trend_icons = {
        "HOT": "🔥",
        "UP": "📈",
        "DOWN": "📉",
        "COOLING": "❄️",
        "STABLE": "➡️"
    }
    trend_icon = trend_icons.get(trend, "➡️")
    
    return cons_icon, trend_icon


def analyze_player(player_name, player_data):
    """Complete analysis of a player's props"""
    results = []
    
    for prop in player_data["props"]:
        game_logs = prop["game_logs"]
        line = prop["line"]
        stat = prop["stat"]
        prop_type = prop["type"]
        
        season_avg = sum(game_logs) / len(game_logs)
        recent_avg = sum(game_logs[-4:]) / 4 if len(game_logs) >= 4 else season_avg
        weighted_avg = calculate_recency_weighted_avg(game_logs)
        
        matchup_mult = calculate_matchup_adjustment(player_data["opp"], prop_type)
        adjusted_proj = weighted_avg * matchup_mult
        
        vol_metrics = calculate_volatility_metrics(game_logs, line)
        
        edge = adjusted_proj - line
        edge_pct = (edge / line) * 100 if line > 0 else 0
        
        matchup_boost = (matchup_mult - 1.0) * 100
        vol_penalty = vol_metrics["cv"] / 10 if vol_metrics["cv"] > 25 else 0
        
        value_score = calculate_value_score(
            edge_pct, 
            vol_metrics["hit_rate"],
            vol_metrics["consistency"],
            matchup_boost,
            vol_penalty
        )
        
        if edge_pct > 20 and vol_metrics["hit_rate"] >= 70:
            play = "OVER ✅"
            priority = "SLAM"
        elif edge_pct > 12 and vol_metrics["hit_rate"] >= 60:
            play = "OVER"
            priority = "STRONG"
        elif edge_pct < -20 and vol_metrics["hit_rate"] <= 30:
            play = "UNDER ✅"
            priority = "SLAM"
        elif edge_pct < -12 and vol_metrics["hit_rate"] <= 40:
            play = "UNDER"
            priority = "STRONG"
        elif edge_pct > 8:
            play = "LEAN OVER"
            priority = "LEAN"
        elif edge_pct < -8:
            play = "LEAN UNDER"
            priority = "LEAN"
        else:
            play = "HOLD"
            priority = "SKIP"
        
        cons_icon, trend_icon = get_visual_indicators(
            vol_metrics["cv"], vol_metrics["trend"], vol_metrics["consistency"]
        )
        
        risk_flags = []
        if player_data.get("injury"):
            risk_flags.append(f"INJURY: {player_data['injury']}")
        if player_data.get("role_change"):
            risk_flags.append(f"ROLE: {player_data['role_change']}")
        
        results.append({
            "player": player_name,
            "team": player_data["team"],
            "opp": player_data["opp"],
            "stat": stat,
            "line": line,
            "season_avg": season_avg,
            "recent_avg": recent_avg,
            "weighted_avg": weighted_avg,
            "matchup_mult": matchup_mult,
            "adjusted_proj": adjusted_proj,
            "edge": edge,
            "edge_pct": edge_pct,
            "hit_rate": vol_metrics["hit_rate"],
            "std_dev": vol_metrics["std_dev"],
            "trend": vol_metrics["trend"],
            "consistency": vol_metrics["consistency"],
            "value_score": value_score,
            "play": play,
            "priority": priority,
            "cons_icon": cons_icon,
            "trend_icon": trend_icon,
            "risk_flags": risk_flags,
        })
    
    return results


def detect_correlations(all_picks):
    """Detect correlated picks in user's selections"""
    warnings = []
    
    for group in CORRELATION_GROUPS:
        matched = []
        for pick in all_picks:
            if (pick["player"] in group["players"] and 
                pick["priority"] in ["SLAM", "STRONG", "LEAN"] and
                any(p in pick["stat"] for p in group.get("props", [pick["stat"]]))):
                matched.append(pick)
        
        if len(matched) >= 2:
            warnings.append({
                "group_name": group["name"],
                "players": [(p["player"], p["stat"]) for p in matched],
                "dependency": group["dependency"],
                "count": len(matched)
            })
    
    return warnings


def print_priority_pick(result, rank):
    """Print detailed priority pick in enhanced format"""
    border = "yellow" if result["priority"] == "SLAM" else "cyan"
    direction = "OVER" if "OVER" in result["play"] else "UNDER"
    
    console.print(Panel.fit(
        f"[bold white]🔥 PRIORITY {rank}: {result['player'].upper()} - {result['stat'].upper()} {direction} {result['line']}[/bold white]",
        border_style=border
    ))
    
    console.print(f"[bold]Value Score: {result['value_score']:.1f}/100[/bold] | "
                  f"Edge: {result['edge']:+.1f} ({result['edge_pct']:+.1f}%) | "
                  f"Hit Rate: {result['hit_rate']:.0f}%")
    
    console.print(f"\n[bold cyan]📊 Projection Metrics:[/bold cyan]")
    console.print(f"  • Season Average: {result['season_avg']:.1f}")
    diff = result['recent_avg'] - result['season_avg']
    color = 'green' if diff > 0 else 'red'
    console.print(f"  • Last 4 Average: {result['recent_avg']:.1f} {result['trend_icon']} "
                  f"[{color}]{diff:+.1f}[/{color}]")
    console.print(f"  • Weighted Projection: {result['weighted_avg']:.1f}")
    
    opp_def = DEFENSE_RANKINGS[result["opp"]]
    matchup_pct = (result["matchup_mult"] - 1) * 100
    m_color = 'green' if matchup_pct > 0 else 'red'
    console.print(f"  • Matchup Adjusted: {result['adjusted_proj']:.1f} "
                  f"[{m_color}]{matchup_pct:+.0f}%[/{m_color}] vs {result['opp']} D")
    
    console.print(f"\n[bold cyan]🎯 Consistency Profile:[/bold cyan] {result['cons_icon']} ({result['consistency']} Volatility)")
    console.print(f"  • Hits line in {result['hit_rate']:.0f}% of games")
    console.print(f"  • Standard deviation: {result['std_dev']:.1f}")
    
    risk_level = "LOW" if result["value_score"] > 70 else ("MODERATE" if result["value_score"] > 50 else "HIGH")
    risk_color = "green" if risk_level == "LOW" else ("yellow" if risk_level == "MODERATE" else "red")
    
    console.print(f"\n[bold cyan]⚠️ Risk Assessment:[/bold cyan] [{risk_color}]{risk_level}[/{risk_color}]")
    
    if result["risk_flags"]:
        for flag in result["risk_flags"]:
            console.print(f"  • [red]{flag}[/red]")
    else:
        console.print(f"  • No significant concerns")
    
    if result["value_score"] >= 80:
        rec = "MAX PLAY (3-4 units)"
    elif result["value_score"] >= 65:
        rec = "STRONG PLAY (2-3 units)"
    elif result["value_score"] >= 50:
        rec = "MODERATE PLAY (1-2 units)"
    else:
        rec = "SMALL PLAY (0.5-1 unit)"
    
    console.print(f"\n[bold green]💡 Recommendation: {rec}[/bold green]")
    console.print("")


def print_correlation_warnings(warnings):
    """Print correlation warnings"""
    if not warnings:
        console.print("[green]✅ No major correlation concerns detected in your picks.[/green]\n")
        return
    
    console.print(Panel.fit(
        "[bold red]🚨 CORRELATED PICKS DETECTED[/bold red]",
        border_style="red"
    ))
    
    for warn in warnings:
        console.print(f"\n[bold]Group: {warn['group_name']}[/bold]")
        for player, stat in warn['players']:
            console.print(f"  • {player} ({stat})")
        console.print(f"[dim]Risk: {warn['dependency']}[/dim]")
        console.print(f"[yellow]Recommendation: Select 1-2 max from this correlated group[/yellow]")
    
    console.print("")


def print_summary_table(all_results):
    """Print summary table of all picks"""
    
    table = Table(title="All Picks Summary (Sorted by Value Score)", show_header=True, header_style="bold cyan")
    table.add_column("Player", width=15)
    table.add_column("Prop", width=12)
    table.add_column("Line", justify="center", width=6)
    table.add_column("Proj", justify="center", width=6)
    table.add_column("Edge", justify="center", width=8)
    table.add_column("Hit%", justify="center", width=5)
    table.add_column("Trend", justify="center", width=5)
    table.add_column("Cons", justify="center", width=5)
    table.add_column("Value", justify="center", width=5)
    table.add_column("Play", width=12)
    
    sorted_results = sorted(all_results, key=lambda x: x["value_score"], reverse=True)
    
    for r in sorted_results:
        if r["priority"] == "SLAM":
            play_style = "bold green" if "OVER" in r["play"] else "bold red"
        elif r["priority"] == "STRONG":
            play_style = "green" if "OVER" in r["play"] else "red"
        elif r["priority"] == "LEAN":
            play_style = "yellow"
        else:
            play_style = "dim"
        
        if r["value_score"] >= 70:
            value_style = "bold green"
        elif r["value_score"] >= 50:
            value_style = "yellow"
        else:
            value_style = "dim"
        
        table.add_row(
            r["player"][:14],
            r["stat"][:11],
            str(r["line"]),
            f"{r['adjusted_proj']:.1f}",
            f"{r['edge']:+.1f}",
            f"{r['hit_rate']:.0f}%",
            r["trend_icon"],
            r["cons_icon"][:2],
            Text(f"{r['value_score']:.0f}", style=value_style),
            Text(r["play"], style=play_style)
        )
    
    console.print(table)


def print_slam_plays(all_results):
    """Print categorized slam plays"""
    slams_over = [r for r in all_results if r["priority"] == "SLAM" and "OVER" in r["play"]]
    slams_under = [r for r in all_results if r["priority"] == "SLAM" and "UNDER" in r["play"]]
    
    if slams_over:
        console.print(Panel.fit("[bold green]🎯 SLAM OVERS[/bold green]", border_style="green"))
        for s in slams_over:
            console.print(f"  {s['player']} {s['stat']} OVER {s['line']} "
                          f"(Proj: {s['adjusted_proj']:.1f}, Edge: {s['edge']:+.1f}, Hit: {s['hit_rate']:.0f}%)")
    
    if slams_under:
        console.print(Panel.fit("[bold red]🎯 SLAM UNDERS[/bold red]", border_style="red"))
        for s in slams_under:
            console.print(f"  {s['player']} {s['stat']} UNDER {s['line']} "
                          f"(Proj: {s['adjusted_proj']:.1f}, Edge: {s['edge']:+.1f}, Hit: {s['hit_rate']:.0f}%)")
    
    console.print("")


def main():
    console.print(Panel.fit(
        "[bold cyan]🏈 UNDERDOG FANTASY ANALYSIS SYSTEM v2.0[/bold cyan]\n"
        "[white]Strategic Intelligence Upgrade[/white]\n"
        "[dim]Matchup Context | Volatility Scoring | Correlation Detection[/dim]\n"
        "[dim]Recency Weighting | Value Score Algorithm[/dim]\n"
        f"[yellow]Games: PIT @ CLE  |  JAX @ IND[/yellow]\n"
        f"[dim]Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]",
        border_style="cyan"
    ))
    
    console.print("""
[bold]ANALYSIS METHODOLOGY:[/bold]
  📊 [cyan]Recency Weighting[/cyan]: 40% Season + 60% Last 4 Games
  🎯 [cyan]Matchup Adjustments[/cyan]: Based on Opponent Defense Rankings (1-32)
  📈 [cyan]Volatility Scoring[/cyan]: Standard Deviation + Hit Rate + Trend
  🔗 [cyan]Correlation Detection[/cyan]: Interdependent Pick Warnings
  💎 [cyan]Value Score[/cyan]: Edge × HitRate × Consistency × Matchup
""")
    
    # Analyze all players
    all_results = []
    for player_name, player_data in PLAYER_DATA.items():
        results = analyze_player(player_name, player_data)
        all_results.extend(results)
    
    all_results.sort(key=lambda x: x["value_score"], reverse=True)
    
    # Top priority picks
    console.print("\n" + "="*70)
    console.print("[bold magenta]            🏆 TOP PRIORITY PICKS (VALUE SCORE 70+)[/bold magenta]")
    console.print("="*70 + "\n")
    
    top_picks = [r for r in all_results if r["value_score"] >= 70 and r["priority"] in ["SLAM", "STRONG"]][:8]
    
    for i, pick in enumerate(top_picks, 1):
        print_priority_pick(pick, i)
    
    # Slam plays summary
    console.print("\n" + "="*70)
    console.print("[bold white]            🎯 SLAM PLAYS SUMMARY[/bold white]")
    console.print("="*70 + "\n")
    print_slam_plays(all_results)
    
    # Correlation warnings
    console.print("\n" + "="*70)
    console.print("[bold yellow]            🔗 CORRELATION ANALYSIS[/bold yellow]")
    console.print("="*70 + "\n")
    
    correlations = detect_correlations(all_results)
    print_correlation_warnings(correlations)
    
    # Full summary table
    console.print("\n" + "="*70)
    console.print("[bold white]            📋 COMPLETE PICK SUMMARY[/bold white]")
    console.print("="*70 + "\n")
    
    print_summary_table(all_results)
    
    console.print("""
[bold]VALUE SCORE INTERPRETATION:[/bold]
  [green]80+[/green]:  Elite priority (multiple strong factors align) → MAX PLAY (3-4 units)
  [yellow]65-79[/yellow]: Strong play (clear edge with manageable risk) → STRONG PLAY (2-3 units)
  [dim]50-64[/dim]: Moderate lean (good edge, some volatility) → MODERATE (1-2 units)
  [red]<50[/red]:  Skip or very small stakes only

[bold]VISUAL INDICATORS:[/bold]
  🔒🔒🔒 High consistency (low volatility)  |  ⚡ High volatility (boom/bust)
  🔥 Hot trend (last 4 > season +10%)  |  📈 Improving  |  📉 Declining
""")
    
    console.print("\n[dim]⚠️ Always verify injury reports and starting lineups before game time![/dim]\n")


if __name__ == "__main__":
    main()
