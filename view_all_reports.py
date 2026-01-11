#!/usr/bin/env python3
"""
View all reports on one page - organized by type and date.
"""

import sys
import io
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich import box

# UTF-8 encoding fix for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

console = Console()

def format_file_size(size_bytes):
    """Format file size in human readable format."""
    for unit in ['B', 'KB', 'MB']:
        if size_bytes < 1024:
            return f"{size_bytes:.0f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}GB"

def format_timestamp(filename):
    """Extract and format timestamp from filename."""
    # Format: FILENAME_DATE_TIME.txt or FILENAME_DATE_TIME.txt
    parts = filename.split('_')
    if len(parts) >= 3:
        date_part = parts[-2]
        time_part = parts[-1].replace('.txt', '')
        try:
            # Parse YYYYMMDD format
            dt = datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H%M%S")
            return dt.strftime("%b %d, %I:%M %p")
        except:
            return "Unknown"
    return "Unknown"

def view_all_reports():
    """Display all reports in organized view."""
    
    outputs_dir = Path("outputs")
    if not outputs_dir.exists():
        console.print("[red]❌ outputs/ directory not found[/red]")
        return
    
    console.print("\n" + "="*80)
    console.print("[bold cyan]📊 ALL REPORTS[/bold cyan]")
    console.print("="*80 + "\n")
    
    # Get all report files
    cheatsheets = sorted(outputs_dir.glob("CHEATSHEET_*.txt"), reverse=True)
    build_reports = sorted(outputs_dir.glob("build_cheatsheet_*.txt"), reverse=True)
    set_reports = sorted(outputs_dir.glob("build_set_report_*.txt"), reverse=True)
    
    # Display Cheatsheets
    if cheatsheets:
        console.print("[bold yellow]📋 DAILY CHEATSHEETS[/bold yellow]")
        table = Table(box=box.ROUNDED)
        table.add_column("Date/Time", style="cyan", width=20)
        table.add_column("Filename", style="white")
        table.add_column("Size", style="dim", width=8)
        
        for f in cheatsheets[:10]:  # Show last 10
            timestamp = format_timestamp(f.name)
            size = format_file_size(f.stat().st_size)
            table.add_row(timestamp, f.name, size)
        
        console.print(table)
        console.print(f"[dim]Showing latest 10 of {len(cheatsheets)} cheatsheets[/dim]\n")
    
    # Display Build Reports
    if build_reports:
        console.print("[bold yellow]🎲 BUILD ENTRY REPORTS[/bold yellow]")
        table = Table(box=box.ROUNDED)
        table.add_column("Date/Time", style="cyan", width=20)
        table.add_column("Filename", style="white")
        table.add_column("Size", style="dim", width=8)
        
        for f in build_reports[:10]:  # Show last 10
            timestamp = format_timestamp(f.name)
            size = format_file_size(f.stat().st_size)
            table.add_row(timestamp, f.name, size)
        
        console.print(table)
        console.print(f"[dim]Showing latest 10 of {len(build_reports)} build reports[/dim]\n")
    
    # Display Set Reports
    if set_reports:
        console.print("[bold yellow]📑 SET PERFORMANCE REPORTS[/bold yellow]")
        table = Table(box=box.ROUNDED)
        table.add_column("Date/Time", style="cyan", width=20)
        table.add_column("Filename", style="white")
        table.add_column("Size", style="dim", width=8)
        
        for f in set_reports[:10]:  # Show last 10
            timestamp = format_timestamp(f.name)
            size = format_file_size(f.stat().st_size)
            table.add_row(timestamp, f.name, size)
        
        console.print(table)
        console.print(f"[dim]Showing latest 10 of {len(set_reports)} set reports[/dim]\n")
    
    # Summary
    total_reports = len(cheatsheets) + len(build_reports) + len(set_reports)
    console.print("="*80)
    console.print(f"[dim]📊 Total: {total_reports} reports | Latest cheatsheet: {cheatsheets[0].name if cheatsheets else 'None'}[/dim]")
    console.print("="*80)
    
    # Latest reports summary
    if cheatsheets:
        console.print("\n[bold cyan]📌 LATEST CHEATSHEET PREVIEW[/bold cyan]")
        console.print("[dim]" + "─"*80 + "[/dim]")

        # Paginate the cheatsheet preview so long files can be inspected interactively.
        with open(cheatsheets[0], 'r', encoding='utf-8') as f:
            lines = [l.rstrip('\n') for l in f.readlines()]

        page_size = 40
        total_lines = len(lines)
        total_pages = (total_lines + page_size - 1) // page_size

        def _show_page(page_idx: int):
            start = page_idx * page_size
            end = min(start + page_size, total_lines)
            console.print(f"[bold]Preview page {page_idx+1}/{total_pages} — lines {start+1}-{end}[/bold]")
            console.print("[dim]" + "─"*80 + "[/dim]")
            for ln in lines[start:end]:
                console.print(ln)
            console.print("[dim]" + "─"*80 + "[/dim]")

        page = 0
        while True:
            _show_page(page)
            if total_pages == 1:
                break
            console.print("[dim]Commands: [Enter]=next, b=back, q=quit[/dim]")
            cmd = input().strip().lower()
            if cmd == 'q':
                break
            if cmd == 'b':
                page = max(0, page - 1)
            else:
                # default: next page
                if page < total_pages - 1:
                    page += 1
                else:
                    break

        console.print(f"[dim](showing preview of {cheatsheets[0].name})[/dim]")
    
    console.print()

if __name__ == "__main__":
    view_all_reports()
