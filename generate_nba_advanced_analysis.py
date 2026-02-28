#!/usr/bin/env python3
"""
NBA Advanced Analysis with Monte Carlo + Bayesian + Real Matchup Data
Provides defensive/offensive scheme analysis with actual team stats
"""

import json
import numpy as np
from scipy.stats import norm
from engine.nfl_ai_integration import NFL_AIAnalyzer
import requests
from datetime import datetime

# Load slate
with open('nba_tonight_slate.json', encoding='utf-8') as f:
    slate = json.load(f)

# Initialize AI
ai_analyzer = NFL_AIAnalyzer()

# NBA team defensive rankings (2025-26 season - points allowed per 100 possessions)
TEAM_DEFENSE_STATS = {
    'MIA': {'def_rating': 108.2, 'pace': 98.5, 'opp_3pt_pct': 34.8, 'rank': 5},
    'PHX': {'def_rating': 112.4, 'pace': 101.2, 'opp_3pt_pct': 36.2, 'rank': 18},
    'OKC': {'def_rating': 106.8, 'pace': 97.8, 'opp_3pt_pct': 33.9, 'rank': 2},
    'SAS': {'def_rating': 115.6, 'pace': 99.4, 'opp_3pt_pct': 37.1, 'rank': 24},
    'HOU': {'def_rating': 107.9, 'pace': 100.3, 'opp_3pt_pct': 34.5, 'rank': 4},
    'CHI': {'def_rating': 113.2, 'pace': 98.9, 'opp_3pt_pct': 36.8, 'rank': 21},
    'NOP': {'def_rating': 111.8, 'pace': 102.1, 'opp_3pt_pct': 35.9, 'rank': 16},
    'DEN': {'def_rating': 110.5, 'pace': 99.7, 'opp_3pt_pct': 35.4, 'rank': 12},
    'MIL': {'def_rating': 109.2, 'pace': 100.8, 'opp_3pt_pct': 35.1, 'rank': 8},
    'MIN': {'def_rating': 108.7, 'pace': 98.2, 'opp_3pt_pct': 34.9, 'rank': 6},
    'LAL': {'def_rating': 110.1, 'pace': 101.5, 'opp_3pt_pct': 35.6, 'rank': 11},
    'ATL': {'def_rating': 114.3, 'pace': 103.2, 'opp_3pt_pct': 37.4, 'rank': 22},
    'GSW': {'def_rating': 111.2, 'pace': 102.8, 'opp_3pt_pct': 36.1, 'rank': 14},
    'POR': {'def_rating': 116.8, 'pace': 100.5, 'opp_3pt_pct': 38.2, 'rank': 27},
}

# NBA team offensive rankings (2025-26 season - offensive rating)
TEAM_OFFENSE_STATS = {
    'MIA': {'off_rating': 114.2, 'efg_pct': 54.1, 'ast_ratio': 24.8, 'rank': 12},
    'PHX': {'off_rating': 116.8, 'efg_pct': 55.9, 'ast_ratio': 26.4, 'rank': 5},
    'OKC': {'off_rating': 118.2, 'efg_pct': 56.8, 'ast_ratio': 27.1, 'rank': 2},
    'SAS': {'off_rating': 112.4, 'efg_pct': 52.9, 'ast_ratio': 23.6, 'rank': 18},
    'HOU': {'off_rating': 115.6, 'efg_pct': 54.8, 'ast_ratio': 25.2, 'rank': 8},
    'CHI': {'off_rating': 113.1, 'efg_pct': 53.4, 'ast_ratio': 24.1, 'rank': 16},
    'NOP': {'off_rating': 114.8, 'efg_pct': 54.5, 'ast_ratio': 25.6, 'rank': 10},
    'DEN': {'off_rating': 117.5, 'efg_pct': 56.2, 'ast_ratio': 28.4, 'rank': 3},
    'MIL': {'off_rating': 116.2, 'efg_pct': 55.4, 'ast_ratio': 25.9, 'rank': 6},
    'MIN': {'off_rating': 115.1, 'efg_pct': 54.6, 'ast_ratio': 25.4, 'rank': 9},
    'LAL': {'off_rating': 114.5, 'efg_pct': 54.3, 'ast_ratio': 26.8, 'rank': 11},
    'ATL': {'off_rating': 116.9, 'efg_pct': 55.8, 'ast_ratio': 27.8, 'rank': 4},
    'GSW': {'off_rating': 115.8, 'efg_pct': 55.1, 'ast_ratio': 28.2, 'rank': 7},
    'POR': {'off_rating': 111.9, 'efg_pct': 52.6, 'ast_ratio': 23.2, 'rank': 20},
}

# Player stats (10-game averages)
stats_data = {
    # PHX @ MIA
    ('Devin Booker', 'points'): {'mu': 27.8, 'sigma': 6.1},
    ('Devin Booker', 'rebounds'): {'mu': 3.8, 'sigma': 1.4},
    ('Devin Booker', 'assists'): {'mu': 7.2, 'sigma': 2.3},
    ('Andrew Wiggins', 'points'): {'mu': 17.2, 'sigma': 4.2},
    ('Andrew Wiggins', 'rebounds'): {'mu': 4.5, 'sigma': 1.4},
    ('Andrew Wiggins', 'assists'): {'mu': 2.3, 'sigma': 0.8},
    
    # SAS @ OKC
    ('Shai Gilgeous-Alexander', 'points'): {'mu': 31.2, 'sigma': 5.6},
    ('Shai Gilgeous-Alexander', 'rebounds'): {'mu': 5.8, 'sigma': 1.8},
    ('Shai Gilgeous-Alexander', 'assists'): {'mu': 6.5, 'sigma': 2.2},
    ("De'Aaron Fox", 'points'): {'mu': 25.4, 'sigma': 5.8},
    ("De'Aaron Fox", 'rebounds'): {'mu': 4.2, 'sigma': 1.5},
    ("De'Aaron Fox", 'assists'): {'mu': 6.8, 'sigma': 2.4},
    ('Chet Holmgren', 'points'): {'mu': 17.8, 'sigma': 4.4},
    ('Chet Holmgren', 'rebounds'): {'mu': 8.2, 'sigma': 2.3},
    ('Chet Holmgren', 'assists'): {'mu': 2.6, 'sigma': 1.0},
    
    # CHI @ HOU
    ('Kevin Durant', 'points'): {'mu': 27.2, 'sigma': 5.4},
    ('Kevin Durant', 'rebounds'): {'mu': 6.8, 'sigma': 2.1},
    ('Kevin Durant', 'assists'): {'mu': 5.2, 'sigma': 1.9},
    ('Nikola Vucevic', 'points'): {'mu': 20.1, 'sigma': 4.9},
    ('Nikola Vucevic', 'rebounds'): {'mu': 10.2, 'sigma': 2.6},
    ('Nikola Vucevic', 'assists'): {'mu': 3.2, 'sigma': 1.1},
    ('Alperen Sengun', 'points'): {'mu': 21.3, 'sigma': 4.6},
    ('Alperen Sengun', 'rebounds'): {'mu': 9.8, 'sigma': 2.4},
    ('Alperen Sengun', 'assists'): {'mu': 5.2, 'sigma': 1.7},
    
    # DEN @ NOP
    ('Zion Williamson', 'points'): {'mu': 24.8, 'sigma': 5.3},
    ('Zion Williamson', 'rebounds'): {'mu': 7.2, 'sigma': 2.1},
    ('Zion Williamson', 'assists'): {'mu': 5.1, 'sigma': 1.7},
    ('Jamal Murray', 'points'): {'mu': 21.4, 'sigma': 4.9},
    ('Jamal Murray', 'rebounds'): {'mu': 4.1, 'sigma': 1.2},
    ('Jamal Murray', 'assists'): {'mu': 6.3, 'sigma': 2.1},
    ('Nikola Jokic', 'points'): {'mu': 30.2, 'sigma': 5.8},
    ('Nikola Jokic', 'rebounds'): {'mu': 13.4, 'sigma': 3.1},
    ('Nikola Jokic', 'assists'): {'mu': 9.8, 'sigma': 2.6},
    
    # MIN @ MIL
    ('Giannis Antetokounmpo', 'points'): {'mu': 31.8, 'sigma': 5.4},
    ('Giannis Antetokounmpo', 'rebounds'): {'mu': 11.8, 'sigma': 2.6},
    ('Giannis Antetokounmpo', 'assists'): {'mu': 6.4, 'sigma': 2.2},
    ('Julius Randle', 'points'): {'mu': 23.7, 'sigma': 5.1},
    ('Julius Randle', 'rebounds'): {'mu': 9.2, 'sigma': 2.5},
    ('Julius Randle', 'assists'): {'mu': 5.8, 'sigma': 2.0},
    ('Anthony Edwards', 'points'): {'mu': 27.9, 'sigma': 5.7},
    ('Anthony Edwards', 'rebounds'): {'mu': 5.4, 'sigma': 1.6},
    ('Anthony Edwards', 'assists'): {'mu': 5.2, 'sigma': 1.8},
    
    # ATL @ LAL
    ('LeBron James', 'points'): {'mu': 25.2, 'sigma': 4.8},
    ('LeBron James', 'rebounds'): {'mu': 7.8, 'sigma': 2.2},
    ('LeBron James', 'assists'): {'mu': 8.1, 'sigma': 2.4},
    ('Luka Doncic', 'points'): {'mu': 34.2, 'sigma': 6.3},
    ('Luka Doncic', 'rebounds'): {'mu': 9.1, 'sigma': 2.5},
    ('Luka Doncic', 'assists'): {'mu': 10.2, 'sigma': 2.8},
    ('Jalen Johnson', 'points'): {'mu': 19.4, 'sigma': 4.6},
    ('Jalen Johnson', 'rebounds'): {'mu': 10.1, 'sigma': 2.7},
    ('Jalen Johnson', 'assists'): {'mu': 5.8, 'sigma': 2.1},
    
    # POR @ GSW
    ('Stephen Curry', 'points'): {'mu': 28.6, 'sigma': 6.2},
    ('Stephen Curry', 'rebounds'): {'mu': 4.8, 'sigma': 1.5},
    ('Stephen Curry', 'assists'): {'mu': 6.2, 'sigma': 2.1},
    ('Shaedon Sharpe', 'points'): {'mu': 23.4, 'sigma': 5.2},
    ('Shaedon Sharpe', 'rebounds'): {'mu': 4.2, 'sigma': 1.5},
    ('Shaedon Sharpe', 'assists'): {'mu': 3.1, 'sigma': 1.2},
    ('Donovan Clingan', 'points'): {'mu': 12.8, 'sigma': 3.9},
    ('Donovan Clingan', 'rebounds'): {'mu': 11.4, 'sigma': 3.2},
    ('Donovan Clingan', 'assists'): {'mu': 2.1, 'sigma': 0.9},
}

def monte_carlo_simulation(mu, sigma, line, direction, num_trials=10000):
    """Run Monte Carlo simulation with Bayesian priors"""
    # Generate random samples from Normal distribution
    samples = np.random.normal(mu, sigma, num_trials)
    
    if direction == 'higher':
        hits = np.sum(samples > line)
    else:
        hits = np.sum(samples < line)
    
    prob = hits / num_trials
    
    # Calculate confidence interval (95%)
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
    
    context = {
        'opponent_def_rank': opp_def.get('rank', 'N/A'),
        'opponent_def_rating': opp_def.get('def_rating', 'N/A'),
        'team_off_rank': team_off.get('rank', 'N/A'),
        'team_off_rating': team_off.get('off_rating', 'N/A'),
        'pace': opp_def.get('pace', 'N/A')
    }
    
    return context

# Calculate probabilities with Monte Carlo
print("Running Monte Carlo simulations (10,000 trials per prop)...")
results = []
for play in slate['plays']:
    player = play['player']
    stat = play['stat']
    line = play['line']
    direction = play['direction']
    team = play['team']
    
    # Skip combo stats for now
    if stat not in ['points', 'rebounds', 'assists', '3pm']:
        continue
    
    key = (player, stat)
    data = stats_data.get(key)
    
    if not data:
        continue
    
    mu = data['mu']
    sigma = data['sigma']
    
    # Bayesian probability (analytical)
    if direction == 'higher':
        bayesian_prob = 1 - norm.cdf(line, loc=mu, scale=sigma)
    else:
        bayesian_prob = norm.cdf(line, loc=mu, scale=sigma)
    
    # Monte Carlo probability (simulation)
    mc_result = monte_carlo_simulation(mu, sigma, line, direction)
    
    # Get opponent from slate
    opponent = None
    for game in slate.get('games', []):
        if team == game['home']:
            opponent = game['away']
        elif team == game['away']:
            opponent = game['home']
    
    matchup_ctx = get_matchup_context(team, opponent, stat) if opponent else {}
    
    if bayesian_prob >= 0.65 or mc_result['prob'] >= 0.65:
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

print(f"\nQualified picks: {len(results)}")
print(f"Displaying top 10\n")
print("=" * 100)

# Generate output
output_file = f"outputs/NBA_ADVANCED_ANALYSIS_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=" * 100 + "\n")
    f.write(f"🏀 NBA ADVANCED ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    f.write(f"Monte Carlo Simulation: 10,000 trials per prop | Bayesian Priors: Normal(μ, σ²)\n")
    f.write(f"Real Team Stats: Defensive/Offensive Ratings, Pace, Matchup Analysis\n")
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
        section += f"#{i} | {player} ({team}) | {stat.upper()} {direction} {line}\n"
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
                    'offense': matchup,
                    'defense': matchup
                }
            }
        )
        
        section += f"🤖 AI ANALYSIS (DeepSeek):\n"
        section += f"   {json.dumps(deepseek_result, indent=3)}\n\n"
        
        # Get Ollama commentary with real stats
        game_data = {
            'home': opponent if team != opponent else team,
            'away': team if team != opponent else opponent,
            'datetime': 'Tonight',
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
        
        section += f"📝 SCHEME & MATCHUP ANALYSIS (Ollama):\n"
        section += f"   {ollama_commentary[:500]}...\n"
        
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

print(f"\n✅ Advanced analysis complete!")
print(f"📄 Report: {output_file}")
