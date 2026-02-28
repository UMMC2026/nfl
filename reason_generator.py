"""
REASON GENERATOR - FUOOM DARK MATTER
Generates supporting reasons and risk factors from pick data

NO AI needed - pure data-driven logic
"""


def generate_reasons(pick_data: dict) -> list:
    """
    Generate 3-5 supporting reasons for a pick from DATA ONLY
    """
    reasons = []
    
    # Extract data
    mu = pick_data.get('mu', 0)
    sigma = pick_data.get('sigma', 0)
    line = pick_data.get('line', 0)
    direction = pick_data.get('direction', 'higher')
    stat = pick_data.get('stat', '').lower()
    player_name = pick_data.get('player', pick_data.get('player_name', 'Player'))
    
    # REASON 1: Gap from line (always include)
    gap = abs(mu - line)
    if direction.lower() in ('higher', 'over') and mu > line:
        reasons.append(
            f"{player_name} averages {mu:.1f} {stat} "
            f"({gap:.1f} above the {line} line)"
        )
    elif direction.lower() in ('lower', 'under') and mu < line:
        reasons.append(
            f"{player_name} averages {mu:.1f} {stat} "
            f"({gap:.1f} below the {line} line)"
        )
    else:
        reasons.append(
            f"{player_name} averages {mu:.1f} {stat} "
            f"over last {pick_data.get('sample_window', 10)} games"
        )
    
    # REASON 2: Recent hit streak (if available)
    recent_hits = pick_data.get('recent_hits')
    recent_total = pick_data.get('recent_total', 10)
    if recent_hits:
        hit_pct = (recent_hits / recent_total) * 100
        reasons.append(
            f"Hit this line in {recent_hits} of last {recent_total} games "
            f"({hit_pct:.0f}% hit rate)"
        )
    
    # REASON 3: Home/away advantage (if significant)
    home_boost = pick_data.get('home_boost')
    location = pick_data.get('location', 'home')
    home_pct = pick_data.get('home_pct')
    away_pct = pick_data.get('away_pct')
    
    if home_boost and location == 'home' and home_boost > 1.05:
        if home_pct and away_pct:
            reasons.append(
                f"Playing at home where {player_name} "
                f"averages {home_pct*100:.0f}% vs {away_pct*100:.0f}% away"
            )
        else:
            reasons.append(
                f"Playing at home with {(home_boost-1)*100:+.0f}% performance boost"
            )
    
    # REASON 4: Opponent weakness (if significant)
    opp_rank = pick_data.get('opponent_rank')
    opponent = pick_data.get('opponent', 'OPP')
    if opp_rank and opp_rank >= 25:
        reasons.append(
            f"{opponent} ranks {opp_rank}th defending {stat} "
            f"(bottom tier defense)"
        )
    elif opp_rank and opp_rank >= 20:
        reasons.append(
            f"{opponent} ranks {opp_rank}th defending {stat} "
            f"(below average defense)"
        )
    
    # REASON 5: Volume trend (if increasing)
    volume_change = pick_data.get('volume_change')
    if volume_change and volume_change > 0.10:
        reasons.append(
            f"Shot volume up {volume_change*100:+.0f}% over last 5 games"
        )
    
    # REASON 6: Matchup history (if available)
    vs_opponent_avg = pick_data.get('vs_opponent_avg')
    if vs_opponent_avg and mu > 0 and vs_opponent_avg > mu * 1.15:
        reasons.append(
            f"Averages {vs_opponent_avg:.1f} {stat} in recent games vs {opponent} "
            f"({(vs_opponent_avg/mu - 1)*100:+.0f}% above normal)"
        )
    
    # REASON 7: Consistency (if very consistent)
    cv = pick_data.get('consistency_cv')
    if cv and cv < 0.30:
        reasons.append(
            f"High consistency with low variance (CV={cv:.0%})"
        )
    
    return reasons[:5]


def generate_risks(pick_data: dict) -> list:
    """
    Generate 2-3 realistic risk factors from DATA
    """
    risks = []
    
    mu = pick_data.get('mu', 0)
    sigma = pick_data.get('sigma', 0)
    cv = pick_data.get('consistency_cv', sigma / mu if mu > 0 else 999)
    stat = pick_data.get('stat', '').lower()
    
    # RISK 1: Variance/consistency concerns
    if cv > 0.50:
        risks.append(
            f"High variance (σ={sigma:.1f}, CV={cv:.0%}) - some games well below average"
        )
    elif cv > 0.35:
        risks.append(
            f"Moderate variance (σ={sigma:.1f}) - occasional low outliers expected"
        )
    
    # RISK 2: Sample size warnings
    sample_size = pick_data.get('sample_size', 10)
    if sample_size < 10:
        risks.append(
            f"Small sample size (only {sample_size} games) - projections less reliable"
        )
    
    # RISK 3: Injury status
    injury_status = pick_data.get('injury_status')
    if injury_status and injury_status != 'ACTIVE':
        risks.append(
            f"Player listed as {injury_status} - monitor pre-game status"
        )
    
    # RISK 4: Foul trouble (for minutes-dependent stats)
    if stat in ['points', 'pts', 'rebounds', 'reb', 'assists', 'ast', 'pra']:
        risks.append(
            f"If early foul trouble limits minutes, {stat} production could drop"
        )
    
    # RISK 5: Opponent strength (if strong)
    opp_rank = pick_data.get('opponent_rank')
    opponent = pick_data.get('opponent', 'OPP')
    if opp_rank is not None and opp_rank <= 5:
        risks.append(
            f"{opponent} ranks {opp_rank}th (elite defense vs {stat})"
        )
    
    if not risks:
        risks.append("Standard variance risk applies (no specific red flags)")
    
    return risks[:3]


def generate_primary_reason(pick_data: dict) -> str:
    """
    Generate the one-sentence primary reason
    """
    mu = pick_data.get('mu', 0)
    line = pick_data.get('line', 0)
    stat = pick_data.get('stat', '').lower()
    recent_hits = pick_data.get('recent_hits')
    recent_total = pick_data.get('recent_total', 10)
    
    parts = []
    
    # Part 1: Average vs line
    gap = abs(mu - line)
    if gap >= 2.0:
        parts.append(f"averaging {mu:.1f} {stat} (well {'above' if mu > line else 'below'} the line)")
    else:
        parts.append(f"averaging {mu:.1f} {stat}")
    
    # Part 2: Recent consistency (if strong)
    if recent_hits and recent_hits >= 7:
        parts.append(f"has hit this in {recent_hits} of last {recent_total} games")
    
    if len(parts) == 2:
        return f"He's {parts[0]} and {parts[1]}"
    else:
        return f"He's {parts[0]}"


def format_reasons_as_bullets(reasons: list) -> str:
    """Format list of reasons as bullet points"""
    if not reasons:
        return "• Strong statistical projection based on recent form"
    return "\n".join([f"• {reason}" for reason in reasons])


def format_risks_as_bullets(risks: list) -> str:
    """Format list of risks as bullet points"""
    if not risks:
        return "• Standard variance applies (no specific red flags)"
    return "\n".join([f"• {risk}" for risk in risks])


if __name__ == "__main__":
    example_pick = {
        'player': 'RJ Barrett',
        'stat': '3pm',
        'line': 0.5,
        'direction': 'higher',
        'mu': 1.6,
        'sigma': 1.3,
        'recent_hits': 8,
        'recent_total': 10,
        'opponent': 'ORL',
        'opponent_rank': 28,
    }
    
    print("REASONS:")
    print(format_reasons_as_bullets(generate_reasons(example_pick)))
    print("\nRISKS:")
    print(format_risks_as_bullets(generate_risks(example_pick)))
    print("\nPRIMARY:")
    print(generate_primary_reason(example_pick))
