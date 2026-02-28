#!/usr/bin/env python3
"""
NBA Wednesday Advanced Analysis - Monte Carlo + Bayesian + Real Team Stats
Games: CLE@PHI, DEN@DAL, BKN@NOP, TOR@IND, NYK@SAC
"""

import json
import numpy as np
from scipy.stats import norm
from engine.nfl_ai_integration import NFL_AIAnalyzer
from datetime import datetime

# Load slate
with open('nba_wed_slate.json', encoding='utf-8') as f:
    slate = json.load(f)

# Initialize AI
ai_analyzer = NFL_AIAnalyzer()

# NBA team defensive rankings (2025-26 season)
TEAM_DEFENSE_STATS = {
    'PHI': {'def_rating': 109.5, 'pace': 99.2, 'opp_3pt_pct': 35.2, 'rank': 9},
    'CLE': {'def_rating': 106.5, 'pace': 97.1, 'opp_3pt_pct': 33.5, 'rank': 1},
    'DAL': {'def_rating': 110.8, 'pace': 100.4, 'opp_3pt_pct': 35.8, 'rank': 13},
    'DEN': {'def_rating': 110.5, 'pace': 99.7, 'opp_3pt_pct': 35.4, 'rank': 12},
    'NOP': {'def_rating': 111.8, 'pace': 102.1, 'opp_3pt_pct': 35.9, 'rank': 16},
    'BKN': {'def_rating': 115.2, 'pace': 101.8, 'opp_3pt_pct': 37.5, 'rank': 25},
    'IND': {'def_rating': 113.7, 'pace': 103.5, 'opp_3pt_pct': 36.9, 'rank': 20},
    'TOR': {'def_rating': 114.5, 'pace': 98.8, 'opp_3pt_pct': 37.2, 'rank': 23},
    'SAC': {'def_rating': 112.3, 'pace': 101.2, 'opp_3pt_pct': 36.3, 'rank': 17},
    'NYK': {'def_rating': 108.9, 'pace': 98.5, 'opp_3pt_pct': 34.7, 'rank': 7},
}

# NBA team offensive rankings (2025-26 season)
TEAM_OFFENSE_STATS = {
    'PHI': {'off_rating': 116.4, 'efg_pct': 55.6, 'ast_ratio': 26.2, 'rank': 4},
    'CLE': {'off_rating': 118.5, 'efg_pct': 57.1, 'ast_ratio': 27.5, 'rank': 1},
    'DAL': {'off_rating': 115.9, 'efg_pct': 54.9, 'ast_ratio': 25.8, 'rank': 6},
    'DEN': {'off_rating': 117.5, 'efg_pct': 56.2, 'ast_ratio': 28.4, 'rank': 3},
    'NOP': {'off_rating': 114.8, 'efg_pct': 54.5, 'ast_ratio': 25.6, 'rank': 10},
    'BKN': {'off_rating': 113.2, 'efg_pct': 53.2, 'ast_ratio': 24.4, 'rank': 15},
    'IND': {'off_rating': 117.2, 'efg_pct': 56.0, 'ast_ratio': 27.9, 'rank': 2},
    'TOR': {'off_rating': 111.5, 'efg_pct': 52.4, 'ast_ratio': 23.8, 'rank': 21},
    'SAC': {'off_rating': 115.3, 'efg_pct': 54.6, 'ast_ratio': 26.4, 'rank': 8},
    'NYK': {'off_rating': 116.1, 'efg_pct': 55.3, 'ast_ratio': 26.7, 'rank': 5},
}

# Player stats (10-game averages for 2025-26 season)
stats_data = {
    # CLE @ PHI
    ('Sam Merrill', 'points'): {'mu': 11.2, 'sigma': 4.8},
    ('Sam Merrill', 'rebounds'): {'mu': 2.3, 'sigma': 1.1},
    ('Sam Merrill', 'assists'): {'mu': 1.8, 'sigma': 0.9},
    ('Donovan Mitchell', 'points'): {'mu': 24.6, 'sigma': 5.9},
    ('Donovan Mitchell', 'rebounds'): {'mu': 4.5, 'sigma': 1.6},
    ('Donovan Mitchell', 'assists'): {'mu': 4.8, 'sigma': 2.1},
    ('Tyrese Maxey', 'points'): {'mu': 26.8, 'sigma': 6.2},
    ('Tyrese Maxey', 'rebounds'): {'mu': 3.4, 'sigma': 1.3},
    ('Tyrese Maxey', 'assists'): {'mu': 6.9, 'sigma': 2.4},
    ('VJ Edgecombe', 'points'): {'mu': 8.5, 'sigma': 3.2},
    ('VJ Edgecombe', 'rebounds'): {'mu': 3.1, 'sigma': 1.4},
    ('VJ Edgecombe', 'assists'): {'mu': 4.2, 'sigma': 1.8},
    ('Joel Embiid', 'points'): {'mu': 28.4, 'sigma': 6.5},
    ('Joel Embiid', 'rebounds'): {'mu': 10.8, 'sigma': 2.9},
    ('Joel Embiid', 'assists'): {'mu': 4.6, 'sigma': 1.9},
    
    # DEN @ DAL
    ('Peyton Watson', 'points'): {'mu': 9.8, 'sigma': 4.2},
    ('Peyton Watson', 'rebounds'): {'mu': 5.4, 'sigma': 2.1},
    ('Peyton Watson', 'assists'): {'mu': 2.1, 'sigma': 1.0},
    
    # BKN @ NOP
    ('Michael Porter', 'points'): {'mu': 24.3, 'sigma': 5.8},
    ('Michael Porter', 'rebounds'): {'mu': 7.2, 'sigma': 2.3},
    ('Michael Porter', 'assists'): {'mu': 3.8, 'sigma': 1.5},
    ('Trey Murphy', 'points'): {'mu': 18.7, 'sigma': 5.1},
    ('Trey Murphy', 'rebounds'): {'mu': 5.2, 'sigma': 1.8},
    ('Trey Murphy', 'assists'): {'mu': 2.4, 'sigma': 1.1},
    
    # TOR @ IND
    ('Brandon Ingram', 'points'): {'mu': 22.4, 'sigma': 5.4},
    ('Brandon Ingram', 'rebounds'): {'mu': 6.1, 'sigma': 2.0},
    ('Brandon Ingram', 'assists'): {'mu': 5.6, 'sigma': 2.2},
    ('Andrew Nembhard', 'points'): {'mu': 11.3, 'sigma': 3.9},
    ('Andrew Nembhard', 'rebounds'): {'mu': 2.8, 'sigma': 1.2},
    ('Andrew Nembhard', 'assists'): {'mu': 5.4, 'sigma': 2.0},
    
    # NYK @ SAC
    ('Jalen Brunson', 'points'): {'mu': 25.2, 'sigma': 5.7},
    ('Jalen Brunson', 'rebounds'): {'mu': 3.6, 'sigma': 1.4},
    ('Jalen Brunson', 'assists'): {'mu': 7.8, 'sigma': 2.5},
}

def monte_carlo_simulation(mu, sigma, line, direction, num_trials=10000):
    """Run Monte Carlo simulation with Bayesian priors"""
    samples = np.random.normal(mu, sigma, num_trials)
    
    if direction == 'higher':
        hits = np.sum(samples > line)
    else:
        hits = np.sum(samples < line)
    
    prob = hits / num_trials
    std_error = np.sqrt(prob * (1 - prob) / num_trials)
    ci_lower = max(0, prob - 1.96 * std_error)
    ci_upper = min(1, prob + 1.96 * std_error)
    
    return {
        'prob': prob,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'trials': num_trials
    }

def get_matchup_context(player_team, opponent_team, stat):
    """Get defensive/offensive context for matchup"""
    opp_def = TEAM_DEFENSE_STATS.get(opponent_team, {})
    team_off = TEAM_OFFENSE_STATS.get(player_team, {})
    
    return {
        'opponent_def_rank': opp_def.get('rank', 'N/A'),
        'opponent_def_rating': opp_def.get('def_rating', 'N/A'),
        'team_off_rank': team_off.get('rank', 'N/A'),
        'team_off_rating': team_off.get('off_rating', 'N/A'),
        'pace': opp_def.get('pace', 'N/A')
    }

# Calculate probabilities
print("Running Monte Carlo simulations (10,000 trials per prop)...")
results = []

for play in slate['plays']:
    player = play['player']
    stat = play['stat']
    line = play['line']
    direction = play['direction']
    team = play['team']
    
    # Handle PRA (skip for now - need to sum stats)
    if stat == 'pra':
        continue
    
    key = (player, stat)
    data = stats_data.get(key)
    
    if not data:
        print(f"⚠️  Missing data for {player} {stat}")
        continue
    
    mu = data['mu']
    sigma = data['sigma']
    
    # Bayesian probability
    if direction == 'higher':
        bayesian_prob = 1 - norm.cdf(line, loc=mu, scale=sigma)
    else:
        bayesian_prob = norm.cdf(line, loc=mu, scale=sigma)
    
    # Monte Carlo probability
    mc_result = monte_carlo_simulation(mu, sigma, line, direction)
    
    # Get opponent
    opponent = None
    for game in slate.get('games', []):
        if team == game['home']:
            opponent = game['away']
        elif team == game['away']:
            opponent = game['home']
    
    matchup_ctx = get_matchup_context(team, opponent, stat) if opponent else {}
    
    if bayesian_prob >= 0.55 or mc_result['prob'] >= 0.55:
        results.append({
            'player': player,
            'team': team,
            'opponent': opponent,
            'stat': stat,
            'line': line,
            'direction': direction,
            'mu': mu,
            'sigma': sigma,
            'bayesian_prob': bayesian_prob,
            'mc_prob': mc_result['prob'],
            'mc_ci_lower': mc_result['ci_lower'],
            'mc_ci_upper': mc_result['ci_upper'],
            'matchup': matchup_ctx
        })

# Sort by Monte Carlo probability
results.sort(key=lambda x: x['mc_prob'], reverse=True)

# Take top 10
top_picks = results[:10]

print(f"\nQualified picks (≥55%): {len(results)}")
print(f"Displaying top 10\n")
print("=" * 100)

# Generate output
output_file = f"outputs/NBA_WED_ANALYSIS_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=" * 100 + "\n")
    f.write(f"🏀 NBA WEDNESDAY NIGHT ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"Games: CLE@PHI, DEN@DAL, BKN@NOP, TOR@IND, NYK@SAC\n")
    f.write(f"Monte Carlo: 10,000 trials | Bayesian Priors: Normal(μ, σ²)\n")
    f.write(f"Real Team Stats: Defensive/Offensive Ratings + Pace\n")
    f.write("=" * 100 + "\n\n")
    
    for i, pick in enumerate(top_picks, 1):
        player = pick['player']
        team = pick['team']
        opponent = pick['opponent'] or 'TBD'
        stat = pick['stat']
        line = pick['line']
        direction = pick['direction']
        mu = pick['mu']
        sigma = pick['sigma']
        bayesian_prob = pick['bayesian_prob']
        mc_prob = pick['mc_prob']
        mc_ci = (pick['mc_ci_lower'], pick['mc_ci_upper'])
        matchup = pick['matchup']
        
        section = f"\n{'=' * 100}\n"
        section += f"#{i} | {player} ({team}) | {stat.upper()} {direction.upper()} {line}\n"
        section += f"{'=' * 100}\n"
        
        section += f"📊 PROBABILITY ENGINES:\n"
        section += f"   • Bayesian (Normal CDF): {bayesian_prob*100:.1f}%\n"
        section += f"   • Monte Carlo (10k trials): {mc_prob*100:.1f}% [95% CI: {mc_ci[0]*100:.1f}%-{mc_ci[1]*100:.1f}%]\n"
        section += f"   • Mean (10-game): {mu:.1f} | Std Dev: {sigma:.2f}\n"
        section += f"   • Status: ✅ QUALIFIED\n\n"
        
        section += f"🏀 MATCHUP CONTEXT ({team} vs {opponent}):\n"
        section += f"   • Opponent Def Rank: #{matchup.get('opponent_def_rank', 'N/A')} ({matchup.get('opponent_def_rating', 'N/A')} rating)\n"
        section += f"   • Team Off Rank: #{matchup.get('team_off_rank', 'N/A')} ({matchup.get('team_off_rating', 'N/A')} rating)\n"
        section += f"   • Expected Pace: {matchup.get('pace', 'N/A')} possessions/game\n\n"
        
        # Get DeepSeek analysis
        props_for_ai = [{
            'player': player,
            'team': team,
            'opponent': opponent,
            'stat': stat,
            'line': line,
            'mu': mu,
            'sigma': sigma,
            'prob': mc_prob,
            'matchup': matchup
        }]
        
        deepseek_result = ai_analyzer.get_deepseek_analysis(
            props_for_ai,
            {
                'games': [f"{team} vs {opponent}"],
                'weather': 'Indoor (controlled)',
                'injuries': [],
                'team_stats': {
                    'opponent_defense': {
                        'rank': matchup.get('opponent_def_rank'),
                        'rating': matchup.get('opponent_def_rating'),
                        'pace': matchup.get('pace')
                    },
                    'team_offense': {
                        'rank': matchup.get('team_off_rank'),
                        'rating': matchup.get('team_off_rating')
                    }
                }
            }
        )
        
        section += f"🤖 AI ANALYSIS (DeepSeek):\n"
        section += f"   {json.dumps(deepseek_result, indent=3)}\n\n"
        
        # Get Ollama commentary
        game_data = {
            'home': opponent if team != opponent else team,
            'away': team if team != opponent else opponent,
            'datetime': 'Wednesday Night',
            'home_stats': {
                'def_rating': TEAM_DEFENSE_STATS.get(opponent, {}).get('def_rating', 'N/A'),
                'def_rank': TEAM_DEFENSE_STATS.get(opponent, {}).get('rank', 'N/A'),
                'off_rating': TEAM_OFFENSE_STATS.get(opponent, {}).get('off_rating', 'N/A'),
                'off_rank': TEAM_OFFENSE_STATS.get(opponent, {}).get('rank', 'N/A'),
                'pace': TEAM_DEFENSE_STATS.get(opponent, {}).get('pace', 'N/A')
            },
            'away_stats': {
                'def_rating': TEAM_DEFENSE_STATS.get(team, {}).get('def_rating', 'N/A'),
                'def_rank': TEAM_DEFENSE_STATS.get(team, {}).get('rank', 'N/A'),
                'off_rating': TEAM_OFFENSE_STATS.get(team, {}).get('off_rating', 'N/A'),
                'off_rank': TEAM_OFFENSE_STATS.get(team, {}).get('rank', 'N/A'),
                'pace': TEAM_DEFENSE_STATS.get(team, {}).get('pace', 'N/A')
            }
        }
        
        ollama_commentary = ai_analyzer.get_ollama_commentary(game_data, props_for_ai)
        
        section += f"📝 DEFENSIVE/OFFENSIVE SCHEME ANALYSIS (Ollama):\n"
        section += f"   {ollama_commentary[:600]}...\n"
        
        print(section)
        f.write(section + "\n")
    
    # Summary
    avg_mc = np.mean([p['mc_prob'] for p in top_picks]) * 100
    avg_bayesian = np.mean([p['bayesian_prob'] for p in top_picks]) * 100
    
    summary = f"\n{'=' * 100}\n"
    summary += f"✅ ANALYSIS COMPLETE | Top 10 Picks\n"
    summary += f"📊 Average Monte Carlo Confidence: {avg_mc:.1f}%\n"
    summary += f"📊 Average Bayesian Confidence: {avg_bayesian:.1f}%\n"
    summary += f"💾 Full report saved to: {output_file}\n"
    summary += "=" * 100 + "\n"
    
    print(summary)
    f.write(summary)

print(f"\n✅ Wednesday night analysis complete!")
print(f"📄 Report: {output_file}")
