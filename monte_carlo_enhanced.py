"""
ENHANCED Monte Carlo with matchup analytics integration.
Combines Bayesian probability + rest day analytics + opponent ratings + blowout probability.
"""

import json
from pathlib import Path
import numpy as np
from scipy.stats import beta
from itertools import combinations
from datetime import datetime
from matchup_analytics import (
    get_team_ratings,
    analyze_matchup_context,
    adjust_probability_for_matchup,
    format_matchup_commentary
)

def load_hydrated_picks():
    """Load all hydrated picks from latest Monte Carlo run."""
    files = [
        "picks_hydrated_late_3pm_assists.json",
        "picks_hydrated_combo.json",
        "picks_hydrated_rebounds.json"
    ]
    
    all_picks = []
    for filename in files:
        filepath = Path(filename)
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_picks.extend(data)
                else:
                    all_picks.append(data)
    
    print(f"📥 Loaded {len(all_picks)} hydrated picks")
    return all_picks

def load_rest_day_analysis():
    """Load rest day analysis from previous run."""
    filepath = Path("outputs/rest_day_analysis.json")
    if not filepath.exists():
        return {}
    
    with open(filepath) as f:
        data = json.load(f)
    
    # Convert to dict keyed by player name
    rest_data = {}
    for item in data:
        player = item['player']
        rest_data[player] = item
    
    print(f"📥 Loaded rest day data for {len(rest_data)} players")
    return rest_data

def calculate_empirical_rate(recent_values, line, direction):
    """Calculate empirical hit rate from recent games."""
    if not recent_values:
        return 0.5
    
    if direction == "higher":
        hits = sum(1 for v in recent_values if v > line)
    else:
        hits = sum(1 for v in recent_values if v < line)
    
    return hits / len(recent_values)

def bayesian_probability(empirical_rate, sample_size, prior_mean=0.5, prior_std=0.15):
    """
    Update probability using Bayesian inference (Beta distribution).
    More conservative than pure empirical for small samples.
    """
    # Convert prior to beta parameters
    prior_alpha = prior_mean * ((prior_mean * (1 - prior_mean) / prior_std**2) - 1)
    prior_beta = (1 - prior_mean) * ((prior_mean * (1 - prior_mean) / prior_std**2) - 1)
    
    # Update with empirical data
    hits = empirical_rate * sample_size
    posterior_alpha = prior_alpha + hits
    posterior_beta = prior_beta + (sample_size - hits)
    
    # Return posterior mean
    return posterior_alpha / (posterior_alpha + posterior_beta)

def adjust_for_rest_days(base_prob, player_name, rest_data):
    """
    Adjust probability based on rest day performance.
    
    Returns: (adjusted_prob, rest_commentary)
    """
    if player_name not in rest_data:
        return base_prob, ""
    
    data = rest_data[player_name]
    
    # Calculate rest advantage
    b2b_avg = data.get('b2b_avg', 0)
    two_plus_avg = data.get('two_plus_avg', 0)
    
    if b2b_avg == 0 and two_plus_avg == 0:
        return base_prob, ""
    
    # Calculate percentage improvement/decline
    if b2b_avg > 0:
        rest_impact = (two_plus_avg - b2b_avg) / b2b_avg
    else:
        rest_impact = 0.0
    
    # Determine upcoming rest context
    upcoming_rest = data.get('upcoming_rest', 1)
    
    # Apply adjustment based on rest impact and upcoming rest
    if upcoming_rest >= 2:  # Player is rested
        if rest_impact > 1.0:  # Huge rest advantage (>100% improvement)
            adjustment = 0.10
            commentary = f"🔋 RESTED (+{rest_impact*100:.0f}% with rest)"
        elif rest_impact > 0.5:  # Strong rest advantage
            adjustment = 0.07
            commentary = f"🔋 Rested (+{rest_impact*100:.0f}%)"
        elif rest_impact > 0.2:  # Moderate advantage
            adjustment = 0.04
            commentary = f"⚡️ Rested (+{rest_impact*100:.0f}%)"
        elif rest_impact < -0.2:  # Contrarian: worse with rest
            adjustment = -0.05
            commentary = f"⚠️ Plays better on B2B ({rest_impact*100:.0f}% with rest)"
        else:
            adjustment = 0.0
            commentary = ""
    elif upcoming_rest == 0:  # Back-to-back
        if rest_impact > 0.5:  # Much better with rest = worse on B2B
            adjustment = -0.07
            commentary = f"😴 B2B (-{rest_impact*100:.0f}% vs rested)"
        elif rest_impact < -0.2:  # Contrarian: better on B2B
            adjustment = 0.05
            commentary = f"⚡️ B2B specialist (+{abs(rest_impact)*100:.0f}%)"
        else:
            adjustment = -0.03
            commentary = f"😴 B2B"
    else:  # Standard 1-day rest
        adjustment = 0.0
        commentary = ""
    
    adjusted_prob = base_prob + adjustment
    adjusted_prob = max(0.05, min(0.95, adjusted_prob))
    
    return adjusted_prob, commentary

def enhance_pick_with_context(pick, rest_data, team_ratings):
    """
    Add full contextual analysis to a pick:
    - Rest day adjustment
    - Opponent defense/offense ratings
    - Blowout probability
    - Final adjusted probability
    """
    player = pick['player']
    team = pick['team']
    stat = pick['stat']
    line = pick['line']
    direction = pick['direction']
    recent_values = pick.get('recent_values', [])
    
    # Get opponent (need to determine from game context)
    # For now, use game matchups: POR vs HOU, GSW vs MIL
    opponent_map = {
        'POR': 'HOU',
        'HOU': 'POR',
        'GSW': 'MIL',
        'MIL': 'GSW'
    }
    opponent = opponent_map.get(team, None)
    
    # Calculate base probabilities
    empirical_rate = calculate_empirical_rate(recent_values, line, direction)
    sample_size = len(recent_values)
    bayesian_prob = bayesian_probability(empirical_rate, sample_size)
    
    # Adjust for rest days
    rest_adjusted_prob, rest_commentary = adjust_for_rest_days(bayesian_prob, player, rest_data)
    
    # Adjust for matchup (if opponent known)
    if opponent and team_ratings:
        matchup_context = analyze_matchup_context(team, opponent, team_ratings)
        final_prob = adjust_probability_for_matchup(rest_adjusted_prob, matchup_context, team, stat)
        matchup_commentary = format_matchup_commentary(player, team, opponent, matchup_context)
    else:
        final_prob = rest_adjusted_prob
        matchup_context = None
        matchup_commentary = ""
    
    # Build enhanced pick
    enhanced = {
        **pick,
        'empirical_rate': round(empirical_rate, 3),
        'bayesian_prob': round(bayesian_prob, 3),
        'rest_adjusted_prob': round(rest_adjusted_prob, 3),
        'final_prob': round(final_prob, 3),
        'rest_commentary': rest_commentary,
        'matchup_commentary': matchup_commentary
    }
    
    if matchup_context:
        enhanced.update({
            'opponent_def_percentile': matchup_context['opponent_def_percentile'],
            'opponent_off_percentile': matchup_context['opponent_off_percentile'],
            'blowout_prob_pct': matchup_context['blowout_prob'],
            'matchup_quality': matchup_context['matchup_quality']
        })
    
    return enhanced

def monte_carlo_combo(picks, payout_multiplier=6, n_simulations=10000):
    """
    Run Monte Carlo simulation on a combo of picks.
    Returns: {p_all_hit, ev_units, win_rate, avg_return}
    """
    probs = [p['final_prob'] for p in picks]
    
    # Simulate outcomes
    results = []
    for _ in range(n_simulations):
        hits = sum(1 for p in probs if np.random.random() < p)
        
        if hits == len(probs):  # All hit
            profit = payout_multiplier - 1  # e.g., 6x payout on $1 = $5 profit
        else:
            profit = -1  # Lost stake
        
        results.append(profit)
    
    # Calculate metrics
    p_all_hit = sum(1 for r in results if r > 0) / n_simulations
    ev_units = np.mean(results)
    win_rate = p_all_hit
    avg_return = ev_units
    
    return {
        'p_all_hit': p_all_hit,
        'ev_units': ev_units,
        'win_rate': win_rate,
        'avg_return': avg_return
    }

def build_and_rank_combos(qualified_picks, legs=3, max_combos=200):
    """
    Build all possible combos and rank by EV.
    Include stat diversity scoring.
    """
    all_combos = list(combinations(qualified_picks, legs))
    print(f"🎲 Analyzing {len(all_combos)} possible {legs}-pick combos...")
    
    results = []
    for combo in all_combos[:max_combos]:
        mc_result = monte_carlo_combo(combo, payout_multiplier=6, n_simulations=10000)
        
        # Calculate stat diversity (prefer different stat types)
        stats = [p['stat'] for p in combo]
        unique_stats = len(set(stats))
        stat_diversity_score = unique_stats / len(stats)
        
        # Calculate team diversity
        teams = [p['team'] for p in combo]
        unique_teams = len(set(teams))
        
        results.append({
            'picks': [f"{p['player']} {p['line']}+ {p['stat']}" for p in combo],
            'players': [p['player'] for p in combo],
            'teams': teams,
            'stats': stats,
            'probs': [p['final_prob'] for p in combo],
            'rest_commentary': [p.get('rest_commentary', '') for p in combo],
            'matchup_commentary': [p.get('matchup_commentary', '') for p in combo],
            'p_all_hit': mc_result['p_all_hit'],
            'ev_units': mc_result['ev_units'],
            'ev_roi_pct': mc_result['ev_units'] * 100,
            'stat_diversity': stat_diversity_score,
            'unique_teams': unique_teams
        })
    
    # Sort by EV
    results.sort(key=lambda x: x['ev_units'], reverse=True)
    
    return results

def format_enhanced_output(combo):
    """Format combo with full context for Telegram."""
    lines = [f"\n{'='*60}"]
    lines.append(f"🏆 E[ROI]: {combo['ev_roi_pct']:+.1f}% | P(All): {combo['p_all_hit']:.1%}")
    lines.append(f"📊 Teams: {', '.join(set(combo['teams']))} | Stats: {', '.join(set(combo['stats']))}")
    lines.append(f"")
    
    for i, (pick, prob, rest, matchup) in enumerate(zip(
        combo['picks'],
        combo['probs'],
        combo['rest_commentary'],
        combo['matchup_commentary']
    ), 1):
        lines.append(f"{i}️⃣ {pick} ({prob:.1%})")
        if rest:
            lines.append(f"   {rest}")
        if matchup:
            lines.append(f"   {matchup}")
    
    return "\n".join(lines)

if __name__ == "__main__":
    print("🚀 ENHANCED MONTE CARLO ANALYSIS")
    print("=" * 60)
    print("📊 Integration: Bayesian + Rest Days + Matchup Analytics")
    print("=" * 60)
    
    # Load data
    picks = load_hydrated_picks()
    rest_data = load_rest_day_analysis()
    team_ratings = get_team_ratings("2024-25")
    
    # Enhance all picks with context
    print(f"\n🔧 Enhancing {len(picks)} picks with contextual analysis...")
    enhanced_picks = []
    
    for pick in picks:
        try:
            enhanced = enhance_pick_with_context(pick, rest_data, team_ratings)
            enhanced_picks.append(enhanced)
        except Exception as e:
            print(f"⚠️ Error enhancing {pick.get('player', 'Unknown')}: {e}")
            continue
    
    # Filter to qualified picks (65%+ final probability)
    threshold = 0.65
    qualified = [p for p in enhanced_picks if p['final_prob'] >= threshold]
    
    print(f"\n✅ {len(qualified)} picks qualify (≥{threshold:.0%} final probability)")
    
    if len(qualified) == 0:
        print("❌ No qualified picks found")
        exit(0)
    
    # Show qualified picks with full context
    print(f"\n{'='*60}")
    print("🎯 QUALIFIED PICKS (with contextual adjustments)")
    print(f"{'='*60}")
    
    for pick in sorted(qualified, key=lambda x: x['final_prob'], reverse=True):
        print(f"\n{pick['player']} {pick['line']}+ {pick['stat']} ({pick['team']})")
        print(f"   Empirical: {pick['empirical_rate']:.1%} → Bayesian: {pick['bayesian_prob']:.1%}")
        print(f"   Rest Adj: {pick['rest_adjusted_prob']:.1%} → FINAL: {pick['final_prob']:.1%}")
        
        if pick.get('opponent_def_percentile'):
            print(f"   Defense: {pick['opponent_def_percentile']:.0f}th %ile | Offense: {pick['opponent_off_percentile']:.0f}th %ile | Blowout: {pick['blowout_prob_pct']:.0f}%")
        
        if pick.get('rest_commentary'):
            print(f"   {pick['rest_commentary']}")
        
        if pick.get('matchup_commentary'):
            print(f"   {pick['matchup_commentary']}")
    
    # Build optimal combos
    print(f"\n{'='*60}")
    print("🎲 BUILDING OPTIMAL COMBOS")
    print(f"{'='*60}")
    
    combos_3 = build_and_rank_combos(qualified, legs=3, max_combos=min(200, len(qualified)**3))
    
    # Show top 10
    print(f"\n🏆 TOP 10 THREE-PICK COMBOS")
    print(f"{'='*60}")
    
    for i, combo in enumerate(combos_3[:10], 1):
        print(f"\n#{i} COMBO")
        print(format_enhanced_output(combo))
    
    # Save results
    output_file = Path("outputs/monte_carlo_enhanced.json")
    output_file.parent.mkdir(exist_ok=True)
    
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'total_picks': len(picks),
        'qualified_picks': len(qualified),
        'threshold': threshold,
        'qualified_picks_detail': qualified,
        'top_30_combos': combos_3[:30]
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✅ Results saved to {output_file}")
    
    # Generate best combo for Telegram
    if combos_3:
        best = combos_3[0]
        print(f"\n{'='*60}")
        print("📱 BEST COMBO FOR TELEGRAM")
        print(f"{'='*60}")
        print(format_enhanced_output(best))
