"""
Analyze slate from latest_slate.txt file
"""
from slate_menu import SlateManager
from rich.console import Console

console = Console()

# Read the slate
with open("latest_slate.txt", "r") as f:
    text = f.read()

# Parse and analyze
manager = SlateManager()
props = manager.parse_underdog_text(text)

console.print(f"\n[green]✓ Parsed {len(props)} props from latest_slate.txt[/green]\n")

if props:
    # Display what was parsed
    console.print("[cyan]Props parsed:[/cyan]")
    for i, p in enumerate(props, 1):
        console.print(f"  {i}. {p['player']:25} {p['stat']:12} {p['line']:5.1f} {p['direction']}")
    
    # Analyze
    manager.add_underdog_props(props)
    console.print("\n[cyan]Analyzing...[/cyan]")
    manager.analyze_all()
    
    # Display
    console.print()
    manager.display_analysis()
    
    # Build entries
    console.print("\n[cyan]Building optimal 3-leg power entries...[/cyan]")
    manager.build_optimal_entries("power", 3, 10)
    
    # Save
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outputs/mil_atl_{timestamp}.json"
    manager.save_results(filename)
    
    console.print(f"\n[bold green]✓ Done! Results saved to {filename}[/bold green]\n")
else:
    console.print("[red]No props parsed[/red]")
