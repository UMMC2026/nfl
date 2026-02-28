"""
Quick analysis of MIL @ ATL props from Underdog (Jan 19, 2026)
"""
import json
from ufa.models.schemas import PropPick
from ufa.analysis.prob import prob_hit
from ufa.ingest.hydrate import hydrate_recent_values
from rich.console import Console
from rich.table import Table

console = Console()

# Load picks
with open("mil_atl_jan19_props.json", "r") as f:
    raw_picks = json.load(f)

picks = [PropPick(**p) for p in raw_picks]

console.print(f"\n[bold cyan]Analyzing {len(picks)} props for MIL @ ATL[/bold cyan]\n")

results = []

for i, pick in enumerate(picks, 1):
    # Hydrate recent values from NBA API
    try:
        recent_values = hydrate_recent_values(
            league="NBA",
            player=pick.player,
            stat_key=pick.stat,
            nba_season="2024-25"
        )
        
        if recent_values:
            p_value = prob_hit(
                line=pick.line,
                direction=pick.direction,
                recent_values=recent_values
            )
        else:
            console.print(f"[yellow]No data for {pick.player} - {pick.stat}[/yellow]")
            p_value = 0.50  # Default to coin flip
            
    except Exception as e:
        console.print(f"[red]Error hydrating {pick.player} - {pick.stat}: {e}[/red]")
        p_value = 0.50
    
    results.append({
        "player": pick.player,
        "team": pick.team,
        "stat": pick.stat,
        "line": pick.line,
        "direction": pick.direction,
        "p_hit": float(p_value),
        "recent_values": recent_values if 'recent_values' in locals() else []
    })

# Sort by probability
results.sort(key=lambda x: x["p_hit"], reverse=True)

# Create table
table = Table(title="MIL @ ATL Props - Ranked by P(hit)", show_lines=True)
table.add_column("Rank", style="cyan", width=5)
table.add_column("Player", style="white", width=25)
table.add_column("Team", style="yellow", width=5)
table.add_column("Stat", style="green", width=12)
table.add_column("Line", style="magenta", width=8)
table.add_column("Dir", style="blue", width=6)
table.add_column("P(hit)", style="bold green", width=8)
table.add_column("Recent (L5)", style="dim", width=30)

for rank, r in enumerate(results, 1):
    recent_str = ""
    if r["recent_values"]:
        recent_str = ", ".join([f"{v:.1f}" for v in r["recent_values"][:5]])
    
    color = "green" if r["p_hit"] >= 0.60 else ("yellow" if r["p_hit"] >= 0.50 else "red")
    
    table.add_row(
        str(rank),
        r["player"],
        r["team"],
        r["stat"],
        f"{r['line']:.1f}",
        r["direction"],
        f"[{color}]{r['p_hit']:.2%}[/{color}]",
        recent_str
    )

console.print(table)

# Print summary stats
high_conf = sum(1 for r in results if r["p_hit"] >= 0.60)
medium_conf = sum(1 for r in results if 0.50 <= r["p_hit"] < 0.60)
low_conf = sum(1 for r in results if r["p_hit"] < 0.50)

console.print(f"\n[bold]Summary:[/bold]")
console.print(f"  High confidence (≥60%): {high_conf}")
console.print(f"  Medium confidence (50-60%): {medium_conf}")
console.print(f"  Low confidence (<50%): {low_conf}")
console.print(f"\n  Total picks: {len(results)}\n")

# Save results
output_file = f"outputs/mil_atl_jan19_analysis.json"
with open(output_file, "w") as f:
    json.dump(results, f, indent=2)

console.print(f"[green]✓ Results saved to {output_file}[/green]\n")
