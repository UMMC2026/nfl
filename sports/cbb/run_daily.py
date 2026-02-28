"""
CBB Daily Pipeline Runner

Entry point for running the full CBB pipeline.
STATUS: PRODUCTION (activated 2026-01-24)
"""
import argparse
from datetime import date
from pathlib import Path
import sys


# --- UNIVERSAL PROJECT ROOT IMPORT PATCH ---
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Preflight cache validation (auto-fix on contamination)
from tools.preflight_cache_validator import PreflightCacheValidator

def _preflight_cache_check():
    """Run preflight cache check and auto-fix contamination."""
    validator = PreflightCacheValidator(_PROJECT_ROOT)
    result = validator.validate("CBB", fix=False)
    
    if not result.passed:
        print("\n[WARN] [CBB] Cache contamination detected during preflight")
        for error in result.errors:
            print(f"   {error}")
        print("   Auto-fixing...")
        
        fix_result = validator.validate("CBB", fix=True)
        print(f"   Fixed {fix_result.fixed_count} contaminated keys")
        
        # Re-validate
        recheck = validator.validate("CBB", fix=False)
        if not recheck.passed:
            raise RuntimeError(
                "[CBB PREFLIGHT FAILED] Cache still contaminated after auto-fix. "
                "Manual intervention required: delete cache/cbb/ or sports/cbb/data/cache/"
            )
        print("   [OK] Cache is now clean")
    else:
        print("[OK] [CBB] Preflight cache check passed")

from sports.cbb.config import CBB_REGISTRY
from sports.cbb.ingest import fetch_schedule, ingest_player_stats
from sports.cbb.features import build_player_features
from sports.cbb.edges import generate_edges, collapse_edges, apply_cbb_edge_gates
from sports.cbb.models import compute_probability
from sports.cbb.validate import apply_render_gate, RenderGateError
from sports.cbb.render import generate_report, write_output


def run_daily_pipeline(
    target_date: str = None,
    dry_run: bool = False,
    conference_filter: str = None
) -> dict:
    """
    Run the full CBB daily pipeline.
    
    Args:
        target_date: Date to run for (defaults to today)
        dry_run: If True, don't write output files
        conference_filter: Optional conference to filter games
        
    Returns:
        Pipeline result summary
    """
    # Check if CBB is enabled
    if not CBB_REGISTRY["enabled"]:
        print(f"[ABORT] CBB is disabled (status: {CBB_REGISTRY['status']})")
        return {"status": "DISABLED", "reason": "CBB not enabled in registry"}
    
    # PREFLIGHT: Auto-fix cache contamination before proceeding
    _preflight_cache_check()
    
    if target_date is None:
        target_date = date.today().isoformat()
    
    print(f"=" * 60)
    print(f"CBB DAILY PIPELINE — {target_date}")
    print(f"Status: {CBB_REGISTRY['status']}")
    print(f"=" * 60)
    
    result = {
        "date": target_date,
        "status": "PENDING",
        "games": 0,
        "edges_generated": 0,
        "edges_primary": 0,
        "edges_blocked": 0,
        "output_files": [],
    }
    
    try:
        # Step 1: Fetch schedule
        print("\n[1/6] Fetching schedule...")
        games = fetch_schedule(target_date, conference_filter)
        result["games"] = len(games)
        print(f"      Found {len(games)} games")
        
        if not games:
            print("[ABORT] No games today")
            result["status"] = "NO_GAMES"
            return result
        

        # Step 2: Ingest player stats
        print("\n[2/6] Ingesting player stats...")
        from sports.cbb.ingest.player_stats import ingest_player_stats
        from sports.cbb.reporting.cbb_roster_averages import generate_cbb_roster_averages_report
        player_stats = ingest_player_stats(target_date)
        print(f"      Loaded stats for {len(player_stats)} players")

        # NBA-style roster averages report
        csv_path = f"data/cbb/raw/player_stats_{target_date.replace('-', '')}.csv"
        out_path = f"data/cbb/roster_averages_{target_date.replace('-', '')}.txt"
        try:
            generate_cbb_roster_averages_report(target_date, csv_path, out_path)
        except Exception as e:
            print(f"[WARN] Could not generate roster averages report: {e}")
        

        # Step 3: Build features (must include recent averages, line sanity, spread/context)
        print("\n[3/6] Building features...")
        player_features = build_player_features(player_stats)
        print(f"      Built features for {len(player_features)} players")

        # Step 4: Generate edges (all gates enforced in edge_gates.py)
        print("\n[4/6] Generating edges...")
        # Fetch lines (multi-source, robust echo/abort)
        from sports.cbb.ingest.lines import fetch_lines
        try:
            lines = fetch_lines(target_date)
        except Exception as e:
            print(f"[ABORT] Slate ingestion failed: {e}")
            result["status"] = "SLATE_INGEST_FAILED"
            result["error"] = str(e)
            return result
        # Compute probabilities
        probabilities = compute_probability(lines, player_features, player_stats)
        # Generate edges with all gates (recent avg, line sanity, spread/context) enforced
        edges = generate_edges(lines, player_features, games[0] if games else None, probabilities)
        print(f"      Generated {len(edges)} edges")
        
        # Step 5: Collapse edges
        print("\n[5/6] Collapsing edges...")
        edges = collapse_edges(edges)
        # --- Diagnostics/Validation ---
        from sports.cbb.validate.diagnostics import validate_cbb_edges
        edge_dicts = [e.to_dict() if hasattr(e, 'to_dict') else e.__dict__ for e in edges]
        valid_edges, blocked_edges, diagnostics = validate_cbb_edges(edge_dicts)
        print(f"      Diagnostics: {len(diagnostics)} issues found")
        for d in diagnostics:
            print(f"         [DIAG] {d}")
        # Rebuild edge objects for valid/blocked
        def find_edge(edict):
            for e in edges:
                if (hasattr(e, 'to_dict') and e.to_dict() == edict) or (not hasattr(e, 'to_dict') and e.__dict__ == edict):
                    return e
            return None
        valid_objs = [find_edge(ed) for ed in valid_edges if find_edge(ed)]
        blocked_objs = [find_edge(ed) for ed in blocked_edges if find_edge(ed)]
        primary = [e for e in valid_objs if getattr(e, 'is_primary', False) and not getattr(e, 'is_blocked', False)]
        blocked = blocked_objs
        result["edges_generated"] = len(edges)
        result["edges_primary"] = len(primary)
        result["edges_blocked"] = len(blocked)
        print(f"      Primary: {len(primary)}, Blocked: {len(blocked)}")
        # Step 6: Validate and render
        print("\n[6/6] Validating and rendering...")
        edges = apply_render_gate(valid_objs, target_date)
        
        # CROSS-SPORT DATABASE: Save top picks
        try:
            from engine.daily_picks_db import save_top_picks
            cbb_edges = []
            for edge in primary:
                edge_dict = edge.to_dict() if hasattr(edge, 'to_dict') else edge.__dict__
                cbb_edges.append({
                    "player": edge_dict.get("player", edge_dict.get("entity", "")),
                    "stat": edge_dict.get("stat", edge_dict.get("market", "")),
                    "line": edge_dict.get("line", 0),
                    "direction": edge_dict.get("direction", ""),
                    "probability": edge_dict.get("probability", 0.5),
                    "tier": edge_dict.get("tier", "LEAN")
                })
            if cbb_edges:
                save_top_picks(cbb_edges, "CBB", top_n=5)
                print(f"      ✓ Cross-Sport DB: Saved top 5 CBB picks")
        except ImportError:
            pass
        except Exception as e:
            print(f"      ⚠️ Cross-Sport DB save failed: {e}")
        
        # UGO EXPORT: Convert to Universal Governance Object format
        try:
            from core.universal_governance_object import adapt_edge, Sport
            ugo_edges = []
            for edge in primary:
                try:
                    edge_dict = edge.to_dict() if hasattr(edge, 'to_dict') else edge.__dict__
                    ugo = adapt_edge(Sport.CBB, edge_dict)
                    ugo_edges.append(ugo.to_dict())
                except Exception:
                    pass
            result["ugo_edges"] = ugo_edges
            result["ugo_count"] = len(ugo_edges)
            print(f"      ✓ UGO Export: {len(ugo_edges)} edges")
        except ImportError:
            pass
        
        report = generate_report(edges, target_date, games)
        
        if not dry_run:
            output_files = write_output(report)
            result["output_files"] = [str(p) for p in output_files.values()]
            print(f"      Wrote {len(output_files)} files")
        else:
            print("      [DRY RUN] Skipping file output")
        
        result["status"] = "SUCCESS"
        
    except RenderGateError as e:
        print(f"\n[RENDER GATE FAILED]\n{e}")
        result["status"] = "RENDER_GATE_FAILED"
        result["error"] = str(e)
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        result["status"] = "ERROR"
        result["error"] = str(e)
        raise
    
    print(f"\n{'=' * 60}")
    print(f"Pipeline complete: {result['status']}")
    print(f"{'=' * 60}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="CBB Daily Pipeline")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write output")
    parser.add_argument("--conference", type=str, help="Filter by conference")
    
    args = parser.parse_args()
    
    result = run_daily_pipeline(
        target_date=args.date,
        dry_run=args.dry_run,
        conference_filter=args.conference
    )
    
    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
