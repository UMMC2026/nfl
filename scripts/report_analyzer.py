#!/usr/bin/env python
"""
Report analyzer - extracts top picks and betting recommendations
from generated cheatsheet reports.
"""
import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple


def parse_cheatsheet(filepath: str) -> Dict:
    """Parse a cheatsheet report and extract key sections."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    result = {
        'generated_at': None,
        'slam_plays': [],
        'strong_plays': [],
        'lean_plays': [],
        'top_overs': [],
        'top_unders': [],
        'availability_flags': [],
        'high_volatility': []
    }
    
    lines = content.split('\n')
    
    current_section = None
    
    for i, line in enumerate(lines):
        # Detect section headers
        if 'SLAM PLAYS' in line:
            current_section = 'slam_plays'
            continue
        elif 'STRONG PLAYS' in line:
            current_section = 'strong_plays'
            continue
        elif 'LEAN PLAYS' in line:
            current_section = 'lean_plays'
            continue
        elif 'TOP OVERS' in line:
            current_section = 'top_overs'
            continue
        elif 'TOP UNDERS' in line:
            current_section = 'top_unders'
            continue
        elif 'HIGH VOLATILITY' in line:
            current_section = 'high_volatility'
            continue
        elif 'AVAILABILITY FLAGS' in line:
            current_section = 'availability_flags'
            continue
        
        # Parse content
        if current_section and line.strip():
            if current_section in ['slam_plays', 'strong_plays', 'lean_plays']:
                if '•' in line:
                    # Extract pick info from formatted line
                    # Format: • Player DIRECTION LINE stat (avg: X) [CONF%] [INJURY: STATUS]
                    match = re.search(
                        r'•\s+([A-Za-z\s]+?)\s+(OVER|UNDER)\s+([\d.]+)\s+([a-z+\s]+?)\s+\(avg:\s+([\d.]+)\)\s+\[(\d+)%\]',
                        line
                    )
                    if match:
                        pick = {
                            'player': match.group(1).strip(),
                            'direction': match.group(2),
                            'line': float(match.group(3)),
                            'stat': match.group(4).strip(),
                            'avg': float(match.group(5)),
                            'confidence': int(match.group(6))
                        }
                        result[current_section].append(pick)
            
            elif current_section in ['top_overs', 'top_unders']:
                if re.match(r'^\s*\d+\s+', line):
                    # Table row
                    parts = line.split()
                    if len(parts) >= 5:
                        pick = {
                            'rank': int(parts[0]),
                            'player': ' '.join(parts[1:-3]),
                            'line': float(parts[-3]),
                            'avg': float(parts[-2]),
                            'confidence': int(parts[-1].rstrip('%'))
                        }
                        result[current_section].append(pick)
            
            elif current_section == 'high_volatility':
                if '!' in line:
                    # Extract volatility info
                    match = re.search(
                        r'!\s+([A-Za-z\s]+?)\s+(\w+[\w\s]*?)\s+std=\s*([\d.]+)',
                        line
                    )
                    if match:
                        vol = {
                            'player': match.group(1).strip(),
                            'stat': match.group(2).strip(),
                            'std_dev': float(match.group(3))
                        }
                        result['high_volatility'].append(vol)
            
            elif current_section == 'availability_flags':
                if '⛔' in line:
                    # Extract flag info
                    match = re.search(
                        r'([A-Za-z\s]+?)\s+(OVER|UNDER)\s+(\d+\.?\d*)\s+(\w+[\w\s]*?)\s+(UNKNOWN|ACTIVE|OUT)',
                        line
                    )
                    if match:
                        flag = {
                            'player': match.group(1).strip(),
                            'direction': match.group(2),
                            'line': float(match.group(3)),
                            'stat': match.group(4).strip(),
                            'status': match.group(5)
                        }
                        result['availability_flags'].append(flag)
    
    return result


def get_top_picks(report: Dict, min_confidence: int = 60) -> List[Dict]:
    """Extract top actionable picks by confidence."""
    picks = []
    
    # Add slam plays (weighted 1.0x)
    for pick in report['slam_plays']:
        pick['category'] = 'SLAM'
        pick['weight'] = 1.0
        picks.append(pick)
    
    # Add strong plays (weighted 0.8x)
    for pick in report['strong_plays']:
        pick['category'] = 'STRONG'
        pick['weight'] = 0.8
        picks.append(pick)
    
    # Add lean plays if above threshold
    for pick in report['lean_plays']:
        if pick['confidence'] >= min_confidence:
            pick['category'] = 'LEAN'
            pick['weight'] = 0.6
            picks.append(pick)
    
    # Sort by confidence
    picks.sort(key=lambda x: x['confidence'], reverse=True)
    
    return picks


def recommend_bet_sizing(picks: List[Dict]) -> Dict:
    """Generate bet sizing recommendations."""
    recommendations = {}
    
    if not picks:
        return {'status': 'insufficient_picks', 'message': 'No qualifying picks found'}
    
    # Group by confidence level
    high = [p for p in picks if p['confidence'] >= 70]
    medium = [p for p in picks if 60 <= p['confidence'] < 70]
    low = [p for p in picks if 50 <= p['confidence'] < 60]
    
    recommendations['high_confidence_picks'] = len(high)
    recommendations['medium_confidence_picks'] = len(medium)
    recommendations['low_confidence_picks'] = len(low)
    
    # Kelly Criterion approximation (conservative)
    if high:
        # For 65%+ confidence, 1-2 units on individual picks
        recommendations['unit_sizing'] = {
            'slam': '2 units (75%+ confidence)',
            'strong': '1 unit (60-74% confidence)',
            'lean': '0.5 units (50-59% confidence)',
            'parlay': 'Avoid 4+ legs unless 80%+ on each'
        }
    else:
        recommendations['unit_sizing'] = {
            'note': 'Low confidence day - consider reduced sizing'
        }
    
    # Parlay recommendations
    if len(picks) >= 2:
        highest = picks[:2]
        avg_conf = sum(p['confidence'] for p in highest) / 2
        
        if avg_conf >= 75:
            recommendations['parlay_recommendation'] = f"2-leg parlay possible (avg {avg_conf:.0f}%)"
        elif avg_conf >= 65:
            recommendations['parlay_recommendation'] = "Skip parlay - individual picks safer"
        else:
            recommendations['parlay_recommendation'] = "Do NOT parlay - insufficient confidence"
    
    return recommendations


def print_analysis(report: Dict):
    """Print formatted analysis of report."""
    print("\n" + "="*70)
    print("  CHEATSHEET ANALYSIS & BETTING RECOMMENDATIONS")
    print("="*70)
    
    # Summary
    print("\n📊 PICK SUMMARY:")
    print(f"  Slam Plays (75%+):     {len(report['slam_plays']):2d}")
    print(f"  Strong Plays (60-74%): {len(report['strong_plays']):2d}")
    print(f"  Lean Plays (50-59%):   {len(report['lean_plays']):2d}")
    print(f"  Total Actionable:      {len(report['slam_plays']) + len(report['strong_plays']) + len(report['lean_plays']):2d}")
    
    # Top picks
    top_picks = get_top_picks(report, min_confidence=60)
    
    if top_picks:
        print("\n🎯 TOP PICKS (60%+ Confidence):")
        print("-" * 70)
        
        for i, pick in enumerate(top_picks[:5], 1):
            player = pick['player'][:20]
            direction = pick['direction']
            line = pick['line']
            stat = pick['stat'][:15]
            conf = pick['confidence']
            category = pick['category']
            
            emoji_map = {'SLAM': '🔥', 'STRONG': '💪', 'LEAN': '📊'}
            emoji = emoji_map.get(category, '📌')
            
            print(f"  {i}. {emoji} {player:20} {direction:5} {line:6.1f} {stat:15} [{conf:3d}%]")
    else:
        print("\n⚠️  No picks meeting confidence threshold (60%+)")
    
    # Betting recommendations
    print("\n💰 BETTING RECOMMENDATIONS:")
    print("-" * 70)
    
    sizing = recommend_bet_sizing(top_picks)
    
    if 'unit_sizing' in sizing:
        print("  Unit Sizing:")
        for level, size in sizing['unit_sizing'].items():
            print(f"    {level.upper():10} → {size}")
    
    if 'parlay_recommendation' in sizing:
        print(f"\n  Parlay Recommendation: {sizing['parlay_recommendation']}")
    
    # Risk summary
    print("\n⚠️  RISK ASSESSMENT:")
    print("-" * 70)
    
    volatility = sorted(report['high_volatility'], key=lambda x: x['std_dev'], reverse=True)
    if volatility:
        print(f"  High Volatility Players (avoid parlays with these):")
        for vol in volatility[:3]:
            print(f"    • {vol['player']:20} {vol['stat']:15} (σ={vol['std_dev']:.1f})")
    
    flags = [f for f in report['availability_flags'] if f['status'] in ['UNKNOWN', 'DOUBTFUL']]
    if flags:
        print(f"\n  Injury Flags to Monitor ({len(flags)} players):")
        for flag in flags[:3]:
            print(f"    • {flag['player']:20} ({flag['status']})")
    
    print("\n" + "="*70)


def main():
    """Find and analyze latest cheatsheet."""
    outputs_dir = Path(__file__).parent.parent / "outputs"
    
    # Find latest STATISTICAL cheatsheet
    reports = sorted(
        outputs_dir.glob("CHEATSHEET_*_STATISTICAL.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not reports:
        print("❌ No cheatsheet reports found. Run generate_cheatsheet.py first.")
        return
    
    latest_report = reports[0]
    print(f"📄 Analyzing: {latest_report.name}")
    
    # Parse and analyze
    report = parse_cheatsheet(str(latest_report))
    print_analysis(report)
    
    # Save analysis as JSON for external use
    json_output = outputs_dir / f"{latest_report.stem}_analysis.json"
    with open(json_output, 'w') as f:
        # Convert for JSON serialization
        clean_report = {k: v for k, v in report.items()}
        json.dump(clean_report, f, indent=2)
    
    print(f"\n✅ Analysis saved to: {json_output.name}")


if __name__ == "__main__":
    main()
