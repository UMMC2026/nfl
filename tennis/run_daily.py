"""
Tennis Daily Run — Autonomous Execution
========================================
Single entry point for full tennis pipeline.
Cron-safe. Gate-enforced. No human required.

Usage:
    python tennis/run_daily.py
    python tennis/run_daily.py --no-telegram
    python tennis/run_daily.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# --- UNIVERSAL PROJECT ROOT IMPORT PATCH ---
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
TENNIS_DIR = Path(__file__).resolve().parent
# Tennis dir MUST be index-0 so tennis-local packages (render, engines, etc.)
# shadow identically-named packages at project root.  Python auto-inserts the
# script directory, but _PROJECT_ROOT insert above may push it to [1].
_tennis_str = str(TENNIS_DIR)
if sys.path[0] != _tennis_str:
    # Remove existing entry (if any) and force to front
    try:
        sys.path.remove(_tennis_str)
    except ValueError:
        pass
    sys.path.insert(0, _tennis_str)

from ingest.ingest_tennis import (
    load_global_config,
    load_player_stats,
)
from engines.generate_totals_sets_edges import (
    generate_all_edges as generate_sets_edges,
    parse_csv_file as parse_sets_csv,
)
from engines.generate_totals_games_edges import (
    generate_all_edges as generate_games_edges,
    parse_paste_file as parse_games_paste,
)
from engines.generate_player_aces_edges import (
    generate_all_edges as generate_aces_edges,
    parse_csv_file as parse_aces_csv,
)
from validate.validate_tennis_output import validate_merged_output
from render.render_report import render_report

INPUTS_DIR = TENNIS_DIR / "inputs"
OUTPUTS_DIR = TENNIS_DIR / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


def clear_outputs():
    """Clear previous day's outputs (safety)."""
    for f in OUTPUTS_DIR.glob("tennis_*.json"):
        if "backup" not in f.name:
            f.unlink()


def load_slate_files():
    """Detect and load available input files."""
    files = {
        "games_paste": None,
        "sets_csv": None,
        "aces_csv": None,
    }
    
    # Check for today's files first, then defaults
    today = datetime.now().strftime("%Y%m%d")
    
    games_candidates = [
        INPUTS_DIR / f"games_paste_{today}.txt",
        INPUTS_DIR / "games_paste.txt",
    ]
    for f in games_candidates:
        if f.exists():
            files["games_paste"] = f
            break
    
    sets_candidates = [
        INPUTS_DIR / f"sets_slate_{today}.csv",
        INPUTS_DIR / "sets_slate.csv",
    ]
    for f in sets_candidates:
        if f.exists():
            files["sets_csv"] = f
            break
    
    aces_candidates = [
        INPUTS_DIR / f"aces_slate_{today}.csv",
        INPUTS_DIR / "aces_slate.csv",
    ]
    for f in aces_candidates:
        if f.exists():
            files["aces_csv"] = f
            break
    
    return files


def run_engines(files: dict, config: dict) -> dict:
    """Run all three engines and merge output."""
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    merged = {
        "generated_at": timestamp,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "engines": {},
    }
    
    max_plays = {
        "TOTAL_SETS": 2,
        "TOTAL_GAMES": 2,
        "PLAYER_ACES": 1,
    }
    
    # TOTAL SETS ENGINE (Primary)
    if files["sets_csv"]:
        print("[ENGINE] TOTAL_SETS — Running...")
        candidates = parse_sets_csv(str(files["sets_csv"]))
        output = generate_sets_edges(candidates, max_plays["TOTAL_SETS"])
        merged["engines"]["TOTAL_SETS_ENGINE"] = output
        print(f"         Playable: {output['playable_count']} | Blocked: {output['blocked_count']}")
    
    # PLAYER ACES ENGINE (Selective)
    if files["aces_csv"]:
        print("[ENGINE] PLAYER_ACES — Running...")
        candidates = parse_aces_csv(str(files["aces_csv"]))
        output = generate_aces_edges(candidates, max_plays["PLAYER_ACES"])
        merged["engines"]["PLAYER_ACES_ENGINE"] = output
        print(f"         Playable: {output['playable_count']} | Blocked: {output['blocked_count']}")
    
    # TOTAL GAMES ENGINE (Secondary)
    if files["games_paste"]:
        print("[ENGINE] TOTAL_GAMES — Running...")
        # Detect surface from config or default
        surface = config.get("default_surface", "HARD")
        tournament = config.get("default_tournament", "")
        candidates = parse_games_paste(str(files["games_paste"]), surface, tournament)
        output = generate_games_edges(candidates, max_plays["TOTAL_GAMES"])
        merged["engines"]["TOTAL_GAMES_ENGINE"] = output
        print(f"         Playable: {output['playable_count']} | Blocked: {output['blocked_count']}")
    
    return merged


def extract_final_plays(merged: dict) -> list:
    """Extract validated plays from merged output."""
    plays = []
    
    for engine_name, engine_data in merged.get("engines", {}).items():
        for edge in engine_data.get("edges", []):
            if edge.get("tier") in ("STRONG", "LEAN"):
                plays.append(edge)
    
    # Sort by probability descending
    plays.sort(key=lambda x: x.get("probability", 0), reverse=True)
    
    return plays


def main():
    parser = argparse.ArgumentParser(description="Tennis Daily Run")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram delivery")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no output")
    parser.add_argument("--surface", default="HARD", help="Default surface")
    parser.add_argument("--tournament", default="", help="Tournament name")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TENNIS DAILY RUN")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Load config
    config = load_global_config()
    config["default_surface"] = args.surface
    config["default_tournament"] = args.tournament
    
    # Clear old outputs
    if not args.dry_run:
        clear_outputs()
    
    # Detect input files
    files = load_slate_files()
    active = sum(1 for v in files.values() if v)
    
    if active == 0:
        print("\n❌ No input files found in tennis/inputs/")
        print("   Expected: games_paste.txt, sets_slate.csv, or aces_slate.csv")
        return 1
    
    print(f"\n[INPUT] Found {active} slate file(s)")
    for k, v in files.items():
        if v:
            print(f"         {k}: {v.name}")
    
    # Run engines
    print("\n" + "-" * 60)
    merged = run_engines(files, config)
    
    if not merged["engines"]:
        print("\n❌ No engines produced output")
        return 1
    
    # DIRECTION GATE (FUOOM bias protection)
    print("\n" + "-" * 60)
    print("[GATE] Direction Bias Check...")
    
    # Import gate
    import sys
    from pathlib import Path
    tennis_dir = Path(__file__).parent
    if str(tennis_dir) not in sys.path:
        sys.path.insert(0, str(tennis_dir))
    from direction_gate import apply_direction_gate
    
    # Extract all edges from all engines
    all_edges = []
    for engine_name, engine_data in merged.get("engines", {}).items():
        all_edges.extend(engine_data.get("edges", []))
    
    # Only pass PLAYABLE edges to direction gate (exclude NO_PLAY)
    playable_tiers = {"SLAM", "STRONG", "LEAN"}
    playable_edges = [e for e in all_edges if e.get("tier", "").upper() in playable_tiers]
    
    # Detect if source props are all same direction (platform constraint)
    prop_directions = set(e.get("direction", "").upper() for e in all_edges if e.get("direction"))
    source_all_same = len(prop_directions) == 1
    
    # Apply direction gate
    filtered_edges = apply_direction_gate(
        playable_edges if playable_edges else all_edges,
        context={},
        source_all_same_direction=source_all_same
    )
    if not filtered_edges:
        print("\n⛔ DIRECTION GATE FAILED — Slate shows structural bias")
        print("   Aborting to prevent betting into model weakness")
        return 1
    print(f"       ✓ Direction Gate PASSED ({len(filtered_edges)} edges)")
    
    # Update merged output with filtered edges
    # Redistribute edges back to their engines
    edge_map = {id(e): e for e in filtered_edges}
    for engine_name, engine_data in merged.get("engines", {}).items():
        original_edges = engine_data.get("edges", [])
        engine_data["edges"] = [e for e in original_edges if id(e) in edge_map]
        engine_data["playable_count"] = len(engine_data["edges"])
    
    # VALIDATION GATE (HARD STOP)
    print("\n" + "-" * 60)
    print("[GATE] Validation...")
    
    passed, errors, summary = validate_merged_output(merged)
    
    if not passed:
        print("\n❌ VALIDATION FAILED — ABORTING")
        for err in errors[:10]:
            print(f"   • {err}")
        return 1
    
    print(f"       ✅ PASSED | Plays: {summary['playable_count']} | Errors: 0")
    
    # Extract final plays
    plays = extract_final_plays(merged)
    
    if not plays:
        print("\n⚠️ No playable edges after validation")
        return 0
    
    # AI REPORT: Top-20 Tennis picks (math-only, no LLM speculation)
    try:
        from ai_commentary import generate_top20_report

        analysis_results = {"sport": "TENNIS", "results": plays}
        top20_report = generate_top20_report(analysis_results, game_context=None, top_n=20)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        ai_path = OUTPUTS_DIR / f"tennis_TOP20_AI_REPORT_{ts}.txt"
        ai_path.write_text(top20_report, encoding="utf-8")
        print(f"       ✓ AI Top-20 report: {ai_path.name}")
    except ImportError:
        pass
    except Exception as e:
        print(f"       ⚠️ AI Top-20 report failed: {e}")

    # CROSS-SPORT DATABASE: Save top picks
    try:
        from engine.daily_picks_db import save_top_picks
        tennis_edges = []
        for edge in plays:
            tennis_edges.append({
                "player": edge.get("match", edge.get("player1", "") + " vs " + edge.get("player2", "")),
                "stat": edge.get("market", edge.get("type", "")),
                "line": edge.get("line", 0),
                "direction": edge.get("direction", ""),
                "probability": edge.get("probability", 0.5),
                "tier": edge.get("tier", "LEAN")
            })
        if tennis_edges:
            save_top_picks(tennis_edges, "Tennis", top_n=5)
            print(f"       ✓ Cross-Sport DB: Saved top 5 Tennis picks")
    except ImportError:
        pass
    except Exception as e:
        print(f"       ⚠️ Cross-Sport DB save failed: {e}")
    
    # UGO EXPORT: Convert to Universal Governance Object format
    try:
        from core.universal_governance_object import adapt_edge, Sport
        ugo_edges = []
        for edge in plays:
            try:
                ugo = adapt_edge(Sport.TENNIS, edge)
                ugo_edges.append(ugo.to_dict())
            except Exception:
                pass
        merged["ugo_edges"] = ugo_edges
        merged["ugo_count"] = len(ugo_edges)
        print(f"       ✓ UGO Export: {len(ugo_edges)} edges")
    except ImportError:
        pass
    
    # Save output
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    
    if not args.dry_run:
        # Full merged output
        merged_path = OUTPUTS_DIR / f"tennis_merged_{ts}.json"
        merged_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        
        # Final plays only
        plays_path = OUTPUTS_DIR / f"tennis_plays_{ts}.json"
        plays_path.write_text(json.dumps(plays, indent=2), encoding="utf-8")
        
        # Symlink for latest
        latest = OUTPUTS_DIR / "tennis_plays_latest.json"
        if latest.exists():
            latest.unlink()
        plays_path_rel = plays_path.name
        # Windows doesn't support symlinks easily, just copy
        latest.write_text(json.dumps(plays, indent=2), encoding="utf-8")
        
        print(f"\n[OUTPUT] {merged_path.name}")
        print(f"[OUTPUT] {plays_path.name}")
    
    # Render report
    print("\n" + "-" * 60)
    report = render_report(merged, "text")
    print(report)
    
    # Telegram delivery
    if not args.no_telegram and not args.dry_run:
        try:
            from telegram.send import send_telegram
            print("\n[TELEGRAM] Sending...")
            send_telegram(plays)
            print("           ✅ Delivered")
        except ImportError:
            print("\n[TELEGRAM] Module not configured, skipping")
        except Exception as e:
            print(f"\n[TELEGRAM] Failed: {e}")
    
    print("\n" + "=" * 60)
    print("RUN COMPLETE")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
