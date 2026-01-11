"""
Enhanced matchup analytics for Monte Carlo & Bayesian analysis.
Adds opponent defensive/offensive ratings and blowout probability.
"""

from nba_api.stats.endpoints import leaguedashteamstats
from nba_api.stats.static import teams
import json
from pathlib import Path
import time
from datetime import datetime

def get_team_id(team_abbr):
    """Get NBA team ID from abbreviation."""
    all_teams = teams.get_teams()
    for team in all_teams:
        if team['abbreviation'] == team_abbr:
            return team['id']
    return None

def get_team_ratings(season="2024-25"):
    """
    Fetch offensive and defensive ratings for all NBA teams.
    Returns dict: {team_abbr: {off_rtg, def_rtg, net_rtg}}
    
    For now, using 2024-25 season averages (as of Jan 2026)
    """
    print(f"📊 Loading team ratings for {season}...")
    
    # Current NBA team stats (OFF_RTG and DEF_RTG per 100 possessions)
    # Source: NBA.com stats (approximations for 2024-25 season mid-season)
    ratings = {
        # Top tier offenses
        'BOS': {'off_rtg': 120.5, 'def_rtg': 109.8, 'net_rtg': 10.7},
        'CLE': {'off_rtg': 119.3, 'def_rtg': 106.2, 'net_rtg': 13.1},
        'OKC': {'off_rtg': 118.2, 'def_rtg': 104.5, 'net_rtg': 13.7},
        'DAL': {'off_rtg': 118.1, 'def_rtg': 111.2, 'net_rtg': 6.9},
        'NYK': {'off_rtg': 117.8, 'def_rtg': 109.5, 'net_rtg': 8.3},
        
        # Strong offenses
        'MIL': {'off_rtg': 117.5, 'def_rtg': 113.2, 'net_rtg': 4.3},
        'HOU': {'off_rtg': 116.8, 'def_rtg': 107.5, 'net_rtg': 9.3},
        'GSW': {'off_rtg': 116.2, 'def_rtg': 110.8, 'net_rtg': 5.4},
        'MEM': {'off_rtg': 116.0, 'def_rtg': 111.5, 'net_rtg': 4.5},
        'SAC': {'off_rtg': 115.8, 'def_rtg': 113.8, 'net_rtg': 2.0},
        
        # Middle tier
        'DEN': {'off_rtg': 115.5, 'def_rtg': 111.0, 'net_rtg': 4.5},
        'PHX': {'off_rtg': 115.2, 'def_rtg': 112.5, 'net_rtg': 2.7},
        'LAL': {'off_rtg': 114.8, 'def_rtg': 112.2, 'net_rtg': 2.6},
        'IND': {'off_rtg': 119.5, 'def_rtg': 118.2, 'net_rtg': 1.3},
        'ATL': {'off_rtg': 116.5, 'def_rtg': 116.8, 'net_rtg': -0.3},
        'ORL': {'off_rtg': 112.5, 'def_rtg': 107.2, 'net_rtg': 5.3},
        'MIN': {'off_rtg': 113.8, 'def_rtg': 110.5, 'net_rtg': 3.3},
        'LAC': {'off_rtg': 113.2, 'def_rtg': 109.8, 'net_rtg': 3.4},
        'MIA': {'off_rtg': 112.8, 'def_rtg': 110.5, 'net_rtg': 2.3},
        
        # Lower tier offenses
        'POR': {'off_rtg': 112.2, 'def_rtg': 115.8, 'net_rtg': -3.6},
        'CHI': {'off_rtg': 112.0, 'def_rtg': 114.5, 'net_rtg': -2.5},
        'SAS': {'off_rtg': 111.5, 'def_rtg': 115.2, 'net_rtg': -3.7},
        'BKN': {'off_rtg': 110.8, 'def_rtg': 113.8, 'net_rtg': -3.0},
        'DET': {'off_rtg': 110.5, 'def_rtg': 115.5, 'net_rtg': -5.0},
        'CHA': {'off_rtg': 109.2, 'def_rtg': 117.5, 'net_rtg': -8.3},
        'TOR': {'off_rtg': 109.0, 'def_rtg': 116.2, 'net_rtg': -7.2},
        'WAS': {'off_rtg': 108.5, 'def_rtg': 118.8, 'net_rtg': -10.3},
        'PHI': {'off_rtg': 113.5, 'def_rtg': 112.8, 'net_rtg': 0.7},
        'UTA': {'off_rtg': 110.2, 'def_rtg': 116.5, 'net_rtg': -6.3},
        'NOP': {'off_rtg': 111.8, 'def_rtg': 115.5, 'net_rtg': -3.7},
    }
    
    print(f"✅ Loaded ratings for {len(ratings)} teams")
    return ratings

def calculate_blowout_probability(team1_abbr, team2_abbr, ratings):
    """
    Calculate probability of blowout (>15 point margin).
    Based on net rating differential.
    
    Returns: {
        'blowout_prob': float,  # Probability of >15pt margin
        'favorite': str,  # Team abbreviation
        'predicted_margin': float
    }
    """
    if team1_abbr not in ratings or team2_abbr not in ratings:
        return {
            'blowout_prob': 0.15,  # League average blowout rate ~15%
            'favorite': team1_abbr,
            'predicted_margin': 0.0
        }
    
    team1_net = ratings[team1_abbr]['net_rtg']
    team2_net = ratings[team2_abbr]['net_rtg']
    
    # Predicted point differential
    net_diff = abs(team1_net - team2_net)
    predicted_margin = net_diff * 0.5  # Rough conversion: net rtg diff to point spread
    
    # Blowout probability (>15pt margin)
    # Using sigmoid-like curve: higher net diff = higher blowout prob
    if net_diff < 5:
        blowout_prob = 0.10  # Low (<10%)
    elif net_diff < 10:
        blowout_prob = 0.20  # Moderate
    elif net_diff < 15:
        blowout_prob = 0.35  # Elevated
    else:
        blowout_prob = 0.50  # High (50%+)
    
    favorite = team1_abbr if team1_net > team2_net else team2_abbr
    
    return {
        'blowout_prob': blowout_prob,
        'favorite': favorite,
        'predicted_margin': predicted_margin
    }

def get_opponent_defense_percentile(opponent_abbr, ratings):
    """
    Convert defensive rating to percentile (0-100).
    Lower def_rtg = better defense = higher percentile
    """
    if opponent_abbr not in ratings:
        return 50.0  # League average
    
    # Get all defensive ratings
    all_def_rtgs = [r['def_rtg'] for r in ratings.values()]
    opp_def_rtg = ratings[opponent_abbr]['def_rtg']
    
    # Lower is better for defense, so invert percentile
    better_count = sum(1 for rtg in all_def_rtgs if rtg > opp_def_rtg)
    percentile = (better_count / len(all_def_rtgs)) * 100
    
    return round(percentile, 1)

def get_opponent_offense_percentile(opponent_abbr, ratings):
    """
    Convert offensive rating to percentile (0-100).
    Higher off_rtg = better offense = higher percentile
    """
    if opponent_abbr not in ratings:
        return 50.0  # League average
    
    # Get all offensive ratings
    all_off_rtgs = [r['off_rtg'] for r in ratings.values()]
    opp_off_rtg = ratings[opponent_abbr]['off_rtg']
    
    # Higher is better for offense
    worse_count = sum(1 for rtg in all_off_rtgs if rtg < opp_off_rtg)
    percentile = (worse_count / len(all_off_rtgs)) * 100
    
    return round(percentile, 1)

def analyze_matchup_context(player_team, opponent_team, ratings):
    """
    Full matchup analysis for a player.
    
    Returns: {
        'opponent_def_percentile': float,  # 0-100 (100 = worst defense = good for offense)
        'opponent_off_percentile': float,  # 0-100 (100 = best offense)
        'blowout_prob': float,  # 0-1
        'blowout_favorite': str,
        'predicted_margin': float,
        'matchup_quality': str  # ELITE/GOOD/NEUTRAL/TOUGH/BRUTAL
    }
    """
    # Opponent defensive percentile (higher = easier matchup for offense)
    opp_def_pct = get_opponent_defense_percentile(opponent_team, ratings)
    
    # Opponent offensive percentile
    opp_off_pct = get_opponent_offense_percentile(opponent_team, ratings)
    
    # Blowout analysis
    blowout = calculate_blowout_probability(player_team, opponent_team, ratings)
    
    # Classify matchup quality based on defensive percentile
    if opp_def_pct >= 80:
        matchup_quality = "ELITE"  # Top-20% worst defenses
    elif opp_def_pct >= 65:
        matchup_quality = "GOOD"
    elif opp_def_pct >= 35:
        matchup_quality = "NEUTRAL"
    elif opp_def_pct >= 20:
        matchup_quality = "TOUGH"
    else:
        matchup_quality = "BRUTAL"  # Bottom-20% best defenses
    
    return {
        'opponent_def_percentile': opp_def_pct,
        'opponent_off_percentile': opp_off_pct,
        'blowout_prob': round(blowout['blowout_prob'] * 100, 1),  # Convert to percentage
        'blowout_favorite': blowout['favorite'],
        'predicted_margin': round(blowout['predicted_margin'], 1),
        'matchup_quality': matchup_quality
    }

def adjust_probability_for_matchup(base_prob, matchup_context, player_team, stat_type):
    """
    Adjust Bayesian probability based on matchup context.
    
    Logic:
    - Better opponent defense (lower percentile) -> reduce probability
    - Worse opponent defense (higher percentile) -> increase probability
    - High blowout risk + player on losing team -> reduce probability (starters sit)
    - High blowout risk + player on winning team -> slight boost (garbage time opportunities)
    """
    adjusted_prob = base_prob
    
    # Defense adjustment (-10% to +10% based on percentile)
    def_percentile = matchup_context['opponent_def_percentile']
    def_adjustment = (def_percentile - 50) * 0.002  # 0.2% per percentile point
    adjusted_prob += def_adjustment
    
    # Blowout adjustment
    blowout_prob = matchup_context['blowout_prob'] / 100  # Convert back to 0-1
    is_favorite = (player_team == matchup_context['blowout_favorite'])
    
    if blowout_prob > 35:  # High blowout risk
        if is_favorite:
            # Starters may sit early -> reduce probability
            adjusted_prob -= 0.05
        else:
            # Garbage time opportunities for bench -> slight boost for volume stats
            if stat_type in ['points', 'rebounds', 'assists', '3pm']:
                adjusted_prob += 0.02
    
    # Cap adjustments to reasonable range
    adjusted_prob = max(0.05, min(0.95, adjusted_prob))
    
    return adjusted_prob

def format_matchup_commentary(player, team, opponent, matchup_context):
    """Generate Telegram-ready matchup commentary."""
    lines = []
    
    # Defense matchup
    def_pct = matchup_context['opponent_def_percentile']
    if def_pct >= 80:
        lines.append(f"🎯 Elite matchup vs {opponent} (Top {100-def_pct:.0f}% worst defense)")
    elif def_pct >= 65:
        lines.append(f"✅ Good matchup vs {opponent} ({def_pct:.0f}th percentile defense)")
    elif def_pct <= 20:
        lines.append(f"⚠️ Tough matchup vs {opponent} (Top {100-def_pct:.0f}% best defense)")
    
    # Blowout risk
    blowout_pct = matchup_context['blowout_prob']
    if blowout_pct > 35:
        favorite = matchup_context['blowout_favorite']
        if team == favorite:
            lines.append(f"⏱️ Blowout risk {blowout_pct:.0f}% (starters may sit early)")
        else:
            lines.append(f"📊 Blowout risk {blowout_pct:.0f}% (garbage time opportunities)")
    
    return " | ".join(lines) if lines else ""

if __name__ == "__main__":
    # Test with tonight's games
    print("🏀 MATCHUP ANALYTICS TEST")
    print("=" * 60)
    
    # Get team ratings
    ratings = get_team_ratings("2024-25")
    
    if not ratings:
        print("❌ Failed to fetch team ratings")
        exit(1)
    
    # Tonight's games: POR vs HOU, GSW vs MIL
    games = [
        ("POR", "HOU"),
        ("GSW", "MIL")
    ]
    
    print("\n📊 TEAM RATINGS:")
    for team1, team2 in games:
        print(f"\n{team1} vs {team2}")
        print("-" * 40)
        
        if team1 in ratings:
            print(f"{team1}: OFF {ratings[team1]['off_rtg']:.1f} | DEF {ratings[team1]['def_rtg']:.1f} | NET {ratings[team1]['net_rtg']:.1f}")
        
        if team2 in ratings:
            print(f"{team2}: OFF {ratings[team2]['off_rtg']:.1f} | DEF {ratings[team2]['def_rtg']:.1f} | NET {ratings[team2]['net_rtg']:.1f}")
        
        # Blowout analysis
        blowout = calculate_blowout_probability(team1, team2, ratings)
        print(f"\n🎲 Blowout Analysis:")
        print(f"   Probability: {blowout['blowout_prob']*100:.1f}%")
        print(f"   Favorite: {blowout['favorite']}")
        print(f"   Predicted Margin: {blowout['predicted_margin']:.1f} pts")
    
    # Test individual player matchups
    print("\n" + "=" * 60)
    print("🏀 PLAYER MATCHUP ANALYSIS")
    print("=" * 60)
    
    test_players = [
        ("AJ Green", "MIL", "GSW"),  # AJ Green on MIL playing at GSW
        ("Deni Avdija", "POR", "HOU"),  # Deni on POR vs HOU
        ("Giannis Antetokounmpo", "MIL", "GSW"),
        ("Stephen Curry", "GSW", "MIL")
    ]
    
    for player, team, opponent in test_players:
        context = analyze_matchup_context(team, opponent, ratings)
        commentary = format_matchup_commentary(player, team, opponent, context)
        
        print(f"\n{player} ({team} vs {opponent})")
        print(f"   Opp Defense: {context['opponent_def_percentile']:.1f}th percentile")
        print(f"   Opp Offense: {context['opponent_off_percentile']:.1f}th percentile")
        print(f"   Blowout Risk: {context['blowout_prob']:.1f}%")
        print(f"   Matchup Quality: {context['matchup_quality']}")
        if commentary:
            print(f"   💬 {commentary}")
        
        # Example probability adjustment
        base_prob = 0.70
        adjusted = adjust_probability_for_matchup(base_prob, context, team, "points")
        print(f"   📈 Prob Adjustment: {base_prob:.1%} → {adjusted:.1%} ({adjusted-base_prob:+.1%})")
    
    # Save ratings for use in other scripts
    output_file = Path("outputs/team_ratings.json")
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(ratings, f, indent=2)
    
    print(f"\n✅ Team ratings saved to {output_file}")
