"""
Direct launcher for the new slate menu system
Bypasses the old menu to avoid conflicts
"""
import sys
from slate_menu import interactive_menu

if __name__ == "__main__":
    print("\n" + "="*70)
    print("  SLATE ANALYZER - PrizePicks & Underdog")
    print("  Interactive Menu System")
    print("="*70 + "\n")
    
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print("\n\n[Cancelled by user]")
        sys.exit(0)
