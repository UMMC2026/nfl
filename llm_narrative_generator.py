"""
LLM Narrative Generator - Create Rich Telegram Narratives
=========================================================
Transforms dry stats into compelling betting narratives

USAGE:
    python llm_narrative_generator.py --portfolio jan8_complete_portfolio.json
    
OUTPUT:
    - Enhanced Telegram message with rich narratives
    - Coaching storylines
    - Historical context
"""

import json
import os
from llm_research_assistant import LLMResearchAssistant


def enhance_pick_narrative(assistant: LLMResearchAssistant, pick: Dict) -> str:
    """Add rich narrative to a pick"""
    narrative = assistant.generate_narrative(pick)
    
    # Format for Telegram
    return f"""• **{pick['player']}** ({pick['team']}) {pick['stat'].upper()} {pick['line']}+ [{pick.get('final_prob', pick.get('prob', 0))*100:.0f}%]
   💡 {pick.get('analytical_edge', pick.get('edge', 'N/A'))}
   📖 {narrative}
"""


def generate_coaching_narrative(assistant: LLMResearchAssistant, game: str, coaching_intel: str) -> str:
    """Expand coaching intel with storytelling"""
    prompt = f"""Expand this coaching intel into a compelling narrative (2-3 sentences):

Game: {game}
Intel: {coaching_intel}

Include tactical details, historical context, or recent adjustments.
Keep sharp and factual."""
    
    return assistant.query_llm(prompt, max_tokens=200).strip()


def main():
    """Generate enhanced Telegram message"""
    assistant = LLMResearchAssistant(use_ollama=True)
    
    # Load portfolio
    portfolio_file = "outputs/jan8_complete_portfolio.json"
    if not os.path.exists(portfolio_file):
        print(f"❌ Portfolio not found: {portfolio_file}")
        return
    
    with open(portfolio_file) as f:
        portfolio = json.load(f)
    
    top_entry = portfolio[0]
    
    print("="*80)
    print("GENERATING ENHANCED TELEGRAM NARRATIVE")
    print("="*80)
    print()
    
    # Enhanced message
    message = f"""🎯 **NBA PICKS - JANUARY 8, 2026**
📊 LLM-Enhanced Analytical Breakdown
🔬 Hybrid System: Math Precision + AI Research

━━━━━━━━━━━━━━━━━━━━━

🔥 **#1 SLAM COMBO (3-PICK POWER)**

"""
    
    # Add picks with narratives
    for pick in top_entry["picks"]:
        print(f"Generating narrative for {pick['player']}...")
        enhanced = enhance_pick_narrative(assistant, pick)
        message += enhanced + "\n"
    
    # Portfolio metrics
    message += f"""
━━━━━━━━━━━━━━━━━━━━━

📈 **PORTFOLIO METRICS:**
✅ P(All Hit): {top_entry['p_win']*100:.0f}%
💰 E[ROI]: +{top_entry['ev_roi']*100:.0f}% (+{top_entry['ev_units']:.2f} units)
🎰 Payout: {top_entry['payout']}x
🏀 Teams: {len(top_entry['teams'])} different
⚡ Mathematical Foundation + AI Research

━━━━━━━━━━━━━━━━━━━━━

🎓 **COACHING NARRATIVES:**

"""
    
    # Add coaching narratives
    coaching_insights = {
        "IND@CHA": "Carlisle vs Lee experience edge, drop coverage exploitable",
        "CLE@MIN": "CLE B2B (106 OFF_RTG vs 118.9 normal = -12.9 drop)",
        "MIA@CHI": "Spoelstra vs Donovan mismatch, Bam feast game",
        "DAL@UTA": "BLOWOUT ALERT (22% probability) - avoided in portfolio"
    }
    
    for game, intel in coaching_insights.items():
        print(f"Expanding {game} coaching intel...")
        narrative = generate_coaching_narrative(assistant, game, intel)
        message += f"""🏀 **{game}:**
   {narrative}

"""
    
    # Footer
    message += f"""━━━━━━━━━━━━━━━━━━━━━

📊 **ANALYTICAL EDGE:**
• 89 props analyzed (20 players, 4 games)
• 35 qualified (≥65% probability)
• 15 primary edges (ONE per player)
• Top {len(portfolio)} entries by E[ROI]

🤖 **SYSTEM ARCHITECTURE:**
• Math Engine: Bayesian Beta-Binomial, EV optimization
• AI Research: Matchup analysis, injury context, narratives
• Human Validation: All insights verified before hardcoding

━━━━━━━━━━━━━━━━━━━━━

🕐 **GAME TIMES (CST):**
• IND@CHA: 6:00 PM
• CLE@MIN: 7:00 PM
• MIA@CHI: 7:00 PM
• DAL@UTA: 8:00 PM

🎯 **BEST OF LUCK!** 🎯
"""
    
    # Save
    with open("llm_enhanced_telegram.txt", "w", encoding="utf-8") as f:
        f.write(message)
    
    print()
    print("="*80)
    print("✅ ENHANCED MESSAGE GENERATED")
    print("Saved to: llm_enhanced_telegram.txt")
    print()
    print("Review the narratives, then send to Telegram!")
    print("="*80)
    
    # Preview
    print()
    print("PREVIEW (first 800 chars):")
    print(message[:800])
    print("...")


if __name__ == "__main__":
    main()
