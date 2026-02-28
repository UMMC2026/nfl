"""
Completely isolated analyzer - ZERO imports from workspace
"""
import sys
import os

# Block menu.py from loading
original_import = __builtins__.__import__

def safe_import(name, *args, **kwargs):
    if 'menu' in name and 'telegram' not in name:
        raise ImportError(f"Blocked import of {name}")
    return original_import(name, *args, **kwargs)

__builtins__.__import__ = safe_import

# Now safe to import
from ufa.models.schemas import PropPick
from ufa.analysis.prob import prob_hit
from ufa.ingest.hydrate import hydrate_recent_values
from ufa.optimizer.entry_builder import build_entries
from ufa.analysis.payouts import power_table
from rich.console import Console
from rich.table import Table
import json
from datetime import datetime

console = Console()

# MIL @ ATL Slate - 3PTM PROPS
PROPS = [
    ("Nickeil Alexander-Walker", "ATL", "3pm", 2.5, "higher"),
    ("AJ Green", "MIL", "3pm", 1.5, "higher"),
    ("CJ McCollum", "ATL", "3pm", 1.5, "higher"),
    ("Bobby Portis", "MIL", "3pm", 0.5, "higher"),
    ("Jalen Johnson", "ATL", "3pm", 0.5, "higher"),
    ("Kevin Porter Jr.", "MIL", "3pm", 1.5, "lower"),
    ("Myles Turner", "MIL", "3pm", 1.5, "higher"),
    ("Onyeka Okongwu", "ATL", "3pm", 1.5, "higher"),
    ("Ryan Rollins", "MIL", "3pm", 1.5, "higher"),
    ("Vit Krejci", "ATL", "3pm", 1.5, "higher"),
    ("Kyle Kuzma", "MIL", "3pm", 0.5, "higher"),
    ("Corey Kispert", "ATL", "3pm", 0.5, "higher"),
    ("Luke Kennard", "ATL", "3pm", 0.5, "higher"),
    ("Giannis Antetokounmpo", "MIL", "3pm", 1.5, "higher"),
    ("Mouhamed Gueye", "ATL", "3pm", 1.5, "higher"),
    ("Gary Harris", "MIL", "3pm", 1.5, "higher"),
    ("Dyson Daniels", "ATL", "3pm", 0.5, "higher"),
]

def main():
    console.print("\n[bold cyan]═══ MIL @ ATL INSTANT ANALYSIS ═══[/bold cyan]\n")
    
    picks = []
    total = len(PROPS)
    
    for idx, (player, team, stat, line, direction) in enumerate(PROPS, 1):
        console.print(f"[yellow]({idx}/{total})[/yellow] {player} {stat} {direction[:1].upper()} {line}...")
        
        # Hydrate recent data
        try:
            recent = hydrate_recent_values("NBA", player, stat, nba_season="2024-25")
            
            if not recent or len(recent) < 3:
                console.print(f"  [red]✗ Insufficient data ({len(recent) if recent else 0} games)[/red]\n")
                continue
            
            # Calculate probability
            p = prob_hit(line, direction, recent_values=recent)
            
            picks.append({
                "player": player,
                "team": team,
                "stat": stat,
                "line": line,
                "direction": direction,
                "p_hit": p,
                "recent_avg": round(sum(recent)/len(recent), 1),
                "recent_games": len(recent)
            })
            
            # Show confidence
            if p >= 0.60:
                conf = "🔥 HIGH"
                color = "bold green"
            elif p >= 0.50:
                conf = "⚡ MEDIUM"
                color = "yellow"
            else:
                conf = "❄️ LOW"
                color = "dim"
            
            console.print(f"  → [{color}]{p*100:.1f}% ({conf})[/{color}] | Avg: {sum(recent)/len(recent):.1f}\n")
            
        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/red]\n")
            continue
    
    if not picks:
        console.print("[red]No valid picks found![/red]")
        return
    
    # Ranked picks table
    console.print(f"\n[bold green]═══ RANKED PICKS ({len(picks)} total) ═══[/bold green]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", width=3)
    table.add_column("Player", width=22)
    table.add_column("Prop", width=28)
    table.add_column("P(hit)", width=7, justify="right")
    table.add_column("Avg", width=6, justify="right")
    table.add_column("Conf", width=10)
    
    ranked = sorted(picks, key=lambda x: x['p_hit'], reverse=True)
    
    for idx, pick in enumerate(ranked, 1):
        prop_str = f"{pick['stat']} {pick['direction'][0].upper()} {pick['line']}"
        p_str = f"{pick['p_hit']*100:.1f}%"
        avg_str = f"{pick['recent_avg']}"
        
        if pick['p_hit'] >= 0.60:
            conf, style = "🔥 HIGH", "bold green"
        elif pick['p_hit'] >= 0.50:
            conf, style = "⚡ MEDIUM", "yellow"
        else:
            conf, style = "❄️ LOW", "dim"
        
        table.add_row(str(idx), pick['player'], prop_str, p_str, avg_str, conf, style=style)
    
    console.print(table)
    
    # Build 3-leg entries
    console.print("\n[bold cyan]═══ BUILDING 3-LEG POWER ENTRIES ═══[/bold cyan]\n")
    
    try:
        entries = build_entries(
            picks=picks,
            payout_table=power_table(),
            legs=3,
            min_teams=2,
            max_player_legs=1,
            same_team_penalty=0.05
        )
        
        console.print(f"[green]✓ Generated {len(entries)} combinations[/green]\n")
        
        # Show top 10 by EV
        entry_table = Table(show_header=True, header_style="bold cyan")
        entry_table.add_column("#", width=3)
        entry_table.add_column("Players", width=55)
        entry_table.add_column("EV", width=8, justify="right")
        entry_table.add_column("P(win)", width=7, justify="right")
        
        for idx, entry in enumerate(entries[:10], 1):
            players_str = " | ".join(entry['players'][:3])
            ev_str = f"+{entry['ev_units']:.2f}u"
            # Calculate joint prob from p_list
            import math
            joint_p = math.prod(entry['p_list']) if entry['p_list'] else 0
            prob_str = f"{joint_p*100:.1f}%"
            
            style = "bold green" if entry['ev_units'] > 0.10 else "yellow" if entry['ev_units'] > 0 else "dim"
            entry_table.add_row(str(idx), players_str, ev_str, prob_str, style=style)
        
        console.print(entry_table)
        
    except Exception as e:
        console.print(f"[red]Error building entries: {e}[/red]")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "slate": "MIL @ ATL",
        "game_time": "Mon 12:10pm",
        "analyzed_at": timestamp,
        "picks": ranked,
        "top_entries": entries[:20] if 'entries' in locals() else []
    }
    
    outfile = f"outputs/MIL_ATL_{timestamp}.json"
    with open(outfile, 'w') as f:
        json.dump(output, f, indent=2)
    
    console.print(f"\n[bold green]✓ Saved to: {outfile}[/bold green]\n")

if __name__ == "__main__":
    main()
