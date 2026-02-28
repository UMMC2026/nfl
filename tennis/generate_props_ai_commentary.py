"""tennis/generate_props_ai_commentary.py

AI Commentary Generator for Tennis Props
=========================================
Generates narrative analysis for TENNIS_CALIBRATED reports using DeepSeek API.

Architecture:
- Layer 2 (LLM Adapter) — produces evidence-based language
- Language rules: "data suggests", "may indicate" — NO imperatives
- NEVER overrides Monte Carlo probabilities
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

TENNIS_DIR = Path(__file__).parent


def _call_deepseek(prompt: str, max_tokens: int = 120) -> Optional[str]:
    """Call DeepSeek API. Returns None on failure."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    try:
        import requests
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.4,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [DeepSeek API Error: {e}]")
    return None


def _parse_calibrated_report(report_path: Path) -> Dict:
    """Parse TENNIS_CALIBRATED report and extract structured data."""
    if not report_path.exists():
        return {}
    
    content = report_path.read_text(encoding='utf-8')
    
    result = {
        'surface': None,
        'timestamp': None,
        'total_playable': 0,
        'strong_picks': [],
        'lean_picks': [],
        'avoid_picks': []
    }
    
    # Extract surface
    surface_match = re.search(r'Surface:\s*(\w+)', content)
    if surface_match:
        result['surface'] = surface_match.group(1)
    
    # Extract timestamp
    time_match = re.search(r'Generated:\s*(.+)', content)
    if time_match:
        result['timestamp'] = time_match.group(1).strip()
    
    # Parse STRONG picks
    strong_section = re.search(r'\[STRONG\].*?\-{70,}(.*?)(?:\[LEAN\]|\[AVOID\]|={70,})', content, re.DOTALL)
    if strong_section:
        result['strong_picks'] = _parse_prop_lines(strong_section.group(1))
    
    # Parse LEAN picks
    lean_section = re.search(r'\[LEAN\].*?\-{70,}(.*?)(?:\[AVOID\]|={70,})', content, re.DOTALL)
    if lean_section:
        result['lean_picks'] = _parse_prop_lines(lean_section.group(1))
    
    result['total_playable'] = len(result['strong_picks']) + len(result['lean_picks'])
    
    return result


def _parse_prop_lines(section: str) -> List[Dict]:
    """Parse individual prop lines from a section."""
    props = []
    lines = section.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('-') or line.startswith('PLAYER'):
            continue
        
        # Parse: PLAYER  PICK  LINE  PROB  n
        parts = line.split()
        if len(parts) < 5:
            continue
        
        try:
            # Extract player (may be multiple words)
            player_parts = []
            i = 0
            while i < len(parts) and not parts[i].isupper() or parts[i] in ['HIGHER', 'LOWER']:
                if parts[i] not in ['HIGHER', 'LOWER']:
                    player_parts.append(parts[i])
                else:
                    break
                i += 1
            
            player = ' '.join(player_parts)
            
            # Find direction
            direction = None
            direction_idx = -1
            for idx, part in enumerate(parts):
                if part in ['HIGHER', 'LOWER']:
                    direction = part
                    direction_idx = idx
                    break
            
            if not direction:
                continue
            
            # Stat is between direction and line
            stat_parts = parts[direction_idx + 1:-3]
            stat = '_'.join(stat_parts)
            
            # Extract line, prob, n
            line = float(parts[-3])
            prob = int(parts[-2].rstrip('%'))
            sample_n = int(parts[-1].split('[')[0])
            
            props.append({
                'player': player,
                'direction': direction,
                'stat': stat,
                'line': line,
                'probability': prob,
                'sample_n': sample_n
            })
        except (ValueError, IndexError) as e:
            # Skip malformed lines
            continue
    
    return props


def _generate_ai_commentary(prop: Dict, surface: str) -> str:
    """Generate AI commentary for a single prop using DeepSeek."""
    player = prop['player']
    stat = prop['stat'].replace('_', ' ')
    direction = prop['direction'].lower()
    line = prop['line']
    prob = prop['probability']
    n = prop['sample_n']
    
    prompt = f"""You are a tennis betting analyst. Generate a concise one-sentence insight (max 25 words) for this prop bet using evidence-based language ('data suggests', 'may indicate', 'stats show'):

Player: {player}
Prop: {direction.upper()} {stat} {line}
Probability: {prob}%
Sample size: {n} matches
Surface: {surface}

Focus on: recent form, surface performance, statistical trends, or matchup dynamics. Be specific but concise. NO imperatives like "bet this" or "lock in"."""

    commentary = _call_deepseek(prompt, max_tokens=50)
    if not commentary:
        # Fallback to data-driven narrative
        if prob >= 70:
            strength = "exceptional statistical edge"
        elif prob >= 65:
            strength = "strong historical trend"
        else:
            strength = "consistent baseline performance"
        
        commentary = f"Monte Carlo projects {direction} probability based on {strength} from {n} match sample."
    
    return commentary


def generate_props_ai_report(report_path: Path, use_ai: bool = True) -> str:
    """
    Generate AI commentary report for Tennis Props.
    
    Args:
        report_path: Path to TENNIS_CALIBRATED_*.txt report
        use_ai: Use DeepSeek API for enhanced commentary
    
    Returns:
        Formatted AI report as string
    """
    data = _parse_calibrated_report(report_path)
    
    if not data or data['total_playable'] == 0:
        return "No playable props found in report."
    
    # Build report
    lines = []
    lines.append("=" * 75)
    lines.append("  TENNIS PROPS — AI COMMENTARY & ANALYSIS")
    lines.append("=" * 75)
    lines.append(f"  Source: {report_path.name}")
    lines.append(f"  Surface: {data['surface'] or 'Unknown'}")
    lines.append(f"  Analysis Generated: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    lines.append("=" * 75)
    lines.append("")
    
    # Summary
    lines.append("  PLAYABLE PROPS SUMMARY")
    lines.append("  " + "-" * 40)
    lines.append(f"  Total Playable: {data['total_playable']}")
    lines.append(f"  STRONG (62-70%): {len(data['strong_picks'])}")
    lines.append(f"  LEAN (55-62%): {len(data['lean_picks'])}")
    lines.append("")
    
    # STRONG Commentary
    if data['strong_picks']:
        lines.append("  [STRONG PLAYS] — BOLD BETS")
        lines.append("  " + "=" * 73)
        for i, prop in enumerate(data['strong_picks'], 1):
            lines.append(f"\n  {i}. {prop['player']} — {prop['direction']} {prop['stat'].replace('_', ' ')} {prop['line']}")
            lines.append(f"     Confidence: {prop['probability']}% | Sample: {prop['sample_n']} matches")
            
            if use_ai and os.getenv("DEEPSEEK_API_KEY"):
                commentary = _generate_ai_commentary(prop, data['surface'] or 'Hard')
                lines.append(f"     💡 {commentary}")
            else:
                lines.append(f"     💡 MC projects {prop['probability']}% edge from {prop['sample_n']} match sample.")
            lines.append("")
    
    # LEAN Commentary
    if data['lean_picks']:
        lines.append("  [LEAN PLAYS] — FILLER LEGS")
        lines.append("  " + "=" * 73)
        
        # Group by player for readability
        by_player = {}
        for prop in data['lean_picks']:
            player = prop['player']
            if player not in by_player:
                by_player[player] = []
            by_player[player].append(prop)
        
        for player, props in by_player.items():
            lines.append(f"\n  {player} ({len(props)} props)")
            lines.append("  " + "-" * 40)
            
            for prop in props:
                lines.append(f"    • {prop['direction']} {prop['stat'].replace('_', ' ')} {prop['line']} ({prop['probability']}%, n={prop['sample_n']})")
                
                if use_ai and os.getenv("DEEPSEEK_API_KEY"):
                    commentary = _generate_ai_commentary(prop, data['surface'] or 'Hard')
                    lines.append(f"      {commentary}")
                else:
                    lines.append(f"      Statistical baseline from {prop['sample_n']} matches.")
            lines.append("")
    
    # Strategy Section
    lines.append("=" * 75)
    lines.append("  RECOMMENDED STRATEGY")
    lines.append("=" * 75)
    lines.append(f"  • Target: 2-4 leg parlays mixing STRONG + LEAN")
    lines.append(f"  • Max {min(2, len(data['strong_picks']))} STRONG per entry")
    lines.append(f"  • Diversify across players (avoid correlation)")
    lines.append(f"  • [CORR] tagged props = DO NOT combine")
    lines.append("")
    lines.append("  Governance: SOP v2.1 — One player, one bet per match")
    lines.append("  Probabilities: 2,000 Monte Carlo simulations per prop")
    lines.append("=" * 75)
    
    return '\n'.join(lines)


def save_props_ai_report(report_path: Path, use_ai: bool = True) -> Optional[Path]:
    """Generate and save AI commentary report."""
    try:
        ai_report = generate_props_ai_report(report_path, use_ai=use_ai)
        
        # Save to outputs
        output_dir = TENNIS_DIR / "outputs"
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"TENNIS_PROPS_AI_REPORT_{timestamp}.txt"
        output_path = output_dir / filename
        
        output_path.write_text(ai_report, encoding='utf-8')
        
        return output_path
    except Exception as e:
        print(f"  Error generating AI report: {e}")
        return None


def main():
    """CLI entry point for generating AI commentary."""
    outputs_dir = TENNIS_DIR / "outputs"
    
    # Find latest TENNIS_CALIBRATED report
    reports = sorted(outputs_dir.glob("TENNIS_CALIBRATED_*.txt"), reverse=True)
    
    if not reports:
        print("✗ No TENNIS_CALIBRATED reports found. Run Props analysis first.")
        return
    
    latest = reports[0]
    print(f"📊 Analyzing: {latest.name}")
    print(f"🤖 Generating AI commentary...")
    
    use_ai = bool(os.getenv("DEEPSEEK_API_KEY"))
    if not use_ai:
        print("⚠️  DEEPSEEK_API_KEY not found — using fallback narratives")
    
    output_path = save_props_ai_report(latest, use_ai=use_ai)
    
    if output_path:
        print(f"\n✅ AI Report saved: {output_path.name}")
        print(f"📄 Reading report...")
        print("\n" + output_path.read_text(encoding='utf-8'))
    else:
        print("✗ Failed to generate report")


if __name__ == "__main__":
    main()
