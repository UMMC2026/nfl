"""Pts+Asts Props Analyzer - MIL @ ATL"""
import sys
sys.path.insert(0, '.')

from ufa.analysis.prob import prob_hit
from ufa.ingest.hydrate import hydrate_recent_values
from rich.console import Console
from rich.table import Table
import json
from datetime import datetime

console = Console()

PROPS = [
    ("Giannis Antetokounmpo", "MIL", "pts+ast", 35.5, "lower"),
    ("Jalen Johnson", "ATL", "pts+ast", 29, "lower"),
    ("Nickeil Alexander-Walker", "ATL", "pts+ast", 22.5, "lower"),
    ("Kevin Porter Jr.", "MIL", "pts+ast", 23.5, "lower"),
    ("CJ McCollum", "ATL", "pts+ast", 20.5, "lower"),
    ("Onyeka Okongwu", "ATL", "pts+ast", 19.5, "lower"),
    ("Ryan Rollins", "MIL", "pts+ast", 18.5, "lower"),
    ("Dyson Daniels", "ATL", "pts+ast", 17.5, "lower"),
    ("AJ Green", "MIL", "pts+ast", 12.5, "lower"),
    ("Bobby Portis", "MIL", "pts+ast", 12.5, "lower"),
    ("Kyle Kuzma", "MIL", "pts+ast", 11.5, "lower"),
    ("Myles Turner", "MIL", "pts+ast", 11.5, "lower"),
    ("Vit Krejci", "ATL", "pts+ast", 8.5, "lower"),
    ("Corey Kispert", "ATL", "pts+ast", 8.5, "lower"),
    ("Luke Kennard", "ATL", "pts+ast", 7.5, "lower"),
    ("Mouhamed Gueye", "ATL", "pts+ast", 5.5, "lower"),
    ("Gary Harris", "MIL", "pts+ast", 3.5, "higher"),
]

console.print("\n[bold cyan]=== PTS+ASTS PROPS - MIL @ ATL ===[/bold cyan]\n")

picks = []
for idx, (player, team, stat, line, direction) in enumerate(PROPS, 1):
    d = "O" if direction == "higher" else "U"
    console.print(f"[yellow]({idx}/{len(PROPS)})[/yellow] {player} {d}{line} pts+ast...")
    
    try:
        recent = hydrate_recent_values("NBA", player, stat, nba_season="2024-25")
        
        if not recent or len(recent) < 3:
            console.print(f"  [red]X Not enough data[/red]\n")
            continue
        
        p = prob_hit(line, direction, recent_values=recent)
        avg = sum(recent)/len(recent)
        
        picks.append({
            "player": player,
            "team": team,
            "line": line,
            "direction": direction,
            "p_hit": p,
            "avg": round(avg, 1),
        })
        
        if p >= 0.60:
            conf, color = "HIGH", "bold green"
        elif p >= 0.50:
            conf, color = "MED", "yellow"
        else:
            conf, color = "LOW", "dim"
        
        console.print(f"  -> [{color}]{p*100:.1f}% ({conf})[/{color}] | Avg: {avg:.1f}\n")
        
    except Exception as e:
        console.print(f"  [red]X {e}[/red]\n")

console.print(f"\n[bold green]=== RANKED PTS+ASTS PICKS ===[/bold green]\n")

table = Table(show_header=True, header_style="bold magenta")
table.add_column("#", width=3)
table.add_column("Player", width=24)
table.add_column("Prop", width=16)
table.add_column("P(hit)", width=7, justify="right")
table.add_column("Avg", width=5, justify="right")
table.add_column("Conf", width=8)

ranked = sorted(picks, key=lambda x: x['p_hit'], reverse=True)

for idx, p in enumerate(ranked, 1):
    prop_str = f"{'O' if p['direction']=='higher' else 'U'} {p['line']}"
    
    if p['p_hit'] >= 0.60:
        conf, style = "HIGH", "bold green"
    elif p['p_hit'] >= 0.50:
        conf, style = "MED", "yellow"
    else:
        conf, style = "LOW", "dim"
    
    table.add_row(str(idx), p['player'], prop_str, f"{p['p_hit']*100:.1f}%", str(p['avg']), conf, style=style)

console.print(table)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
with open(f"outputs/PTS_AST_MIL_ATL_{ts}.json", 'w') as f:
    json.dump({"picks": ranked}, f, indent=2)

console.print(f"\n[green]Saved to outputs/PTS_AST_MIL_ATL_{ts}.json[/green]\n")
