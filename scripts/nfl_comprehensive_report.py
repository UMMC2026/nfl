"""
NFL Comprehensive Report Generator with Telegram Support
Generates detailed analysis reports and sends to Telegram
"""

import json
import sys
import io
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Force UTF-8 encoding for Windows console
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from telegram_push import _send as telegram_send
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


def generate_comprehensive_report(analysis_file: Path) -> str:
    """Generate detailed NFL analysis report."""
    
    with open(analysis_file, 'r') as f:
        data = json.load(f)
    
    # Handle both data formats
    picks = data.get('picks', data.get('results', []))
    
    report = []
    report.append("=" * 80)
    report.append("🏈 NFL COMPREHENSIVE ANALYSIS REPORT")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Total Props Analyzed: {len(picks)}")
    report.append("")
    
    # Group by tier/action
    tiers = {
        'SLAM': [p for p in picks if p.get('tier') == 'SLAM' or p.get('action') == 'SLAM'],
        'STRONG': [p for p in picks if p.get('tier') == 'STRONG' or p.get('action') == 'STRONG' or p.get('grade') in ['A', 'A+']],
        'LEAN': [p for p in picks if p.get('tier') == 'LEAN' or p.get('action') in ['CONSIDER', 'LEAN'] or p.get('grade') == 'B'],
        'NO_PLAY': [p for p in picks if p.get('tier') == 'NO_PLAY' or p.get('action') in ['NO PLAY', 'PASS'] or p.get('grade') in ['C', 'D', 'F']]
    }
    
    # SLAM picks
    if tiers['SLAM']:
        report.append("🔥 SLAM PLAYS (80%+ Confidence)")
        report.append("=" * 80)
        for i, pick in enumerate(tiers['SLAM'], 1):
            report.extend(_format_pick_detailed(pick, i))
        report.append("")
    
    # STRONG picks
    if tiers['STRONG']:
        report.append("💪 STRONG PLAYS (65-79% Confidence)")
        report.append("=" * 80)
        for i, pick in enumerate(tiers['STRONG'], 1):
            report.extend(_format_pick_detailed(pick, i))
        report.append("")
    
    # LEAN picks
    if tiers['LEAN']:
        report.append("⚡ LEAN PLAYS (55-64% Confidence)")
        report.append("=" * 80)
        for i, pick in enumerate(tiers['LEAN'], 1):
            report.extend(_format_pick_detailed(pick, i))
        report.append("")
    
    # NO PLAY summary (condensed)
    if tiers['NO_PLAY']:
        report.append(f"❌ NO PLAY ({len(tiers['NO_PLAY'])} props below threshold)")
        report.append("-" * 80)
        for pick in tiers['NO_PLAY'][:5]:  # Show top 5
            report.append(f"  • {pick.get('player')} - {pick.get('stat')} {pick.get('direction')} {pick.get('line')} ({pick.get('probability', 0)*100:.1f}%)")
        if len(tiers['NO_PLAY']) > 5:
            report.append(f"  ... and {len(tiers['NO_PLAY']) - 5} more")
        report.append("")
    
    # Summary statistics
    report.append("=" * 80)
    report.append("📊 SUMMARY")
    report.append("=" * 80)
    report.append(f"SLAM:      {len(tiers['SLAM'])} picks")
    report.append(f"STRONG:    {len(tiers['STRONG'])} picks")
    report.append(f"LEAN:      {len(tiers['LEAN'])} picks")
    report.append(f"NO PLAY:   {len(tiers['NO_PLAY'])} picks")
    report.append("")
    
    playable = len(tiers['SLAM']) + len(tiers['STRONG']) + len(tiers['LEAN'])
    if playable > 0:
        probs = [p.get('probability', 0) if isinstance(p.get('probability'), float) else 0 
                 for p in picks if p.get('tier') not in ['NO_PLAY'] or p.get('action') not in ['NO PLAY', 'PASS']]
        if probs:
            avg_prob = sum(probs) / len(probs)
            report.append(f"Average Confidence (Playable): {avg_prob*100:.1f}%")
        report.append(f"Recommended Parlays: {min(3, playable)} legs")
    else:
        report.append("⚠️  No playable picks found. Consider lowering thresholds or analyzing different slate.")
    
    report.append("=" * 80)
    
    return "\n".join(report)


def _format_pick_detailed(pick: Dict[str, Any], index: int) -> List[str]:
    """Format a single pick with full details."""
    lines = []
    
    lines.append(f"\n#{index} ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"👤 {pick.get('player', 'Unknown')} ({pick.get('team', 'N/A')})")
    lines.append(f"📊 {pick.get('stat', '').upper()} {pick.get('direction', '').upper()} {pick.get('line', 0)}")
    lines.append("")
    
    # Handle both probability formats (0-1 decimal or 0-100 percentage)
    prob = pick.get('probability', 0)
    if isinstance(prob, (int, float)):
        prob_pct = prob * 100 if prob <= 1.0 else prob
    else:
        prob_pct = 0
    
    edge = pick.get('edge', 0) or 0
    recent_avg = pick.get('mu', pick.get('recent_avg', 0)) or 0
    sigma = pick.get('sigma', 0) or 0
    sample_n = pick.get('sample_n', pick.get('sample_size', 0)) or 0
    gap = pick.get('gap', pick.get('line_gap', 0)) or 0
    
    lines.append(f"   Confidence:    {prob_pct:.1f}%")
    lines.append(f"   Edge:          {edge:+.1f}%")
    lines.append(f"   Recent Avg:    {recent_avg:.1f} (σ={sigma:.1f}, n={sample_n})")
    lines.append(f"   Line Gap:      {gap:+.1f} pts")
    
    # Additional context if available
    if pick.get('opponent'):
        lines.append(f"   vs Opponent:   {pick['opponent']}")
    
    if pick.get('usage_rate'):
        lines.append(f"   Usage Rate:    {pick['usage_rate']:.1f}%")
    
    if pick.get('specialist'):
        lines.append(f"   Specialist:    {pick['specialist']}")
    
    if pick.get('risk_flags'):
        lines.append(f"   ⚠️ Risk Flags: {', '.join(pick['risk_flags'])}")
    
    # Show grade if present
    if pick.get('grade'):
        lines.append(f"   Grade:         {pick['grade']}")
    
    lines.append("─" * 78)
    
    return lines


def generate_telegram_message(analysis_file: Path, ai_commentary: str = None) -> str:
    """Generate Telegram-formatted message - TOP 10 picks only."""
    
    with open(analysis_file, 'r') as f:
        data = json.load(f)
    
    # Handle both data formats
    picks = data.get('picks', data.get('results', []))
    
    # Filter to playable picks only (not including NO PLAY or low grades)
    playable = [p for p in picks 
                if p.get('tier') in ['SLAM', 'STRONG', 'LEAN'] 
                or p.get('action') in ['SLAM', 'STRONG', 'CONSIDER', 'LEAN']
                or p.get('grade') in ['A+', 'A', 'B']]
    
    if not playable:
        return "❌ No playable NFL picks found for today.\nAll props below confidence threshold."
    
    # Sort by probability and take TOP 10
    def get_prob(p):
        prob = p.get('probability', 0)
        return prob * 100 if prob <= 1.0 else prob
    
    playable.sort(key=get_prob, reverse=True)
    top_10 = playable[:10]
    
    message = "🏈 *NFL TOP 10 PICKS*\n"
    message += "=" * 40 + "\n\n"
    
    # Display top 10 with ranking
    for i, pick in enumerate(top_10, 1):
        emoji = "📈" if pick.get('direction', '').lower() in ['higher', 'over'] else "📉"
        prob = get_prob(pick)
        
        # Tier badge
        tier = pick.get('tier') or pick.get('action', '')
        grade = pick.get('grade', '')
        if tier == 'SLAM' or grade == 'A+':
            badge = "🔥"
        elif tier == 'STRONG' or grade == 'A':
            badge = "💪"
        else:
            badge = "⚡"
        
        message += f"{badge} *#{i}* - {pick.get('player')} ({pick.get('team', 'N/A')})\n"
        message += f"   {emoji} {pick.get('stat', '').upper()} {pick.get('direction', '').upper()} {pick.get('line', 0)}\n"
        message += f"   💯 {prob:.1f}% confidence"
        
        # Add opponent if available
        if pick.get('opponent'):
            message += f" | vs {pick['opponent']}"
        
        message += "\n\n"
    
    message += "=" * 40 + "\n"
    message += f"📊 Showing Top {len(top_10)} of {len(playable)} Playable\n"
    message += "🎯 Risk-First Analysis | Drive-Level MC\n"
    
    # Add AI commentary if provided
    if ai_commentary:
        message += "\n💬 *AI INSIGHTS*\n"
        message += ai_commentary[:400]  # Truncate if too long
    
    return message


def send_to_telegram(message: str) -> bool:
    """Send message to Telegram."""
    if not TELEGRAM_AVAILABLE:
        print("⚠️  Telegram module not available")
        return False
    
    try:
        if telegram_send(message):
            print("✅ Message sent to Telegram!")
            return True
        else:
            print("⚠️  Telegram send failed (check bot token/chat ID)")
            return False
    except Exception as e:
        print(f"⚠️  Telegram error: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate NFL comprehensive reports")
    parser.add_argument("--file", type=str, help="Path to NFL analysis JSON file")
    parser.add_argument("--telegram", action="store_true", help="Send to Telegram")
    parser.add_argument("--output", type=str, help="Output file path for report")
    parser.add_argument("--with-ai", action="store_true", help="Include AI commentary")
    
    args = parser.parse_args()
    
    # Find latest NFL analysis file if not specified
    if not args.file:
        outputs_dir = Path("outputs")
        nfl_files = sorted(outputs_dir.glob("nfl_analysis_*.json"), reverse=True)
        if not nfl_files:
            print("❌ No NFL analysis files found in outputs/")
            sys.exit(1)
        args.file = str(nfl_files[0])
        print(f"📁 Using latest file: {args.file}")
    
    analysis_file = Path(args.file)
    
    if not analysis_file.exists():
        print(f"❌ File not found: {analysis_file}")
        sys.exit(1)
    
    # Generate AI commentary if requested or if sending to Telegram
    ai_commentary = None
    if args.with_ai or args.telegram:
        sys.path.insert(0, str(Path(__file__).parent.parent / "engines" / "nfl"))
        try:
            from nfl_ai_commentary import add_commentary_to_analysis
            print("🤖 Generating AI commentary...")
            ai_commentary = add_commentary_to_analysis(analysis_file)
        except Exception as e:
            print(f"⚠️  AI commentary failed: {e}")
            ai_commentary = None
    
    # Generate comprehensive report
    if not args.telegram:
        print("\n🏈 Generating comprehensive NFL report...\n")
        report = generate_comprehensive_report(analysis_file)
        print(report)
        
        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"\n💾 Report saved to: {args.output}")
    
    # Send to Telegram if requested
    if args.telegram:
        print("\n📱 Generating Telegram message...")
        telegram_msg = generate_telegram_message(analysis_file, ai_commentary)
        
        # Show message preview
        print("\n" + "=" * 80)
        print("TELEGRAM MESSAGE PREVIEW")
        print("=" * 80)
        print(telegram_msg)
        print("=" * 80)
        
        # Send
        send_to_telegram(telegram_msg)
