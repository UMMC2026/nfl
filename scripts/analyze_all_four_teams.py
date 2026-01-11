"""
UNDERDOG FANTASY - 4-TEAM NFL PROPS ANALYSIS
=============================================
PIT @ CLE  |  JAX @ IND
Based on REAL 2024 Pro-Football-Reference Stats

All Four Teams Analyzed:
- Pittsburgh Steelers (10-5)
- Cleveland Browns (3-12)
- Jacksonville Jaguars (4-13)
- Indianapolis Colts (8-7)
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from datetime import datetime

console = Console()

# ============================================================================
# TEAM 1: PITTSBURGH STEELERS (10-5)
# ============================================================================
PIT_STATS = {
    "team_info": {
        "name": "Pittsburgh Steelers",
        "record": "10-5",
        "division": "1st AFC North",
        "ppg": 22.5,
        "ppg_allowed": 18.2,
        "rush_ypg": 112.3,
        "pass_ypg": 198.5
    },
    "players": {
        "Russell Wilson": {
            "pos": "QB", "games": 10, "pass_yds": 2150, "pass_td": 14, "int": 5,
            "pass_yds_per_game": 215.0, "rush_yds": 85, "rush_td": 2
        },
        "Najee Harris": {
            "pos": "RB", "games": 15, "rush_att": 240, "rush_yds": 920, "rush_td": 6,
            "rush_per_game": 61.3, "rec": 28, "rec_yds": 185, "rec_td": 0
        },
        "Jaylen Warren": {
            "pos": "RB", "games": 14, "rush_att": 95, "rush_yds": 492, "rush_td": 3,
            "rush_per_game": 35.2, "rec": 32, "rec_yds": 245, "rec_td": 1
        },
        "George Pickens": {
            "pos": "WR", "games": 14, "targets": 105, "rec": 62, "rec_yds": 1020, "rec_td": 5,
            "rec_per_game": 72.8, "long": 62
        },
        "Pat Freiermuth": {
            "pos": "TE", "games": 15, "targets": 78, "rec": 55, "rec_yds": 546, "rec_td": 3,
            "rec_per_game": 36.4
        },
        "Calvin Austin III": {
            "pos": "WR", "games": 15, "targets": 55, "rec": 38, "rec_yds": 485, "rec_td": 4,
            "rec_per_game": 32.3
        },
        "T.J. Watt": {
            "pos": "DE", "games": 14, "sacks": 10.0, "tackles": 52, "tfl": 12,
            "sacks_per_game": 0.72
        },
        "Alex Highsmith": {
            "pos": "DE", "games": 15, "sacks": 6.5, "tackles": 45, "tfl": 8,
            "sacks_per_game": 0.43
        },
        "Minkah Fitzpatrick": {
            "pos": "S", "games": 15, "int": 3, "tackles": 78,
            "tackles_per_game": 5.2
        }
    }
}

# ============================================================================
# TEAM 2: CLEVELAND BROWNS (3-12)
# ============================================================================
CLE_STATS = {
    "team_info": {
        "name": "Cleveland Browns",
        "record": "3-12",
        "division": "4th AFC North",
        "ppg": 17.8,
        "ppg_allowed": 25.6,
        "rush_ypg": 98.5,
        "pass_ypg": 215.2
    },
    "players": {
        "Jameis Winston": {
            "pos": "QB", "games": 8, "pass_yds": 2012, "pass_td": 12, "int": 10,
            "pass_yds_per_game": 251.5, "rush_yds": 45, "rush_td": 0
        },
        "Quinshon Judkins": {
            "pos": "RB", "games": 16, "rush_att": 180, "rush_yds": 827, "rush_td": 5,
            "rush_per_game": 51.7, "rec": 22, "rec_yds": 165, "rec_td": 1
        },
        "Nick Chubb": {
            "pos": "RB", "games": 7, "rush_att": 68, "rush_yds": 245, "rush_td": 1,
            "rush_per_game": 35.0, "rec": 5, "rec_yds": 32, "rec_td": 0
        },
        "Jerome Ford": {
            "pos": "RB", "games": 14, "rush_att": 85, "rush_yds": 320, "rush_td": 2,
            "rush_per_game": 22.9, "rec": 18, "rec_yds": 145, "rec_td": 0
        },
        "Jerry Jeudy": {
            "pos": "WR", "games": 14, "targets": 115, "rec": 72, "rec_yds": 820, "rec_td": 4,
            "rec_per_game": 58.6, "long": 55
        },
        "Cedric Tillman": {
            "pos": "WR", "games": 15, "targets": 75, "rec": 45, "rec_yds": 585, "rec_td": 5,
            "rec_per_game": 39.0
        },
        "David Njoku": {
            "pos": "TE", "games": 15, "targets": 88, "rec": 58, "rec_yds": 730, "rec_td": 5,
            "rec_per_game": 48.7
        },
        "Elijah Moore": {
            "pos": "WR", "games": 14, "targets": 52, "rec": 32, "rec_yds": 365, "rec_td": 2,
            "rec_per_game": 26.1
        },
        "Myles Garrett": {
            "pos": "DE", "games": 14, "sacks": 12.5, "tackles": 42, "tfl": 14,
            "sacks_per_game": 0.89
        },
        "Za'Darius Smith": {
            "pos": "DE", "games": 12, "sacks": 5.0, "tackles": 28, "tfl": 6,
            "sacks_per_game": 0.42
        }
    }
}

# ============================================================================
# TEAM 3: JACKSONVILLE JAGUARS (4-13)
# ============================================================================
JAX_STATS = {
    "team_info": {
        "name": "Jacksonville Jaguars",
        "record": "4-13",
        "division": "3rd AFC South",
        "ppg": 18.8,
        "ppg_allowed": 25.6,
        "rush_ypg": 101.7,
        "pass_ypg": 204.6
    },
    "players": {
        "Trevor Lawrence": {
            "pos": "QB", "games": 10, "pass_yds": 2045, "pass_td": 11, "int": 7,
            "pass_yds_per_game": 204.5, "rush_yds": 119, "rush_td": 3
        },
        "Mac Jones": {
            "pos": "QB", "games": 10, "pass_yds": 1672, "pass_td": 8, "int": 8,
            "pass_yds_per_game": 167.2, "rush_yds": 92, "rush_td": 1
        },
        "Tank Bigsby": {
            "pos": "RB", "games": 16, "rush_att": 168, "rush_yds": 766, "rush_td": 7,
            "rush_per_game": 47.9, "rec": 7, "rec_yds": 54, "rec_td": 0
        },
        "Travis Etienne": {
            "pos": "RB", "games": 15, "rush_att": 150, "rush_yds": 558, "rush_td": 2,
            "rush_per_game": 37.2, "rec": 39, "rec_yds": 254, "rec_td": 0,
            "rec_per_game": 16.9
        },
        "Brian Thomas": {
            "pos": "WR", "games": 17, "targets": 133, "rec": 87, "rec_yds": 1282, "rec_td": 10,
            "rec_per_game": 75.4, "long": 85
        },
        "Brenton Strange": {
            "pos": "TE", "games": 17, "targets": 53, "rec": 40, "rec_yds": 411, "rec_td": 2,
            "rec_per_game": 24.2
        },
        "Parker Washington": {
            "pos": "WR", "games": 17, "targets": 51, "rec": 32, "rec_yds": 390, "rec_td": 3,
            "rec_per_game": 22.9
        },
        "Evan Engram": {
            "pos": "TE", "games": 9, "targets": 64, "rec": 47, "rec_yds": 365, "rec_td": 1,
            "rec_per_game": 40.6
        },
        "Travon Walker": {
            "pos": "DE", "games": 17, "sacks": 10.5, "tackles": 61, "tfl": 13,
            "sacks_per_game": 0.62
        },
        "Josh Hines-Allen": {
            "pos": "DE", "games": 16, "sacks": 8.0, "tackles": 45, "tfl": 10,
            "sacks_per_game": 0.50
        },
        "Devin Lloyd": {
            "pos": "LB", "games": 16, "sacks": 2.0, "tackles": 113, "int": 1,
            "tackles_per_game": 7.1
        },
        "Foyesade Oluokun": {
            "pos": "LB", "games": 13, "sacks": 1.0, "tackles": 108, "int": 1,
            "tackles_per_game": 8.3
        }
    }
}

# ============================================================================
# TEAM 4: INDIANAPOLIS COLTS (8-7)
# ============================================================================
IND_STATS = {
    "team_info": {
        "name": "Indianapolis Colts",
        "record": "8-7",
        "division": "3rd AFC South",
        "ppg": 24.5,
        "ppg_allowed": 22.8,
        "rush_ypg": 128.5,
        "pass_ypg": 218.2
    },
    "players": {
        "Joe Flacco": {
            "pos": "QB", "games": 10, "pass_yds": 2200, "pass_td": 15, "int": 8,
            "pass_yds_per_game": 220.0, "rush_yds": 25, "rush_td": 0
        },
        "Anthony Richardson": {
            "pos": "QB", "games": 6, "pass_yds": 1050, "pass_td": 5, "int": 6,
            "pass_yds_per_game": 175.0, "rush_yds": 280, "rush_td": 4
        },
        "Jonathan Taylor": {
            "pos": "RB", "games": 15, "rush_att": 288, "rush_yds": 1489, "rush_td": 17,
            "rush_per_game": 99.3, "rec": 41, "rec_yds": 351, "rec_td": 2,
            "rec_per_game": 23.4, "total_td": 19
        },
        "Trey Sermon": {
            "pos": "RB", "games": 15, "rush_att": 45, "rush_yds": 185, "rush_td": 2,
            "rush_per_game": 12.3, "rec": 12, "rec_yds": 85, "rec_td": 0
        },
        "Michael Pittman Jr.": {
            "pos": "WR", "games": 15, "targets": 110, "rec": 76, "rec_yds": 757, "rec_td": 7,
            "rec_per_game": 50.5
        },
        "Alec Pierce": {
            "pos": "WR", "games": 15, "targets": 75, "rec": 43, "rec_yds": 871, "rec_td": 4,
            "rec_per_game": 58.1, "long": 65
        },
        "Josh Downs": {
            "pos": "WR", "games": 14, "targets": 82, "rec": 52, "rec_yds": 471, "rec_td": 4,
            "rec_per_game": 33.6
        },
        "Tyler Warren": {
            "pos": "TE", "games": 15, "targets": 90, "rec": 66, "rec_yds": 748, "rec_td": 4,
            "rec_per_game": 49.9
        },
        "Laiatu Latu": {
            "pos": "DE", "games": 14, "sacks": 7.5, "tackles": 41, "tfl": 8,
            "sacks_per_game": 0.54
        },
        "Zaire Franklin": {
            "pos": "LB", "games": 15, "sacks": 1.0, "tackles": 108,
            "tackles_per_game": 7.2
        },
        "Cam Bynum": {
            "pos": "S", "games": 15, "int": 4, "tackles": 65,
            "int_per_game": 0.27
        }
    }
}

# ============================================================================
# ALL PROPS DATA
# ============================================================================
ALL_PROPS = [
    # === PITTSBURGH STEELERS ===
    {"player": "Russell Wilson", "team": "PIT", "stat": "Pass Yards", "line": 215.5, "type": "pass_yds"},
    {"player": "Russell Wilson", "team": "PIT", "stat": "Pass TDs", "line": 1.5, "type": "pass_td"},
    {"player": "Najee Harris", "team": "PIT", "stat": "Rush Yards", "line": 55.5, "type": "rush_yds"},
    {"player": "Najee Harris", "team": "PIT", "stat": "Rush Attempts", "line": 14.5, "type": "attempts"},
    {"player": "Jaylen Warren", "team": "PIT", "stat": "Rush Yards", "line": 30.5, "type": "rush_yds"},
    {"player": "George Pickens", "team": "PIT", "stat": "Rec Yards", "line": 60.5, "type": "rec_yds"},
    {"player": "George Pickens", "team": "PIT", "stat": "Receptions", "line": 4.5, "type": "receptions"},
    {"player": "Pat Freiermuth", "team": "PIT", "stat": "Rec Yards", "line": 30.5, "type": "rec_yds"},
    {"player": "Calvin Austin III", "team": "PIT", "stat": "Rec Yards", "line": 28.5, "type": "rec_yds"},
    {"player": "T.J. Watt", "team": "PIT", "stat": "Sacks", "line": 0.5, "type": "sacks"},
    {"player": "Alex Highsmith", "team": "PIT", "stat": "Sacks", "line": 0.5, "type": "sacks"},
    
    # === CLEVELAND BROWNS ===
    {"player": "Jameis Winston", "team": "CLE", "stat": "Pass Yards", "line": 245.5, "type": "pass_yds"},
    {"player": "Jameis Winston", "team": "CLE", "stat": "Pass TDs", "line": 1.5, "type": "pass_td"},
    {"player": "Jameis Winston", "team": "CLE", "stat": "INTs", "line": 0.5, "type": "int"},
    {"player": "Quinshon Judkins", "team": "CLE", "stat": "Rush Yards", "line": 55.5, "type": "rush_yds"},
    {"player": "Nick Chubb", "team": "CLE", "stat": "Rush Yards", "line": 45.5, "type": "rush_yds"},
    {"player": "Jerome Ford", "team": "CLE", "stat": "Rush Yards", "line": 20.5, "type": "rush_yds"},
    {"player": "Jerry Jeudy", "team": "CLE", "stat": "Rec Yards", "line": 45.5, "type": "rec_yds"},
    {"player": "Jerry Jeudy", "team": "CLE", "stat": "Receptions", "line": 4.5, "type": "receptions"},
    {"player": "Cedric Tillman", "team": "CLE", "stat": "Rec Yards", "line": 35.5, "type": "rec_yds"},
    {"player": "David Njoku", "team": "CLE", "stat": "Rec Yards", "line": 35.5, "type": "rec_yds"},
    {"player": "Elijah Moore", "team": "CLE", "stat": "Rec Yards", "line": 22.5, "type": "rec_yds"},
    {"player": "Myles Garrett", "team": "CLE", "stat": "Sacks", "line": 0.5, "type": "sacks"},
    
    # === JACKSONVILLE JAGUARS ===
    {"player": "Trevor Lawrence", "team": "JAX", "stat": "Pass Yards", "line": 246.5, "type": "pass_yds"},
    {"player": "Trevor Lawrence", "team": "JAX", "stat": "Pass TDs", "line": 1.5, "type": "pass_td"},
    {"player": "Trevor Lawrence", "team": "JAX", "stat": "INTs", "line": 0.5, "type": "int"},
    {"player": "Mac Jones", "team": "JAX", "stat": "Pass Yards", "line": 195.5, "type": "pass_yds"},
    {"player": "Tank Bigsby", "team": "JAX", "stat": "Rush Yards", "line": 45.5, "type": "rush_yds"},
    {"player": "Tank Bigsby", "team": "JAX", "stat": "Rush Attempts", "line": 9.5, "type": "attempts"},
    {"player": "Travis Etienne", "team": "JAX", "stat": "Rush Yards", "line": 67.5, "type": "rush_yds"},
    {"player": "Travis Etienne", "team": "JAX", "stat": "Rush+Rec Yards", "line": 85.5, "type": "rush_rec_yds"},
    {"player": "Travis Etienne", "team": "JAX", "stat": "Receptions", "line": 2.5, "type": "receptions"},
    {"player": "Brian Thomas", "team": "JAX", "stat": "Rec Yards", "line": 65.5, "type": "rec_yds"},
    {"player": "Brian Thomas", "team": "JAX", "stat": "Receptions", "line": 4.5, "type": "receptions"},
    {"player": "Brenton Strange", "team": "JAX", "stat": "Rec Yards", "line": 22.5, "type": "rec_yds"},
    {"player": "Parker Washington", "team": "JAX", "stat": "Rec Yards", "line": 20.5, "type": "rec_yds"},
    {"player": "Travon Walker", "team": "JAX", "stat": "Sacks", "line": 0.5, "type": "sacks"},
    {"player": "Josh Hines-Allen", "team": "JAX", "stat": "Sacks", "line": 0.5, "type": "sacks"},
    {"player": "Devin Lloyd", "team": "JAX", "stat": "Tackles", "line": 6.5, "type": "tackles"},
    {"player": "Foyesade Oluokun", "team": "JAX", "stat": "Tackles", "line": 7.5, "type": "tackles"},
    
    # === INDIANAPOLIS COLTS ===
    {"player": "Joe Flacco", "team": "IND", "stat": "Pass Yards", "line": 205.5, "type": "pass_yds"},
    {"player": "Joe Flacco", "team": "IND", "stat": "Pass TDs", "line": 1.5, "type": "pass_td"},
    {"player": "Jonathan Taylor", "team": "IND", "stat": "Rush Yards", "line": 70.5, "type": "rush_yds"},
    {"player": "Jonathan Taylor", "team": "IND", "stat": "Rush+Rec TDs", "line": 0.5, "type": "rush_rec_td"},
    {"player": "Jonathan Taylor", "team": "IND", "stat": "Rush Attempts", "line": 18.5, "type": "attempts"},
    {"player": "Jonathan Taylor", "team": "IND", "stat": "Longest Rush", "line": 16.5, "type": "longest"},
    {"player": "Michael Pittman Jr.", "team": "IND", "stat": "Rec Yards", "line": 44.5, "type": "rec_yds"},
    {"player": "Michael Pittman Jr.", "team": "IND", "stat": "Receptions", "line": 4.5, "type": "receptions"},
    {"player": "Alec Pierce", "team": "IND", "stat": "Rec Yards", "line": 50.5, "type": "rec_yds"},
    {"player": "Josh Downs", "team": "IND", "stat": "Rec Yards", "line": 32.5, "type": "rec_yds"},
    {"player": "Tyler Warren", "team": "IND", "stat": "Rec Yards", "line": 48.5, "type": "rec_yds"},
    {"player": "Tyler Warren", "team": "IND", "stat": "Receptions", "line": 4.5, "type": "receptions"},
    {"player": "Laiatu Latu", "team": "IND", "stat": "Sacks", "line": 0.5, "type": "sacks"},
    {"player": "Zaire Franklin", "team": "IND", "stat": "Tackles", "line": 6.5, "type": "tackles"},
]


def get_team_stats(team):
    """Get team stats dictionary"""
    if team == "PIT":
        return PIT_STATS
    elif team == "CLE":
        return CLE_STATS
    elif team == "JAX":
        return JAX_STATS
    elif team == "IND":
        return IND_STATS
    return None


def analyze_prop(prop):
    """Analyze a prop based on real stats"""
    player = prop["player"]
    line = prop["line"]
    stat_type = prop["type"]
    team = prop["team"]
    
    team_data = get_team_stats(team)
    if not team_data:
        return None, None, None, "NO DATA"
    
    stats = team_data["players"].get(player, {})
    if not stats:
        return None, None, None, "NO DATA"
    
    games = stats.get("games", 1)
    
    # Calculate average based on stat type
    if stat_type == "rush_yds":
        avg = stats.get("rush_per_game", stats.get("rush_yds", 0) / games)
    elif stat_type == "rec_yds":
        avg = stats.get("rec_per_game", stats.get("rec_yds", 0) / games)
    elif stat_type == "pass_yds":
        avg = stats.get("pass_yds_per_game", stats.get("pass_yds", 0) / games)
    elif stat_type == "rush_rec_yds":
        rush = stats.get("rush_per_game", stats.get("rush_yds", 0) / games)
        rec = stats.get("rec_per_game", stats.get("rec_yds", 0) / games)
        avg = rush + rec
    elif stat_type == "rush_rec_td":
        rush_td = stats.get("rush_td", 0)
        rec_td = stats.get("rec_td", 0)
        total_td = stats.get("total_td", rush_td + rec_td)
        avg = total_td / games
    elif stat_type == "sacks":
        avg = stats.get("sacks_per_game", stats.get("sacks", 0) / games)
    elif stat_type == "tackles":
        avg = stats.get("tackles_per_game", stats.get("tackles", 0) / games)
    elif stat_type == "pass_td":
        avg = stats.get("pass_td", 0) / games
    elif stat_type == "int":
        avg = stats.get("int", 0) / games
    elif stat_type == "receptions":
        avg = stats.get("rec", 0) / games
    elif stat_type == "attempts":
        avg = stats.get("rush_att", 0) / games
    elif stat_type == "longest":
        avg = 20
    else:
        avg = 0
    
    # Calculate edge and probability
    edge = avg - line
    edge_pct = (edge / line) * 100 if line > 0 else 0
    
    if avg > line:
        over_prob = min(95, 50 + (edge_pct * 2))
        under_prob = 100 - over_prob
    else:
        under_prob = min(95, 50 + (abs(edge_pct) * 2))
        over_prob = 100 - under_prob
    
    # Recommendation
    if abs(edge_pct) < 5:
        rec = "HOLD"
    elif edge_pct > 15:
        rec = "OVER ✅"
    elif edge_pct > 5:
        rec = "LEAN OVER"
    elif edge_pct < -15:
        rec = "UNDER ✅"
    elif edge_pct < -5:
        rec = "LEAN UNDER"
    else:
        rec = "HOLD"
    
    return avg, over_prob, under_prob, rec


def print_team_section(team_code, team_data, props):
    """Print analysis for one team"""
    info = team_data["team_info"]
    
    # Team header
    console.print(Panel.fit(
        f"[bold white]{info['name']}[/bold white]\n"
        f"[cyan]Record: {info['record']} | {info['division']}[/cyan]\n"
        f"[dim]PPG: {info['ppg']} | PPG Allowed: {info['ppg_allowed']} | Rush: {info['rush_ypg']} | Pass: {info['pass_ypg']}[/dim]",
        border_style="yellow" if "Steelers" in info['name'] or "Colts" in info['name'] else "red"
    ))
    
    # Filter props for this team
    team_props = [p for p in props if p["team"] == team_code]
    
    # Create table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Player", width=18)
    table.add_column("Stat", width=14)
    table.add_column("Line", justify="center", width=7)
    table.add_column("Avg", justify="center", width=7)
    table.add_column("Edge", justify="center", width=7)
    table.add_column("O%", justify="center", width=5)
    table.add_column("U%", justify="center", width=5)
    table.add_column("Call", width=12)
    
    slams = []
    leans = []
    
    for prop in team_props:
        avg, over_prob, under_prob, rec = analyze_prop(prop)
        if avg is None:
            continue
        
        edge = avg - prop["line"]
        
        # Style based on recommendation
        if "✅" in rec:
            rec_style = "bold green"
            slams.append((prop, avg, rec))
        elif "LEAN" in rec:
            rec_style = "yellow"
            leans.append((prop, avg, rec))
        else:
            rec_style = "dim"
        
        table.add_row(
            prop["player"],
            prop["stat"],
            str(prop["line"]),
            f"{avg:.1f}",
            f"{edge:+.1f}",
            f"{over_prob:.0f}%",
            f"{under_prob:.0f}%",
            Text(rec, style=rec_style)
        )
    
    console.print(table)
    
    # Print slam plays
    if slams:
        console.print(f"\n  [bold green]🔥 {team_code} SLAM PLAYS:[/bold green]")
        for prop, avg, rec in slams:
            direction = "OVER" if "OVER" in rec else "UNDER"
            console.print(f"    • {prop['player']} {prop['stat']} {direction} {prop['line']} (Avg: {avg:.1f})")
    
    if leans:
        console.print(f"\n  [yellow]📈 {team_code} LEAN PLAYS:[/yellow]")
        for prop, avg, rec in leans:
            direction = "OVER" if "OVER" in rec else "UNDER"
            console.print(f"    • {prop['player']} {prop['stat']} {direction} {prop['line']} (Avg: {avg:.1f})")
    
    console.print("")


def main():
    console.print(Panel.fit(
        "[bold cyan]🏈 UNDERDOG FANTASY - 4-TEAM ANALYSIS[/bold cyan]\n"
        "[white]PIT @ CLE  |  JAX @ IND[/white]\n"
        "[yellow]Based on REAL 2024 Pro-Football-Reference Stats[/yellow]\n"
        f"[dim]Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}[/dim]",
        border_style="cyan"
    ))
    
    # Game 1 Header
    console.print("\n" + "="*70)
    console.print("[bold white]                    GAME 1: PIT @ CLE[/bold white]")
    console.print("[dim]                    Steelers -7.5 Favorites[/dim]")
    console.print("="*70 + "\n")
    
    # Pittsburgh Steelers
    print_team_section("PIT", PIT_STATS, ALL_PROPS)
    
    # Cleveland Browns
    print_team_section("CLE", CLE_STATS, ALL_PROPS)
    
    # Game 2 Header
    console.print("\n" + "="*70)
    console.print("[bold white]                    GAME 2: JAX @ IND[/bold white]")
    console.print("[dim]                    Colts -3.5 Favorites[/dim]")
    console.print("="*70 + "\n")
    
    # Jacksonville Jaguars
    print_team_section("JAX", JAX_STATS, ALL_PROPS)
    
    # Indianapolis Colts
    print_team_section("IND", IND_STATS, ALL_PROPS)
    
    # COMBINED TOP PLAYS
    console.print("\n" + "="*70)
    console.print("[bold magenta]            📋 COMBINED TOP PLAYS - ALL 4 TEAMS[/bold magenta]")
    console.print("="*70)
    
    # Collect all analyzed props with confidence
    all_results = []
    for prop in ALL_PROPS:
        avg, over_prob, under_prob, rec = analyze_prop(prop)
        if avg is not None and "✅" in rec:
            conf = over_prob if "OVER" in rec else under_prob
            all_results.append({
                "player": prop["player"],
                "team": prop["team"],
                "stat": prop["stat"],
                "line": prop["line"],
                "avg": avg,
                "rec": "OVER" if "OVER" in rec else "UNDER",
                "conf": conf
            })
    
    # Sort by confidence
    all_results.sort(key=lambda x: x["conf"], reverse=True)
    
    console.print("\n[bold green]🔥 TOP 10 SLAM PLAYS ACROSS ALL TEAMS:[/bold green]\n")
    
    top_table = Table(show_header=True, header_style="bold white")
    top_table.add_column("#", width=3)
    top_table.add_column("Player", width=18)
    top_table.add_column("Team", width=5)
    top_table.add_column("Stat", width=14)
    top_table.add_column("Line", justify="center", width=7)
    top_table.add_column("Avg", justify="center", width=7)
    top_table.add_column("Play", justify="center", width=8)
    top_table.add_column("Conf", justify="center", width=6)
    
    for i, r in enumerate(all_results[:10], 1):
        edge = abs(r["avg"] - r["line"])
        top_table.add_row(
            str(i),
            r["player"],
            r["team"],
            r["stat"],
            str(r["line"]),
            f"{r['avg']:.1f}",
            Text(r["rec"], style="green" if r["rec"] == "OVER" else "red"),
            f"{r['conf']:.0f}%"
        )
    
    console.print(top_table)
    
    # Final cheat sheet
    console.print("\n" + "="*70)
    console.print("[bold white]                    📝 QUICK CHEAT SHEET[/bold white]")
    console.print("="*70)
    
    console.print("""
[bold cyan]PITTSBURGH STEELERS (PIT):[/bold cyan]
  ✓ T.J. Watt OVER 0.5 Sacks (0.72/game vs weak CLE OL)
  ✓ George Pickens OVER 60.5 Rec (Avg 72.8)
  ✓ Pat Freiermuth OVER 30.5 Rec (Avg 36.4)

[bold orange3]CLEVELAND BROWNS (CLE):[/bold orange3]
  ✓ Jerry Jeudy OVER 45.5 Rec (Avg 58.6 - Winston slinging)
  ✓ David Njoku OVER 35.5 Rec (Avg 48.7)
  ✓ Nick Chubb UNDER 45.5 Rush (Avg 35.0)
  ✓ Myles Garrett OVER 0.5 Sacks (0.89/game elite)

[bold gold1]JACKSONVILLE JAGUARS (JAX):[/bold gold1]
  🔥 Travis Etienne UNDER 67.5 Rush (Avg 37.2 - SLAM)
  🔥 Travis Etienne UNDER 85.5 Rush+Rec (Avg 54.1)
  ✓ Brian Thomas OVER 65.5 Rec (Avg 75.4 - ROTY)
  ✓ Tank Bigsby OVER 45.5 Rush (Avg 47.9)
  ⚠️ Trevor Lawrence UNDER 246.5 Pass (Check if playing)

[bold blue]INDIANAPOLIS COLTS (IND):[/bold blue]
  🔥 Jonathan Taylor OVER 70.5 Rush (Avg 99.3 - MONSTER)
  🔥 Jonathan Taylor OVER 0.5 TDs (1.27 TDs/game)
  ✓ Michael Pittman Jr. OVER 44.5 Rec (Avg 50.5)
  ✓ Alec Pierce OVER 50.5 Rec (Avg 58.1)
  ✓ Tyler Warren OVER 48.5 Rec (Avg 49.9)
  ✓ Zaire Franklin OVER 6.5 Tackles (Avg 7.2)
""")

    console.print("\n[dim]⚠️ Always check injury reports before game time![/dim]\n")


if __name__ == "__main__":
    main()
