"""soccer/soccer_props_pipeline.py

Soccer Player Props Analysis Pipeline
=====================================
Orchestrates the full flow:
1. Load props from saved JSON
2. For each prop, check for cached stats or prompt user
3. Run Monte Carlo simulation
4. Apply gates and tier logic
5. Output RISK_FIRST JSON + text report

CRITICAL: This is MANUAL HYDRATION only.
- No scraping
- User provides stats via interactive prompts or JSON import
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

import sys
sys.path.insert(0, str(Path(__file__).parent))

from data.soccer_stats_api import SoccerPlayerStats, get_soccer_stats_store
from sim.soccer_props_monte_carlo import SoccerPropsMCEngine, SoccerMCResult, run_simulation_for_prop


# Tier thresholds (match project standards)
TIER_THRESHOLDS = {
    "SLAM": 0.75,    # ≥75% probability
    "STRONG": 0.65,  # ≥65%
    "LEAN": 0.55,    # ≥55%
}


@dataclass
class SoccerPropEdge:
    """A single prop edge after analysis."""
    
    edge_id: str
    player: str
    team: str
    opponent: str
    stat: str
    line: float
    direction: str  # "OVER" | "UNDER"
    probability: float
    tier: str       # "SLAM" | "STRONG" | "LEAN" | "NO_PLAY"
    confidence: str # "HIGH" | "MEDIUM" | "LOW" | "NO_DATA"
    edge: float
    mean: float
    std: float
    p50: float
    sample_size: int
    audit_hash: str
    data_sources: List[str]
    hydration_mode: str  # "cached" | "manual" | "missing"


def _compute_audit_hash(player: str, stat: str, line: float, direction: str) -> str:
    """Generate deterministic audit hash."""
    s = f"{player}|{stat}|{line}|{direction}"
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def _compute_tier(prob: float) -> str:
    """Determine tier based on probability."""
    if prob >= TIER_THRESHOLDS["SLAM"]:
        return "SLAM"
    elif prob >= TIER_THRESHOLDS["STRONG"]:
        return "STRONG"
    elif prob >= TIER_THRESHOLDS["LEAN"]:
        return "LEAN"
    else:
        return "NO_PLAY"


def load_props_slate(filepath: str) -> List[Dict]:
    """
    Load props from a saved JSON file (from paste ingest).
    
    Returns list of prop dicts with keys:
    - player, team, opponent, stat, line, position, matchup, badge, direction
    """
    with open(filepath) as f:
        data = json.load(f)
    return data.get("plays", [])


def analyze_props_slate(
    props: List[Dict],
    *,
    interactive: bool = True,
    num_sims: int = 10000,
    skip_all_missing: bool = False,
) -> List[SoccerPropEdge]:
    """
    Run Monte Carlo analysis on each prop.
    
    Args:
        props: List of prop dicts from paste ingest
        interactive: If True, prompt for missing stats
        num_sims: Number of MC simulations
    
    Returns:
        List of SoccerPropEdge with probabilities and tiers
    """
    store = get_soccer_stats_store()
    engine = SoccerPropsMCEngine(num_simulations=num_sims)
    
    edges: List[SoccerPropEdge] = []
    seen = set()  # Dedupe (player|stat|line|direction)
    
    for prop in props:
        player = prop.get("player", "")
        team = prop.get("team", "")
        opponent = prop.get("opponent", "")
        stat = prop.get("stat", "")
        line = float(prop.get("line", 0))
        position = prop.get("position", "Unknown")
        direction = prop.get("direction", "higher").upper()
        
        if direction in ("HIGHER", "MORE"):
            direction = "OVER"
        elif direction in ("LOWER", "LESS"):
            direction = "UNDER"
        
        # Dedupe key
        key = f"{player}|{stat}|{line}|{direction}"
        if key in seen:
            continue
        seen.add(key)
        
        # Try to get cached stats
        stats = store.get_player_stats(player, team)
        hydration_mode = "cached" if stats else "missing"
        
        # Interactive: prompt for stats if missing
        if stats is None and interactive and not skip_all_missing:
            print(f"\n⚠️  No stats cached for {player} ({team})")
            try:
                resp = input("Enter stats now? (y/n/A=skip all): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n⚠️ Input cancelled, skipping...")
                resp = "n"
            
            if resp == "y":
                stats = store.interactive_input(player, team, position, stat)
                hydration_mode = "manual"
            elif resp == "a":
                # Skip all remaining missing stats
                skip_all_missing = True
                print("   → Skipping all remaining missing stats...")
            # Empty input or 'n' or anything else = skip this player
        
        # Run simulation
        if stats:
            mc_result = engine.simulate_prop(stats, stat, line)
        else:
            # Use baseline estimates with position hint
            mc_result = run_simulation_for_prop(player, team, stat, line, stats=None, position=position)
            if mc_result.confidence == "BASELINE":
                hydration_mode = "baseline"
        
        # Pick probability based on direction
        if direction == "OVER":
            prob = mc_result.prob_over
        else:
            prob = mc_result.prob_under
        
        tier = _compute_tier(prob)
        audit_hash = _compute_audit_hash(player, stat, line, direction)
        
        edge = SoccerPropEdge(
            edge_id=f"soccer_prop_{audit_hash}",
            player=player,
            team=team,
            opponent=opponent,
            stat=stat,
            line=line,
            direction=direction,
            probability=prob,
            tier=tier,
            confidence=mc_result.confidence,
            edge=mc_result.edge if direction == "OVER" else -mc_result.edge,
            mean=mc_result.mean,
            std=mc_result.std,
            p50=mc_result.p50,
            sample_size=mc_result.sample_size,
            audit_hash=audit_hash,
            data_sources=["manual_input"] if hydration_mode == "manual" else (["cache"] if hydration_mode == "cached" else []),
            hydration_mode=hydration_mode,
        )
        edges.append(edge)
    
    return edges


def render_props_report(edges: List[SoccerPropEdge]) -> str:
    """Generate text report from edges."""
    lines = []
    lines.append("=" * 70)
    lines.append("[SOCCER] PLAYER PROPS ANALYSIS REPORT")
    lines.append(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"   Total props: {len(edges)}")
    
    # Count baseline vs real data
    baseline_count = sum(1 for e in edges if e.confidence == "BASELINE" or e.sample_size == 0)
    real_data_count = len(edges) - baseline_count
    
    if baseline_count > 0:
        lines.append("")
        lines.append("   ⚠️  WARNING: BASELINE ESTIMATES IN USE")
        lines.append(f"       {baseline_count}/{len(edges)} props have NO REAL PLAYER DATA")
        lines.append("       These use generic position averages (NOT ACTIONABLE)")
        if baseline_count == len(edges):
            lines.append("")
            lines.append("   ❌ ALL PICKS ARE BASELINE - CANNOT MAKE INFORMED DECISIONS")
            lines.append("      Run option [7] API FETCH or [5] MANUAL INPUT for real stats")
    
    lines.append("=" * 70)
    lines.append("")
    
    # Group by tier, but split BASELINE from real data
    real_actionable = [e for e in edges if e.tier in ("SLAM", "STRONG", "LEAN") and e.confidence != "BASELINE" and e.sample_size > 0]
    baseline_all = [e for e in edges if e.confidence == "BASELINE" or e.sample_size == 0]
    
    # SHOW REAL DATA FIRST (if any)
    if real_actionable:
        lines.append(f"\n{'='*70}")
        lines.append(f" ✅ ACTIONABLE PICKS (Real Player Data) — {len(real_actionable)} props")
        lines.append(f"{'='*70}")
        
        by_tier = {"SLAM": [], "STRONG": [], "LEAN": []}
        for e in real_actionable:
            by_tier.get(e.tier, []).append(e)
        
        for tier in ["SLAM", "STRONG", "LEAN"]:
            tier_edges = by_tier.get(tier, [])
            if tier_edges:
                lines.append(f"\n  [{tier}]")
                for e in sorted(tier_edges, key=lambda x: -x.probability):
                    dir_sym = "⬆️" if e.direction == "OVER" else "⬇️"
                    lines.append(
                        f"    {dir_sym} {e.player} ({e.team}) | {e.stat} {e.direction} {e.line} | "
                        f"p={e.probability*100:.1f}% | mean={e.mean:.2f} | n={e.sample_size}"
                    )
    else:
        lines.append(f"\n{'='*70}")
        lines.append(" ⚠️  NO ACTIONABLE PICKS WITH REAL DATA")
        lines.append("     All props below use BASELINE estimates (not reliable)")
        lines.append(f"{'='*70}")
    
    # SHOW BASELINE DATA (with clear warning)
    if baseline_all:
        lines.append(f"\n{'='*70}")
        lines.append(f" ⚠️  BASELINE ESTIMATES (NOT ACTIONABLE) — {len(baseline_all)} props")
        lines.append("     These use generic league averages, NOT real player stats")
        lines.append(f"{'='*70}")
        
        # Group by implied tier (for reference only)
        by_tier = {"SLAM": [], "STRONG": [], "LEAN": [], "NO_PLAY": []}
        for e in baseline_all:
            by_tier.get(e.tier, by_tier["NO_PLAY"]).append(e)
        
        for tier in ["SLAM", "STRONG", "LEAN", "NO_PLAY"]:
            tier_edges = by_tier[tier]
            if tier_edges:
                lines.append(f"\n  [{tier}] (baseline only - not real)")
                for e in sorted(tier_edges, key=lambda x: -x.probability)[:10]:  # Limit to top 10
                    dir_sym = "⬆️" if e.direction == "OVER" else "⬇️"
                    lines.append(
                        f"    {dir_sym} {e.player} ({e.team}) | {e.stat} {e.direction} {e.line} | "
                        f"p={e.probability*100:.1f}% | mean={e.mean:.2f} | ⚠️ BASELINE"
                    )
                if len(tier_edges) > 10:
                    lines.append(f"    ... and {len(tier_edges) - 10} more")
    
    # Summary
    lines.append("")
    lines.append("-" * 70)
    lines.append(f"REAL DATA: {real_data_count} | BASELINE: {baseline_count}")
    if real_data_count == 0:
        lines.append("❌ NO REAL PLAYER DATA - Cannot make informed betting decisions!")
        lines.append("   → Use option [7] to fetch stats from API-Football")
        lines.append("   → Or use option [5] to manually input player stats")
    lines.append("-" * 70)
    
    return "\n".join(lines)


def save_risk_first_json(edges: List[SoccerPropEdge], output_dir: Path) -> str:
    """Save edges to RISK_FIRST JSON format."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"soccer_props_RISK_FIRST_{ts}.json"
    filepath = output_dir / filename
    
    data = {
        "generated": datetime.now().isoformat(),
        "total_props": len(edges),
        "edges": [asdict(e) for e in edges],
    }
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    return str(filepath)


def run_props_pipeline(
    slate_path: str,
    *,
    interactive: bool = True,
    num_sims: int = 10000,
    skip_all_missing: bool = False,
) -> Dict[str, Any]:
    """
    Main entry point for soccer props analysis.
    
    Args:
        slate_path: Path to saved props JSON
        interactive: If True, prompt for missing stats
        num_sims: Number of MC simulations
        skip_all_missing: If True, skip all players with missing stats
    
    Returns:
        Dict with report_path, json_path, summary
    """
    print(f"\n[SOCCER PROPS] Loading slate: {slate_path}")
    props = load_props_slate(slate_path)
    print(f"[SOCCER PROPS] Found {len(props)} props in slate")
    
    print(f"[SOCCER PROPS] Running Monte Carlo ({num_sims} sims per prop)...")
    edges = analyze_props_slate(
        props, 
        interactive=interactive, 
        num_sims=num_sims,
        skip_all_missing=skip_all_missing,
    )
    
    # UGO EXPORT: Convert to Universal Governance Object format
    try:
        from core.universal_governance_object import adapt_edge, Sport
        ugo_edges = []
        for edge in edges:
            try:
                edge_dict = edge.to_dict() if hasattr(edge, 'to_dict') else edge.__dict__
                ugo = adapt_edge(Sport.SOCCER, edge_dict)
                ugo_edges.append(ugo.to_dict())
            except Exception:
                pass
        print(f"✓ UGO Export: {len(ugo_edges)} edges")
    except ImportError:
        ugo_edges = []
    
    # Render report
    report = render_props_report(edges)
    print(report)
    
    # Save outputs
    output_dir = Path(__file__).parent / "outputs"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save text report
    report_path = output_dir / f"soccer_props_report_{ts}.txt"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    # Save RISK_FIRST JSON
    json_path = save_risk_first_json(edges, output_dir)
    
    # Summary
    actionable = len([e for e in edges if e.tier in ("SLAM", "STRONG", "LEAN")])
    missing = len([e for e in edges if e.hydration_mode == "missing"])
    
    print(f"\n✅ Report saved: {report_path}")
    print(f"✅ RISK_FIRST JSON: {json_path}")
    
    return {
        "report_path": str(report_path),
        "json_path": json_path,
        "total_props": len(edges),
        "actionable": actionable,
        "missing_data": missing,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python soccer_props_pipeline.py <slate_path> [--no-interactive]")
        sys.exit(1)
    
    slate = sys.argv[1]
    interactive = "--no-interactive" not in sys.argv
    
    run_props_pipeline(slate, interactive=interactive)
