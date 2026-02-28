"""
CBB Interactive Menu — NBA-Style Diagnostic & Reporting

Provides CBB-specific menu options for report export, diagnostics, cheat sheet, context features, and calibration tools.
"""

import sys
from sports.cbb.report_generator import generate_cbb_report, generate_cheatsheet, generate_stat_rankings
from sports.cbb.diagnostics import run_diagnostics

MENU_OPTIONS = {
    'R': 'Export Report — Save full CBB report to file',
    'W': 'View/Export Report by Name',
    'D': 'Diagnosis All — Check all CBB reports for issues',
    'H': 'Cheat Sheet — Generate quick reference CBB report',
    'E': 'Context Features — Coach, Pace, Rotation Flags',
    'L': 'Role Layer Filter — Filter by archetype/stats',
    'P': 'Probability Breakdown — Confidence composition for each pick',
    'K': 'Distribution Preview — Monte Carlo simulation visualization',
    'X': "Loss Expectation — Loss frequency & worst-case scenarios",
    'S': 'Stat Rankings — Top-5 picks per stat category (Enhanced)',
    'DR': 'Drift Detector — Calibration drift alerts & status',
    'CM': 'Migrate Calibration — Convert old picks to new schema',
    'CE': 'Setup Environment — Configure calibration tracking',
}

def print_menu():
    print("\nCBB Diagnostic & Reporting Menu:")
    for key, desc in MENU_OPTIONS.items():
        print(f"[{key}] {desc}")
    print("[Q] Quit")


def main():
    while True:
        print_menu()
        choice = input("Select option: ").strip().upper()
        if choice == 'Q':
            sys.exit(0)
        elif choice == 'R':
            generate_cbb_report()
        elif choice == 'H':
            generate_cheatsheet()
        elif choice == 'S':
            generate_stat_rankings()
        elif choice == 'D':
            run_diagnostics()
        # Add additional handlers for other menu options as needed
        else:
            print("Option not implemented yet.")

if __name__ == "__main__":
    main()
