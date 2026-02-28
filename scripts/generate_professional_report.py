#!/usr/bin/env python3
"""
PROFESSIONAL NBA REPORT GENERATOR
==================================
Combines Monte Carlo Entry Optimization with Team-by-Team Analysis
into a single, professional-grade report.

Usage:
    python scripts/generate_professional_report.py
    python scripts/generate_professional_report.py --label NBASUNDAY1
    python scripts/generate_professional_report.py --json-file outputs/NBASUNDAY1_RISK_FIRST_20260201_FROM_UD.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_stat_key_block() -> str:
    """Return the stat key reference block."""
    return """STAT KEY (basketball):
   PTS=Points | REB=Rebounds | AST=Assists | STL=Steals | BLK=Blocks | TOV=Turnovers
   3PM=3-pointers made (aka 3PT/3PTS) | STOCKS=STL+BLK | PRA=PTS+REB+AST
   PR=PTS+REB | PA=PTS+AST | RA=REB+AST"""


def format_tier_badge(prob: float) -> str:
    """Return tier badge based on probability."""
    if prob >= 80:
        return "🔥 SLAM"
    elif prob >= 65:
        return "✅ STRONG"
    elif prob >= 55:
        return "📊 LEAN"
    else:
        return "⚠️ MARGINAL"


def format_direction_arrow(direction: str) -> str:
    """Return direction indicator."""
    d = str(direction).lower()
    if d in ("higher", "over"):
        return "▲ OVER"
    elif d in ("lower", "under"):
        return "▼ UNDER"
    return direction


def generate_monte_carlo_section(picks: List[Dict], min_conf: float = 65.0) -> str:
    """Generate Monte Carlo optimization section."""
    try:
        from quant_modules import optimize_entries
    except ImportError:
        return "Monte Carlo module not available.\n"
    
    if not picks:
        return "No picks available for Monte Carlo optimization.\n"
    
    # Filter qualifying picks
    qualifying = [p for p in picks if p.get("status_confidence", p.get("probability", 0)) >= min_conf]
    
    if len(qualifying) < 2:
        return f"Insufficient qualifying picks for Monte Carlo ({len(qualifying)} < 2 required).\n"
    
    try:
        result = optimize_entries(picks, verbose=False)
        return result.generate_report() if hasattr(result, 'generate_report') else str(result)
    except Exception as e:
        return f"Monte Carlo optimization error: {e}\n"


def build_team_section(team: str, edges: List[Dict], opponent: str = "UNK", context: str = "") -> str:
    """Build formatted section for one team."""
    lines = []
    
    # Team header with separator
    lines.append(f"┌{'─' * 68}┐")
    lines.append(f"│  TEAM: {team:<15} vs {opponent:<15} {'│':>34}")
    lines.append(f"└{'─' * 68}┘")
    
    # Matchup context if available
    if context:
        for ctx_line in context.split("\n"):
            if ctx_line.strip():
                lines.append(f"   {ctx_line.strip()}")
        lines.append("")
    
    # Sort edges by confidence
    sorted_edges = sorted(
        edges,
        key=lambda x: x.get("status_confidence", x.get("probability", x.get("effective_confidence", 0))),
        reverse=True
    )
    
    lines.append("   TOP EDGES:")
    lines.append("   " + "─" * 64)
    
    for i, edge in enumerate(sorted_edges[:7], 1):  # Top 7 per team
        player = edge.get("player", "Unknown")
        stat = edge.get("stat", "?").upper()
        direction = edge.get("direction", "?")
        line_val = edge.get("line", "?")
        prob = edge.get("status_confidence", edge.get("probability", edge.get("effective_confidence", 0)))
        prob_val = float(prob) if isinstance(prob, (int, float)) else 0
        
        tier = edge.get("status", edge.get("decision", "?"))
        mu = edge.get("mu", edge.get("mean", edge.get("avg", 0)))
        sigma = edge.get("sigma", edge.get("std", 0))
        
        # Build context notes
        ctx_parts = []
        if mu and mu > 0:
            ctx_parts.append(f"μ={mu:.1f}")
        if sigma and sigma > 0:
            ctx_parts.append(f"σ={sigma:.1f}")
        
        edge_pct = edge.get("edge", 0)
        if edge_pct and edge_pct > 0:
            ctx_parts.append(f"edge={edge_pct:.1f}%")
        
        ctx_str = f" [{', '.join(ctx_parts)}]" if ctx_parts else ""
        
        # Format direction
        dir_str = "OVER" if direction.lower() in ("higher", "over") else "UNDER" if direction.lower() in ("lower", "under") else direction
        
        lines.append(f"   {i}) {player:<20} {stat:<6} {dir_str:<5} {line_val:>5} — {tier:<7} ({prob_val:.1f}%){ctx_str}")
    
    lines.append("")
    return "\n".join(lines)


def build_summary_stats(all_edges: List[Dict]) -> str:
    """Build summary statistics section."""
    if not all_edges:
        return ""
    
    lines = []
    lines.append("=" * 70)
    lines.append("SLATE SUMMARY STATISTICS")
    lines.append("=" * 70)
    
    # Count by tier
    tier_counts = {}
    for e in all_edges:
        tier = e.get("status", e.get("decision", "UNKNOWN"))
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    total = len(all_edges)
    lines.append(f"\nTotal Props Analyzed: {total}")
    lines.append("\nTier Distribution:")
    for tier, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
        pct = (count / total) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"   {tier:<12} {bar} {count:>3} ({pct:.1f}%)")
    
    # Average confidence by stat
    stat_data = {}
    for e in all_edges:
        stat = e.get("stat", "other")
        prob = e.get("status_confidence", e.get("probability", 0))
        if stat not in stat_data:
            stat_data[stat] = []
        stat_data[stat].append(float(prob) if isinstance(prob, (int, float)) else 0)
    
    lines.append("\nAverage Confidence by Stat:")
    for stat, probs in sorted(stat_data.items(), key=lambda x: -sum(x[1])/len(x[1]) if x[1] else 0):
        if probs:
            avg = sum(probs) / len(probs)
            lines.append(f"   {stat.upper():<12} {avg:.1f}% (n={len(probs)})")
    
    # Direction bias
    higher = sum(1 for e in all_edges if e.get("direction", "").lower() in ("higher", "over"))
    lower = total - higher
    lines.append(f"\nDirection Bias: {higher} OVER / {lower} UNDER ({higher/total*100:.1f}% / {lower/total*100:.1f}%)")
    
    lines.append("")
    return "\n".join(lines)


def build_top_plays_section(all_edges: List[Dict], top_n: int = 15) -> str:
    """Build the top plays across all teams section."""
    if not all_edges:
        return ""
    
    lines = []
    lines.append("=" * 70)
    lines.append("🎯 TOP PLAYS — SLATE LEADERS (ALL TEAMS)")
    lines.append("=" * 70)
    lines.append("")
    
    # Sort by confidence descending
    sorted_edges = sorted(
        all_edges,
        key=lambda x: x.get("status_confidence", x.get("probability", x.get("effective_confidence", 0))),
        reverse=True
    )
    
    lines.append(f"{'#':<3} {'PLAYER':<22} {'STAT':<8} {'DIR':<6} {'LINE':>6} {'PROB':>7} {'TIER':<8} {'TEAM':<5}")
    lines.append("─" * 70)
    
    for i, edge in enumerate(sorted_edges[:top_n], 1):
        player = edge.get("player", "Unknown")[:20]
        stat = edge.get("stat", "?").upper()[:6]
        direction = "OVER" if edge.get("direction", "").lower() in ("higher", "over") else "UNDER"
        line_val = edge.get("line", "?")
        prob = edge.get("status_confidence", edge.get("probability", edge.get("effective_confidence", 0)))
        prob_val = float(prob) if isinstance(prob, (int, float)) else 0
        tier = edge.get("status", edge.get("decision", "?"))[:7]
        team = edge.get("team", "?")[:4]
        
        lines.append(f"{i:<3} {player:<22} {stat:<8} {direction:<6} {line_val:>6} {prob_val:>6.1f}% {tier:<8} {team:<5}")
    
    lines.append("")
    return "\n".join(lines)


def build_parlay_suggestions(all_edges: List[Dict]) -> str:
    """Build parlay suggestion section."""
    if not all_edges:
        return ""
    
    lines = []
    lines.append("=" * 70)
    lines.append("🎲 PARLAY CONSTRUCTION GUIDE")
    lines.append("=" * 70)
    lines.append("")
    
    # Filter to actionable picks (>= 60% confidence)
    actionable = [e for e in all_edges if e.get("status_confidence", e.get("probability", 0)) >= 60]
    
    if len(actionable) < 3:
        lines.append("Insufficient high-confidence picks for parlay construction.")
        lines.append("")
        return "\n".join(lines)
    
    # Group by stat for diversification
    by_stat = {}
    for e in actionable:
        stat = e.get("stat", "other")
        by_stat.setdefault(stat, []).append(e)
    
    lines.append("DIVERSIFICATION POOLS:")
    for stat, picks in sorted(by_stat.items(), key=lambda x: -len(x[1])):
        count = len(picks)
        top_player = picks[0].get("player", "?") if picks else "?"
        lines.append(f"   {stat.upper():<10} {count} picks (best: {top_player})")
    
    # Build sample 3-leg parlay
    lines.append("\nSAMPLE 3-LEG POWER PLAY:")
    lines.append("   (select from different stats for diversification)")
    
    used_stats = set()
    suggested = []
    sorted_actionable = sorted(actionable, key=lambda x: -x.get("status_confidence", x.get("probability", 0)))
    
    for e in sorted_actionable:
        stat = e.get("stat", "other")
        if stat not in used_stats and len(suggested) < 3:
            suggested.append(e)
            used_stats.add(stat)
    
    combined_prob = 1.0
    for i, e in enumerate(suggested, 1):
        player = e.get("player", "?")
        stat = e.get("stat", "?").upper()
        direction = "OVER" if e.get("direction", "").lower() in ("higher", "over") else "UNDER"
        line_val = e.get("line", "?")
        prob = e.get("status_confidence", e.get("probability", 0))
        prob_val = float(prob) / 100 if isinstance(prob, (int, float)) else 0.5
        combined_prob *= prob_val
        lines.append(f"   {i}. {player} {stat} {direction} {line_val} ({prob_val*100:.1f}%)")
    
    lines.append(f"\n   Combined probability: {combined_prob*100:.1f}%")
    lines.append(f"   3-leg POWER payout: 6x")
    lines.append(f"   Expected value: {combined_prob * 6 - 1:+.2f} units")
    
    lines.append("")
    return "\n".join(lines)


def generate_professional_report(
    analysis_data: Dict[str, Any],
    label: str = "NBA_SLATE",
    include_mc: bool = True,
    include_summary: bool = True,
    include_top_plays: bool = True,
    include_parlay: bool = True
) -> str:
    """
    Generate a comprehensive professional report.
    
    Args:
        analysis_data: Full analysis results (from risk_first_analyzer or similar)
        label: Label for the report
        include_mc: Include Monte Carlo optimization section
        include_summary: Include summary statistics
        include_top_plays: Include top plays section
        include_parlay: Include parlay suggestions
    
    Returns:
        Formatted report string
    """
    report_lines = []
    timestamp = datetime.now().isoformat()
    
    # ═══════════════════════════════════════════════════════════════════════
    # HEADER
    # ═══════════════════════════════════════════════════════════════════════
    report_lines.append("╔" + "═" * 68 + "╗")
    report_lines.append(f"║{'PROFESSIONAL NBA ANALYSIS REPORT':^68}║")
    report_lines.append(f"║{label:^68}║")
    report_lines.append("╠" + "═" * 68 + "╣")
    report_lines.append(f"║  Generated: {timestamp:<54}║")
    report_lines.append(f"║  System: UNDERDOG ANALYSIS — Risk-First Quant Engine{' ' * 14}║")
    report_lines.append("╚" + "═" * 68 + "╝")
    report_lines.append("")
    
    # Stat key
    report_lines.append(get_stat_key_block())
    report_lines.append("")
    
    # Extract results
    results = analysis_data.get("results", [])
    if not results:
        report_lines.append("No results available in analysis data.")
        return "\n".join(report_lines)
    
    # ═══════════════════════════════════════════════════════════════════════
    # MONTE CARLO OPTIMIZATION (if enabled)
    # ═══════════════════════════════════════════════════════════════════════
    if include_mc:
        report_lines.append("=" * 70)
        report_lines.append("MONTE CARLO ENTRY OPTIMIZATION")
        report_lines.append("=" * 70)
        report_lines.append("")
        
        mc_report = generate_monte_carlo_section(results)
        report_lines.append(mc_report)
        report_lines.append("")
    
    # ═══════════════════════════════════════════════════════════════════════
    # TOP PLAYS SECTION (if enabled)
    # ═══════════════════════════════════════════════════════════════════════
    if include_top_plays:
        report_lines.append(build_top_plays_section(results, top_n=15))
    
    # ═══════════════════════════════════════════════════════════════════════
    # TEAM-BY-TEAM BREAKDOWN
    # ═══════════════════════════════════════════════════════════════════════
    report_lines.append("=" * 70)
    report_lines.append("TEAM-BY-TEAM ANALYSIS")
    report_lines.append("=" * 70)
    report_lines.append("")
    
    # Group by team
    by_team: Dict[str, List[Dict]] = {}
    team_opponents: Dict[str, str] = {}
    
    for r in results:
        if not isinstance(r, dict):
            continue
        team = r.get("team") or "UNK"
        by_team.setdefault(str(team), []).append(r)
        opp = r.get("opponent")
        if opp:
            team_opponents[str(team)] = str(opp)
    
    # Try to get matchup context
    try:
        from nba_team_context import get_matchup_summary
        has_context = True
    except ImportError:
        has_context = False
    
    # Build each team section
    for team in sorted(by_team.keys()):
        edges = by_team[team]
        opponent = team_opponents.get(team, "UNK")
        
        context = ""
        if has_context:
            try:
                context = get_matchup_summary(team, opponent) or ""
            except Exception:
                pass
        
        report_lines.append(build_team_section(team, edges, opponent, context))
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUMMARY STATISTICS (if enabled)
    # ═══════════════════════════════════════════════════════════════════════
    if include_summary:
        report_lines.append(build_summary_stats(results))
    
    # ═══════════════════════════════════════════════════════════════════════
    # PARLAY SUGGESTIONS (if enabled)
    # ═══════════════════════════════════════════════════════════════════════
    if include_parlay:
        report_lines.append(build_parlay_suggestions(results))
    
    # ═══════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════
    report_lines.append("=" * 70)
    report_lines.append("GOVERNANCE & DISCLAIMER")
    report_lines.append("=" * 70)
    report_lines.append("""
This report is generated by a risk-first quantitative analysis system.
All probabilities are model estimates based on historical performance.

RISK MANAGEMENT:
• Never exceed 3% of bankroll on a single entry
• Parlays carry exponentially higher variance
• Past performance does not guarantee future results

For entertainment purposes only. Gamble responsibly.
""")
    
    report_lines.append("─" * 70)
    report_lines.append(f"Report ID: {label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    report_lines.append("System: UNDERDOG ANALYSIS v2.0 — Risk-First Quant Engine")
    report_lines.append("─" * 70)
    
    return "\n".join(report_lines)


def find_latest_analysis_file(label: str = None) -> Optional[Path]:
    """Find the latest analysis JSON file."""
    outputs_dir = PROJECT_ROOT / "outputs"
    if not outputs_dir.exists():
        return None
    
    patterns = [
        f"{label}_RISK_FIRST_*.json" if label else "*RISK_FIRST_*.json",
        f"{label}_*.json" if label else "*.json"
    ]
    
    for pattern in patterns:
        files = sorted(outputs_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            return files[0]
    
    return None


def main():
    import argparse
    
    # Ensure UTF-8 output for Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    parser = argparse.ArgumentParser(description="Generate professional NBA analysis report")
    parser.add_argument("--label", default=None, help="Label prefix (e.g., NBASUNDAY1)")
    parser.add_argument("--json-file", default=None, help="Path to analysis JSON file")
    parser.add_argument("--output", default=None, help="Output file path (default: auto-generated)")
    parser.add_argument("--no-mc", action="store_true", help="Skip Monte Carlo section")
    parser.add_argument("--no-summary", action="store_true", help="Skip summary statistics")
    parser.add_argument("--no-top-plays", action="store_true", help="Skip top plays section")
    parser.add_argument("--no-parlay", action="store_true", help="Skip parlay suggestions")
    
    args = parser.parse_args()
    
    # Find or load data
    if args.json_file:
        json_path = Path(args.json_file)
    else:
        json_path = find_latest_analysis_file(args.label)
    
    if not json_path or not json_path.exists():
        print("ERROR: No analysis file found. Run analysis first or specify --json-file")
        sys.exit(1)
    
    print(f"Loading: {json_path.name}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Determine label
    label = args.label or json_path.stem.split("_")[0] or "NBA_SLATE"
    
    # Generate report
    report = generate_professional_report(
        data,
        label=label,
        include_mc=not args.no_mc,
        include_summary=not args.no_summary,
        include_top_plays=not args.no_top_plays,
        include_parlay=not args.no_parlay
    )
    
    # Save report
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = PROJECT_ROOT / "outputs" / f"{label}_PROFESSIONAL_REPORT_{timestamp}.txt"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding='utf-8')
    
    print(f"SUCCESS: Report saved: {output_path}")
    print("\n" + "=" * 70)
    print(report[:2000])  # Preview first 2000 chars
    if len(report) > 2000:
        print(f"\n... ({len(report) - 2000} more characters)")


if __name__ == "__main__":
    main()
