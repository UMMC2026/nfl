
"""
Universal Slate Ingestion & Analysis System
Select a sport to analyze: NBA, NFL, Tennis, CBB, Golf, etc.
"""


import sys
import importlib
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from datetime import datetime
import json

console = Console()

# Your MIL @ ATL slate
SLATE = """Ryan Rollins|MIL|rebounds|5.5|higher
Giannis Antetokounmpo|MIL|points|30.5|lower
Jalen Johnson|ATL|pts+reb+ast|39|lower
Jalen Johnson|ATL|points|21.5|lower
Kevin Porter|MIL|pts+reb+ast|28.5|lower
Giannis Antetokounmpo|MIL|pts+reb+ast|45.5|lower
Kyle Kuzma|MIL|points|9.5|lower
Bobby Portis|MIL|points|11.5|lower
Bobby Portis|MIL|pts+ast|12.5|lower
Nickeil Alexander-Walker|ATL|points|19.5|lower
Giannis Antetokounmpo|MIL|dunks|4|lower
CJ McCollum|ATL|points|17|lower"""

def analyze():
    console.print("\n[bold cyan]═══ ANALYZING MIL @ ATL ═══[/bold cyan]\n")
    
    picks = []
    for idx, line in enumerate(SLATE.strip().split('\n'), 1):
        parts = line.split('|')
        player, team, stat, value, direction = parts
        
        console.print(f"[yellow]({idx}/12)[/yellow] Hydrating {player} {stat}...")
        
        # Get recent values
        recent = hydrate_recent_values("NBA", player, stat, nba_season="2024-25")
        
        if not recent:
            console.print(f"  [red]⚠ No data found[/red]")
            continue
            
        # Calculate probability
        p = prob_hit(float(value), direction, recent_values=recent)
        
        picks.append({
            "player": player,
            "team": team,
            "stat": stat,
            "line": float(value),
            "direction": direction,
            "p_hit": p,
            "recent_avg": sum(recent)/len(recent) if recent else 0,
            "recent_games": len(recent)
        })
        
        confidence = "🔥 HIGH" if p >= 0.60 else "⚡ MEDIUM" if p >= 0.50 else "❄️ LOW"

        # --- MENU SYSTEM ---
        def show_menu():
            console.print("\n[bold cyan]Universal Slate Ingestion & Analysis System[/bold cyan]")
            console.print("[bold]Select a sport to analyze:[/bold]")
            options = [
                ("NBA", "nba"),
                ("NFL", "nfl"),
                ("Tennis", "tennis"),
                ("CBB", "cbb"),
                ("Golf", "golf"),
                ("Exit", "exit")
            ]
            for idx, (label, _) in enumerate(options, 1):
                console.print(f"  [{idx}] {label}")
            choice = Prompt.ask("\nEnter number", choices=[str(i) for i in range(1, len(options)+1)])
            return options[int(choice)-1][1]

        def run_nba():
            # Import and run the original NBA analyzer (inlined for now)
            from ufa.models.schemas import PropPick
            from ufa.analysis.prob import prob_hit
            from ufa.ingest.hydrate import hydrate_recent_values
            from ufa.optimizer.entry_builder import build_entries
            from ufa.analysis.payouts import power_table

            SLATE = """Ryan Rollins|MIL|rebounds|5.5|higher
        Giannis Antetokounmpo|MIL|points|30.5|lower
        Jalen Johnson|ATL|pts+reb+ast|39|lower
        Jalen Johnson|ATL|points|21.5|lower
        Kevin Porter|MIL|pts+reb+ast|28.5|lower
        Giannis Antetokounmpo|MIL|pts+reb+ast|45.5|lower
        Kyle Kuzma|MIL|points|9.5|lower
        Bobby Portis|MIL|points|11.5|lower
        Bobby Portis|MIL|pts+ast|12.5|lower
        Nickeil Alexander-Walker|ATL|points|19.5|lower
        Giannis Antetokounmpo|MIL|dunks|4|lower
        CJ McCollum|ATL|points|17|lower"""

            console.print("\n[bold cyan]═══ ANALYZING MIL @ ATL ═══[/bold cyan]\n")
            picks = []
            for idx, line in enumerate(SLATE.strip().split('\n'), 1):
                parts = line.split('|')
                player, team, stat, value, direction = parts
                console.print(f"[yellow]({idx}/12)[/yellow] Hydrating {player} {stat}...")
                recent = hydrate_recent_values("NBA", player, stat, nba_season="2024-25")
                if not recent:
                    console.print(f"  [red]⚠ No data found[/red]")
                    continue
                p = prob_hit(float(value), direction, recent_values=recent)
                picks.append({
                    "player": player,
                    "team": team,
                    "stat": stat,
                    "line": float(value),
                    "direction": direction,
                    "p_hit": p,
                    "recent_avg": sum(recent)/len(recent) if recent else 0,
                    "recent_games": len(recent)
                })
                confidence = "🔥 HIGH" if p >= 0.60 else "⚡ MEDIUM" if p >= 0.50 else "❄️ LOW"
                console.print(f"  → {p*100:.1f}% ({confidence})\n")
            # Show ranked picks
            console.print("\n[bold green]═══ RANKED PICKS ═══[/bold green]\n")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Rank", width=5)
            table.add_column("Player", width=20)
            table.add_column("Prop", width=25)
            table.add_column("P(hit)", width=8)
            table.add_column("Conf", width=12)
            for idx, pick in enumerate(sorted(picks, key=lambda x: x['p_hit'], reverse=True), 1):
                prop_str = f"{pick['stat']} {pick['direction'][:1].upper()} {pick['line']}"
                p_str = f"{pick['p_hit']*100:.1f}%"
                if pick['p_hit'] >= 0.60:
                    conf = "🔥 HIGH"
                    style = "bold green"
                elif pick['p_hit'] >= 0.50:
                    conf = "⚡ MEDIUM"
                    style = "yellow"
                else:
                    conf = "❄️ LOW"
                    style = "dim"
                table.add_row(
                    str(idx), pick['player'], prop_str, p_str, conf, style=style
                )
            console.print(table)
            # Build 3-leg power entries
            console.print("\n[bold cyan]═══ BUILDING 3-LEG POWER ENTRIES ═══[/bold cyan]\n")
            entries = build_entries(
                picks=picks,
                payout_table=power_table,
                legs=3,
                min_teams=2,
                max_player_legs=1,
                same_team_penalty=0.05
            )
            console.print(f"[green]✓ Generated {len(entries)} entries[/green]\n")
            # Show top 10
            entry_table = Table(show_header=True, header_style="bold cyan")
            entry_table.add_column("Rank", width=5)
            entry_table.add_column("Players", width=50)
            entry_table.add_column("EV", width=8)
            entry_table.add_column("Prob", width=8)
            for idx, entry in enumerate(entries[:10], 1):
                players_str = ", ".join(entry['players'][:3])
                ev_str = f"+{entry['ev_units']:.2f}u"
                prob_str = f"{entry['joint_prob']*100:.1f}%"
                entry_table.add_row(
                    str(idx), players_str, ev_str, prob_str,
                    style="green" if entry['ev_units'] > 0.10 else "yellow"
                )
            console.print(entry_table)
            # Save results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = {
                "slate": "MIL @ ATL",
                "analyzed_at": timestamp,
                "picks": picks,
                "top_entries": entries[:20]
            }
            outfile = f"outputs/MIL_ATL_{timestamp}.json"
            with open(outfile, 'w') as f:
                json.dump(output, f, indent=2)
            console.print(f"\n[bold green]✓ Saved to: {outfile}[/bold green]\n")

        def run_golf():
            # Example: run the golf round prediction agent
            try:
                golf_mod = importlib.import_module("golf_agents.round_prediction")
                if hasattr(golf_mod, "main"):
                    golf_mod.main()
                else:
                    console.print("[yellow]Golf agent loaded. Please run your golf analysis script manually or add a main() entrypoint.[/yellow]")
            except Exception as e:
                console.print(f"[red]Golf analysis failed: {e}[/red]")

        def run_other(sport):
            console.print(f"[yellow]No pipeline implemented for {sport.upper()} yet.[/yellow]")

        def main():
            while True:
                sport = show_menu()
                if sport == "nba":
                    run_nba()
                elif sport == "golf":
                    run_golf()
                elif sport == "exit":
                    console.print("[bold green]Goodbye![/bold green]")
                    break
                else:
                    run_other(sport)

        if __name__ == "__main__":
            main()
