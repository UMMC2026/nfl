"""
NARRATIVE TEMPLATES - FUOOM DARK MATTER
Template library for converting technical picks into subscriber-friendly reports
"""

# ═══════════════════════════════════════════════════════════════════
# TIER-BASED TEMPLATES
# ═══════════════════════════════════════════════════════════════════

ELITE_TEMPLATE = """
💎 {player_name} - {stat_display} ({confidence:.1f}% CONFIDENCE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 THE PLAY:
{player_name} to {direction_verb} {line} {stat_full_name} tonight vs {opponent}. 
{primary_reason}. This is one of our ELITE tier picks.

📈 WHY WE LIKE IT:
{reason_bullets}

⚠️ RISK FACTORS:
{risk_bullets}

💰 VALUE ASSESSMENT:
Edge: {edge_display}
Confidence: {sigma_display}
Recommended Bet Size: {kelly_pct:.1f}% of bankroll (Kelly-optimal)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Technical Details]
μ={mu:.1f}, σ={sigma:.1f}, z={z_score:+.2f}, P(hit)={confidence:.1f}%, Kelly={kelly_pct:.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

STRONG_TEMPLATE = """
✨ {player_name} - {stat_display} ({confidence:.1f}% CONFIDENCE)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 THE PLAY:
{player_name} to {direction_verb} {line} {stat_full_name} vs {opponent}. 
{primary_reason}. A solid STRONG tier pick.

📈 KEY REASONS:
{reason_bullets}

⚠️ WATCH OUT FOR:
{risk_bullets}

💰 VALUE:
Edge: {edge_display} | Confidence: {sigma_display}
Bet Size: {kelly_pct:.1f}%

[μ={mu:.1f}, σ={sigma:.1f}, z={z_score:+.2f}, P={confidence:.1f}%]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

LEAN_TEMPLATE = """
📊 {player_name} - {stat_display} ({confidence:.1f}%)
────────────────────────────────────────────────

{player_name} to {direction_verb} {line} {stat_full_name} vs {opponent}.
{primary_reason}.

• Edge: {edge_display}
• Risk: {risk_bullets}
• Size: {kelly_pct:.1f}%

[μ={mu:.1f}, σ={sigma:.1f}, P={confidence:.1f}%]
"""


def get_template(tier_or_confidence) -> str:
    """
    Get appropriate template based on tier name OR confidence level
    
    Args:
        tier_or_confidence: Either string tier ('ELITE', 'STRONG', 'LEAN') 
                           or float confidence (0-100)
    """
    if isinstance(tier_or_confidence, str):
        tier = tier_or_confidence.upper()
        if tier == 'ELITE':
            return ELITE_TEMPLATE
        elif tier == 'STRONG':
            return STRONG_TEMPLATE
        else:
            return LEAN_TEMPLATE
    else:
        # Assume float confidence
        confidence = tier_or_confidence
        if confidence >= 80:
            return ELITE_TEMPLATE
        elif confidence >= 65:
            return STRONG_TEMPLATE
        else:
            return LEAN_TEMPLATE


# ═══════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════════

STAT_DISPLAY_MAP = {
    'pts': 'Points',
    'points': 'Points',
    'reb': 'Rebounds',
    'rebounds': 'Rebounds',
    'ast': 'Assists',
    'assists': 'Assists',
    '3pm': '3-Pointers',
    'threes': '3-Pointers',
    'pra': 'PTS+REB+AST',
    'pts+reb+ast': 'PTS+REB+AST',
    'stl': 'Steals',
    'blk': 'Blocks',
    'reb+ast': 'REB+AST',
    'pts+ast': 'PTS+AST',
}


def format_stat_display(stat: str, line: float, direction: str) -> str:
    """Format stat display like '3PM HIGHER 0.5'"""
    stat_upper = stat.upper()
    dir_upper = direction.upper()
    return f"{stat_upper} {dir_upper} {line}"


def format_stat_full_name(stat: str) -> str:
    """Get full name of stat"""
    return STAT_DISPLAY_MAP.get(stat.lower(), stat)


def format_direction_verb(direction: str) -> str:
    """Convert direction to verb"""
    if direction.lower() in ('higher', 'over'):
        return 'go OVER'
    else:
        return 'stay UNDER'


def format_edge_display(edge: float, stat: str) -> str:
    """Format edge display"""
    stat_name = format_stat_full_name(stat).lower()
    if edge >= 0:
        return f"+{edge:.1f} {stat_name} above line"
    else:
        return f"{edge:.1f} {stat_name} below line"


def format_sigma_display(z_score: float) -> str:
    """Format sigma/confidence display"""
    if abs(z_score) >= 1.0:
        return f"{z_score:+.2f} sigma (ELITE tier)"
    elif abs(z_score) >= 0.5:
        return f"{z_score:+.2f} standard deviations (STRONG tier)"
    else:
        return f"{z_score:+.2f} sigma (LEAN tier)"


def format_kelly_display(kelly_pct: float) -> str:
    """Format Kelly bet sizing"""
    if kelly_pct <= 0:
        return "1-2% of bankroll (minimum size)"
    return f"{kelly_pct:.1f}% of bankroll (Kelly-optimal)"


def format_tier_emoji(tier: str) -> str:
    """Get emoji for tier"""
    emoji_map = {
        'ELITE': '🔥',
        'STRONG': '💪',
        'LEAN': '📊',
        'AVOID': '⚠️'
    }
    return emoji_map.get(tier.upper(), '📈')


# ═══════════════════════════════════════════════════════════════════
# FUOOM INTRO/OUTRO TEMPLATES
# ═══════════════════════════════════════════════════════════════════

FUOOM_INTRO = """
Welcome to **FUOOM DARK MATTER** - your daily dose of data-driven prop analysis.

Every pick below has been processed through our Monte Carlo simulation engine, 
calibrated against 440+ historical outcomes, and filtered through our risk-first 
governance system.

**How to read this report:**
- 🔥 **ELITE** (75%+): Our highest conviction plays. Full Kelly sizing.
- 💪 **STRONG** (65-74%): High-quality edges worth serious attention.
- 📊 **LEAN** (55-64%): Positive EV but proceed with smaller stakes.

*Remember: Even 75% plays lose 1 in 4. Bankroll management is non-negotiable.*
"""

FUOOM_OUTRO = """
**RISK DISCLAIMER:**
All projections are based on historical data and Monte Carlo simulations. 
Past performance does not guarantee future results. Bet responsibly and 
never wager more than you can afford to lose.

*Questions? Reply to this report or DM us on Discord.*

— The FUOOM DARK MATTER Team
"""


def get_tier_name(confidence: float) -> str:
    """Get tier name from confidence"""
    if confidence >= 80:
        return "ELITE"
    elif confidence >= 65:
        return "STRONG"
    elif confidence >= 55:
        return "LEAN"
    else:
        return "NO_PLAY"
