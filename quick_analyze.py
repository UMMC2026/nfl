"""
DIRECT SLATE ANALYSIS - No Menu, Just Results
Paste your Underdog slate and get instant analysis
"""
import sys
from slate_menu import SlateManager
from rich.console import Console

console = Console()

def main():
    console.print("\n[bold cyan]═══ PASTE YOUR UNDERDOG SLATE ═══[/bold cyan]")
    console.print("[yellow]Paste the slate below, then press Ctrl+Z (Windows) or Ctrl+D (Mac/Linux)[/yellow]\n")
    
    # Read from stdin
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    
    text = '\n'.join(lines)
    
    if not text.strip():
        console.print("[red]No input received.[/red]")
        return
    
    # Parse
    console.print("\n[cyan]Parsing...[/cyan]")
    manager = SlateManager()
    props = manager.parse_underdog_text(text)
    
    if not props:
        console.print("[red]No props parsed. Check format.[/red]")
        return
    
    console.print(f"[green]✓ Parsed {len(props)} props[/green]")
    
    # Add to manager
    manager.add_underdog_props(props)
    
    # Analyze
    console.print("\n[cyan]Analyzing with NBA stats...[/cyan]")
    manager.analyze_all()
    
    # Display results
    console.print()
    manager.display_analysis()
    
    # Ask if they want to build entries
    console.print("\n[bold]Build optimal entries?[/bold]")
    console.print("  [1] Yes - 3-leg power")
    console.print("  [2] Yes - 4-leg power")
    console.print("  [3] Yes - 3-leg flex")
    console.print("  [4] No - just save and exit")
    
    try:
        choice = input("\nChoice (1-4): ").strip()
        
        if choice == "1":
            manager.build_optimal_entries("power", 3, 10)
        elif choice == "2":
            manager.build_optimal_entries("power", 4, 10)
        elif choice == "3":
            manager.build_optimal_entries("flex", 3, 10)
    except:
        pass
    
    # Save
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outputs/underdog_analysis_{timestamp}.json"
    manager.save_results(filename)
    
    console.print(f"\n[bold green]✓ Complete![/bold green]\n")

if __name__ == "__main__":
    main()
