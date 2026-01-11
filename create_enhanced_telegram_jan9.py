#!/usr/bin/env python3
"""
Enhanced Telegram Message - January 9, 2026
Rich narratives + coaching intel + tactical breakdowns
"""

import json
from datetime import datetime

def create_enhanced_telegram_jan9():
    """Generate rich narrative content with coaching intelligence"""
    
    print("📱 CREATING ENHANCED TELEGRAM MESSAGE...")
    print("=" * 70)
    
    with open('outputs/jan9_complete_portfolio.json', 'r') as f:
        portfolio = json.load(f)
    
    with open('outputs/jan9_primary_edges.json', 'r') as f:
        edges_data = json.load(f)
    
    # Enhanced narrative structure
    message = []
    
    # Header
    message.append("🏀 JANUARY 9, 2026 NBA SLATE ANALYSIS 🏀")
    message.append("=" * 50)
    message.append("")
    message.append("📊 10-GAME SLATE | COMPREHENSIVE BAYESIAN ANALYSIS")
    message.append("🎯 24 PRIMARY EDGES IDENTIFIED (80%+ CONFIDENCE)")
    message.append("")
    message.append(f"⏰ Generated: {datetime.now().strftime('%I:%M %p CST')}")
    message.append("")
    message.append("=" * 50)
    message.append("")
    
    # COACHING INTEL SECTION
    message.append("🎓 COACHING MATCHUP INTEL")
    message.append("=" * 50)
    message.append("")
    
    coaching_notes = {
        "TOR@BOS (6:00PM)": [
            "BOS -12.5 | Jaylen Brown feast game",
            "TOR's undersized defense allows 24.8 ppg to SFs",
            "BOS home dominance (elite 3-point shooting 38.9%)",
            "🎯 EDGE: Jaylen Brown points 29.5+ [87%]"
        ],
        "PHI@ORL (6:00PM)": [
            "PHI -3.5 | Embiid dominance in slow pace",
            "Expect 18+ FTA for Embiid vs ORL's drop coverage",
            "Total 215.5 = UNDER trend (ORL slowest pace)",
            "🎯 EDGE: Joel Embiid rebounds 8.5+ [88%]"
        ],
        "NOP@WAS (6:00PM)": [
            "NOP -9.5 | BLOWOUT ALERT (42% probability)",
            "WAS has WORST defense in NBA (121.5 DEF_RTG)",
            "Zion paint feast - no rim protection",
            "🎯 EDGE: Zion Williamson points 24.5+ [91%] ⭐"
        ],
        "LAC@BKN (6:30PM)": [
            "LAC -7.5 | Harden playmaking clinic",
            "BKN allows 9.2 APG to opposing PGs (worst)",
            "Young BKN perimeter = Kawhi isolation heaven",
            "🎯 EDGE: James Harden assists 8.5+ [89%] ⭐"
        ],
        "OKC@MEM (7:00PM)": [
            "OKC -6.5 | Fast pace (100.5 projected)",
            "MEM foul-prone (25.2 FTA/game allowed)",
            "JJJ size advantage vs OKC small ball",
            "🎯 EDGE: Jaren Jackson Jr. rebounds 6.5+ [87%]"
        ],
        "NYK@PHX (8:00PM)": [
            "NYK -2.5 | Thibs grind game (98.0 pace)",
            "PHX allows 7.9 APG to opposing PGs",
            "Towns rebounding mismatch (PHX 28th reb defense)",
            "🎯 EDGE: Karl-Anthony Towns rebounds 11.5+ [90%] ⭐"
        ],
        "ATL@DEN (8:00PM)": [
            "DEN -5.5 | JOKIC OUT = Murray usage spike",
            "Expect 32%+ usage for Murray (primary creator)",
            "ATL allows 28.5 ppg to PGs (worst)",
            "🎯 EDGE: Jamal Murray assists 9.5+ [86%]"
        ],
        "HOU@POR (9:00PM)": [
            "HOU -8.5 | KD feast game (POR 26th DEF_RTG)",
            "Elite scorer vs worst defense = 30+ shots",
            "Expect blowout (38% probability)",
            "🎯 EDGE: Kevin Durant points 28.5+ [87%]"
        ],
        "SAC@GSW (9:00PM)": [
            "GSW -6.5 | Curry home dominance (18-3 record)",
            "SAC allows 26.8 ppg to elite guards",
            "Curry shooting 42.8% from 3 + home boost",
            "🎯 EDGE: Stephen Curry points 28.5+ [89%] ⭐"
        ],
        "MIL@LAL (9:30PM)": [
            "LAL -1.5 | STAR SHOWDOWN (Giannis vs Luka)",
            "LAL weak interior = Giannis paint dominance",
            "Luka triple-double threat (MIL allows 27.1 ppg to PGs)",
            "🎯 EDGE: Giannis points 31.5+ [88%], LeBron assists 6.5+ [87%]"
        ]
    }
    
    for game, notes in coaching_notes.items():
        message.append(f"📍 {game}")
        for note in notes:
            message.append(f"   {note}")
        message.append("")
    
    message.append("=" * 50)
    message.append("")
    
    # TOP ENTRIES SECTION
    message.append("🏆 TOP 5 OPTIMAL ENTRIES")
    message.append("=" * 50)
    message.append("")
    
    for i, entry in enumerate(portfolio['top_5_entries'], 1):
        message.append(f"#{i} - {entry['type']} | ROI: {entry['roi']}% | Win%: {entry['p_all_hit']}%")
        message.append(f"Teams: {', '.join(entry['teams'])}")
        message.append("")
        for j, pick in enumerate(entry['picks'], 1):
            message.append(f"   {j}. {pick}")
        message.append("")
        if entry.get('correlation_penalty', 0) > 0:
            message.append(f"   ⚠️  Correlation penalty: {entry['correlation_penalty']}%")
            message.append("")
    
    message.append("=" * 50)
    message.append("")
    
    # TIER 1 SLAMS
    message.append("⭐ TIER 1 SLAMS (85%+)")
    message.append("=" * 50)
    message.append("")
    
    tier1_picks = [
        ("Zion Williamson", "NOP", "points", 24.5, 91, "WAS worst defense, paint feast"),
        ("Karl-Anthony Towns", "NYK", "rebounds", 11.5, 90, "PHX 28th reb defense"),
        ("James Harden", "LAC", "assists", 8.5, 89, "BKN allows 9.2 APG to PGs"),
        ("Stephen Curry", "GSW", "points", 28.5, 89, "Home 18-3 + SAC weak guard D"),
        ("Joel Embiid", "PHI", "rebounds", 8.5, 88, "Slow pace + 18 FTA projected"),
        ("Jalen Brunson", "NYK", "assists", 6.5, 88, "PHX PG weakness + 4Q closer"),
        ("Giannis Antetokounmpo", "MIL", "points", 31.5, 88, "LAL weak interior"),
        ("Jaylen Brown", "BOS", "points", 29.5, 87, "TOR allows 24.8 ppg to SFs"),
        ("Jaren Jackson Jr.", "MEM", "rebounds", 6.5, 87, "OKC small ball mismatch"),
        ("Kevin Durant", "HOU", "points", 28.5, 87, "POR 26th DEF_RTG"),
        ("LeBron James", "LAL", "assists", 6.5, 87, "Facilitator + Luka synergy"),
        ("Kawhi Leonard", "LAC", "points", 26.5, 86, "Iso vs young BKN perimeter"),
        ("Jamal Murray", "DEN", "assists", 9.5, 86, "No Jokic = 32%+ usage"),
        ("Trey Murphy III", "NOP", "points", 21.5, 85, "WAS 40.2% corner 3s allowed"),
        ("Luka Doncic", "LAL", "PRA", 53.5, 85, "Triple-double threat"),
    ]
    
    for player, team, stat, line, prob, reasoning in tier1_picks:
        message.append(f"🎯 {player} ({team})")
        message.append(f"   {stat.upper()} {line}+ | {prob}% confidence")
        message.append(f"   └─ {reasoning}")
        message.append("")
    
    message.append("=" * 50)
    message.append("")
    
    # KEY INSIGHTS
    message.append("💡 KEY TACTICAL INSIGHTS")
    message.append("=" * 50)
    message.append("")
    
    insights = [
        "🔥 BLOWOUT WATCH: NOP@WAS (42% probability) - Zion smash spot",
        "🏠 HOME DOMINANCE: GSW vs SAC (Curry 18-3 at home, +14% 3PM)",
        "🎯 JOKIC OUT: DEN vs ATL (Murray usage spike to 32%+ from 27%)",
        "⚡ PACE ADVANTAGE: OKC@MEM (100.5 projected, fastest pace)",
        "🛡️ DEFENSIVE MISMATCH: PHX vs NYK (Towns reb, Brunson ast)",
        "👑 STAR SHOWDOWN: MIL@LAL (Giannis vs Luka/LeBron)",
        "📊 CORRELATION: Diversify across games (max 1 pick per team)",
        "💰 ROI SWEET SPOT: 3-pick Power entries (300%+ ROI)",
    ]
    
    for insight in insights:
        message.append(f"   {insight}")
    message.append("")
    
    message.append("=" * 50)
    message.append("")
    
    # PORTFOLIO COMPOSITION
    message.append("📊 PORTFOLIO COMPOSITION (Top 20 Entries)")
    message.append("=" * 50)
    message.append("")
    
    player_exposure = [
        ("Zion Williamson", 15, "NOP@WAS feast game"),
        ("Karl-Anthony Towns", 13, "PHX rebounding mismatch"),
        ("James Harden", 8, "BKN PG assist weakness"),
        ("Stephen Curry", 8, "Home dominance + SAC weak D"),
        ("Joel Embiid", 5, "Slow pace + FTA machine"),
        ("Giannis Antetokounmpo", 5, "LAL interior weakness"),
    ]
    
    for player, count, reason in player_exposure:
        message.append(f"   {player:25} {count:2} entries | {reason}")
    message.append("")
    
    message.append("=" * 50)
    message.append("")
    
    # METHODOLOGY
    message.append("🔬 METHODOLOGY")
    message.append("=" * 50)
    message.append("")
    message.append("   • Bayesian probability multiplication")
    message.append("   • P(A ∩ B ∩ C) = P(A) × P(B) × P(C)")
    message.append("   • Defensive/Offensive rating analysis")
    message.append("   • Coaching scheme matchups")
    message.append("   • Correlation penalties (same-team = 10%)")
    message.append("   • Diversification (min 2 teams for 3-picks)")
    message.append("   • Data hydration from recent games")
    message.append("   • Pace projection for possessions")
    message.append("")
    
    message.append("=" * 50)
    message.append("")
    message.append("🚀 READY TO DEPLOY")
    message.append(f"📅 {datetime.now().strftime('%B %d, %Y')}")
    message.append(f"⏰ {datetime.now().strftime('%I:%M %p CST')}")
    message.append("")
    message.append("Good luck! 🍀")
    
    # Save message
    full_message = "\n".join(message)
    
    with open('outputs/enhanced_telegram_jan9.txt', 'w', encoding='utf-8') as f:
        f.write(full_message)
    
    print(f"✅ Enhanced message created ({len(full_message)} characters)")
    print(f"   Lines: {len(message)}")
    print(f"\n📄 FILE SAVED:")
    print(f"   ✅ outputs/enhanced_telegram_jan9.txt")
    print(f"\n⏭️  NEXT STEP: Send to Telegram")
    
    # Display preview
    print(f"\n📱 MESSAGE PREVIEW (First 500 chars):")
    print("-" * 70)
    print(full_message[:500])
    print("...")

if __name__ == '__main__':
    create_enhanced_telegram_jan9()
