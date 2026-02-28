"""
Tennis Report Renderer
======================
Render final tennis picks report.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

TENNIS_DIR = Path(__file__).parent
OUTPUTS_DIR = TENNIS_DIR / "outputs"


def load_latest_scored() -> Dict:
    """Load latest scored tennis edges."""
    filepath = OUTPUTS_DIR / "tennis_scored_latest.json"
    if filepath.exists():
        return json.loads(filepath.read_text())
    return None


def render_text_report(data: Dict) -> str:
    """Render plain text report."""
    lines = []
    
    lines.append("=" * 70)
    lines.append("🎾 TENNIS MATCH WINNER ANALYSIS")
    lines.append(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 70)
    
    edges = data.get("edges", [])
    # Scored output now includes all edges; only render playable (non-blocked and not avoid/no_play)
    playable = [
        e for e in edges
        if not e.get("blocked")
        and str(e.get("tier") or "").upper() not in {"AVOID", "NO_PLAY", "BLOCKED"}
    ]
    slam = [e for e in playable if str(e.get("tier") or "").upper() == "SLAM"]
    strong = [e for e in playable if str(e.get("tier") or "").upper() == "STRONG"]
    lean = [e for e in playable if str(e.get("tier") or "").upper() == "LEAN"]
    
    lines.append(f"\n📊 SUMMARY: {len(slam)} SLAM | {len(strong)} STRONG | {len(lean)} LEAN")
    lines.append("")

    if slam:
        lines.append("🔥 SLAM PLAYS")
        lines.append("-" * 50)
        for e in slam:
            lines.append(f"\n  #{e.get('rank', '?')} {e['player'].upper()}")
            lines.append(f"     vs {e['opponent']} | {e['surface']} {e['round']}")
            lines.append(f"     Tour: {e.get('tour', 'ATP')}")
            lines.append(f"     Model: {e['probability']:.1%} | Line: {e.get('line', '?')}")
            lines.append(f"     Edge: {e['edge']:+.1%} | Score: {e.get('score', 0):.4f}")
    
    if strong:
        lines.append("🔥 STRONG PLAYS")
        lines.append("-" * 50)
        for e in strong:
            lines.append(f"\n  #{e.get('rank', '?')} {e['player'].upper()}")
            lines.append(f"     vs {e['opponent']} | {e['surface']} {e['round']}")
            lines.append(f"     Tour: {e.get('tour', 'ATP')}")
            lines.append(f"     Model: {e['probability']:.1%} | Line: {e.get('line', '?')}")
            lines.append(f"     Edge: {e['edge']:+.1%} | Score: {e.get('score', 0):.4f}")
    
    if lean:
        lines.append("\n\n📈 LEAN PLAYS")
        lines.append("-" * 50)
        for e in lean:
            lines.append(f"\n  #{e.get('rank', '?')} {e['player'].upper()}")
            lines.append(f"     vs {e['opponent']} | {e['surface']} {e['round']}")
            lines.append(f"     Model: {e['probability']:.1%} | Edge: {e['edge']:+.1%}")
    
    lines.append("\n" + "=" * 70)
    lines.append("⚠️  Singles only. Match winner market only. Pre-match only.")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def render_report(data: Dict = None, save: bool = True) -> str:
    """Render and optionally save report."""
    
    if data is None:
        data = load_latest_scored()
    
    if not data:
        print("✗ No scored edges found")
        return ""
    
    report = render_text_report(data)
    
    if save:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        report_file = OUTPUTS_DIR / f"tennis_report_{timestamp}.txt"
        report_file.write_text(report, encoding='utf-8')
        
        # Also save as latest
        latest_file = OUTPUTS_DIR / "tennis_report_latest.txt"
        latest_file.write_text(report, encoding='utf-8')
        
        print(f"✓ Report saved: {report_file}")
    
    return report


if __name__ == "__main__":
    report = render_report()
    print(report)
