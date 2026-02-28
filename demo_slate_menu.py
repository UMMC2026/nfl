"""
Demo: Shows how the slate menu works with both platforms
"""
from slate_menu import SlateManager
from rich.console import Console

console = Console()

def demo():
    """Quick demo of slate menu functionality"""
    
    console.print("\n[bold cyan]═══ SLATE MENU DEMO ═══[/bold cyan]\n")
    
    # Create manager
    manager = SlateManager()
    
    # Load existing Underdog data
    console.print("[yellow]Step 1: Loading Underdog slate...[/yellow]")
    manager.load_from_file("mil_atl_jan19_props.json", "underdog")
    
    # Simulate PrizePicks data (you would paste this)
    console.print("\n[yellow]Step 2: Adding sample PrizePicks props...[/yellow]")
    prizepicks_sample = [
        {
            "player": "Damian Lillard",
            "team": "MIL",
            "stat": "points",
            "line": 25.5,
            "direction": "higher",
            "source": "prizepicks"
        },
        {
            "player": "Trae Young",
            "team": "ATL",
            "stat": "assists",
            "line": 11.5,
            "direction": "higher",
            "source": "prizepicks"
        }
    ]
    manager.add_prizepicks_props(prizepicks_sample)
    
    # Analyze all
    console.print("\n[yellow]Step 3: Analyzing all props (hydrating stats from NBA API)...[/yellow]")
    manager.analyze_all()
    
    # Display results
    console.print("\n[yellow]Step 4: Displaying ranked results...[/yellow]")
    manager.display_analysis()
    
    # Build entries
    console.print("\n[yellow]Step 5: Building optimal 3-leg power entries...[/yellow]")
    entries = manager.build_optimal_entries(format_type="power", legs=3, max_entries=5)
    
    # Save
    console.print("\n[yellow]Step 6: Saving results...[/yellow]")
    manager.save_results("outputs/demo_combined_analysis.json")
    
    console.print("\n[bold green]✓ Demo complete![/bold green]")
    console.print("\n[cyan]Next steps:[/cyan]")
    console.print("  • Run: [bold]python slate_menu.py menu[/bold]")
    console.print("  • Paste your own Underdog or PrizePicks slates")
    console.print("  • Get instant analysis and optimal entries")
    console.print("\n")

if __name__ == "__main__":
    demo()
