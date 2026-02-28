"""3PTM Props Analyzer - MIL @ ATL"""
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

console.print("\n[bold cyan]═══ 3PTM PROPS ANALYSIS - MIL @ ATL ═══[/bold cyan]\n")

picks = []
for idx, (player, team, stat, line, direction) in enumerate(PROPS, 1):
    console.print(f"[yellow]({idx}/{len(PROPS)})[/yellow] {player} {line} 3PM {direction.upper()}...")
    
    try:
        recent = hydrate_recent_values("NBA", player, stat, nba_season="2024-25")
        
        if not recent or len(recent) < 3:
            console.print(f"  [red]✗ Not enough data[/red]\n")
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
            "games": len(recent)
        })
        
        if p >= 0.60:
            conf, color = "🔥 HIGH", "bold green"
        elif p >= 0.50:
            conf, color = "⚡ MED", "yellow"
        else:
            conf, color = "❄️ LOW", "dim"
        
        console.print(f"  → [{color}]{p*100:.1f}% ({conf})[/{color}] | Avg: {avg:.1f} 3PM\n")
        
    except Exception as e:
        console.print(f"  [red]✗ {e}[/red]\n")

# Show results
console.print(f"\n[bold green]═══ RANKED 3PTM PICKS ({len(picks)} total) ═══[/bold green]\n")

table = Table(show_header=True, header_style="bold magenta")
table.add_column("#", width=3)
table.add_column("Player", width=24)
table.add_column("Prop", width=18)
table.add_column("P(hit)", width=7, justify="right")
table.add_column("Avg", width=5, justify="right")
table.add_column("Conf", width=10)

ranked = sorted(picks, key=lambda x: x['p_hit'], reverse=True)

for idx, p in enumerate(ranked, 1):
    prop_str = f"{'O' if p['direction']=='higher' else 'U'} {p['line']} 3PM"
    
    if p['p_hit'] >= 0.60:
        conf, style = "🔥 HIGH", "bold green"
    elif p['p_hit'] >= 0.50:
        conf, style = "⚡ MEDIUM", "yellow"
    else:
        conf, style = "❄️ LOW", "dim"
    
    table.add_row(str(idx), p['player'], prop_str, f"{p['p_hit']*100:.1f}%", str(p['avg']), conf, style=style)

console.print(table)

# Save
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
with open(f"outputs/3PTM_MIL_ATL_{ts}.json", 'w') as f:
    json.dump({"picks": ranked}, f, indent=2)

console.print(f"\n[green]✓ Saved to outputs/3PTM_MIL_ATL_{ts}.json[/green]\n")
