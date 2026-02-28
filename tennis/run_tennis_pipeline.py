"""
Tennis Run Pipeline — Orchestrator
===================================
Runs all three engines → merges → validates → renders.

Single command execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TENNIS_DIR = Path(__file__).parent
sys.path.insert(0, str(TENNIS_DIR))

from engines.generate_totals_games_edges import (
    generate_all_edges as generate_totals_games,
    TotalGamesCandidate,
    parse_paste_file as parse_games_paste,
)
from engines.generate_totals_sets_edges import (
    generate_all_edges as generate_totals_sets,
    TotalSetsCandidate,
    parse_csv_file as parse_sets_csv,
)
from engines.generate_player_aces_edges import (
    generate_all_edges as generate_player_aces,
    PlayerAcesCandidate,
    parse_csv_file as parse_aces_csv,
)
from validate.validate_tennis_output import validate_merged_output
from render.render_report import render_report

OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def run_full_pipeline(
    games_paste_file: str = None,
    games_surface: str = "HARD",
    games_tournament: str = "",
    sets_csv: str = None,
    aces_csv: str = None,
    max_plays_per_engine: Dict[str, int] = None,
    output_format: str = "text",
) -> int:
    """
    Run full tennis pipeline.
    
    Returns exit code (0 = success, 1 = validation failure).
    """
    if max_plays_per_engine is None:
        max_plays_per_engine = {
            "TOTAL_GAMES": 2,
            "TOTAL_SETS": 2,
            "PLAYER_ACES": 1,
        }
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    ts_short = datetime.now().strftime("%Y%m%d_%H%M")
    
    merged = {
        "generated_at": timestamp,
        "engines": {},
    }
    
    # -------------------------------------------------------------------------
    # TOTAL GAMES ENGINE
    # -------------------------------------------------------------------------
    if games_paste_file:
        print(f"[1/3] Running TOTAL_GAMES engine...")
        candidates = parse_games_paste(games_paste_file, games_surface, games_tournament)
        print(f"      Parsed {len(candidates)} candidates")
        
        output = generate_totals_games(candidates, max_plays_per_engine.get("TOTAL_GAMES", 2))
        merged["engines"]["TOTAL_GAMES_ENGINE"] = output
        
        print(f"      Playable: {output['playable_count']} | Blocked: {output['blocked_count']}")
    else:
        print("[1/3] TOTAL_GAMES: No input file, skipping")
    
    # -------------------------------------------------------------------------
    # TOTAL SETS ENGINE
    # -------------------------------------------------------------------------
    if sets_csv and Path(sets_csv).exists():
        print(f"[2/3] Running TOTAL_SETS engine...")
        candidates = parse_sets_csv(sets_csv)
        print(f"      Parsed {len(candidates)} candidates")
        
        output = generate_totals_sets(candidates, max_plays_per_engine.get("TOTAL_SETS", 2))
        merged["engines"]["TOTAL_SETS_ENGINE"] = output
        
        print(f"      Playable: {output['playable_count']} | Blocked: {output['blocked_count']}")
    else:
        print("[2/3] TOTAL_SETS: No input file, skipping")
    
    # -------------------------------------------------------------------------
    # PLAYER ACES ENGINE
    # -------------------------------------------------------------------------
    if aces_csv and Path(aces_csv).exists():
        print(f"[3/3] Running PLAYER_ACES engine...")
        candidates = parse_aces_csv(aces_csv)
        print(f"      Parsed {len(candidates)} candidates")
        
        output = generate_player_aces(candidates, max_plays_per_engine.get("PLAYER_ACES", 1))
        merged["engines"]["PLAYER_ACES_ENGINE"] = output
        
        print(f"      Playable: {output['playable_count']} | Blocked: {output['blocked_count']}")
    else:
        print("[3/3] PLAYER_ACES: No input file, skipping")
    
    # -------------------------------------------------------------------------
    # MERGE OUTPUT
    # -------------------------------------------------------------------------
    if not merged["engines"]:
        print("\n❌ No engines produced output. Nothing to validate.")
        return 1
    
    merged_path = OUTPUTS_DIR / f"tennis_merged_{ts_short}.json"
    merged_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"\nMerged output: {merged_path}")
    
    # -------------------------------------------------------------------------
    # VALIDATION GATE
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("VALIDATION GATE")
    print("=" * 60)
    
    passed, errors, summary = validate_merged_output(merged)
    
    print(f"Edges checked: {summary['edges_checked']}")
    print(f"Playable: {summary['playable_count']} | Blocked: {summary['blocked_count']}")
    print(f"Errors: {summary['error_count']}")
    
    if not passed:
        print("\n❌ VALIDATION FAILED")
        for err in errors[:10]:
            print(f"  • {err}")
        return 1
    
    print("\n✅ VALIDATION PASSED")
    
    # -------------------------------------------------------------------------
    # RENDER REPORT
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    
    report = render_report(merged, output_format)
    print(report)
    
    # Save report
    ext = {"text": "txt", "markdown": "md", "json": "json"}.get(output_format, "txt")
    report_path = OUTPUTS_DIR / f"tennis_report_{ts_short}.{ext}"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_path}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description="Tennis Pipeline Orchestrator")
    parser.add_argument("--games-paste", help="Total Games paste file")
    parser.add_argument("--games-surface", default="HARD", help="Surface for games paste")
    parser.add_argument("--games-tournament", default="", help="Tournament for games paste")
    parser.add_argument("--sets-csv", help="Total Sets CSV file")
    parser.add_argument("--aces-csv", help="Player Aces CSV file")
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    
    args = parser.parse_args()
    
    return run_full_pipeline(
        games_paste_file=args.games_paste,
        games_surface=args.games_surface,
        games_tournament=args.games_tournament,
        sets_csv=args.sets_csv,
        aces_csv=args.aces_csv,
        output_format=args.format,
    )


if __name__ == "__main__":
    raise SystemExit(main())
