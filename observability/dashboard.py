"""
FUOOM Observability Dashboard
=============================
Console-based dashboard showing all observability metrics.

Usage:
    python -m observability.dashboard
    
    # Or from code:
    from observability.dashboard import show_dashboard
    show_dashboard()
"""

import os
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observability.metrics import get_metrics
from observability.circuit_breaker import get_circuit_breaker
from observability.tracer import get_tracer
from observability.health import get_health_checker


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def show_dashboard(clear: bool = True):
    """Show the full observability dashboard."""
    if clear:
        clear_screen()
    
    print("=" * 70)
    print("  📊 FUOOM OBSERVABILITY DASHBOARD")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Health Status
    health = get_health_checker()
    health.print_status()
    
    # Circuit Breakers
    cb = get_circuit_breaker()
    cb.print_status()
    
    # Metrics Summary
    metrics = get_metrics()
    metrics.print_summary()
    
    # Recent Trace (if any)
    tracer = get_tracer()
    current_trace = tracer.get_current_trace()
    if current_trace:
        print("\n📍 Current Trace Active")
        print(f"   Spans: {len(current_trace)}")


def show_metrics_only():
    """Show only metrics."""
    metrics = get_metrics()
    metrics.print_summary()


def show_circuits_only():
    """Show only circuit breaker status."""
    cb = get_circuit_breaker()
    cb.print_status()


def show_health_only():
    """Show only health status."""
    health = get_health_checker()
    health.print_status()


def interactive_menu():
    """Interactive observability menu."""
    while True:
        clear_screen()
        print("=" * 50)
        print("  📊 FUOOM OBSERVABILITY")
        print("=" * 50)
        print("\n  [1] Full Dashboard")
        print("  [2] Health Status Only")
        print("  [3] Circuit Breakers Only")
        print("  [4] Metrics Only")
        print("  [5] Reset All Circuits")
        print("  [6] Save Metrics Snapshot")
        print("\n  [Q] Quit")
        print("=" * 50)
        
        choice = input("\nSelect option: ").strip().upper()
        
        if choice == '1':
            show_dashboard(clear=True)
            input("\nPress Enter to continue...")
        elif choice == '2':
            clear_screen()
            show_health_only()
            input("\nPress Enter to continue...")
        elif choice == '3':
            clear_screen()
            show_circuits_only()
            input("\nPress Enter to continue...")
        elif choice == '4':
            clear_screen()
            show_metrics_only()
            input("\nPress Enter to continue...")
        elif choice == '5':
            cb = get_circuit_breaker()
            cb.reset_all()
            print("✅ All circuits reset")
            input("\nPress Enter to continue...")
        elif choice == '6':
            metrics = get_metrics()
            metrics.save_snapshot()
            print("✅ Metrics snapshot saved")
            input("\nPress Enter to continue...")
        elif choice == 'Q':
            break


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="FUOOM Observability Dashboard")
    parser.add_argument("--health", action="store_true", help="Show health only")
    parser.add_argument("--circuits", action="store_true", help="Show circuits only")
    parser.add_argument("--metrics", action="store_true", help="Show metrics only")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_menu()
    elif args.health:
        show_health_only()
    elif args.circuits:
        show_circuits_only()
    elif args.metrics:
        show_metrics_only()
    else:
        show_dashboard()
