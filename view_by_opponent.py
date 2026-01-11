#!/usr/bin/env python3
"""
View picks organized by opponent matchup instead of by confidence tier.
Groups all HOU and BKN players together for same-team parlay building.
"""

import json
from collections import defaultdict
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
import sys
import io

# UTF-8 encoding fix for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

console = Console()

# Known matchups for grouping (define weekly games here)
MATCHUPS = {
    "HOU": "BKN",
    "BKN": "HOU",
    "DET": "MIA",
    "MIA": "DET",
    "PHI": "DAL",
    "DAL": "PHI",
}

def get_confidence_tier(prob):
    """Return confidence tier based on probability."""
    if prob is None:
        return "UNKNOWN"
    if prob >= 0.68:
        return "🔒 SLAM"
    elif prob >= 0.60:
        return "✅ STRONG"
    elif prob >= 0.52:
        return "⚠️  LEAN"
    elif prob >= 0.48:
        return "🔄 FLIP"
    else:
        return "❌ FADE"

def get_edge_color(edge_pct):
    """Return color for edge percentage."""
    if edge_pct is None or edge_pct == 0:
        return "white"
    if edge_pct >= 100:
        return "bold green"
    elif edge_pct >= 50:
        return "green"
    elif edge_pct >= 0:
        return "yellow"
    else:
        return "red"

def group_picks_by_matchup(hydrated_data):
    """
    Group picks by matchup (game).
    Returns dict: {(team1, team2): {team1: [picks], team2: [picks]}}
    """
    games = defaultdict(lambda: defaultdict(list))
    
    for pick in hydrated_data:
        # Extract team from pick
        team = pick.get("team", "UNK")
        
        # Get opponent from MATCHUPS dict
        opponent = MATCHUPS.get(team, None)
        
        if opponent is None:
            # Single team game, skip or add as standalone
            continue
        
        # Create matchup key (alphabetical for consistency)
        matchup = tuple(sorted([team, opponent]))
        
        # Store pick
        games[matchup][team].append(pick)
    
    return games

def display_by_opponent():
    """Display picks grouped by opponent matchup (from VALIDATED output)."""
    
    # Read from VALIDATED output, not hydrated input
    output_file = Path("outputs/validated_primary_edges.json")
    if not output_file.exists():
        console.print("[red]❌ outputs/validated_primary_edges.json not found[/red]")
        console.print("[yellow]Run daily pipeline first: python daily_pipeline.py[/yellow]")
        return
    
    with open(output_file) as f:
        validated_data = json.load(f)
    
    # Build dynamic matchups from the validated data itself
    teams_playing = set()
    for edge in validated_data:
        team = edge.get("team", "").upper()
        if team:
            teams_playing.add(team)
    
    # Extract matchups from validated edges
    matchups_found = defaultdict(set)
    for edge in validated_data:
        team = edge.get("team", "").upper()
        opponent = edge.get("opponent", "").upper()
        if team and opponent:
            matchup_key = tuple(sorted([team, opponent]))
            matchups_found[matchup_key].add((team, opponent))
    
    console.print("\n" + "="*80)
    console.print("[bold cyan]🏀 PICKS GROUPED BY OPPONENT MATCHUP[/bold cyan]")
    console.print("="*80 + "\n")
    
    # Group validated edges by matchup
    games = defaultdict(lambda: defaultdict(list))
    
    for edge in validated_data:
        team = edge.get("team", "").upper()
        opponent = edge.get("opponent", "").upper()
        
        if not team or not opponent:
            continue
        
        matchup = tuple(sorted([team, opponent]))
        games[matchup][team].append(edge)
    
    # Sort and display
    for matchup in sorted(games.keys()):
        team1, team2 = matchup
        teams_picks = games[matchup]
        
        console.print(f"[bold yellow]⚔️  {team1} vs {team2}[/bold yellow]")
        console.print("[dim]" + "─"*76 + "[/dim]")
        
        # Display each team's picks
        for team in sorted(teams_picks.keys()):
            edges = teams_picks[team]
            
            if edges:
                console.print(f"\n  [bold blue]{team} PLAYERS ({len(edges)} picks):[/bold blue]")
                
                # Sort edges by player name
                edges = sorted(edges, key=lambda e: e.get("player", ""))
                for edge in edges:
                    player = edge.get("player", "Unknown")
                    direction = edge.get("direction", "?")
                    line = edge.get("line", "?")
                    stat = edge.get("stat", "?")
                    
                    # Get probability from validated data
                    prob = edge.get("probability")  # NEW: from validation
                    
                    # Build display
                    tier = get_confidence_tier(prob)
                    
                    # Format stat info
                    stat_info = ""
                    mu = edge.get("mu")
                    sigma = edge.get("sigma")
                    if mu is not None and sigma is not None:
                        stat_info = f" | μ={mu:.1f}, σ={sigma:.1f}"
                    
                    # Display (simplified, no edge coloring for now)
                    direction_str = "O" if direction == "higher" else "U"
                    prob_str = f"{prob*100:.0f}%" if prob else "?%"
                    
                    console.print(
                        f"    • {player:25} {direction_str:1} {str(line):6} {stat:15} [{prob_str:3} {tier}]{stat_info}"
                    )
        
        console.print()
    
    # Summary
    total_edges = len(validated_data)
    grouped_edges = sum(len(edges) for team_dict in games.values() for edges in team_dict.values())
    
    console.print("="*80)
    console.print(f"[dim]📊 Total: {total_edges} validated picks | Grouped: {grouped_edges} picks[/dim]")
    console.print("="*80)

if __name__ == "__main__":
    display_by_opponent()
