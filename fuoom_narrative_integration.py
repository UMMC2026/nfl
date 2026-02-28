"""
FUOOM NARRATIVE INTEGRATION
Connects narrative templates to your existing FUOOM pipeline

Usage:
    from fuoom_narrative_integration import generate_fuoom_narrative_report
    
    # Load your existing picks JSON
    with open('outputs/FRYDAY8DAT_RISK_FIRST_20260130_FROM_UD.json') as f:
        picks_data = json.load(f)
    
    # Generate narrative report
    report = generate_fuoom_narrative_report(picks_data, "FRIDAY NBA")
    
    # Save it
    with open('outputs/FRIDAY_NARRATIVE_REPORT.txt', 'w') as f:
        f.write(report)
"""

import json
from datetime import datetime
from pathlib import Path

# Import the template system
from narrative_templates import (
    get_template, 
    format_stat_display,
    format_stat_full_name,
    format_direction_verb,
    format_edge_display,
    format_sigma_display,
    format_kelly_display,
    get_tier_name
)

from reason_generator import (
    generate_reasons,
    generate_risks,
    generate_primary_reason,
    format_reasons_as_bullets,
    format_risks_as_bullets
)


# ═══════════════════════════════════════════════════════════════════
# FUOOM DATA ADAPTER
# ═══════════════════════════════════════════════════════════════════

def adapt_fuoom_pick_to_narrative(pick):
    """
    Convert FUOOM pick format to narrative template format
    
    Your FUOOM picks have fields like:
    - player, team, opponent, stat, line, direction
    - mu, sigma, effective_confidence, edge, z_score
    - sample_n
    
    We enrich with additional fields for better narratives.
    """
    
    # Get confidence (handle different field names in FUOOM output)
    confidence = (
        pick.get('effective_confidence') or 
        pick.get('status_confidence') or 
        pick.get('model_confidence') or 
        pick.get('confidence') or 
        pick.get('eff%') or 
        pick.get('prob', 0)
    )
    
    # Get sample size (handle different field names)
    sample_size = pick.get('sample_n') or pick.get('n') or pick.get('sample_size', 10)
    
    # Get mu (handle different field names)
    mu = pick.get('mu') or pick.get('recent_avg') or pick.get('mean', 0)
    
    # Base fields (from your data)
    adapted = {
        'player': pick.get('player', 'Unknown'),
        'player_name': pick.get('player', 'Unknown'),
        'team': pick.get('team', 'UNK'),
        'opponent': pick.get('opponent', 'OPP') if pick.get('opponent', 'UNK') != 'UNK' else 'OPP',
        'stat': pick.get('stat', ''),
        'line': pick.get('line', 0),
        'direction': pick.get('direction', 'higher'),
        'mu': mu,
        'sigma': pick.get('sigma', 0),
        'confidence': confidence,
        'edge': pick.get('edge', 0),
        'z_score': pick.get('z_score', 0),
        'sample_size': sample_size,
        'n': sample_size,
    }
    
    # Calculate Kelly percentage (if not provided)
    if 'kelly_pct' not in pick:
        # Simple Kelly: edge * confidence
        edge_decimal = (confidence / 100) - 0.5  # Convert to decimal edge over 50%
        kelly = max(0, min(edge_decimal * 2 * 100, 25))  # Cap at 25%
        adapted['kelly_pct'] = kelly
    else:
        adapted['kelly_pct'] = pick.get('kelly_pct', 0)
    
    # Estimate recent hits from confidence (approximation)
    if 'recent_hits' not in pick:
        adapted['recent_hits'] = int((confidence / 100) * sample_size)
        adapted['recent_total'] = sample_size
    else:
        adapted['recent_hits'] = pick.get('recent_hits')
        adapted['recent_total'] = pick.get('recent_total', 10)
    
    # Add placeholder context (can be enhanced later with real data)
    adapted['location'] = pick.get('location', 'unknown')
    adapted['home_boost'] = pick.get('home_boost', 1.0)
    adapted['opponent_rank'] = pick.get('opponent_rank')
    
    # Calculate coefficient of variation (for risk assessment)
    if adapted['mu'] > 0:
        adapted['consistency_cv'] = adapted['sigma'] / adapted['mu']
    else:
        adapted['consistency_cv'] = 0.5
    
    return adapted


def enhance_fuoom_pick_with_narrative(pick):
    """
    Main function: Take a FUOOM pick and generate narrative
    """
    
    # Adapt FUOOM data format
    adapted_pick = adapt_fuoom_pick_to_narrative(pick)
    
    # Select template based on confidence
    template = get_template(adapted_pick['confidence'])
    
    # Generate reasons and risks
    reasons = generate_reasons(adapted_pick)
    risks = generate_risks(adapted_pick)
    primary_reason = generate_primary_reason(adapted_pick)
    
    # Format display strings
    template_data = {
        # Player & pick basics
        'player_name': adapted_pick['player_name'],
        'stat_display': format_stat_display(
            adapted_pick['stat'], 
            adapted_pick['line'], 
            adapted_pick['direction']
        ),
        'stat_full_name': format_stat_full_name(adapted_pick['stat']),
        'direction_verb': format_direction_verb(adapted_pick['direction']),
        'line': adapted_pick['line'],
        'opponent': adapted_pick['opponent'],
        'confidence': adapted_pick['confidence'],
        
        # Core stats
        'mu': adapted_pick['mu'],
        'sigma': adapted_pick['sigma'],
        'z_score': adapted_pick['z_score'],
        'kelly_pct': adapted_pick['kelly_pct'],
        
        # Narrative components
        'primary_reason': primary_reason,
        'reason_bullets': format_reasons_as_bullets(reasons),
        'risk_bullets': format_risks_as_bullets(risks),
        
        # Formatted displays
        'edge_display': format_edge_display(adapted_pick['edge'], adapted_pick['stat']),
        'sigma_display': format_sigma_display(adapted_pick['z_score']),
        'kelly_display': format_kelly_display(adapted_pick['kelly_pct']),
        'tier_name': get_tier_name(adapted_pick['confidence']),
    }
    
    # Fill template
    narrative = template.format(**template_data)
    
    return narrative


# ═══════════════════════════════════════════════════════════════════
# FUOOM REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════════

def generate_fuoom_narrative_report(picks_data, slate_name="DAILY PICKS"):
    """
    Generate full narrative report from FUOOM picks data
    
    Args:
        picks_data: Either:
            - List of pick dicts
            - Dict with 'picks' key containing list
            - Path to JSON file
        slate_name: Report title
    
    Returns:
        String: Full formatted narrative report
    """
    
    # Handle different input formats
    if isinstance(picks_data, (str, Path)):
        # Load from file
        with open(picks_data, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract picks array - check common keys
        if isinstance(data, dict):
            picks = data.get('results', data.get('picks', data.get('entries', [])))
        else:
            picks = data
    
    elif isinstance(picks_data, dict):
        # Extract from dict - check common keys
        picks = picks_data.get('results', picks_data.get('picks', picks_data.get('entries', [])))
    
    else:
        # Already a list
        picks = picks_data
    
    # Helper to get confidence from any field name
    def get_conf(p):
        return (
            p.get('effective_confidence') or 
            p.get('status_confidence') or
            p.get('model_confidence') or 
            p.get('confidence') or 
            p.get('eff%') or 
            p.get('prob', 0)
        )
    
    # Filter to only actionable picks (confidence >= 55%)
    actionable_picks = []
    for p in picks:
        conf = get_conf(p)
        if conf >= 55:
            actionable_picks.append(p)
    
    # Sort by confidence (descending)
    actionable_picks.sort(key=lambda x: get_conf(x), reverse=True)
    
    # Separate by tier
    elite_picks = [p for p in actionable_picks if get_conf(p) >= 80]
    strong_picks = [p for p in actionable_picks if 65 <= get_conf(p) < 80]
    lean_picks = [p for p in actionable_picks if 55 <= get_conf(p) < 65]
    
    # Build report
    report_lines = [
        "=" * 80,
        f"🎯 {slate_name.upper()} - FUOOM NARRATIVE REPORT",
        "=" * 80,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}",
        "",
        "━" * 80,
        "📊 EXECUTIVE SUMMARY",
        "━" * 80,
        f"Total Actionable Picks: {len(actionable_picks)}",
        f"  💎 ELITE (80%+):     {len(elite_picks)} picks",
        f"  ✨ STRONG (65-79%):  {len(strong_picks)} picks",
        f"  📈 LEAN (55-64%):    {len(lean_picks)} picks",
        "",
        "=" * 80,
        ""
    ]
    
    # Elite picks section
    if elite_picks:
        report_lines.extend([
            "",
            "💎" * 40,
            "💎 ELITE PICKS (80%+ CONFIDENCE)",
            "💎 These are our highest-conviction plays",
            "💎" * 40,
            ""
        ])
        
        for i, pick in enumerate(elite_picks, 1):
            narrative = enhance_fuoom_pick_with_narrative(pick)
            report_lines.append(f"═══ ELITE PICK #{i} ═══")
            report_lines.append(narrative)
            report_lines.append("")
    
    # Strong picks section
    if strong_picks:
        report_lines.extend([
            "",
            "✨" * 40,
            "✨ STRONG PICKS (65-79% CONFIDENCE)",
            "✨ High-quality plays with solid edges",
            "✨" * 40,
            ""
        ])
        
        for i, pick in enumerate(strong_picks, 1):
            narrative = enhance_fuoom_pick_with_narrative(pick)
            report_lines.append(f"═══ STRONG PICK #{i} ═══")
            report_lines.append(narrative)
            report_lines.append("")
    
    # Lean picks (limit to top 10)
    if lean_picks:
        report_lines.extend([
            "",
            "📈" * 40,
            f"📈 LEAN PICKS (55-64% CONFIDENCE) - Top {min(10, len(lean_picks))}",
            "📈 Consider for parlays or smaller positions",
            "📈" * 40,
            ""
        ])
        
        for i, pick in enumerate(lean_picks[:10], 1):
            narrative = enhance_fuoom_pick_with_narrative(pick)
            report_lines.append(f"═══ LEAN PICK #{i} ═══")
            report_lines.append(narrative)
            report_lines.append("")
    
    # Footer
    report_lines.extend([
        "",
        "=" * 80,
        "🎯 FUOOM DARK MATTER - Quantitative Sports Betting",
        "=" * 80,
        "",
        "💡 BETTING REMINDERS:",
        "  • Follow recommended Kelly sizing (protects your bankroll)",
        "  • Track all bets for continuous improvement",
        "  • Even 90% picks lose 10% of the time (variance is real)",
        "  • Never bet more than you can afford to lose",
        "",
        "⚠️  DISCLAIMER:",
        "  This is for entertainment purposes only. Past performance does not",
        "  guarantee future results. Bet responsibly.",
        "",
        "=" * 80,
        "END OF REPORT",
        "=" * 80,
    ])
    
    return "\n".join(report_lines)


# ═══════════════════════════════════════════════════════════════════
# QUICK TEST FUNCTION
# ═══════════════════════════════════════════════════════════════════

def test_with_sample_pick():
    """
    Quick test using sample pick data
    """
    
    # Create sample pick in FUOOM format
    sample_pick = {
        'player': 'Cam Thomas',
        'team': 'BKN',
        'opponent': 'HOU',
        'stat': 'points',
        'line': 16.5,
        'direction': 'lower',
        'mu': 8.7,
        'sigma': 4.4,
        'confidence': 86.6,
        'edge': 7.8,
        'z_score': 1.77,
        'n': 10,
    }
    
    print("=" * 80)
    print("TESTING NARRATIVE GENERATION")
    print("=" * 80)
    print()
    
    narrative = enhance_fuoom_pick_with_narrative(sample_pick)
    print(narrative)
    
    print()
    print("=" * 80)
    print("✅ Test complete! If this looks good, ready to run on full slate.")
    print("=" * 80)


if __name__ == "__main__":
    test_with_sample_pick()
