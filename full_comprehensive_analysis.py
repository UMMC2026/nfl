#!/usr/bin/env python3
"""
COMPREHENSIVE WEDNESDAY NBA ANALYSIS
All stat types: PTS, REB, AST, PRA, PR, PA, RA, 3PM, STL, BLK
Monte Carlo + Bayesian + DeepSeek + Ollama
"""

import numpy as np
from scipy.stats import norm
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import requests

load_dotenv()

# AI Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OLLAMA_URL = "http://localhost:11434/api/generate"

# Import comprehensive stats
from comprehensive_stats_dict import PLAYER_STATS, calculate_combo_stats

# Enhanced Team Defense with Schemes
TEAM_DEFENSE = {
    'PHI': {'rank': 9, 'rating': 109.5, 'scheme': 'Drop coverage with Embiid anchor', 'strength': 'Interior defense'},
    'CLE': {'rank': 1, 'rating': 106.5, 'scheme': 'Switch-heavy with elite rim protection', 'strength': 'Paint defense'},
    'IND': {'rank': 20, 'rating': 113.7, 'scheme': 'Pace-first, bend-don\'t-break', 'strength': 'Transition stops'},
    'TOR': {'rank': 23, 'rating': 114.5, 'scheme': 'Aggressive trapping', 'strength': 'Perimeter pressure'},
    'CHI': {'rank': 21, 'rating': 113.2, 'scheme': 'Switch with Vucevic drop', 'strength': 'Pick-and-roll coverage'},
    'UTA': {'rank': 28, 'rating': 117.2, 'scheme': 'Conservative drop', 'strength': 'Limited in transition'},
    'NOP': {'rank': 16, 'rating': 111.8, 'scheme': 'Athletic switching', 'strength': 'Perimeter closeouts'},
    'BKN': {'rank': 25, 'rating': 115.2, 'scheme': 'High variance switching', 'strength': 'Weak rim protection'},
    'DAL': {'rank': 13, 'rating': 110.8, 'scheme': 'Conservative with Flagg anchor', 'strength': 'Disciplined rotations'},
    'DEN': {'rank': 12, 'rating': 110.5, 'scheme': 'Jokic zone with help', 'strength': 'Smart rotations'},
    'SAC': {'rank': 17, 'rating': 112.3, 'scheme': 'Pace-matching defense', 'strength': 'Transition stops'},
    'NYK': {'rank': 7, 'rating': 108.9, 'scheme': 'Thibs aggressive hedge', 'strength': 'Physical defensive identity'},
    'LAC': {'rank': 10, 'rating': 109.8, 'scheme': 'Kawhi elite switching', 'strength': 'Elite perimeter defense'},
    'WAS': {'rank': 29, 'rating': 118.5, 'scheme': 'Rebuilding, inconsistent', 'strength': 'Limited'},
}

# Team Offense Styles
TEAM_OFFENSE = {
    'PHI': {'rating': 115.8, 'pace': 97.2, 'style': 'Embiid post-up with spacing'},
    'CLE': {'rating': 118.2, 'pace': 98.5, 'style': 'Mitchell/Garland PnR attack'},
    'IND': {'rating': 121.3, 'pace': 103.2, 'style': 'Fastest pace, transition'},
    'TOR': {'rating': 110.5, 'pace': 99.1, 'style': 'Balanced attack, Ingram creation'},
    'CHI': {'rating': 112.4, 'pace': 100.1, 'style': 'Vucevic hub with perimeter shooting'},
    'UTA': {'rating': 108.9, 'pace': 96.8, 'style': 'Methodical halfcourt'},
    'NOP': {'rating': 116.7, 'pace': 100.8, 'style': 'Zion downhill attack'},
    'BKN': {'rating': 111.2, 'pace': 101.5, 'style': 'Isolation heavy'},
    'DAL': {'rating': 117.2, 'pace': 98.9, 'style': 'Flagg + shooters spacing'},
    'DEN': {'rating': 119.5, 'pace': 97.8, 'style': 'Jokic orchestrated offense'},
    'SAC': {'rating': 118.9, 'pace': 102.3, 'style': 'Fast-paced Fox/DeRozan'},
    'NYK': {'rating': 114.6, 'pace': 96.5, 'style': 'Brunson PnR, halfcourt grind'},
    'LAC': {'rating': 116.1, 'pace': 97.1, 'style': 'Kawhi/Harden two-man game'},
    'WAS': {'rating': 109.8, 'pace': 100.5, 'style': 'Young talent development'},
}

# Coaching Styles
COACHING_STYLES = {
    'PHI': {'coach': 'Nick Nurse', 'style': 'Creative schemes, aggressive adjustments'},
    'CLE': {'coach': 'Kenny Atkinson', 'style': 'Player development, offensive fluidity'},
    'IND': {'coach': 'Rick Carlisle', 'style': 'Offensive genius, fast tempo'},
    'TOR': {'coach': 'Darko Rajakovic', 'style': 'Player empowerment, pace-and-space'},
    'CHI': {'coach': 'Billy Donovan', 'style': 'Defensive fundamentals, motion offense'},
    'UTA': {'coach': 'Will Hardy', 'style': 'Defensive discipline, rebuilding focus'},
    'NOP': {'coach': 'Willie Green', 'style': 'Zion-centric, up-tempo'},
    'BKN': {'coach': 'Jordi Fernandez', 'style': 'First-year, player-led system'},
    'DAL': {'coach': 'Jason Kidd', 'style': 'Defensive-minded, strategic'},
    'DEN': {'coach': 'Michael Malone', 'style': 'Jokic system maestro'},
    'SAC': {'coach': 'Mike Brown', 'style': 'Pace-and-space, defensive improvement'},
    'NYK': {'coach': 'Tom Thibodeau', 'style': 'Defensive identity, grinding halfcourt'},
    'LAC': {'coach': 'Tyronn Lue', 'style': 'Star management, playoff pedigree'},
    'WAS': {'coach': 'Brian Keefe', 'style': 'Development-focused, rebuilding'},
}

# Wednesday games matchups
MATCHUPS = {
    'CLE': 'PHI', 'PHI': 'CLE',
    'TOR': 'IND', 'IND': 'TOR',
    'UTA': 'CHI', 'CHI': 'UTA',
    'BKN': 'NOP', 'NOP': 'BKN',
    'DEN': 'DAL', 'DAL': 'DEN',
    'NYK': 'SAC', 'SAC': 'NYK',
    'WAS': 'LAC', 'LAC': 'WAS',
}

# Load FULL slate from JSON
with open('nba_full_wednesday_comprehensive.json', 'r') as f:
    slate_data = json.load(f)
    PROPS = slate_data['plays']

def mc_sim(mu, sigma, line, direction, trials=10000):
    """Monte Carlo simulation"""
    samples = np.random.normal(mu, sigma, trials)
    if direction == 'higher':
        hits = np.sum(samples > line)
    else:
        hits = np.sum(samples < line)
    return hits / trials

def get_stat_params(player, stat):
    """Get mean and sigma for any stat type (single or combo)"""
    combo_types = ['pra', 'pr', 'pa', 'ra', 'stocks']
    
    if stat in combo_types:
        # Calculate combo stat
        mu, sigma = calculate_combo_stats(player, stat)
        return mu, sigma
    else:
        # Direct lookup
        key = (player, stat)
        if key in PLAYER_STATS:
            return PLAYER_STATS[key]
        return None, None

def get_deepseek_analysis(player, stat, line, direction, mu, sigma, mc_prob, bay_prob, player_team, opp_team):
    """Get analytical commentary from DeepSeek"""
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API key not configured"
    
    stat_display = stat.upper()
    if stat == 'pra':
        stat_display = "PTS+REB+AST"
    elif stat == 'pr':
        stat_display = "PTS+REB"
    elif stat == 'pa':
        stat_display = "PTS+AST"
    elif stat == 'ra':
        stat_display = "REB+AST"
    elif stat == '3pm':
        stat_display = "3-Pointers Made"
    elif stat == 'stocks':
        stat_display = "BLK+STL"
    
    prompt = f"""Analyze this NBA prop bet with Bayesian statistics:

Player: {player} ({player_team})
Opponent: {opp_team} (Def #{TEAM_DEFENSE[opp_team]['rank']}, {TEAM_DEFENSE[opp_team]['rating']} rating)
Stat: {stat_display} {direction} {line}
Recent average: {mu:.1f} ± {sigma:.1f}
Monte Carlo: {mc_prob*100:.1f}%
Bayesian: {bay_prob*100:.1f}%

Defense scheme: {TEAM_DEFENSE[opp_team]['scheme']}
Offense style: {TEAM_OFFENSE[player_team]['style']}

Provide 2-3 sentence analytical breakdown focusing on statistical edge and matchup context."""

    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200
            },
            timeout=15
        )
        return response.json()['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"DeepSeek error: {str(e)[:80]}"

def get_ollama_commentary(player, stat, player_team, opp_team):
    """Get coaching/scheme matchup commentary from Ollama"""
    player_coach = COACHING_STYLES[player_team]['coach']
    player_style = COACHING_STYLES[player_team]['style']
    opp_coach = COACHING_STYLES[opp_team]['coach']
    opp_style = COACHING_STYLES[opp_team]['style']
    
    stat_context = stat.upper()
    if stat == 'pra':
        stat_context = "all-around PTS+REB+AST production"
    elif stat in ['pr', 'pa', 'ra']:
        stat_context = f"{stat.upper()} combo stat"
    
    prompt = f"""NBA coaching matchup analysis (2-3 sentences max):

{player_team} ({player_coach}: {player_style})
vs
{opp_team} ({opp_coach}: {opp_style})

How does {player}'s {stat_context} benefit from this coaching/scheme matchup?"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3.2:1b",
                "prompt": prompt,
                "stream": True,
                "options": {"num_predict": 200, "temperature": 0.7}
            },
            timeout=25,
            stream=True
        )
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "response" in chunk:
                    full_response += chunk["response"]
                if chunk.get("done"):
                    break
        
        return full_response.strip()[:400]
    except Exception as e:
        return f"Ollama error: {str(e)[:80]}"

# Process all props
print("\n" + "="*100)
print("COMPREHENSIVE WEDNESDAY NBA ANALYSIS - ALL STAT TYPES")
print("Analyzing: PTS, REB, AST, PRA, PR, PA, RA, 3PM, STL, BLK")
print("="*100 + "\n")

results = []
skipped = []

for prop in PROPS:
    player = prop['player']
    stat = prop['stat']
    line = prop['line']
    direction = prop['direction']
    team = prop['team']
    opp = MATCHUPS.get(team)
    
    if not opp:
        continue
    
    # Get stat parameters (handles both single and combo stats)
    mu, sigma = get_stat_params(player, stat)
    
    if mu is None or sigma is None:
        skipped.append(f"{player} - {stat}")
        continue
    
    # Monte Carlo
    mc_prob = mc_sim(mu, sigma, line, direction)
    
    # Bayesian (Normal CDF)
    z = (line - mu) / sigma
    bay_prob = 1 - norm.cdf(z) if direction == 'higher' else norm.cdf(z)
    
    # Qualify if >= 65%
    if mc_prob >= 0.65:
        results.append({
            'player': player,
            'team': team,
            'opp': opp,
            'stat': stat,
            'line': line,
            'direction': direction,
            'mu': mu,
            'sigma': sigma,
            'mc': mc_prob,
            'bay': bay_prob
        })

# Sort by MC probability
results.sort(key=lambda x: x['mc'], reverse=True)

# Display top 30 WITH FULL AI COMMENTARY
print(f"Analyzed {len(PROPS)} props | Qualified: {len(results)} | Skipped: {len(skipped)}\n")

for i, r in enumerate(results[:30], 1):
    # Use canonical thresholds from config/thresholds.py
    from config.thresholds import implied_tier
    tier = implied_tier(r['mc'], 'NBA')
    if tier == "SLAM":
        tier = "HOT"  # Legacy display name
    
    stat_display = r['stat'].upper()
    if r['stat'] == 'pra':
        stat_display = "PTS+REB+AST"
    elif r['stat'] == 'pr':
        stat_display = "PTS+REB"
    elif r['stat'] == 'pa':
        stat_display = "PTS+AST"
    elif r['stat'] == 'ra':
        stat_display = "REB+AST"
    elif r['stat'] == '3pm':
        stat_display = "3-Pointers Made"
    
    print(f"\n{'='*100}")
    print(f"{tier} PICK #{i} | MC: {r['mc']*100:.1f}% | BAYESIAN: {r['bay']*100:.1f}%")
    print(f"{'='*100}")
    print(f"\nPLAYER: {r['player']} ({r['team']})")
    print(f"PROP: {stat_display} {r['direction'].upper()} {r['line']}")
    print(f"STATS: Average {r['mu']:.1f} +/- {r['sigma']:.1f} (last 10 games)")
    
    print(f"\nMATCHUP: {r['team']} @ {r['opp']}")
    print(f"  {r['team']} Offense: {TEAM_OFFENSE[r['team']]['style']}")
    print(f"    Rating: {TEAM_OFFENSE[r['team']]['rating']} | Pace: {TEAM_OFFENSE[r['team']]['pace']}")
    print(f"  {r['opp']} Defense: Rank #{TEAM_DEFENSE[r['opp']]['rank']} ({TEAM_DEFENSE[r['opp']]['rating']} rating)")
    print(f"    Scheme: {TEAM_DEFENSE[r['opp']]['scheme']}")
    
    print(f"\nCOACHING MATCHUP:")
    print(f"  {r['team']}: {COACHING_STYLES[r['team']]['coach']} - {COACHING_STYLES[r['team']]['style']}")
    print(f"  {r['opp']}: {COACHING_STYLES[r['opp']]['coach']} - {COACHING_STYLES[r['opp']]['style']}")
    
    print(f"\n--- DEEPSEEK ANALYTICAL REPORT ---")
    deepseek_analysis = get_deepseek_analysis(
        r['player'], r['stat'], r['line'], r['direction'],
        r['mu'], r['sigma'], r['mc'], r['bay'],
        r['team'], r['opp']
    )
    print(deepseek_analysis)
    
    print(f"\n--- OLLAMA SCHEME COMMENTARY ---")
    ollama_commentary = get_ollama_commentary(r['player'], r['stat'], r['team'], r['opp'])
    print(ollama_commentary)
    print()

# Save to file
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
output_file = f"outputs/COMPREHENSIVE_WEDNESDAY_{timestamp}.txt"
os.makedirs("outputs", exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("="*100 + "\n")
    f.write("COMPREHENSIVE WEDNESDAY NBA ANALYSIS - ALL STAT TYPES\n")
    f.write("PTS, REB, AST, PRA, PR, PA, RA, 3PM, STL, BLK\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}\n")
    f.write("="*100 + "\n\n")
    
    for i, r in enumerate(results[:30], 1):
        tier = implied_tier(r['mc'], 'NBA')
        if tier == "SLAM":
            tier = "HOT"  # Legacy display name
        
        stat_display = r['stat'].upper()
        if r['stat'] == 'pra':
            stat_display = "PTS+REB+AST"
        elif r['stat'] == 'pr':
            stat_display = "PTS+REB"
        elif r['stat'] == 'pa':
            stat_display = "PTS+AST"
        elif r['stat'] == 'ra':
            stat_display = "REB+AST"
        
        f.write(f"\n{'='*100}\n")
        f.write(f"{tier} PICK #{i} | MC: {r['mc']*100:.1f}% | BAYESIAN: {r['bay']*100:.1f}%\n")
        f.write(f"{'='*100}\n\n")
        f.write(f"PLAYER: {r['player']} ({r['team']})\n")
        f.write(f"PROP: {stat_display} {r['direction'].upper()} {r['line']}\n")
        f.write(f"STATS: Average {r['mu']:.1f} +/- {r['sigma']:.1f}\n\n")
        
        f.write(f"MATCHUP: {r['team']} @ {r['opp']}\n")
        f.write(f"  Defense: Rank #{TEAM_DEFENSE[r['opp']]['rank']} | Scheme: {TEAM_DEFENSE[r['opp']]['scheme']}\n\n")
        
        # Get AI commentary
        deepseek = get_deepseek_analysis(r['player'], r['stat'], r['line'], r['direction'],
                                        r['mu'], r['sigma'], r['mc'], r['bay'],
                                        r['team'], r['opp'])
        ollama = get_ollama_commentary(r['player'], r['stat'], r['team'], r['opp'])
        
        f.write(f"--- DEEPSEEK ANALYTICAL REPORT ---\n{deepseek}\n\n")
        f.write(f"--- OLLAMA SCHEME COMMENTARY ---\n{ollama}\n\n")

print(f"\n{'='*100}")
print(f"Total qualified picks (>=65%): {len(results)}")
print(f"Average confidence: {np.mean([r['mc'] for r in results])*100:.1f}%")
print(f"\nFull analysis saved to: {output_file}")
print(f"{'='*100}")
