#!/usr/bin/env python3
"""
Telegram messaging template with dual-domain classifications
Applied to all game-specific analysis sends
"""

def format_pick_with_domain(pick_data: dict) -> str:
    """
    Format a pick with domain classification for Telegram
    
    Args:
        pick_data: {
            'player': str,
            'stat': str,
            'line': float,
            'domain_type': 'HYBRID' | 'CONVICTION' | 'VALUE' | 'REJECT',
            'reasoning': str,
            'confidence': float,
            'mu': float | None,
            'mu_gap': float | None,
        }
    
    Returns:
        Formatted message string
    """
    
    player = pick_data['player']
    stat = pick_data['stat']
    domain = pick_data['domain_type']
    reasoning = pick_data['reasoning']
    confidence = pick_data.get('confidence', 0)
    mu = pick_data.get('mu', None)
    mu_gap = pick_data.get('mu_gap', None)
    
    # Domain emoji mapping
    domain_emoji = {
        'HYBRID': '🎯',
        'CONVICTION': '🔒',
        'VALUE': '💎',
        'REJECT': '❌'
    }
    
    emoji = domain_emoji.get(domain, '?')
    
    # Build message based on domain type
    if domain == 'REJECT':
        # Don't include rejected picks in messages
        return None
    elif domain == 'HYBRID':
        # Highlight as premium play
        return f"{emoji} *{domain}* | {player} {stat}\n    ✓ {reasoning}"
    elif domain == 'CONVICTION':
        # Highlight regime strength
        return f"{emoji} *{domain}* | {player} {stat}\n    ✓ {confidence:.0f}% conviction: {reasoning}"
    elif domain == 'VALUE':
        # Highlight statistical edge
        if mu_gap:
            return f"{emoji} *{domain}* | {player} {stat}\n    ✓ +{mu_gap:.1f}pt edge: {reasoning}"
        else:
            return f"{emoji} *{domain}* | {player} {stat}\n    ✓ {reasoning}"
    
    return f"{emoji} *{domain}* | {player} {stat}\n    ✓ {reasoning}"


def build_game_message(game_name: str, picks: list[dict], capital_allocation: dict) -> str:
    """
    Build complete Telegram message for a game
    
    Args:
        game_name: e.g., "MIA @ DET"
        picks: List of pick dicts with domain classifications
        capital_allocation: {'HYBRID': units, 'CONVICTION': units, 'VALUE': units}
    
    Returns:
        Formatted message ready for Telegram
    """
    
    # Filter to non-rejected picks
    active_picks = [p for p in picks if p['domain_type'] != 'REJECT']
    
    # Count by type
    hybrid_count = sum(1 for p in active_picks if p['domain_type'] == 'HYBRID')
    conviction_count = sum(1 for p in active_picks if p['domain_type'] == 'CONVICTION')
    value_count = sum(1 for p in active_picks if p['domain_type'] == 'VALUE')
    
    # Build message
    msg = f"🏀 *{game_name}*\n"
    msg += f"Slate: {hybrid_count} HYBRID | {conviction_count} CONVICTION | {value_count} VALUE\n"
    msg += "─" * 50 + "\n\n"
    
    # Add picks grouped by domain
    for domain in ['HYBRID', 'CONVICTION', 'VALUE']:
        domain_picks = [p for p in active_picks if p['domain_type'] == domain]
        if domain_picks:
            for pick in domain_picks:
                pick_str = format_pick_with_domain(pick)
                if pick_str:
                    msg += pick_str + "\n"
            msg += "\n"
    
    # Add capital recommendation
    msg += "─" * 50 + "\n"
    msg += "💰 *Capital Allocation*\n"
    total_units = sum(capital_allocation.values())
    
    for domain in ['HYBRID', 'CONVICTION', 'VALUE']:
        units = capital_allocation.get(domain, 0)
        if units > 0:
            pct = (units / total_units * 100) if total_units > 0 else 0
            msg += f"  {domain}: {units} units ({pct:.0f}%)\n"
    
    msg += f"\n  *Total Deploy:* {total_units} units (maintain dry powder)\n"
    
    return msg


# Example usage
if __name__ == "__main__":
    
    # Example picks from MIA @ DET
    picks_example = [
        {
            'player': 'Jamal Murray',
            'stat': 'points O 18.5',
            'line': 18.5,
            'domain_type': 'HYBRID',
            'reasoning': 'μ=21.5 vs 18.5 (+3pt edge) + 72% conviction',
            'confidence': 72,
            'mu': 21.5,
            'mu_gap': 3.0,
        },
        {
            'player': 'Jimmy Butler',
            'stat': 'pts+reb+ast O 35.5',
            'line': 35.5,
            'domain_type': 'CONVICTION',
            'reasoning': 'μ data unavailable, but 65% conviction based on role/matchup',
            'confidence': 65,
            'mu': None,
            'mu_gap': None,
        },
        {
            'player': 'Bam Adebayo',
            'stat': 'rebounds O 8.5',
            'line': 8.5,
            'domain_type': 'VALUE',
            'reasoning': '+3.5pt edge (μ=12), but only 52% conviction',
            'confidence': 52,
            'mu': 12.0,
            'mu_gap': 3.5,
        },
        {
            'player': 'Tyler Herro',
            'stat': 'points O 15.5',
            'line': 15.5,
            'domain_type': 'REJECT',
            'reasoning': 'insufficient on both domains',
            'confidence': 48,
            'mu': 16.2,
            'mu_gap': 0.7,
        },
    ]
    
    capital_alloc = {
        'HYBRID': 6,
        'CONVICTION': 8,
        'VALUE': 5,
    }
    
    message = build_game_message("MIA @ DET (7:00 ET)", picks_example, capital_alloc)
    print(message)
