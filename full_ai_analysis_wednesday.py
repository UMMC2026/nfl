#!/usr/bin/env python3
"""
FULL AI ANALYSIS - WEDNESDAY NBA SLATE
Monte Carlo + Bayesian + DeepSeek + Ollama
Complete with defensive/offensive schemes and coaching matchups
"""

import json
import numpy as np
from scipy.stats import norm
from datetime import datetime
import os
from dotenv import load_dotenv
import requests

load_dotenv()

# AI Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OLLAMA_URL = "http://localhost:11434/api/generate"

# Load slate
with open('nba_full_slate.json') as f:
    slate = json.load(f)

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

# Player stats (10-game averages)
stats = {
    ('Joel Embiid', 'points'): (28.4, 6.5), ('Joel Embiid', 'rebounds'): (10.8, 2.9), ('Joel Embiid', 'assists'): (4.6, 1.9),
    ('Donovan Mitchell', 'points'): (24.6, 5.9), ('Donovan Mitchell', 'rebounds'): (4.5, 1.6), ('Donovan Mitchell', 'assists'): (4.8, 2.1),
    ('Tyrese Maxey', 'points'): (26.8, 6.2), ('Tyrese Maxey', 'rebounds'): (3.4, 1.3), ('Tyrese Maxey', 'assists'): (6.9, 2.4),
    ('Paul George', 'points'): (18.2, 5.3), ('Paul George', 'rebounds'): (6.1, 2.0), ('Paul George', 'assists'): (4.8, 1.9),
    ('Evan Mobley', 'points'): (16.9, 4.5), ('Evan Mobley', 'rebounds'): (9.8, 2.6), ('Evan Mobley', 'assists'): (2.8, 1.2),
    ('Darius Garland', 'points'): (20.1, 5.4), ('Darius Garland', 'assists'): (6.8, 2.3),
    ('Jarrett Allen', 'points'): (13.2, 3.8), ('Jarrett Allen', 'rebounds'): (10.4, 2.7),
    ('Sam Merrill', 'points'): (11.2, 4.8),
    
    ('Brandon Ingram', 'points'): (22.4, 5.4), ('Brandon Ingram', 'rebounds'): (6.1, 2.0), ('Brandon Ingram', 'assists'): (5.6, 2.2),
    ('Pascal Siakam', 'points'): (21.7, 5.2), ('Pascal Siakam', 'rebounds'): (8.1, 2.4), ('Pascal Siakam', 'assists'): (4.2, 1.7),
    ('Scottie Barnes', 'points'): (19.8, 4.9), ('Scottie Barnes', 'rebounds'): (8.9, 2.5), ('Scottie Barnes', 'assists'): (6.1, 2.3),
    ('Andrew Nembhard', 'points'): (11.3, 3.9), ('Andrew Nembhard', 'assists'): (5.4, 2.0),
    
    ('Nikola Vucevic', 'points'): (20.1, 4.9), ('Nikola Vucevic', 'rebounds'): (10.2, 2.6), ('Nikola Vucevic', 'assists'): (3.2, 1.1),
    ('Keyonte George', 'points'): (24.3, 5.8), ('Keyonte George', 'assists'): (7.2, 2.5),
    ('Coby White', 'points'): (18.9, 4.7), ('Coby White', 'assists'): (4.9, 1.8),
    
    ('Zion Williamson', 'points'): (24.8, 5.3), ('Zion Williamson', 'rebounds'): (7.2, 2.1), ('Zion Williamson', 'assists'): (5.1, 1.7),
    ('Michael Porter Jr.', 'points'): (24.3, 5.8), ('Michael Porter Jr.', 'rebounds'): (7.2, 2.3), ('Michael Porter Jr.', 'assists'): (2.4, 1.0),
    ('Trey Murphy III', 'points'): (18.7, 5.1), ('Trey Murphy III', 'rebounds'): (5.2, 1.8),
    
    ('Jamal Murray', 'points'): (22.1, 5.7), ('Jamal Murray', 'assists'): (6.4, 2.2),
    ('Cooper Flagg', 'points'): (19.4, 5.2), ('Cooper Flagg', 'rebounds'): (7.8, 2.4),
    ('Peyton Watson', 'points'): (12.6, 3.9), ('Peyton Watson', 'rebounds'): (6.1, 2.0),
    
    ('Jalen Brunson', 'points'): (27.2, 6.1), ('Jalen Brunson', 'assists'): (7.8, 2.5),
    ('Karl-Anthony Towns', 'points'): (25.4, 5.9), ('Karl-Anthony Towns', 'rebounds'): (11.2, 2.8),
    ('DeMar DeRozan', 'points'): (22.8, 5.3), ('DeMar DeRozan', 'assists'): (5.1, 1.9),
    ('Domantas Sabonis', 'rebounds'): (13.2, 2.9), ('Domantas Sabonis', 'assists'): (7.1, 2.3),
    
    ('Kawhi Leonard', 'points'): (23.7, 5.6), ('Kawhi Leonard', 'rebounds'): (6.4, 2.1),
    ('James Harden', 'points'): (18.9, 4.8), ('James Harden', 'assists'): (9.2, 2.7),
    ('Alex Sarr', 'points'): (12.3, 3.7), ('Alex Sarr', 'rebounds'): (7.9, 2.3),
}

def mc_sim(mu, sigma, line, direction, trials=10000):
    """Monte Carlo simulation with 10k trials"""
    samples = np.random.normal(mu, sigma, trials)
    if direction == 'higher':
        hits = np.sum(samples > line)
    else:
        hits = np.sum(samples < line)
    return hits / trials

def get_deepseek_analysis(player, stat, line, direction, mu, sigma, mc_prob, bay_prob, player_team, opp_team):
    """Get analytical Bayesian commentary from DeepSeek"""
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API key not configured"
    
    prompt = f"""Analyze this NBA prop bet with Bayesian statistics:

Player: {player} ({player_team})
Opponent: {opp_team} (Def #{TEAM_DEFENSE[opp_team]['rank']}, {TEAM_DEFENSE[opp_team]['rating']} rating)
Stat: {stat} {direction} {line}
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
    
    prompt = f"""NBA coaching matchup analysis (2-3 sentences max):

{player_team} ({player_coach}: {player_style})
vs
{opp_team} ({opp_coach}: {opp_style})

How does {player}'s {stat} production benefit from this coaching/scheme matchup?"""

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
        
        return full_response.strip()[:400]  # Limit length
    except Exception as e:
        return f"Ollama error: {str(e)[:80]}"

# Build team matchups
matchups = {}
for game in slate['games']:
    away = game['away']
    home = game['home']
    matchups[away] = home
    matchups[home] = away

# Process all props
results = []
for play in slate['plays']:
    player = play['player']
    stat = play['stat']
    line = play['line']
    direction = play['direction']
    team = play['team']
    opp = matchups.get(team)
    
    if not opp:
        continue
    
    key = (player, stat)
    if key not in stats:
        continue
    
    mu, sigma = stats[key]
    
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

# Display top 15 WITH FULL AI COMMENTARY
print("\n" + "="*95)
print("FULL AI ANALYSIS - WEDNESDAY NBA SLATE - TOP 15 PICKS")
print("Monte Carlo + Bayesian + DeepSeek + Ollama")
print("="*95 + "\n")

for i, r in enumerate(results[:15], 1):
    # Use canonical thresholds from config/thresholds.py
    from config.thresholds import implied_tier
    tier = implied_tier(r['mc'], 'NBA')
    if tier == "SLAM":
        tier = "HOT"  # Legacy display name
    print(f"\n{'='*95}")
    print(f"{tier} PICK #{i} | MC: {r['mc']*100:.1f}% | BAYESIAN: {r['bay']*100:.1f}%")
    print(f"{'='*95}")
    print(f"\nPLAYER: {r['player']} ({r['team']})")
    print(f"PROP: {r['stat'].upper()} {r['direction'].upper()} {r['line']}")
    print(f"STATS: Average {r['mu']:.1f} +/- {r['sigma']:.1f} (last 10 games)")
    
    print(f"\nMATCHUP: {r['team']} @ {r['opp']}")
    print(f"  {r['team']} Offense: {TEAM_OFFENSE[r['team']]['style']}")
    print(f"    Rating: {TEAM_OFFENSE[r['team']]['rating']} | Pace: {TEAM_OFFENSE[r['team']]['pace']}")
    print(f"  {r['opp']} Defense: Rank #{TEAM_DEFENSE[r['opp']]['rank']} ({TEAM_DEFENSE[r['opp']]['rating']} rating)")
    print(f"    Scheme: {TEAM_DEFENSE[r['opp']]['scheme']}")
    print(f"    Strength: {TEAM_DEFENSE[r['opp']]['strength']}")
    
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

# Save to file with full reports
timestamp = datetime.now().strftime("%Y%m%d_%H%M")
output_file = f"outputs/FULL_AI_WEDNESDAY_{timestamp}.txt"
os.makedirs("outputs", exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("="*95 + "\n")
    f.write("FULL AI ANALYSIS - WEDNESDAY NBA SLATE\n")
    f.write("Monte Carlo + Bayesian + DeepSeek + Ollama\n")
    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}\n")
    f.write("="*95 + "\n\n")
    
    for i, r in enumerate(results[:15], 1):
        tier = implied_tier(r['mc'], 'NBA')
        if tier == "SLAM":
            tier = "HOT"  # Legacy display name
        f.write(f"\n{'='*95}\n")
        f.write(f"{tier} PICK #{i} | MC: {r['mc']*100:.1f}% | BAYESIAN: {r['bay']*100:.1f}%\n")
        f.write(f"{'='*95}\n\n")
        f.write(f"PLAYER: {r['player']} ({r['team']})\n")
        f.write(f"PROP: {r['stat'].upper()} {r['direction'].upper()} {r['line']}\n")
        f.write(f"STATS: Average {r['mu']:.1f} +/- {r['sigma']:.1f} (last 10 games)\n\n")
        
        f.write(f"MATCHUP: {r['team']} @ {r['opp']}\n")
        f.write(f"  {r['team']} Offense: {TEAM_OFFENSE[r['team']]['style']}\n")
        f.write(f"    Rating: {TEAM_OFFENSE[r['team']]['rating']} | Pace: {TEAM_OFFENSE[r['team']]['pace']}\n")
        f.write(f"  {r['opp']} Defense: Rank #{TEAM_DEFENSE[r['opp']]['rank']} ({TEAM_DEFENSE[r['opp']]['rating']} rating)\n")
        f.write(f"    Scheme: {TEAM_DEFENSE[r['opp']]['scheme']}\n")
        f.write(f"    Strength: {TEAM_DEFENSE[r['opp']]['strength']}\n\n")
        
        f.write(f"COACHING MATCHUP:\n")
        f.write(f"  {r['team']}: {COACHING_STYLES[r['team']]['coach']} - {COACHING_STYLES[r['team']]['style']}\n")
        f.write(f"  {r['opp']}: {COACHING_STYLES[r['opp']]['coach']} - {COACHING_STYLES[r['opp']]['style']}\n\n")
        
        # Get AI commentary for file
        deepseek = get_deepseek_analysis(r['player'], r['stat'], r['line'], r['direction'],
                                        r['mu'], r['sigma'], r['mc'], r['bay'],
                                        r['team'], r['opp'])
        ollama = get_ollama_commentary(r['player'], r['stat'], r['team'], r['opp'])
        
        f.write(f"--- DEEPSEEK ANALYTICAL REPORT ---\n{deepseek}\n\n")
        f.write(f"--- OLLAMA SCHEME COMMENTARY ---\n{ollama}\n\n")

print(f"\n{'='*95}")
print(f"Total qualified picks (>=65%): {len(results)}")
print(f"Average confidence: {np.mean([r['mc'] for r in results])*100:.1f}%")
print(f"\nFull AI analysis saved to: {output_file}")
print(f"{'='*95}")
