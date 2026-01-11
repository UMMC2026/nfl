#!/usr/bin/env python
"""
Hydrate NBA picks with recent game log values from nba_api.

Usage:
    python scripts/hydrate_nba_picks.py picks_dec30_nba.json --season 2024-25
    python scripts/hydrate_nba_picks.py picks_dec30_nba.json --season 2024-25 --output picks_dec30_nba_filled.json
"""

import json
import sys
import time
import argparse
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Stat key mapping to nba_api column names
# Single stats map to string, combo stats map to list of columns to sum
NBA_STAT_MAP = {
    # Core single stats
    "points": "PTS",
    "rebounds": "REB", 
    "assists": "AST",
    "3pm": "FG3M",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TOV",
    "minutes": "MIN",
    
    # Combo stats (sum of columns)
    "pts+reb+ast": ["PTS", "REB", "AST"],
    "pts+reb": ["PTS", "REB"],
    "pts+ast": ["PTS", "AST"],
    "stl+blk": ["STL", "BLK"],
    "reb+ast": ["REB", "AST"],
    
    # Alternate naming (Underdog format)
    "pra": ["PTS", "REB", "AST"],
    "pr": ["PTS", "REB"],
    "pa": ["PTS", "AST"],
    "ra": ["REB", "AST"],
}


def fetch_player_gamelog(player_name: str, stat_key: str, season: str = "2024-25", last_n: int = 10):
    """Fetch recent game values for a player/stat combo."""
    try:
        from nba_api.stats.static import players
        from nba_api.stats.endpoints import playergamelog
    except ImportError:
        raise RuntimeError("nba_api not installed. Run: pip install nba_api")

    col = NBA_STAT_MAP.get(stat_key)
    if not col:
        return None, f"Unsupported stat: {stat_key}"

    # Find player
    matches = players.find_players_by_full_name(player_name)
    if not matches:
        # Try partial match
        all_players = players.get_players()
        name_lower = player_name.lower()
        matches = [p for p in all_players if name_lower in p["full_name"].lower()]
    
    if not matches:
        return None, f"Player not found: {player_name}"

    pid = int(matches[0]["id"])
    
    try:
        gl = playergamelog.PlayerGameLog(player_id=pid, season=season, timeout=30)
        df = gl.get_data_frames()[0]
    except Exception as e:
        return None, f"API error: {e}"

    if df.empty:
        return None, "No games found"

    # Handle combo stats (list of columns to sum) vs single stats (string)
    if isinstance(col, list):
        # Combo stat - sum multiple columns
        for c in col:
            if c not in df.columns:
                return None, f"Column {c} not in data"
        vals = df[col].head(last_n).sum(axis=1).astype(float).tolist()
    else:
        # Single stat
        if col not in df.columns:
            return None, f"Column {col} not in data"
        vals = df[col].head(last_n).astype(float).tolist()
    
    if len(vals) < 2:
        return None, "Not enough games"
    
    return vals, None


def hydrate_picks(input_file: str, season: str = "2024-25", output_file: str = None, last_n: int = 10):
    """Load picks JSON, hydrate each with recent_values, save result."""
    
    input_path = Path(input_file)
    if not input_path.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        return
    
    with open(input_path, "r", encoding="utf-8") as f:
        picks = json.load(f)
    
    console.print(f"\n[bold cyan]Hydrating {len(picks)} NBA picks from {season} season[/bold cyan]\n")
    
    # Track unique player/stat combos to avoid duplicate API calls
    cache = {}
    results = {"success": 0, "failed": 0, "skipped": 0}
    errors = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching game logs...", total=len(picks))
        
        for i, pick in enumerate(picks):
            player = pick.get("player", "")
            stat = pick.get("stat", "")
            cache_key = f"{player}|{stat}"
            
            progress.update(task, description=f"[cyan]{player}[/cyan] - {stat}")
            
            # Skip if already has recent_values
            if pick.get("recent_values") and len(pick["recent_values"]) >= 5:
                results["skipped"] += 1
                progress.advance(task)
                continue
            
            # Check cache
            if cache_key in cache:
                vals, err = cache[cache_key]
            else:
                vals, err = fetch_player_gamelog(player, stat, season, last_n)
                cache[cache_key] = (vals, err)
                # Rate limit to avoid API throttling
                time.sleep(0.6)
            
            if vals:
                pick["recent_values"] = vals
                results["success"] += 1
            else:
                errors.append(f"{player} ({stat}): {err}")
                results["failed"] += 1
            
            progress.advance(task)
    
    # Output file
    if output_file is None:
        output_file = str(input_path.with_stem(input_path.stem + "_filled"))
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(picks, f, indent=2)
    
    # Summary table
    console.print()
    table = Table(title="Hydration Summary")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right")
    table.add_row("✓ Hydrated", f"[green]{results['success']}[/green]")
    table.add_row("⊘ Skipped (had data)", f"[yellow]{results['skipped']}[/yellow]")
    table.add_row("✗ Failed", f"[red]{results['failed']}[/red]")
    console.print(table)
    
    if errors:
        console.print("\n[yellow]Errors:[/yellow]")
        for err in errors[:10]:  # Limit output
            console.print(f"  [dim]• {err}[/dim]")
        if len(errors) > 10:
            console.print(f"  [dim]... and {len(errors) - 10} more[/dim]")
    
    console.print(f"\n[green]✓ Saved to {output_file}[/green]\n")
    
    # Show sample of hydrated data
    hydrated = [p for p in picks if p.get("recent_values")]
    if hydrated:
        console.print("[bold]Sample hydrated picks:[/bold]")
        sample_table = Table()
        sample_table.add_column("Player", style="white")
        sample_table.add_column("Stat", style="cyan")
        sample_table.add_column("Line", justify="right")
        sample_table.add_column("Avg (L10)", justify="right", style="green")
        sample_table.add_column("Last 3", style="dim")
        
        for p in hydrated[:8]:
            vals = p["recent_values"]
            avg = sum(vals) / len(vals)
            last3 = ", ".join([str(int(v)) for v in vals[:3]])
            sample_table.add_row(
                p["player"],
                p["stat"],
                str(p["line"]),
                f"{avg:.1f}",
                last3
            )
        console.print(sample_table)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hydrate NBA picks with recent game logs")
    parser.add_argument("input", help="Input JSON file with picks")
    parser.add_argument("--season", default="2024-25", help="NBA season (e.g., 2024-25)")
    parser.add_argument("--output", "-o", help="Output file (default: input_filled.json)")
    parser.add_argument("--games", "-n", type=int, default=10, help="Number of recent games to fetch")
    
    args = parser.parse_args()
    hydrate_picks(args.input, args.season, args.output, args.games)
