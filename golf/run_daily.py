"""
Golf Daily Pipeline
====================
Single entry point for full golf analysis.

Usage:
    python golf/run_daily.py
    python golf/run_daily.py --dry-run
    python golf/run_daily.py --slate inputs/slate.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Fix Windows console encoding for emojis
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# --- UNIVERSAL PROJECT ROOT IMPORT PATCH ---
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

GOLF_DIR = Path(__file__).parent
INPUTS_DIR = GOLF_DIR / "inputs"
OUTPUTS_DIR = GOLF_DIR / "outputs"
DATA_DIR = GOLF_DIR / "data"

# Ensure directories exist
for d in [INPUTS_DIR, OUTPUTS_DIR, DATA_DIR]:
    d.mkdir(exist_ok=True)

from golf.config import GOLF_REGISTRY, GOLF_THRESHOLDS
from golf.ingest.underdog_parser import parse_underdog_golf_slate, load_slate_from_file
from golf.ingest.prizepicks_parser import parse_prizepicks_slate
from golf.engines.generate_edges import (
    generate_all_edges,
    filter_edges_by_tier,
    filter_edges_optimizable,
    save_edges,
    GolfEdge,
)
from golf.engines.golf_monte_carlo import GolfMonteCarloSimulator


def clear_outputs():
    """Clear previous outputs (safety)."""
    for f in OUTPUTS_DIR.glob("golf_*.json"):
        if "backup" not in f.name:
            try:
                f.unlink()
            except:
                pass


def load_slate_files() -> Optional[Path]:
    """Detect and load available input files."""
    today = datetime.now().strftime("%Y%m%d")
    
    candidates = [
        INPUTS_DIR / f"slate_{today}.txt",
        INPUTS_DIR / "slate.txt",
        INPUTS_DIR / f"underdog_{today}.txt",
        INPUTS_DIR / "underdog.txt",
    ]
    
    for f in candidates:
        if f.exists():
            return f
    
    return None


def load_player_database() -> int:
    """Load player statistics database and return count."""
    try:
        from golf.data.player_database import get_player_database
        db = get_player_database()
        return len(db)
    except ImportError:
        return 0


def enrich_edges_with_mc(edges: List[GolfEdge]) -> List[GolfEdge]:
    """Enrich edges with Monte Carlo simulation results."""
    sim = GolfMonteCarloSimulator(iterations=10000, seed=42)
    
    for edge in edges:
        if edge.market == "round_strokes":
            player_avg = edge.player_avg or 71.0
            player_std = edge.player_stddev or 3.0
            
            result = sim.simulate_round_score(
                player_avg=player_avg,
                player_stddev=player_std,
                lines=[edge.line]
            )
            
            if edge.direction == "higher":
                edge.probability = result.prob_over.get(edge.line, 0.50)
            else:
                edge.probability = result.prob_under.get(edge.line, 0.50)
        
        elif edge.market == "birdies":
            avg_birdies = edge.player_avg or 4.0
            
            result = sim.simulate_birdies(
                avg_birdies=avg_birdies,
                lines=[edge.line]
            )
            
            if edge.direction == "higher":
                edge.probability = result.prob_over.get(edge.line, 0.50)
            else:
                edge.probability = result.prob_under.get(edge.line, 0.50)
        
        elif edge.market == "finishing_position":
            expected_finish = edge.player_avg or edge.line
            
            result = sim.simulate_tournament_finish(
                expected_finish=expected_finish,
                lines=[edge.line]
            )
            
            # "better" = lower position number
            if edge.direction == "better":
                edge.probability = result.prob_under.get(edge.line, 0.50)
            else:
                edge.probability = result.prob_over.get(edge.line, 0.50)
    
    return edges


def generate_report(edges: List[GolfEdge], tournament: str) -> str:
    """Generate human-readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"⛳ GOLF ANALYSIS REPORT — {tournament}")
    lines.append(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    
    # Summary
    optimizable = [e for e in edges if e.pick_state == "OPTIMIZABLE"]
    vetted = [e for e in edges if e.pick_state == "VETTED"]
    rejected = [e for e in edges if e.pick_state == "REJECTED"]
    strong = [e for e in edges if e.tier == "STRONG"]
    lean = [e for e in edges if e.tier == "LEAN"]
    
    lines.append(f"\n📊 SUMMARY")
    lines.append(f"   Total Props: {len(edges)}")
    lines.append(f"   Optimizable: {len(optimizable)}")
    lines.append(f"   STRONG Tier: {len(strong)}")
    lines.append(f"   LEAN Tier: {len(lean)}")
    lines.append(f"   Vetted: {len(vetted)}")
    lines.append(f"   Rejected: {len(rejected)}")
    
    # Top Picks
    lines.append(f"\n{'='*60}")
    lines.append("🎯 TOP PICKS (OPTIMIZABLE)")
    lines.append("=" * 60)
    
    sorted_edges = sorted(optimizable, key=lambda e: e.probability, reverse=True)
    
    from ai_commentary import generate_pick_commentary
    from add_quick_analysis import generate_analysis
    from add_deepseek_analysis import call_deepseek, generate_analysis_prompt
    for edge in sorted_edges[:15]:
        lines.append(f"\n⛳ {edge.player}")
        lines.append(f"   {edge.market.replace('_', ' ').title()}: {edge.line} {edge.direction.upper()}")
        lines.append(f"   Probability: {edge.probability:.1%} | Tier: {edge.tier}")
        if edge.higher_mult or edge.lower_mult:
            mult = edge.higher_mult if edge.direction == "higher" else edge.lower_mult
            if mult:
                lines.append(f"   Multiplier: {mult}x")
        if edge.player_avg:
            lines.append(f"   Player Avg: {edge.player_avg:.1f}")
        # AI Math Commentary
        try:
            math_comment = generate_pick_commentary(edge.to_dict())
            lines.append(f"   [AI Math] {math_comment}")
        except Exception as ex:
            lines.append(f"   [AI Math] Commentary unavailable: {ex}")
        # Quick Analysis Commentary
        try:
            quick_comment = generate_analysis(edge.to_dict())
            lines.append(f"   [Quick Analysis] {quick_comment}")
        except Exception as ex:
            lines.append(f"   [Quick Analysis] Commentary unavailable: {ex}")
        # DeepSeek AI Commentary
        try:
            prompt = generate_analysis_prompt(edge.to_dict())
            deepseek_comment = call_deepseek(prompt, max_tokens=60)
            lines.append(f"   [DeepSeek AI] {deepseek_comment}")
        except Exception as ex:
            lines.append(f"   [DeepSeek AI] Commentary unavailable: {ex}")
    
    # All edges by player
    lines.append(f"\n{'='*60}")
    lines.append("📋 ALL EDGES BY PLAYER")
    lines.append("=" * 60)
    
    players = sorted(set(e.player for e in edges))
    for player in players:
        player_edges = [e for e in edges if e.player == player]
        lines.append(f"\n{player}")
        for edge in player_edges:
            state_icon = "✓" if edge.pick_state == "OPTIMIZABLE" else "○"
            lines.append(f"  {state_icon} {edge.market}: {edge.line} {edge.direction} → {edge.probability:.1%} [{edge.tier}]")
            # AI Math Commentary
            try:
                math_comment = generate_pick_commentary(edge.to_dict())
                lines.append(f"    [AI Math] {math_comment}")
            except Exception as ex:
                lines.append(f"    [AI Math] Commentary unavailable: {ex}")
            # Quick Analysis Commentary
            try:
                quick_comment = generate_analysis(edge.to_dict())
                lines.append(f"    [Quick Analysis] {quick_comment}")
            except Exception as ex:
                lines.append(f"    [Quick Analysis] Commentary unavailable: {ex}")
            # DeepSeek AI Commentary
            try:
                prompt = generate_analysis_prompt(edge.to_dict())
                deepseek_comment = call_deepseek(prompt, max_tokens=60)
                lines.append(f"    [DeepSeek AI] {deepseek_comment}")
            except Exception as ex:
                lines.append(f"    [DeepSeek AI] Commentary unavailable: {ex}")
    
    # VETTED section - viable props excluded from optimization
    if vetted:
        lines.append(f"\n{'='*60}")
        lines.append(f"⚠️  VETTED PICKS ({len(vetted)}) — Context Only")
        lines.append("=" * 60)
        lines.append("   Viable props excluded from optimization due to data quality")
        lines.append("")
        
        # Group by avoid_reason
        reason_map = {
            "unverified_player": "⚠️ UNVERIFIED PLAYER DATA",
            "high_variance_market": "⚠️ HIGH VARIANCE MARKET",
            "missing_sg_data": "⚠️ MISSING SG DATA",
        }
        
        for reason_key, reason_label in reason_map.items():
            reason_edges = [e for e in vetted if e.avoid_reason == reason_key]
            if reason_edges:
                lines.append(f"   [{reason_label}]")
                for edge in sorted(reason_edges, key=lambda e: e.probability, reverse=True):
                    lines.append(f"   {edge.player} — {edge.market.replace('_', ' ').title()} {edge.line} {edge.direction.upper()}")
                    lines.append(f"   {edge.probability:.1%} | {edge.tier}")
                    if edge.player_avg:
                        lines.append(f"   Avg: {edge.player_avg:.1f}")
                    lines.append("")
    
    # REJECTED section - low confidence picks
    if rejected:
        lines.append(f"\n{'='*60}")
        lines.append(f"🚫 REJECTED PICKS ({len(rejected)}) — Below Threshold")
        lines.append("=" * 60)
        lines.append("   Props below minimum confidence threshold")
        lines.append("")
        
        # Group by avoid_reason
        low_conf = [e for e in rejected if e.avoid_reason == "low_confidence"]
        tier_threshold = [e for e in rejected if e.avoid_reason == "tier_threshold"]
        
        if low_conf:
            lines.append(f"   [Low Confidence]")
            for edge in sorted(low_conf, key=lambda e: e.probability, reverse=True)[:10]:
                lines.append(f"   {edge.player} — {edge.market.replace('_', ' ').title()} {edge.line} {edge.direction.upper()}")
                lines.append(f"   {edge.probability:.1%} — Too low for consideration")
            if len(low_conf) > 10:
                lines.append(f"   ... and {len(low_conf) - 10} more")
            lines.append("")
        
        if tier_threshold:
            lines.append(f"   [Below Tier Threshold]")
            for edge in sorted(tier_threshold, key=lambda e: e.probability, reverse=True)[:10]:
                lines.append(f"   {edge.player} — {edge.market.replace('_', ' ').title()} {edge.line} {edge.direction.upper()}")
                lines.append(f"   {edge.probability:.1%} | {edge.tier}")
            if len(tier_threshold) > 10:
                lines.append(f"   ... and {len(tier_threshold) - 10} more")
            lines.append("")
    
    return "\n".join(lines)


def run_daily_pipeline(
    slate_file: Optional[Path] = None,
    dry_run: bool = False,
    min_tier: str = "LEAN",
) -> Dict:
    """
    Run the full golf daily pipeline.
    
    Args:
        slate_file: Path to slate file (auto-detect if None)
        dry_run: If True, don't write output files
        min_tier: Minimum tier to include in output
        
    Returns:
        Pipeline result summary
    """
    print("=" * 60)
    print(f"⛳ GOLF DAILY PIPELINE — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"   Status: {GOLF_REGISTRY['status']}")
    print("=" * 60)
    
    result = {
        "date": datetime.now().isoformat(),
        "status": "PENDING",
        "props_parsed": 0,
        "edges_generated": 0,
        "edges_optimizable": 0,
        "output_files": [],
    }
    
    try:
        # Step 1: Load slate
        print("\n[1/5] Loading slate...")
        
        if slate_file is None:
            slate_file = load_slate_files()
        
        if slate_file is None:
            print("      ⚠️  No slate file found")
            print("      Create: golf/inputs/slate.txt with Underdog/PrizePicks paste")
            
            # Check for clipboard/stdin input
            print("\n      Or paste props now (Ctrl+Z when done):")
            try:
                import sys
                if not sys.stdin.isatty():
                    text = sys.stdin.read()
                    # Try PrizePicks format first, fallback to Underdog
                    props = parse_prizepicks_slate(text)
                    if not props:
                        props = parse_underdog_golf_slate(text)
                else:
                    result["status"] = "NO_SLATE"
                    return result
            except:
                result["status"] = "NO_SLATE"
                return result
        else:
            # Load and parse file - try both formats
            with open(slate_file) as f:
                text = f.read()
            
            # Try PrizePicks format first (more common)
            props = parse_prizepicks_slate(text)
            if not props:
                props = parse_underdog_golf_slate(text)
            
            print(f"      ✓ Loaded {len(props)} props from {slate_file.name}")
        
        result["props_parsed"] = len(props)
        
        if not props:
            print("      [ABORT] No props parsed")
            result["status"] = "NO_PROPS"
            return result
        
        # Step 2: Load player database
        print("\n[2/5] Loading player database...")
        player_count = load_player_database()
        print(f"      ✓ {player_count} players in database")
        
        # Step 3: Generate edges
        print("\n[3/5] Generating edges...")
        edges = generate_all_edges(props)
        print(f"      ✓ Generated {len(edges)} raw edges")
        
        # Step 4: Monte Carlo enrichment
        print("\n[4/5] Running Monte Carlo simulations...")
        edges = enrich_edges_with_mc(edges)
        
        # Re-assign tiers after MC
        from golf.engines.generate_edges import assign_tier, determine_pick_state
        for edge in edges:
            edge.tier = assign_tier(edge.probability, edge.market)
            edge.pick_state, edge.avoid_reason = determine_pick_state(edge)
        
        optimizable = [e for e in edges if e.pick_state == "OPTIMIZABLE"]
        print(f"      ✓ {len(optimizable)} edges OPTIMIZABLE")
        
        result["edges_generated"] = len(edges)
        result["edges_optimizable"] = len(optimizable)
        
        # Step 5: Generate output
        print("\n[5/5] Generating output...")
        
        # UGO EXPORT: Convert to Universal Governance Object format
        try:
            from core.universal_governance_object import adapt_edge, Sport
            ugo_edges = []
            for edge in optimizable:
                try:
                    edge_dict = edge.to_dict() if hasattr(edge, 'to_dict') else edge.__dict__
                    ugo = adapt_edge(Sport.GOLF, edge_dict)
                    ugo_edges.append(ugo.to_dict())
                except Exception:
                    pass
            result["ugo_edges"] = ugo_edges
            result["ugo_count"] = len(ugo_edges)
            print(f"      ✓ UGO Export: {len(ugo_edges)} edges")
        except ImportError:
            pass
        
        # CROSS-SPORT DATABASE: Save top picks
        try:
            from engine.daily_picks_db import save_top_picks
            golf_edges = []
            for edge in optimizable:
                edge_dict = edge.to_dict() if hasattr(edge, 'to_dict') else edge.__dict__
                golf_edges.append({
                    "player": edge_dict.get("player", ""),
                    "stat": edge_dict.get("market", edge_dict.get("stat", "")),
                    "line": edge_dict.get("line", 0),
                    "direction": edge_dict.get("direction", ""),
                    "probability": edge_dict.get("probability", 0.5),
                    "tier": edge_dict.get("tier", "LEAN")
                })
            if golf_edges:
                save_top_picks(golf_edges, "Golf", top_n=5)
                print(f"      ✓ Cross-Sport DB: Saved top 5 Golf picks")
        except ImportError:
            pass
        except Exception as e:
            print(f"      ⚠️ Cross-Sport DB save failed: {e}")
        
        # Get tournament name
        tournament = props[0].get("tournament", "Unknown Tournament") if props else "Golf"
        
        # Generate report
        report = generate_report(edges, tournament)
        print(report)
        
        if not dry_run:
            # Save edges JSON
            today = datetime.now().strftime("%Y%m%d")
            edges_file = OUTPUTS_DIR / f"golf_edges_{today}.json"
            save_edges(edges, edges_file)
            result["output_files"].append(str(edges_file))
            
            # Save report (use UTF-8 encoding for emojis)
            report_file = OUTPUTS_DIR / f"golf_report_{today}.txt"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)
            result["output_files"].append(str(report_file))
            
            print(f"\n      ✓ Saved {len(result['output_files'])} files")
        else:
            print("\n      [DRY RUN] Skipping file output")
        
        result["status"] = "SUCCESS"
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        result["status"] = "ERROR"
        result["error"] = str(e)
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"Pipeline complete: {result['status']}")
    print(f"{'='*60}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Golf Daily Pipeline")
    parser.add_argument("--slate", type=str, help="Path to slate file")
    parser.add_argument("--dry-run", action="store_true", help="Don't write output")
    parser.add_argument("--min-tier", type=str, default="LEAN", help="Minimum tier")
    
    args = parser.parse_args()
    
    slate_file = Path(args.slate) if args.slate else None
    
    result = run_daily_pipeline(
        slate_file=slate_file,
        dry_run=args.dry_run,
        min_tier=args.min_tier,
    )
    
    return 0 if result["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
