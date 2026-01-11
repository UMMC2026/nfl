"""
Interactive Signal Menu for Underdog Fantasy Analyzer.

AUTHORITATIVE MENU
- Option [1] runs the TRUTH PIPELINE ONLY (daily_pipeline.py)
- All downstream actions must rely on validated output
"""

import os
import sys
import json
import asyncio
import io
import subprocess
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────────────────────
# UTF-8 FIX (Windows)
# ─────────────────────────────────────────────────────────────
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Rich UI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()

# ─────────────────────────────────────────────────────────────
# MENU CONFIG
# ─────────────────────────────────────────────────────────────

MENU_OPTIONS = {
    "1": ("🔄 VALIDATE TRUTH PIPELINE", "Ingests picks → validates against ESPN schedule + active roster → outputs 77 edges (REQUIRED BEFORE ANY SEND)"),
    "2": ("📤 SEND RANKED PICKS", "Broadcasts validated picks to Telegram (REQUIRES: run [1] first, file timestamp = today)"),
    "3": ("📊 VIEW RANKED PICKS", "Displays ranked validated picks (READ-ONLY, shows only picks from [1] output)"),
    "3b": ("⚔️ VIEW BY MATCHUP", "Inspects picks grouped by opponent (READ-ONLY, shows confidence tiers from live calculation)"),
    "3c": ("📤 SEND BY MATCHUP", "Broadcasts matchup-grouped picks to Telegram (REQUIRES: [1] run today)"),
    "3d": ("📉 SEND UNDERS", "Broadcasts UNDER picks by opponent to Telegram (REQUIRES: [1] run today)"),
    "4": ("🎲 BUILD PARLAYS", "Generates optimized entry combinations (REQUIRES: [1] must be run first, uses validated edges only)"),
    "5": ("📤 SEND PARLAYS", "Broadcasts parlay entries to Telegram (REQUIRES: [1] and [4] completed)"),
    "6": ("📤 SEND RANKED PICKS", "Alias for option [2] (REQUIRES: [1] run today)"),
    "7": ("📂 VIEW ALL REPORTS", "Displays output directory (READ-ONLY, diagnostic)"),
    "8": ("📈 VIEW STATS", "Historical performance metrics (READ-ONLY, diagnostic)"),
    "9": ("🔍 HYDRATE PICKS", "Fetches recent stats from ESPN (optional, pre-step to [1])"),
    "10": ("📝 EDIT PICKS", "Edit picks.json in editor (PRECONDITION: [1] will re-ingest after save)"),
    "11": ("⚙️ SETTINGS", "Configure environment variables (REQUIRES: restart after changes)"),
    "12": ("📊 UPDATE BOX SCORES", "Fetch final game results from ESPN and update historical performance (FINAL-ONLY reconciliation)"),
    "0": ("👋 EXIT", "Close program"),
}

VALIDATED_OUTPUT = Path("outputs/validated_primary_edges.json")

# ─────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────

def print_header():
    console.clear()
    console.print(
        """
╔═══════════════════════════════════════════════════════════════╗
║     🏀 UNDERDOG FANTASY ANALYZER 🏀                          ║
║     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ║
║     TRUTH-GATED SIGNAL OPERATIONS                             ║
╚═══════════════════════════════════════════════════════════════╝
""",
        style="bold cyan",
    )


def print_menu():
    table = Table(box=box.ROUNDED, show_header=False)
    table.add_column("Key", style="bold yellow", width=5)
    table.add_column("Option", style="bold white", width=28)
    table.add_column("Description", style="dim")

    for key, (label, desc) in MENU_OPTIONS.items():
        table.add_row(f"[{key}]", label, desc)

    console.print(table)
    console.print()


def print_status():
    validated = VALIDATED_OUTPUT.exists()
    ts = (
        datetime.fromtimestamp(VALIDATED_OUTPUT.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        if validated else "—"
    )

    status = f"""
Validated Output: [{'green' if validated else 'red'}]{'READY' if validated else 'MISSING'}[/]
Last Run: {ts}
"""
    console.print(Panel(status.strip(), title="System Status", border_style="blue"))

# ─────────────────────────────────────────────────────────────
# HARD GATE
# ─────────────────────────────────────────────────────────────

def require_validated_output(action: str) -> bool:
    if not VALIDATED_OUTPUT.exists():
        console.print(
            f"[red]❌ Cannot {action}: validated output missing.[/]\n"
            "[dim]Run [1] Daily Pipeline first.[/]"
        )
        input("\nPress Enter to continue...")
        return False
    return True

# ─────────────────────────────────────────────────────────────
# MENU ACTIONS
# ─────────────────────────────────────────────────────────────

def run_daily_pipeline():
    """AUTHORITATIVE PIPELINE EXECUTION"""

    console.print("\n[bold cyan]🔄 Running Daily Pipeline (Truth Path)...[/]\n")

    try:
        result = subprocess.run(
            [sys.executable, "daily_pipeline.py"],
            cwd=Path.cwd(),
            capture_output=False,
            text=True,
        )

        if result.returncode != 0:
            console.print("\n[red]❌ Pipeline failed. No output generated.[/]")
            input("\nPress Enter to continue...")
            return

        if not VALIDATED_OUTPUT.exists():
            console.print("[red]❌ Pipeline ran but validated output missing.[/]")
            input("\nPress Enter to continue...")
            return

        console.print("[green]✅ Daily pipeline completed successfully.[/]")
        console.print(f"[dim]Output:[/] {VALIDATED_OUTPUT}")

    except Exception as e:
        console.print(f"[red]❌ Execution error:[/] {e}")

    input("\nPress Enter to continue...")

# ─────────────────────────────────────────────────────────────
# PLACEHOLDER ACTIONS (UNCHANGED)
# NOTE: These must load from validated_primary_edges.json internally
# ─────────────────────────────────────────────────────────────

def send_telegram():
    if not require_validated_output("send Telegram signals"):
        return
    subprocess.run([sys.executable, "send_telegram_signals.py"])


def rank_picks():
    if not require_validated_output("view ranked picks"):
        return
    subprocess.run([sys.executable, "view_ranked_picks.py"])


def view_by_opponent():
    if not require_validated_output("view by opponent"):
        return
    subprocess.run([sys.executable, "view_by_opponent.py"])


def send_by_opponent():
    if not require_validated_output("send by opponent"):
        return
    subprocess.run([sys.executable, "send_telegram_by_opponent.py"])


def send_unders():
    if not require_validated_output("send unders"):
        return
    subprocess.run([sys.executable, "send_telegram_unders.py"])


def build_parlays():
    if not require_validated_output("build parlays"):
        return
    subprocess.run([sys.executable, "build_parlays.py"])


def send_parlays():
    if not require_validated_output("send parlays"):
        return
    subprocess.run([sys.executable, "send_telegram_parlays.py"])


def send_ranked_picks():
    if not require_validated_output("send ranked picks"):
        return
    subprocess.run([sys.executable, "send_telegram_ranked.py"])


def view_all_reports():
    """Run the reports viewer in-process if possible, otherwise fall back to subprocess.

    Running in-process avoids strange subprocess resolution issues on Windows where
    launching the script could invoke the wrong entrypoint. We prefer to import
    and call the function directly when available.
    """
    try:
        # Try in-process import and call
        from view_all_reports import view_all_reports as _v
        _v()
    except Exception:
        # Fallback: spawn a subprocess (legacy behavior)
        subprocess.run([sys.executable, "view_all_reports.py"])
    input("\nPress Enter to continue...")


def view_stats():
    subprocess.run([sys.executable, "view_stats.py"])


def hydrate_picks():
    subprocess.run([sys.executable, "hydrate_picks.py"])


def edit_picks():
    os.startfile("picks.json") if Path("picks.json").exists() else None


def settings_menu():
    os.startfile(".env") if Path(".env").exists() else None


def update_box_scores():
    """Fetch final game results from ESPN and update ResultsTracker"""
    console.print("\n[bold cyan]📊 Updating Box Scores (FINAL-ONLY reconciliation)...[/]\n")
    
    try:
        result = subprocess.run(
            [sys.executable, "update_box_scores.py"],
            cwd=Path.cwd(),
            capture_output=False,
            text=True,
        )
        
        if result.returncode == 0:
            console.print("[green]✅ Box scores updated successfully.[/]")
        else:
            console.print("[red]❌ Box score update failed.[/]")
            
    except Exception as e:
        console.print(f"[red]❌ Error updating box scores: {e}[/]")
    
    input("\nPress Enter to continue...")

# ─────────────────────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────────────────────

def main():
    while True:
        print_header()
        print_status()
        print_menu()

        choice = Prompt.ask("Select option", choices=list(MENU_OPTIONS.keys()), default="1")

        if choice == "0":
            console.print("\n[bold cyan]👋 Goodbye.[/]\n")
            break
        elif choice == "1":
            run_daily_pipeline()
        elif choice == "2":
            send_telegram()
        elif choice == "3":
            rank_picks()
        elif choice == "3b":
            view_by_opponent()
        elif choice == "3c":
            send_by_opponent()
        elif choice == "3d":
            send_unders()
        elif choice == "4":
            build_parlays()
        elif choice == "5":
            send_parlays()
        elif choice == "6":
            send_ranked_picks()
        elif choice == "7":
            view_all_reports()
        elif choice == "8":
            view_stats()
        elif choice == "9":
            hydrate_picks()
        elif choice == "10":
            edit_picks()
        elif choice == "11":
            settings_menu()
        elif choice == "12":
            update_box_scores()


if __name__ == "__main__":
    main()
