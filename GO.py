"""
STANDALONE SLATE ANALYZER
No imports until needed - bypasses all menu conflicts
"""

def main():
    print("\n" + "="*70)
    print("  SLATE ANALYZER - Direct Analysis (No Menu)")
    print("="*70 + "\n")
    
    print("Reading slate from latest_slate.txt...")
    
    with open("latest_slate.txt", "r") as f:
        text = f.read()
    
    # NOW import (after all user code has run)
    from slate_menu import SlateManager
    from rich.console import Console
    
    console = Console()
    
    # Parse
    manager = SlateManager()
    props = manager.parse_underdog_text(text)
    
    print(f"\n✓ Parsed {len(props)} props\n")
    
    if not props:
        print("ERROR: No props parsed")
        return
    
    # Show what was parsed
    console.print("[cyan]Props:[/cyan]")
    for i, p in enumerate(props, 1):
        print(f"  {i:2}. {p['player']:25} {p['team']:3} {p['stat']:12} {p['line']:5.1f} {p['direction']:7}")
    
    # Analyze
    manager.add_underdog_props(props)
    print("\nAnalyzing with NBA API...")
    manager.analyze_all()
    
    # Display
    print()
    manager.display_analysis()
    
    # Build entries
    print("\n[Building optimal 3-leg power entries...]")
    manager.build_optimal_entries("power", 3, 10)
    
    # Save
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"outputs/analysis_{timestamp}.json"
    manager.save_results(filename)
    
    print(f"\n✓ Results saved to {filename}\n")

if __name__ == "__main__":
    # Run without any prior imports
    main()
