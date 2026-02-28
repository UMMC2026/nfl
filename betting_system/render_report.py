#!/usr/bin/env python3
"""
RENDER_REPORT.PY — SOP v2.1 REPORT GENERATION
=============================================
Stage 6: Generate final output report

⚠️  THIS SCRIPT MUST ONLY RUN AFTER validate_output.py PASSES ⚠️

Running this directly bypasses the validation gate and violates SOP v2.1.
Use run_pipeline.py instead.

Version: 2.1.0
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


# ============================================================================
# SAFETY CHECK
# ============================================================================

def check_validation_passed() -> bool:
    """
    Verify that validation gate passed before rendering
    
    SOP v2.1 Rule: No stage may be skipped
    """
    validation_report = Path("outputs/validation_report.json")
    
    if not validation_report.exists():
        print("❌ BLOCKED: No validation report found")
        print("   Run validate_output.py first")
        return False
    
    with open(validation_report, 'r') as f:
        report = json.load(f)
    
    if report.get('summary', {}).get('status') != 'PASSED':
        print("❌ BLOCKED: Validation did not pass")
        print(f"   Errors: {report.get('summary', {}).get('checks_failed', 'unknown')}")
        return False
    
    return True


# ============================================================================
# REPORT GENERATION
# ============================================================================

class ReportRenderer:
    """
    Generates human-readable reports from scored edges
    """
    
    def __init__(self, scored_data: Dict):
        self.data = scored_data
        self.edges = scored_data.get('edges', [])
        self.summary = scored_data.get('summary', {})
        
    def render_text_report(self) -> str:
        """Generate plain text report"""
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append("SPORTS BETTING R&D — DAILY PICKS REPORT")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"SOP Version: 2.1 (Truth-Enforced)")
        lines.append("=" * 70)
        
        # Summary
        lines.append("\n📊 SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Edges Analyzed: {self.summary.get('total_edges', 0)}")
        lines.append(f"Actionable Picks: {self.summary.get('actionable_edges', 0)}")
        lines.append(f"Total Units Recommended: {self.summary.get('total_recommended_units', 0)}")
        lines.append(f"Average Expected Value: {self.summary.get('avg_expected_value', 0)}%")
        
        # By tier breakdown
        lines.append("\n📈 BY CONFIDENCE TIER")
        lines.append("-" * 40)
        for tier in ['SLAM', 'STRONG', 'LEAN']:
            tier_data = self.summary.get('by_tier', {}).get(tier, {})
            if tier_data.get('count', 0) > 0:
                lines.append(f"{tier}: {tier_data['count']} edges | {tier_data['actionable']} actionable | {tier_data['avg_ev']}% avg EV")
        
        # Top picks by tier
        for tier in ['SLAM', 'STRONG', 'LEAN']:
            tier_edges = [e for e in self.edges if e.get('tier') == tier and e.get('is_actionable')]
            if tier_edges:
                lines.append(f"\n🎯 {tier} PICKS")
                lines.append("-" * 40)
                for edge in tier_edges[:5]:  # Top 5 per tier
                    lines.append(self._format_pick(edge))
        
        # Risk warnings
        flagged = [e for e in self.edges if e.get('risk_flags')]
        if flagged:
            lines.append("\n⚠️  RISK ALERTS")
            lines.append("-" * 40)
            for edge in flagged[:5]:
                flags = ', '.join(edge.get('risk_flags', []))
                lines.append(f"• {edge.get('player_name')}: {flags}")
        
        # Footer
        lines.append("\n" + "=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def render_json_report(self) -> Dict:
        """Generate structured JSON report"""
        
        # Organize by tier
        picks_by_tier = {
            'SLAM': [],
            'STRONG': [],
            'LEAN': []
        }
        
        for edge in self.edges:
            tier = edge.get('tier')
            if tier in picks_by_tier and edge.get('is_actionable'):
                picks_by_tier[tier].append({
                    'player': edge.get('player_name'),
                    'game': edge.get('game_id'),
                    'stat': edge.get('stat_type'),
                    'direction': edge.get('direction'),
                    'line': edge.get('primary_line'),
                    'projection': edge.get('projection'),
                    'confidence': edge.get('confidence'),
                    'expected_value': edge.get('expected_value'),
                    'recommended_units': edge.get('recommended_units'),
                    'risk_flags': edge.get('risk_flags', [])
                })
        
        return {
            'report_type': 'daily_picks',
            'generated_at': datetime.utcnow().isoformat() + "Z",
            'sop_version': '2.1',
            'summary': self.summary,
            'picks': picks_by_tier,
            'total_picks': sum(len(v) for v in picks_by_tier.values()),
            'validation_status': 'PASSED'
        }
    
    def render_markdown_report(self) -> str:
        """Generate markdown report for display"""
        lines = []
        
        lines.append("# 🎯 Daily Picks Report")
        lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**SOP Version:** 2.1 (Truth-Enforced)")
        lines.append("")
        
        # Summary table
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Total Edges | {self.summary.get('total_edges', 0)} |")
        lines.append(f"| Actionable | {self.summary.get('actionable_edges', 0)} |")
        lines.append(f"| Avg EV | {self.summary.get('avg_expected_value', 0)}% |")
        lines.append(f"| Total Units | {self.summary.get('total_recommended_units', 0)} |")
        lines.append("")
        
        # Picks by tier
        for tier in ['SLAM', 'STRONG', 'LEAN']:
            tier_edges = [e for e in self.edges if e.get('tier') == tier and e.get('is_actionable')]
            if tier_edges:
                emoji = {'SLAM': '🔥', 'STRONG': '💪', 'LEAN': '👍'}[tier]
                lines.append(f"## {emoji} {tier} Picks")
                lines.append("")
                lines.append("| Player | Stat | Line | Dir | Proj | Conf | EV | Units |")
                lines.append("|--------|------|------|-----|------|------|----|----|")
                for edge in tier_edges[:5]:
                    lines.append(
                        f"| {edge.get('player_name')} | "
                        f"{edge.get('stat_type')} | "
                        f"{edge.get('primary_line')} | "
                        f"{edge.get('direction')} | "
                        f"{edge.get('projection')} | "
                        f"{edge.get('confidence'):.1%} | "
                        f"{edge.get('expected_value')}% | "
                        f"{edge.get('recommended_units')} |"
                    )
                lines.append("")
        
        lines.append("---")
        lines.append("*Report validated per SOP v2.1*")
        
        return "\n".join(lines)
    
    def _format_pick(self, edge: Dict) -> str:
        """Format a single pick for text output"""
        return (
            f"  {edge.get('player_name')} | "
            f"{edge.get('stat_type')} {edge.get('direction')} {edge.get('primary_line')} | "
            f"Proj: {edge.get('projection')} | "
            f"Conf: {edge.get('confidence'):.1%} | "
            f"EV: {edge.get('expected_value')}% | "
            f"Units: {edge.get('recommended_units')}"
        )


# ============================================================================
# FILE I/O
# ============================================================================

def load_scored_edges(filepath: str) -> Dict:
    """Load scored edges from validation-passed file"""
    with open(filepath, 'r') as f:
        return json.load(f)


def save_reports(renderer: ReportRenderer, output_dir: str):
    """Save all report formats"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Text report
    text_report = renderer.render_text_report()
    with open(f"{output_dir}/report.txt", 'w') as f:
        f.write(text_report)
    
    # JSON report
    json_report = renderer.render_json_report()
    with open(f"{output_dir}/report.json", 'w') as f:
        json.dump(json_report, f, indent=2)
    
    # Markdown report
    md_report = renderer.render_markdown_report()
    with open(f"{output_dir}/report.md", 'w') as f:
        f.write(md_report)


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Report Rendering Pipeline Stage
    
    Usage: python render_report.py [sport] [date]
    
    ⚠️  REQUIRES: validate_output.py must pass first
    """
    print("=" * 60)
    print("SOP v2.1 REPORT RENDERING")
    print("=" * 60)
    
    # SAFETY: Check validation passed
    print("\n🔒 Checking validation gate...")
    if not check_validation_passed():
        print("\n❌ RENDERING BLOCKED")
        print("   Validation gate did not pass.")
        print("   Use run_pipeline.py to ensure correct execution order.")
        sys.exit(1)
    
    print("   ✅ Validation passed")
    
    # Load scored edges
    input_file = "outputs/edges.json"
    if not Path(input_file).exists():
        print(f"\n❌ ERROR: Scored edges not found: {input_file}")
        sys.exit(1)
    
    print(f"\n📂 Loading scored edges from: {input_file}")
    data = load_scored_edges(input_file)
    
    # Render reports
    print("\n📝 Rendering reports...")
    renderer = ReportRenderer(data)
    save_reports(renderer, "outputs")
    
    # Print text report to console
    print("\n" + renderer.render_text_report())
    
    # List generated files
    print("\n📁 Generated Reports:")
    print("   • outputs/report.txt")
    print("   • outputs/report.json")
    print("   • outputs/report.md")
    
    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
