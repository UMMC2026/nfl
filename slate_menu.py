"""
Interactive Menu System for PrizePicks & Underdog Slates
Accepts slates from multiple sources and provides unified analysis
"""
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
import typer

from ufa.models.schemas import PropPick
from ufa.analysis.prob import prob_hit
from ufa.ingest.hydrate import hydrate_recent_values
from ufa.optimizer.entry_builder import build_entries
from ufa.analysis.payouts import power_table, flex_table

console = Console()
app = typer.Typer()


class SlateManager:
    """Manages props from both PrizePicks and Underdog"""
    
    def __init__(self):
        self.prizepicks_props: List[Dict] = []
        self.underdog_props: List[Dict] = []
        self.all_props: List[Dict] = []
        self.analyzed_props: List[Dict] = []
    
    def parse_underdog_text(self, text: str) -> List[Dict]:
        """Parse Underdog format from terminal paste"""
        # Prefer the shared parser (handles Goblin/Demon/Taco, More/Less, taco double-number lines, etc.)
        try:
            from parse_underdog_paste import parse_text as _parse_ud

            parsed = _parse_ud(text)
            if parsed:
                for p in parsed:
                    p.setdefault("source", "underdog")
                return parsed
        except Exception:
            # Fall back to legacy heuristic parser below.
            pass

        props = []
        lines = [line.strip() for line in text.strip().split('\n')]
        
        # NBA teams for detection
        NBA_TEAMS = ['MIL', 'ATL', 'BOS', 'LAL', 'GSW', 'PHX', 'DAL', 'DEN', 'MIA', 'NYK', 
                     'BKN', 'PHI', 'CLE', 'ORL', 'MEM', 'SAC', 'NOP', 'MIN', 'IND', 'CHI', 
                     'TOR', 'CHA', 'WAS', 'DET', 'POR', 'HOU', 'OKC', 'SAS', 'UTA', 'LAC']
        
        i = 0
        while i < len(lines):
            # Look for team line pattern: "TEAM - Position"
            if ' - ' in lines[i] and any(team in lines[i] for team in NBA_TEAMS):
                team_line = lines[i]
                team = None
                for t in NBA_TEAMS:
                    if t in team_line:
                        team = t
                        break
                
                # Player name is usually 1-2 lines before team line
                player = None
                if i >= 1:
                    # Check previous line for player name
                    prev_line = lines[i-1]
                    # Clean up player name (remove "Demon" and other suffixes)
                    player = (prev_line
                              .replace('Demon', '')
                              .replace('Goblin', '')
                              .replace('Taco', '')
                              .strip())
                
                if not player or not team:
                    i += 1
                    continue
                
                # Look ahead for line value (should be a number)
                line_value = None
                stat_type = None
                direction = None
                
                # Scan next 10 lines for the pattern
                for j in range(i+1, min(i+15, len(lines))):
                    line_text = lines[j]
                    
                    # Try to parse as float (this is the line value)
                    if line_value is None:
                        try:
                            # Taco lines may have two numbers stuck together (e.g. "31.524.5")
                            nums = re.findall(r"\d+\.?\d*", line_text)
                            if not nums:
                                raise ValueError("no numeric value")
                            line_value = float(nums[-1])
                            # Next line should be stat type
                            if j+1 < len(lines):
                                stat_type = lines[j+1]
                                # Line after that should be direction
                                if j+2 < len(lines):
                                    direction_text = lines[j+2]
                                    direction = 'higher' if direction_text in ['More', 'Higher'] else 'lower'
                                    break
                        except ValueError:
                            continue
                
                if player and team and line_value is not None and stat_type and direction:
                    # Map stat names
                    stat_map = {
                        'Points': 'points',
                        'Rebounds': 'rebounds',
                        'Assists': 'assists',
                        'PRA': 'pts+reb+ast',
                        'Pts+Asts': 'pts+ast',
                        'Reb+Asts': 'reb+ast',
                        'Pts+Rebs': 'pts+reb',
                        '3-PT Made': '3pm',
                        'Blocks': 'blocks',
                        'Steals': 'steals',
                        '3s': '3pm',
                        'Blks+Stls': 'stl+blk'
                    }
                    
                    stat_key = stat_map.get(stat_type, stat_type.lower().replace(' ', '_').replace('+', '_'))
                    
                    props.append({
                        'player': player,
                        'team': team,
                        'stat': stat_key,
                        'line': line_value,
                        'direction': direction,
                        'source': 'underdog'
                    })
            
            i += 1
        
        return props
    
    def parse_prizepicks_text(self, text: str) -> List[Dict]:
        """Parse PrizePicks format from chat paste"""
        props = []
        lines = text.strip().split('\n')
        
        for line in lines:
            # PrizePicks format: "Player Name OVER/UNDER X.X Stat (TEAM)"
            # Example: "LeBron James OVER 25.5 Points (LAL)"
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) < 4:
                continue
            
            # Find OVER/UNDER
            direction_idx = None
            direction = None
            for i, part in enumerate(parts):
                if part.upper() in ['OVER', 'UNDER', 'MORE', 'LESS']:
                    direction_idx = i
                    direction = 'higher' if part.upper() in ['OVER', 'MORE'] else 'lower'
                    break
            
            if direction_idx is None:
                continue
            
            # Player name is everything before direction
            player = ' '.join(parts[:direction_idx])
            
            # Line value is after direction
            if direction_idx + 1 < len(parts):
                try:
                    line_value = float(parts[direction_idx + 1])
                except ValueError:
                    continue
                
                # Stat and team
                remaining = parts[direction_idx + 2:]
                team = None
                stat_parts = []
                
                for part in remaining:
                    if part.startswith('(') and part.endswith(')'):
                        team = part.strip('()')
                    else:
                        stat_parts.append(part)
                
                stat_name = ' '.join(stat_parts)
                
                # Map stat names
                stat_map = {
                    'Points': 'points',
                    'Rebounds': 'rebounds',
                    'Assists': 'assists',
                    'PRA': 'pts+reb+ast',
                    'Pts+Asts': 'pts+ast',
                    'Pts+Rebs': 'pts+reb',
                    '3-PT Made': '3pm',
                    'Fantasy Score': 'fantasy_score'
                }
                
                stat_key = stat_map.get(stat_name, stat_name.lower().replace(' ', '_'))
                
                props.append({
                    'player': player,
                    'team': team or 'UNK',
                    'stat': stat_key,
                    'line': line_value,
                    'direction': direction,
                    'source': 'prizepicks'
                })
        
        return props
    
    def load_from_file(self, filepath: str, source: str = 'underdog'):
        """Load props from JSON file"""
        try:
            with open(filepath, 'r') as f:
                props = json.load(f)
            
            for prop in props:
                prop['source'] = source
            
            if source == 'prizepicks':
                self.prizepicks_props.extend(props)
            else:
                self.underdog_props.extend(props)
            
            self.all_props = self.prizepicks_props + self.underdog_props
            console.print(f"[green]✓ Loaded {len(props)} props from {filepath}[/green]")
        except Exception as e:
            console.print(f"[red]Error loading {filepath}: {e}[/red]")
    
    def add_underdog_props(self, props: List[Dict]):
        """Add Underdog props"""
        self.underdog_props.extend(props)
        self.all_props = self.prizepicks_props + self.underdog_props
    
    def add_prizepicks_props(self, props: List[Dict]):
        """Add PrizePicks props"""
        self.prizepicks_props.extend(props)
        self.all_props = self.prizepicks_props + self.underdog_props
    
    def analyze_all(self):
        """Analyze all loaded props"""
        console.print("\n[bold cyan]Analyzing all props...[/bold cyan]\n")
        
        results = []
        for prop in self.all_props:
            try:
                recent_values = hydrate_recent_values(
                    league="NBA",
                    player=prop['player'],
                    stat_key=prop['stat'],
                    nba_season="2024-25"
                )
                
                if recent_values:
                    p_value = prob_hit(
                        line=prop['line'],
                        direction=prop['direction'],
                        recent_values=recent_values
                    )
                else:
                    p_value = 0.50
                    
            except Exception as e:
                console.print(f"[yellow]Warning: {prop['player']} - {prop['stat']}: {e}[/yellow]")
                p_value = 0.50
                recent_values = []
            
            results.append({
                **prop,
                'p_hit': float(p_value),
                'recent_values': recent_values
            })
        
        # Sort by probability
        results.sort(key=lambda x: x['p_hit'], reverse=True)
        self.analyzed_props = results
        
        return results
    
    def display_analysis(self):
        """Display analyzed props in a table"""
        if not self.analyzed_props:
            console.print("[yellow]No props analyzed yet. Run analysis first.[/yellow]")
            return
        
        table = Table(title="Combined Analysis - All Props", show_lines=True, box=box.ROUNDED)
        table.add_column("Rank", style="cyan", width=5)
        table.add_column("Source", style="magenta", width=10)
        table.add_column("Player", style="white", width=20)
        table.add_column("Team", style="yellow", width=5)
        table.add_column("Stat", style="green", width=12)
        table.add_column("Line", style="blue", width=8)
        table.add_column("Dir", style="blue", width=6)
        table.add_column("P(hit)", style="bold green", width=8)
        table.add_column("Recent (L5)", style="dim", width=25)
        
        for rank, r in enumerate(self.analyzed_props, 1):
            recent_str = ""
            if r.get('recent_values'):
                recent_str = ", ".join([f"{v:.1f}" for v in r['recent_values'][:5]])
            
            color = "green" if r['p_hit'] >= 0.60 else ("yellow" if r['p_hit'] >= 0.50 else "red")
            
            table.add_row(
                str(rank),
                r['source'].upper(),
                r['player'],
                r['team'],
                r['stat'],
                f"{r['line']:.1f}",
                r['direction'],
                f"[{color}]{r['p_hit']:.2%}[/{color}]",
                recent_str
            )
        
        console.print(table)
        
        # Summary stats
        high_conf = sum(1 for r in self.analyzed_props if r['p_hit'] >= 0.60)
        medium_conf = sum(1 for r in self.analyzed_props if 0.50 <= r['p_hit'] < 0.60)
        low_conf = sum(1 for r in self.analyzed_props if r['p_hit'] < 0.50)
        
        pp_count = sum(1 for r in self.analyzed_props if r['source'] == 'prizepicks')
        ud_count = sum(1 for r in self.analyzed_props if r['source'] == 'underdog')
        
        summary = Panel.fit(
            f"[bold]Summary:[/bold]\n"
            f"  High confidence (≥60%): {high_conf}\n"
            f"  Medium confidence (50-60%): {medium_conf}\n"
            f"  Low confidence (<50%): {low_conf}\n\n"
            f"  PrizePicks props: {pp_count}\n"
            f"  Underdog props: {ud_count}\n"
            f"  Total: {len(self.analyzed_props)}",
            border_style="cyan",
            title="Analysis Summary"
        )
        console.print(summary)
    
    def build_optimal_entries(self, format_type: str = "power", legs: int = 3, max_entries: int = 10):
        """Build optimal entries from analyzed props"""
        if not self.analyzed_props:
            console.print("[yellow]No props analyzed yet.[/yellow]")
            return
        
        # Filter high confidence picks
        good_picks = [p for p in self.analyzed_props if p['p_hit'] >= 0.55]
        
        if len(good_picks) < legs:
            console.print(f"[yellow]Not enough high-confidence picks ({len(good_picks)}) for {legs}-leg entries[/yellow]")
            return
        
        console.print(f"\n[bold cyan]Building {format_type.upper()} entries with {legs} legs...[/bold cyan]\n")
        
        payout_table = power_table() if format_type == "power" else flex_table()
        
        entries = build_entries(
            picks=good_picks,
            payout_table=payout_table,
            legs=legs,
            min_teams=2,
            max_player_legs=1,
            max_team_legs=0
        )
        
        # Display top entries
        table = Table(title=f"Top {min(max_entries, len(entries))} Entries", box=box.ROUNDED)
        table.add_column("Rank", style="cyan")
        table.add_column("Players", style="white", width=40)
        table.add_column("EV", style="bold green")
        table.add_column("Win%", style="yellow")
        table.add_column("Teams", style="magenta")
        
        for i, entry in enumerate(entries[:max_entries], 1):
            # entry has: players, stats, directions, p_list, teams, ev_units
            players_str = ", ".join([p[:15] for p in entry['players']])
            teams_str = "+".join(entry['teams'])
            
            # Calculate win probability from p_list
            win_prob = 1.0
            for p in entry['p_list']:
                win_prob *= p
            
            table.add_row(
                str(i),
                players_str,
                f"{entry.get('ev_units', 0):.3f}",
                f"{win_prob:.2%}",
                teams_str
            )
        
        console.print(table)
        
        return entries[:max_entries]
    
    def save_results(self, filename: str = None):
        """Save analyzed props to file"""
        if not self.analyzed_props:
            console.print("[yellow]Nothing to save yet.[/yellow]")
            return
        
        if not filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"outputs/combined_analysis_{timestamp}.json"
        
        Path(filename).parent.mkdir(exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(self.analyzed_props, f, indent=2)
        
        console.print(f"[green]✓ Saved to {filename}[/green]")


def interactive_menu():
    """Interactive menu for slate management"""
    manager = SlateManager()
    
    while True:
        console.clear()
        console.print(Panel.fit(
            "[bold cyan]Slate Analysis Menu[/bold cyan]\n"
            "[bold]PrizePicks & Underdog Integration[/bold]",
            border_style="cyan"
        ))
        
        console.print("\n[bold]Current Status:[/bold]")
        console.print(f"  PrizePicks props: {len(manager.prizepicks_props)}")
        console.print(f"  Underdog props: {len(manager.underdog_props)}")
        console.print(f"  Total props: {len(manager.all_props)}")
        console.print(f"  Analyzed: {len(manager.analyzed_props)}")
        
        console.print("\n[bold]Menu Options:[/bold]")
        console.print("  [cyan]1[/cyan] - Paste Underdog slate (from terminal)")
        console.print("  [cyan]2[/cyan] - Paste PrizePicks slate (from chat)")
        console.print("  [cyan]3[/cyan] - Load from JSON file")
        console.print("  [cyan]4[/cyan] - Analyze all props")
        console.print("  [cyan]5[/cyan] - View analysis results")
        console.print("  [cyan]6[/cyan] - Build optimal entries")
        console.print("  [cyan]7[/cyan] - Save results")
        console.print("  [cyan]8[/cyan] - Clear all props")
        console.print("  [cyan]9[/cyan] - [bold magenta]Generate FUOOM Subscriber Report[/bold magenta]")
        console.print("  [cyan]q[/cyan] - Quit")
        
        choice = Prompt.ask("\n[bold]Select option[/bold]", default="4")
        
        if choice == "1":
            console.print("\n[yellow]Paste Underdog slate (Ctrl+D or Ctrl+Z when done):[/yellow]")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            
            text = '\n'.join(lines)
            props = manager.parse_underdog_text(text)
            
            if props:
                manager.add_underdog_props(props)
                console.print(f"[green]✓ Added {len(props)} Underdog props[/green]")
            else:
                console.print("[red]No props parsed. Check format.[/red]")
            
            input("\nPress Enter to continue...")
        
        elif choice == "2":
            console.print("\n[yellow]Paste PrizePicks slate (Ctrl+D or Ctrl+Z when done):[/yellow]")
            lines = []
            try:
                while True:
                    line = input()
                    lines.append(line)
            except EOFError:
                pass
            
            text = '\n'.join(lines)
            props = manager.parse_prizepicks_text(text)
            
            if props:
                manager.add_prizepicks_props(props)
                console.print(f"[green]✓ Added {len(props)} PrizePicks props[/green]")
            else:
                console.print("[red]No props parsed. Check format.[/red]")
            
            input("\nPress Enter to continue...")
        
        elif choice == "3":
            filepath = Prompt.ask("Enter file path")
            source = Prompt.ask("Source", choices=["underdog", "prizepicks"], default="underdog")
            manager.load_from_file(filepath, source)
            input("\nPress Enter to continue...")
        
        elif choice == "4":
            manager.analyze_all()
            input("\nPress Enter to continue...")
        
        elif choice == "5":
            manager.display_analysis()
            input("\nPress Enter to continue...")
        
        elif choice == "6":
            format_type = Prompt.ask("Format", choices=["power", "flex"], default="power")
            legs = int(Prompt.ask("Number of legs", default="3"))
            max_entries = int(Prompt.ask("Max entries to show", default="10"))
            
            manager.build_optimal_entries(format_type, legs, max_entries)
            input("\nPress Enter to continue...")
        
        elif choice == "7":
            filename = Prompt.ask("Filename (leave blank for auto)", default="")
            manager.save_results(filename if filename else None)
            input("\nPress Enter to continue...")
        
        elif choice == "8":
            if Confirm.ask("Clear all props?"):
                manager.prizepicks_props = []
                manager.underdog_props = []
                manager.all_props = []
                manager.analyzed_props = []
                console.print("[green]✓ Cleared[/green]")
            input("\nPress Enter to continue...")
        
        elif choice == "9":
            # Generate FUOOM Subscriber Report
            if not manager.analyzed_props:
                console.print("[red]No analyzed props. Run option 4 first.[/red]")
            else:
                try:
                    from report_enhancer import enhance_report, save_enhanced_report
                    
                    # Convert analyzed props to FUOOM format
                    picks_for_report = []
                    for prop in manager.analyzed_props:
                        # Only include picks that passed (PLAY, STRONG, LEAN)
                        decision = prop.get('decision', '')
                        if decision in ('PLAY', 'STRONG', 'LEAN'):
                            picks_for_report.append({
                                'player': prop.get('player', ''),
                                'stat': prop.get('stat', ''),
                                'line': prop.get('line', 0),
                                'direction': prop.get('direction', 'higher'),
                                'probability': prop.get('effective_confidence', 50) / 100,
                                'mu': prop.get('mu', 0),
                                'sigma': prop.get('sigma', 0),
                                'opponent': prop.get('opponent', 'OPP'),
                                'recent_hits': prop.get('hit_count'),
                                'recent_total': 10,
                            })
                    
                    if not picks_for_report:
                        console.print("[yellow]No qualified picks for report (need PLAY/STRONG/LEAN decisions)[/yellow]")
                    else:
                        use_llm = Confirm.ask("Use DeepSeek LLM for polish?", default=False)
                        filepath = save_enhanced_report(picks_for_report, "NBA", use_llm=use_llm)
                        console.print(f"[green]✓ FUOOM report saved: {filepath}[/green]")
                        console.print(f"[cyan]  {len(picks_for_report)} picks included[/cyan]")
                        
                        # Option to view it
                        if Confirm.ask("Open report?", default=True):
                            with open(filepath, 'r', encoding='utf-8') as f:
                                console.print(Panel(f.read(), title="FUOOM DARK MATTER", border_style="magenta"))
                                
                except ImportError as e:
                    console.print(f"[red]Error: report_enhancer.py not found: {e}[/red]")
                except Exception as e:
                    console.print(f"[red]Error generating report: {e}[/red]")
            
            input("\nPress Enter to continue...")
        
        elif choice.lower() == "q":
            console.print("[cyan]Goodbye![/cyan]")
            break


@app.command()
def menu():
    """Launch interactive slate analysis menu"""
    interactive_menu()


@app.command()
def quick_underdog(file: str = typer.Argument(..., help="Path to Underdog JSON file")):
    """Quick analysis of Underdog slate from file"""
    manager = SlateManager()
    manager.load_from_file(file, 'underdog')
    manager.analyze_all()
    manager.display_analysis()


@app.command()
def quick_prizepicks(file: str = typer.Argument(..., help="Path to PrizePicks JSON file")):
    """Quick analysis of PrizePicks slate from file"""
    manager = SlateManager()
    manager.load_from_file(file, 'prizepicks')
    manager.analyze_all()
    manager.display_analysis()


@app.command()
def combined(
    underdog_file: str = typer.Option(None, help="Underdog JSON file"),
    prizepicks_file: str = typer.Option(None, help="PrizePicks JSON file")
):
    """Analyze combined slate from both sources"""
    manager = SlateManager()
    
    if underdog_file:
        manager.load_from_file(underdog_file, 'underdog')
    
    if prizepicks_file:
        manager.load_from_file(prizepicks_file, 'prizepicks')
    
    if manager.all_props:
        manager.analyze_all()
        manager.display_analysis()
    else:
        console.print("[red]No props loaded. Provide at least one file.[/red]")


if __name__ == "__main__":
    app()
