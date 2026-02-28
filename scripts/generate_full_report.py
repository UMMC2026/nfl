"""
UNIVERSAL FULL REPORT GENERATOR
Human-readable analysis reports for NBA | NFL | Tennis | CBB
"""
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

class FullReportGenerator:
    """Generate comprehensive human-readable analysis reports"""
    
    def __init__(self, picks: List[Dict], sport: str = "NBA", metadata: Dict = None):
        # Filter out picks with no data (sample_n/n/sample_size == 0 or missing)
        def has_data(p):
            n = p.get("sample_n", p.get("n", p.get("sample_size", 0)))
            return n is not None and n > 0
        self.picks = [p for p in picks if has_data(p)]
        self.sport = sport.upper()
        self.metadata = metadata or {}
        self.timestamp = datetime.now()
    
    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """Generate full text report"""
        lines = []
        
        # Header
        date_formatted = self.timestamp.strftime("%B %d, %Y")
        time_formatted = self.timestamp.strftime("%I:%M %p")
        label = self.metadata.get("label", "SLATE")
        source = self.metadata.get("source_file", "Unknown")
        
        lines.append("=" + "=" * 78 + "=")
        lines.append("||" + " " * 78 + "||")
        lines.append("||" + f"{self.sport} PROPS ANALYZER - FULL REPORT".center(78) + "||")
        lines.append("||" + "=" * 38 + "=" * 38 + "||")
        lines.append("||" + f"SLATE: {label}".center(78) + "||")
        lines.append("||" + " " + "=" * 78 + "||")
        lines.append("")
        lines.append(f"  Report Date:    {date_formatted}")
        lines.append(f"  Generated At:   {time_formatted}")
        lines.append(f"  Data Source:    {source}")
        lines.append("")
        
        # Executive Summary
        summary = self._generate_summary()
        lines.append("+" + "-" * 78 + "+")
        lines.append("|" + "  EXECUTIVE SUMMARY".ljust(78) + "|")
        lines.append("+" + "-" * 78 + "+")
        lines.append("|" + f"  Total Props Analyzed:  {summary['total']:<13} Actionable Plays:  {summary['actionable']:<18}|")
        lines.append("|" + f"  [PLAY] Tier:           {summary['play']:<13} [LEAN] Tier:        {summary['lean']:<18}|")
        lines.append("|" + f"  Directional Bias:      {summary['overs']} OVERs / {summary['unders']} UNDERs".ljust(78) + "|")
        lines.append("+" + "-" * 78 + "+")
        lines.append("")
        lines.append("")
        
        # Group picks by tier/status
        grouped = self._group_picks()
        
        # PLAY tier
        if grouped.get("PLAY"):
            lines.append("=" * 80)
            lines.append(f"  [HIGH CONVICTION PLAYS] ({len(grouped['PLAY'])})")
            lines.append("  Strongest edge - recommended for singles or entry building")
            lines.append("=" * 80)
            lines.append("")
            for idx, pick in enumerate(grouped["PLAY"], 1):
                lines.extend(self._format_pick(idx, pick, show_failure_lens=True))
            lines.append("")
        
        # LEAN tier
        if grouped.get("LEAN"):
            lines.append("=" * 80)
            lines.append(f"  [MODERATE PLAYS - LEAN] ({len(grouped['LEAN'])})")
            lines.append("  Moderate confidence (65-74%) - consider for parlays")
            lines.append("=" * 80)
            lines.append("")
            for idx, pick in enumerate(grouped["LEAN"], 1):
                lines.extend(self._format_pick(idx, pick, show_failure_lens=True))
            lines.append("")
        
        # NO PLAY tier
        no_plays = grouped.get("NO PLAY", []) + grouped.get("PASS", [])
        if no_plays:
            lines.append("=" * 80)
            lines.append(f"  [NO PLAY] ({len(no_plays)})")
            lines.append("  Below threshold - insufficient edge or confidence")
            lines.append("=" * 80)
            lines.append("")
            for idx, pick in enumerate(no_plays[:20], 1):  # Show top 20
                lines.extend(self._format_pick(idx, pick, show_failure_lens=False))
            if len(no_plays) > 20:
                lines.append(f"\n  ... and {len(no_plays) - 20} more props below threshold\n")
            lines.append("")
        
        # BLOCKED tier
        if grouped.get("BLOCKED"):
            lines.append("=" * 80)
            lines.append(f"  [BLOCKED] ({len(grouped['BLOCKED'])})")
            lines.append("  Failed hard gates - do not play")
            lines.append("=" * 80)
            lines.append("")
            for idx, pick in enumerate(grouped["BLOCKED"], 1):
                lines.extend(self._format_pick(idx, pick, show_failure_lens=False))
            lines.append("")
        
        # Methodology footer
        lines.append("+" + "-" * 78 + "+")
        lines.append("|" + "  METHODOLOGY".ljust(78) + "|")
        lines.append("+" + "-" * 78 + "+")
        lines.append("|" + "  * Confidence = P(hit) via probabilistic model".ljust(78) + "|")
        lines.append("|" + "  * Edge = (Confidence - Breakeven%) / Breakeven% x 100".ljust(78) + "|")
        lines.append("|" + "  * PLAY threshold: 75%+ confidence with positive edge".ljust(78) + "|")
        lines.append("|" + "  * LEAN threshold: 65-74% confidence with positive edge".ljust(78) + "|")
        lines.append("+" + "-" * 78 + "+")
        lines.append("")
        
        lines.append("+" + "-" * 78 + "+")
        lines.append("|" + "  DISCLAIMER".ljust(78) + "|")
        lines.append("+" + "-" * 78 + "+")
        lines.append("|" + "  This analysis is for informational purposes only.".ljust(78) + "|")
        lines.append("|" + "  Past performance does not guarantee future results.".ljust(78) + "|")
        lines.append("|" + "  Always gamble responsibly.".ljust(78) + "|")
        lines.append("+" + "-" * 78 + "+")
        lines.append("")
        
        lines.append("=" * 80)
        lines.append("  END OF REPORT")
        lines.append("=" * 80)
        
        report_text = "\n".join(lines)
        
        # Save if path provided
        if output_path:
            output_path.write_text(report_text, encoding='utf-8')
            print(f"[OK] Saved: {output_path}")
        
        return report_text
    
    def _generate_summary(self) -> Dict:
        """Calculate summary statistics"""
        total = len(self.picks)
        
        # Count by tier/status/decision
        play = sum(1 for p in self.picks if (p.get("status") or p.get("decision") or p.get("tier", "")).upper() == "PLAY")
        lean = sum(1 for p in self.picks if (p.get("status") or p.get("decision") or p.get("tier", "")).upper() == "LEAN")
        
        actionable = play + lean
        
        # Count directional bias (only for PLAY/LEAN)
        play_lean_picks = [p for p in self.picks if (p.get("status") or p.get("decision") or p.get("tier", "")).upper() in ["PLAY", "LEAN"]]
        overs = sum(1 for p in play_lean_picks if (p.get("direction") or "").lower() in ["higher", "over"])
        unders = sum(1 for p in play_lean_picks if (p.get("direction") or "").lower() in ["lower", "under"])
        
        return {
            "total": total,
            "play": play,
            "lean": lean,
            "actionable": actionable,
            "overs": overs,
            "unders": unders
        }
    
    def _group_picks(self) -> Dict[str, List[Dict]]:
        """Group picks by tier/status"""
        grouped = {}
        
        for pick in self.picks:
            tier = (pick.get("status") or pick.get("decision") or pick.get("tier", "NO PLAY")).upper()
            if tier not in grouped:
                grouped[tier] = []
            grouped[tier].append(pick)
        
        # Sort each group by confidence descending
        for tier in grouped:
            grouped[tier].sort(key=lambda p: p.get("confidence", p.get("probability", 0)), reverse=True)
        
        return grouped
    
    def _format_pick(self, idx: int, pick: Dict, show_failure_lens: bool = True) -> List[str]:
        """Format a single pick for display"""
        lines = []
        
        player = pick.get("player", pick.get("entity", "Unknown"))
        team = pick.get("team", "")
        stat = pick.get("stat", pick.get("market", ""))
        line = pick.get("line", 0)
        direction = (pick.get("direction") or "").upper()
        
        # Convert decimal to percentage if needed
        prob_raw = pick.get("confidence", pick.get("probability", 0))
        confidence = prob_raw * 100 if prob_raw <= 1.0 else prob_raw
        edge = pick.get("edge", 0)
        # FIX: Look for mu first (from risk_first_analyzer), then recent_avg, then avg
        recent_avg = pick.get("mu", pick.get("recent_avg", pick.get("avg", 0)))
        # FIX: Look for sigma first (from risk_first_analyzer), then recent_std, then std
        recent_std = pick.get("sigma", pick.get("recent_std", pick.get("std", 0)))
        # FIX: Look for sample_n first (from risk_first_analyzer), then n, then sample_size
        sample_size = pick.get("sample_n", pick.get("n", pick.get("sample_size", 0)))
        line_gap = pick.get("line_gap", 0)

        # Patch: handle None values for stats
        if recent_avg is None:
            recent_avg = 0.0
        if recent_std is None:
            recent_std = 0.0
        if sample_size is None:
            sample_size = 0
        if line_gap is None:
            line_gap = 0.0
        
        # Context
        context_parts = []
        if pick.get("matchup_adj"):
            context_parts.append(f"Matchup: {pick['matchup_adj']:+.1f}%")
        if pick.get("opponent_rank"):
            rank = pick["opponent_rank"]
            if rank <= 5:
                context_parts.append(f"WARNING vs Elite D (#{rank})")
        
        context_str = ", ".join(context_parts) if context_parts else ""
        
        lines.append(f"  +- #{idx} " + "-" * 60)
        lines.append(f"  |  {player} ({team})")
        lines.append(f"  |  {stat} {direction} {line}")
        lines.append(f"  |")
        lines.append(f"  |  Confidence:  {confidence:.1f}%")
        lines.append(f"  |  Edge:        {edge:+.1f}%")
        lines.append(f"  |  Recent Avg:  {recent_avg:.1f}  (sigma={recent_std:.1f}, n={sample_size})")
        lines.append(f"  |  Line Gap:    {line_gap:+.1f} pts")
        if context_str:
            lines.append(f"  |  Context:     {context_str}")
        
        # Failure lens
        if show_failure_lens and pick.get("risk_reasons"):
            lines.append(f"  |  Failure Lens:")
            # FIX: Compare actual values, not based on direction
            comp_symbol = '>' if recent_avg > line else '<' if recent_avg < line else '='
            edge_str = f"{edge:+.1f}%" if edge >= 0 else f"{edge:.1f}%"
            lines.append(f"  |   * Math says: Recent Avg {recent_avg:.1f} {comp_symbol} Line {line}, {confidence:.1f}% confidence, {edge_str} edge")
            lines.append(f"  |   * Structural risk: {', '.join(pick['risk_reasons'])}")
            if direction in ["HIGHER", "OVER"]:
                lines.append(f"  |   * Correct lens: UNDER is more protected. OVER is fragile in current market context.")
            else:
                lines.append(f"  |   * Correct lens: UNDER is aligned; consider NO PLAY if variance or context risks are high.")
        
        lines.append(f"  +" + "-" * 64)
        lines.append("")
        
        return lines


def main():
    parser = argparse.ArgumentParser(description="Generate full human-readable report")
    parser.add_argument("--sport", type=str, default="NBA", help="Sport (NBA/NFL/Tennis/CBB)")
    parser.add_argument("--input", type=str, required=True, help="Input JSON file path")
    
    args = parser.parse_args()
    
    # Load data
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[X] File not found: {input_path}")
        return
    
    data = json.loads(input_path.read_text())
    
    # Extract picks and metadata
    if isinstance(data, dict) and "results" in data:
        picks = data["results"]
        metadata = {k: v for k, v in data.items() if k != "results"}
    elif isinstance(data, list):
        picks = data
        metadata = {}
    else:
        picks = []
        metadata = {}
    
    if not picks:
        print(f"[X] No picks found in {input_path.name}")
        return
    
    # Add source file to metadata
    metadata["source_file"] = input_path.name
    if "label" not in metadata:
        # Extract label from filename
        stem = input_path.stem.replace("_RISK_FIRST_20260124_FROM_UD", "").replace("_FROM_UD", "")
        metadata["label"] = stem
    
    # Generate report
    generator = FullReportGenerator(picks, args.sport, metadata)
    
    # Output path
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = metadata.get("label", "SLATE")
    output_path = input_path.parent / f"{label}_FULL_REPORT_{ts}.txt"
    
    report = generator.generate_report(output_path)
    
    print(f"\n[*] Generated {args.sport} full report")
    print(f"[*] {len(picks)} picks analyzed")
    print(f"\n--- Preview (first 60 lines) ---\n")
    print("\n".join(report.split("\n")[:60]))
    print("\n... [see full file for complete report] ...")


if __name__ == "__main__":
    main()
