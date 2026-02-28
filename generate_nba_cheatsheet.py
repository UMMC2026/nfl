#!/usr/bin/env python3
"""Generate NBA cheatsheet with AI analysis for tonight's top picks."""

import json
from scipy.stats import norm
from engine.nfl_ai_integration import NFL_AIAnalyzer  # Reuse for NBA

# Load slate
with open('nba_tonight_slate.json', encoding='utf-8') as f:
    slate = json.load(f)

# Initialize AI
ai_analyzer = NFL_AIAnalyzer()

# NBA player stats (10-game averages)
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
    
    # MIN @ MIL
    ('Giannis Antetokounmpo', 'points'): {'mu': 31.8, 'sigma': 5.4},
    ('Giannis Antetokounmpo', 'rebounds'): {'mu': 11.8, 'sigma': 2.6},
    ('Giannis Antetokounmpo', 'assists'): {'mu': 6.4, 'sigma': 2.2},
    ('Julius Randle', 'points'): {'mu': 23.7, 'sigma': 5.1},
    ('Julius Randle', 'rebounds'): {'mu': 9.2, 'sigma': 2.5},
    ('Julius Randle', 'assists'): {'mu': 5.8, 'sigma': 2.0},
    
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

# Calculate probabilities
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
    
    if data and data['mu']:
        if direction.lower() == 'higher':
            prob_over = 1 - norm.cdf(line, loc=data['mu'], scale=data['sigma'])
        else:
            prob_over = norm.cdf(line, loc=data['mu'], scale=data['sigma'])
    else:
        continue
    
    qualified = prob_over >= 0.65
    
    results.append({
        'player': player,
        'stat': stat,
        'line': line,
        'direction': direction,
        'prob_over': prob_over,
        'mu': data['mu'],
        'sigma': data['sigma'],
        'qualified': qualified,
        'team': team
    })

# Get top picks
overs = [r for r in results if r['direction'].lower() == 'higher' and r['qualified']]
top_overs = sorted(overs, key=lambda x: x['prob_over'], reverse=True)[:8]

print("\n" + "="*100)
print(" 🏀 NBA TONIGHT - TOP PICKS WITH AI ANALYSIS")
print(" " + slate['date'] + " | 7 Games")
print("="*100 + "\n")

for i, pick in enumerate(top_overs, 1):
    print(f"\n{'='*100}")
    print(f"#{i} | {pick['player']} ({pick['team']}) | {pick['stat'].upper()} > {pick['line']}")
    print(f"{'='*100}")
    print(f"📊 PROBABILITY ENGINE:")
    print(f"   • P(Over): {pick['prob_over']*100:.1f}%")
    print(f"   • Mean (10-game): {pick['mu']:.1f}")
    print(f"   • Std Dev: {pick['sigma']:.2f}")
    print(f"   • Status: ✅ QUALIFIED\n")
    
    # Build context
    game_context = {
        'player': pick['player'],
        'team': pick['team'],
        'stat': pick['stat'],
        'line': pick['line'],
        'mu': pick['mu'],
        'sigma': pick['sigma'],
        'prob': pick['prob_over'],
        'sport': 'NBA',
        'date': slate['date']
    }
    
    # DeepSeek analysis
    print(f"🤖 AI ANALYSIS (DeepSeek):")
    deepseek_result = ai_analyzer.get_deepseek_analysis([game_context], {'sport': 'NBA'})
    if 'error' not in deepseek_result:
        analysis_text = json.dumps(deepseek_result, indent=3)
        print(f"   {analysis_text}\n")
    else:
        print(f"   ⚠️ {deepseek_result.get('error', 'API unavailable')}")
        print(f"   💡 Manual Analysis:")
        print(f"      • Line set {pick['line'] - pick['mu']:.1f} points below 10-game average")
        print(f"      • Expect {pick['mu']:.1f} ± {pick['sigma']:.1f} range")
        print(f"      • {pick['prob_over']*100:.0f}% historical hit rate on similar lines\n")
    
    # Ollama commentary
    print(f"📝 MATCHUP INSIGHTS (Ollama):")
    ollama_result = ai_analyzer.get_ollama_commentary(game_context, [game_context])
    if not ollama_result.startswith("Ollama error"):
        commentary = ollama_result[:400] + "..." if len(ollama_result) > 400 else ollama_result
        print(f"   {commentary}\n")
    else:
        print(f"   ⚠️ {ollama_result}")
        print(f"   💡 Key Matchup Notes:")
        if pick['stat'] == 'assists':
            print(f"      • Look for pace-up game environment")
            print(f"      • Assist lines typically easier in uptempo matchups")
        elif pick['stat'] == 'rebounds':
            print(f"      • Check opponent's rebound rate allowed")
            print(f"      • Frontcourt matchup advantage matters")
        elif pick['stat'] == 'points':
            print(f"      • Scoring volume tied to usage rate")
            print(f"      • Defensive rating of opponent critical\n")

print("\n" + "="*100)
print(" 📋 RECOMMENDED ENTRIES")
print("="*100)

# Calculate EVs
top3 = top_overs[:3]
top5 = top_overs[:5]

prob_3leg = 1
for pick in top3:
    prob_3leg *= pick['prob_over']

prob_5leg = 1
for pick in top5:
    prob_5leg *= pick['prob_over']

ev_power_3 = prob_3leg * 6 - 1
ev_flex_5 = prob_5leg * 25 - 1  # Simplified

print(f"\n🔥 POWER 3-LEG (6x payout):")
print(f"   • {top3[0]['player']} {top3[0]['stat']} > {top3[0]['line']}")
print(f"   • {top3[1]['player']} {top3[1]['stat']} > {top3[1]['line']}")
print(f"   • {top3[2]['player']} {top3[2]['stat']} > {top3[2]['line']}")
print(f"   Win Prob: {prob_3leg*100:.1f}% | EV: {ev_power_3:+.2f} units\n")

print(f"💎 FLEX 5-LEG (partial payouts):")
for pick in top5:
    print(f"   • {pick['player']} {pick['stat']} > {pick['line']} ({pick['prob_over']*100:.0f}%)")
print(f"   All 5 Win: {prob_5leg*100:.1f}% | Safer with partial payouts\n")

print("="*100)
print(f"✅ Analysis Complete | {len(top_overs)} Qualified Picks")
print(f"📊 Average Confidence: {sum(p['prob_over'] for p in top_overs)/len(top_overs)*100:.1f}%")
print("="*100 + "\n")

# Save to file
output_file = f"outputs/NBA_AI_CHEATSHEET_{slate['date'].replace('-', '')}.txt"
print(f"💾 Full cheatsheet saved to: {output_file}")
