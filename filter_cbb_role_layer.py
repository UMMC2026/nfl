# CBB Role Layer Filter (NBA-style)
# Usage: python filter_cbb_role_layer.py <CBB_JSON_FILE>

import sys
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from sports.cbb.cbb_archetypes import CBB_ARCHETYPES, CBB_SPECIALIST_STATS

console = Console()

MENU = f"""
╭────────────────────── Filter Options ───────────────────────╮
│ CBB ROLE LAYER FILTER MENU                                  │
│                                                             │
│ [1] Show OPTIMAL picks (PRIMARY_SCORER + primary stats)     │
│ [2] Show RISKY picks to AVOID (HIGH_USAGE_VOLATILITY flags) │
│ [3] Filter by archetype                                     │
│ [4] Show archetype distribution                             │
│ [5] Custom confidence threshold                             │
│ [6] Export filtered picks to JSON                           │
│ [7] Show SPECIALIST picks (REB/3PM/STL/BLK specialists)     │
│ [0] Exit                                                    │
╰─────────────────────────────────────────────────────────────╯
"""

def load_cbb_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def filter_optimal(picks):
    return [p for p in picks if p.get("archetype") == "PRIMARY_SCORER" and p.get("confidence", 0) >= 55]

def filter_specialists(picks):
    return [p for p in picks if p.get("cbb_specialist_flags")]

def show_table(picks, title):
    table = Table(title=title)
    table.add_column("Player")
    table.add_column("Stat")
    table.add_column("Line")
    table.add_column("Dir")
    table.add_column("Conf%")
    table.add_column("Archetype")
    table.add_column("Flags")
    for p in picks:
        table.add_row(
            p.get("player", ""),
            p.get("stat", ""),
            str(p.get("line", "")),
            p.get("direction", ""),
            str(p.get("confidence", "")),
            p.get("archetype", ""),
            ", ".join(p.get("cbb_specialist_flags", []))
        )
    console.print(table)

def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python filter_cbb_role_layer.py <CBB_JSON_FILE>[/red]")
        sys.exit(1)
    file_path = sys.argv[1]
    data = load_cbb_json(file_path)
    picks = data.get("results", data)
    while True:
        console.print(MENU)
        opt = input("Select option: ").strip()
        if opt == "0":
            break
        elif opt == "1":
            show_table(filter_optimal(picks), "⭐ OPTIMAL PICKS (PRIMARY_SCORER, Conf >= 55%)")
        elif opt == "7":
            show_table(filter_specialists(picks), "⭐ SPECIALIST PICKS (Stat Specialists)")
        elif opt == "3":
            console.print("\nAvailable archetypes in current data:")
            for a in CBB_ARCHETYPES:
                console.print(f"  - {a}")
            name = input("Enter archetype name: ").strip()
            show_table([p for p in picks if p.get("archetype") == name], f"Picks: {name}")
        else:
            console.print("[yellow]Option not implemented in starter. Use 1, 3, 7, or 0.[/yellow]")

if __name__ == "__main__":
    main()
