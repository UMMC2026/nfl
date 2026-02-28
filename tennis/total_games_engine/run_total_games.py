"""
CLI Batch Runner — Total Games Engine
======================================
Processes slate CSV → outputs results CSV + console report.

Usage:
    python run_total_games.py --input slate.csv --output results.csv
    python run_total_games.py --input slate.csv --output results.csv --surface HARD
    python run_total_games.py --input slate.csv --json
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from total_games_engine import MatchInput, process_match, process_slate
from governance import governance_gate, split_by_governance

# =========================
# TOURNAMENT → SURFACE MAP
# =========================

TOURNAMENT_SURFACE_MAP = {
    # Grand Slams
    "australian open": "HARD",
    "french open": "CLAY",
    "roland garros": "CLAY",
    "wimbledon": "GRASS",
    "us open": "HARD",
    # ATP 1000
    "indian wells": "HARD",
    "miami": "HARD",
    "monte carlo": "CLAY",
    "madrid": "CLAY",
    "rome": "CLAY",
    "canada": "HARD",
    "cincinnati": "HARD",
    "shanghai": "HARD",
    "paris": "INDOOR",
    # ATP 500
    "dubai": "HARD",
    "acapulco": "HARD",
    "barcelona": "CLAY",
    "queen's": "GRASS",
    "halle": "GRASS",
    "hamburg": "CLAY",
    "washington": "HARD",
    "tokyo": "HARD",
    "beijing": "HARD",
    "vienna": "INDOOR",
    "basel": "INDOOR",
}


def resolve_surface(tournament: str) -> str | None:
    """Resolve surface from tournament name."""
    if not tournament:
        return None
    return TOURNAMENT_SURFACE_MAP.get(tournament.lower().strip())


def parse_csv(input_path: str) -> list:
    """Parse input CSV into MatchInput objects."""
    matches = []
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Infer rating gap from line if not provided
            line = float(row["total_games_line"])
            rating_gap = row.get("rating_gap", "").upper()
            if not rating_gap:
                # Heuristic: low lines suggest mismatch
                if line <= 19.5 or (line > 33.5 and line <= 32.5):
                    rating_gap = "LARGE"
                else:
                    rating_gap = "EVEN"
            
            match = MatchInput(
                player_1=row["player_1"],
                player_2=row["player_2"],
                total_games_line=line,
                tournament=row.get("tournament", ""),
                surface=row.get("surface", ""),
                date=row.get("date", ""),
                rating_gap=rating_gap,
            )
            matches.append(match)
    return matches


def write_csv(results: list, output_path: str):
    """Write results to CSV."""
    if not results:
        print("No results to write.")
        return
    
    fieldnames = list(results[0].to_dict().keys())
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(r.to_dict())


def print_report(results: list):
    """Print formatted console report."""
    approved, blocked = split_by_governance(results)
    
    print("\n" + "=" * 75)
    print("TOTAL GAMES ENGINE — BATCH RESULTS")
    print("=" * 75)
    print(f"Processed: {len(results)} | Approved: {len(approved)} | Blocked: {len(blocked)}")
    print("-" * 75)
    
    # Sort approved by absolute delta (strongest edge first)
    approved_sorted = sorted(approved, key=lambda x: abs(x[0].delta or 0), reverse=True)
    
    # Split by direction
    overs = [(r, rsn) for r, rsn in approved_sorted if r.direction == "OVER"]
    unders = [(r, rsn) for r, rsn in approved_sorted if r.direction == "UNDER"]
    
    if overs:
        print("\n[OVERS]")
        print(f"{'MATCH':<45} | {'LINE':>5} | {'EXP':>5} | {'Δ':>6} | {'CONF':<8} | {'FMT':<3}")
        print("-" * 85)
        for r, rsn in overs[:10]:
            match_str = f"{r.player_1} vs {r.player_2}"[:45]
            print(f"{match_str:<45} | {r.total_games_line:>5.1f} | {r.expected_games:>5.1f} | {r.delta:>+6.1f} | {r.confidence:<8} | {r.format:<3}")
    
    if unders:
        print("\n[UNDERS]")
        print(f"{'MATCH':<45} | {'LINE':>5} | {'EXP':>5} | {'Δ':>6} | {'CONF':<8} | {'FMT':<3}")
        print("-" * 85)
        for r, rsn in unders[:10]:
            match_str = f"{r.player_1} vs {r.player_2}"[:45]
            print(f"{match_str:<45} | {r.total_games_line:>5.1f} | {r.expected_games:>5.1f} | {r.delta:>+6.1f} | {r.confidence:<8} | {r.format:<3}")
    
    if not overs and not unders:
        print("\n(No approved plays)")
    
    if blocked:
        print(f"\n[BLOCKED: {len(blocked)}]")
        for r, rsn in blocked[:5]:
            match_str = f"{r.player_1} vs {r.player_2}"[:45]
            print(f"  {match_str}: {rsn}")
        if len(blocked) > 5:
            print(f"  ... and {len(blocked) - 5} more")
    
    print("=" * 75)


def main():
    parser = argparse.ArgumentParser(description="Total Games Engine — Batch Processor")
    parser.add_argument("--input", required=True, help="Input CSV file")
    parser.add_argument("--output", help="Output CSV file (optional)")
    parser.add_argument("--surface", help="Override surface for all matches (HARD/CLAY/GRASS/INDOOR)")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of report")
    
    args = parser.parse_args()
    
    # Parse input
    matches = parse_csv(args.input)
    
    if not matches:
        print("No matches found in input file.")
        return 1
    
    # Process matches
    results = []
    for m in matches:
        # Resolve surface: CLI override > CSV column > tournament lookup
        surface = args.surface or m.surface or resolve_surface(m.tournament)
        result = process_match(m, surface)
        results.append(result)
    
    # Output
    if args.output:
        write_csv(results, args.output)
        print(f"Results written to: {args.output}")
    
    if args.json:
        output = {
            "engine": "TOTAL_GAMES_ENGINE_v1",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "total": len(results),
            "results": [r.to_dict() for r in results],
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(results)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
