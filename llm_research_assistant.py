"""
LLM Research Assistant - Automates Manual Research for NBA Props
================================================================
Generates matchup insights, injury context, coaching analysis
Outputs JSON for human review → hardcode into MATCHUP_ADJUSTMENTS

USAGE:
    python llm_research_assistant.py --slate jan8_complete_slate.json
    python llm_research_assistant.py --games "CLE@MIN,IND@CHA"
    
OUTPUT:
    - llm_matchup_suggestions.json (for hardcoding)
    - llm_narrative_insights.txt (for Telegram)
    - llm_alerts.json (injuries, coaching changes)
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import requests

# LLM Configuration
OLLAMA_API = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"  # Faster, lighter model
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # Fallback

class LLMResearchAssistant:
    def __init__(self, use_ollama=True):
        self.use_ollama = use_ollama
        self.cache = {}
        
    def query_llm(self, prompt: str, max_tokens: int = 500) -> str:
        """Query LLM (Ollama first, OpenAI fallback)"""
        if self.use_ollama:
            try:
                response = requests.post(
                    OLLAMA_API,
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3}  # Low temp for factual
                    },
                    timeout=90
                )
                if response.status_code == 200:
                    return response.json().get("response", "")
            except Exception as e:
                print(f"⚠️ Ollama failed: {e}, falling back to OpenAI...")
        
        # Fallback to OpenAI
        if not OPENAI_API_KEY:
            return "ERROR: No LLM available (Ollama down, no OpenAI key)"
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"ERROR: {e}"
    
    def analyze_matchup(self, game: str, context: Dict) -> Dict:
        """
        Analyze specific game matchup
        
        Args:
            game: "CLE@MIN"
            context: {
                "spread": "CLE -3.5",
                "total": 221.5,
                "rest": {"CLE": "B2B", "MIN": "1 day"},
                "players": ["Garland", "Randle", "Edwards"]
            }
        
        Returns:
            {
                "adjustments": [
                    {"player": "Garland", "stat": "assists", "adj": -10, "reason": "..."},
                ],
                "coaching_intel": "...",
                "blowout_risk": 15
            }
        """
        prompt = f"""Analyze NBA matchup: {game}
        
Context:
- Spread: {context.get('spread', 'N/A')}
- Total: {context.get('total', 'N/A')}
- Rest: {context.get('rest', {})}
- Key players: {', '.join(context.get('players', []))}

Provide:
1. Player-specific adjustments (stat, percentage change, reasoning)
2. Coaching schemes (defensive tendencies, pace impact)
3. Blowout probability (0-100%)

Format as JSON:
{{
    "adjustments": [
        {{"player": "Player Name", "stat": "assists", "adj_pct": -10, "reason": "B2B fatigue reduces court vision"}}
    ],
    "coaching_intel": "...",
    "blowout_risk": 15
}}
"""
        
        response = self.query_llm(prompt, max_tokens=800)
        
        # Parse JSON from response
        try:
            # Extract JSON from markdown if present
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            return json.loads(json_str)
        except:
            # Fallback: return raw text
            return {
                "adjustments": [],
                "coaching_intel": response,
                "blowout_risk": 0,
                "raw_response": response
            }
    
    def check_injuries(self, teams: List[str]) -> Dict[str, List[Dict]]:
        """
        Check injury reports for teams
        
        Returns:
            {
                "CLE": [{"player": "LeBron", "status": "OUT", "impact": "..."}],
                "MIN": []
            }
        """
        prompt = f"""Check injury reports for NBA teams: {', '.join(teams)}
        
Provide current injury status (as of January 8, 2026):
- Player name
- Status (OUT, DOUBTFUL, QUESTIONABLE, PROBABLE)
- Impact on props (which players benefit)

Format as JSON:
{{
    "CLE": [
        {{"player": "Player Name", "status": "OUT", "injury": "ankle", "impact": "Garland usage +5%"}}
    ]
}}
"""
        
        response = self.query_llm(prompt)
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            return json.loads(json_str)
        except:
            return {"error": response}
    
    def generate_narrative(self, pick: Dict) -> str:
        """
        Generate rich narrative for a pick
        
        Args:
            pick: {
                "player": "Bam Adebayo",
                "team": "MIA",
                "opponent": "CHI",
                "stat": "points",
                "line": 16.5,
                "prob": 82,
                "edge": "CHI allows 58.2% at rim"
            }
        
        Returns:
            "Bam Adebayo feasted for 24/12 last time vs CHI. Their rim protection
            collapsed after Vucevic trade - opponents shoot 58.2% at rim (29th in NBA).
            Spoelstra runs 4-5 P&R sets per game targeting weak big rotation."
        """
        prompt = f"""Write a compelling 2-3 sentence narrative for this NBA prop bet:

Player: {pick['player']} ({pick['team']})
Opponent: {pick['opponent']}
Prop: {pick['stat']} {pick['line']}+
Probability: {pick['prob']}%
Edge: {pick.get('edge', 'N/A')}

Include:
- Recent performance vs opponent
- Defensive scheme vulnerability
- Coaching tactical advantage
- Statistical context

Keep factual, sharp, no fluff."""
        
        return self.query_llm(prompt, max_tokens=200).strip()
    
    def scan_news(self, keywords: List[str]) -> List[Dict]:
        """
        Scan for breaking news (coaching changes, lineup rotations, etc.)
        
        Args:
            keywords: ["coaching changes", "B2B", "blowout games"]
        
        Returns:
            [{"topic": "...", "alert": "...", "impact": "..."}]
        """
        prompt = f"""Scan NBA news for: {', '.join(keywords)}

Focus on today's games (January 8, 2026).
Identify actionable intelligence for prop betting.

Format as JSON array:
[
    {{"topic": "CLE B2B", "alert": "2nd night, travel from BOS", "impact": "Expect -10% offensive efficiency"}}
]
"""
        
        response = self.query_llm(prompt, max_tokens=400)
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            return json.loads(json_str)
        except:
            return [{"error": response}]


def main():
    """Demo: Analyze tonight's slate"""
    assistant = LLMResearchAssistant(use_ollama=True)
    
    print("="*80)
    print("LLM RESEARCH ASSISTANT - NBA PROPS")
    print("="*80)
    print()
    
    # Load slate
    slate_file = "outputs/jan8_complete_slate.json"
    if not os.path.exists(slate_file):
        print(f"❌ Slate file not found: {slate_file}")
        return
    
    with open(slate_file) as f:
        slate = json.load(f)
    
    games = slate.get("games", [])
    print(f"Loaded {len(games)} games\n")
    
    # Analyze each game
    all_suggestions = []
    
    for game_info in games:
        game = game_info["matchup"]
        print(f"🏀 Analyzing {game}...")
        
        context = {
            "spread": game_info.get("spread", "N/A"),
            "total": game_info.get("total", "N/A"),
            "time": game_info.get("time", "N/A"),
            "players": list(set(p["player"] for p in slate["picks"] if p["team"] in game))[:5]
        }
        
        analysis = assistant.analyze_matchup(game, context)
        all_suggestions.append({
            "game": game,
            "analysis": analysis
        })
        
        print(f"   • {len(analysis.get('adjustments', []))} adjustments found")
        print(f"   • Blowout risk: {analysis.get('blowout_risk', 0)}%")
        print()
    
    # Check injuries
    print("🏥 Checking injury reports...")
    teams = list(set([g["matchup"].split("@")[0] for g in games] + [g["matchup"].split("@")[1] for g in games]))
    injuries = assistant.check_injuries(teams)
    print(f"   • {sum(len(v) for v in injuries.values() if isinstance(v, list))} injuries found\n")
    
    # Scan news
    print("📰 Scanning breaking news...")
    news = assistant.scan_news(["B2B", "blowout games", "coaching changes", "lineup rotations"])
    print(f"   • {len(news)} alerts\n")
    
    # Save outputs
    output = {
        "timestamp": datetime.now().isoformat(),
        "games_analyzed": len(games),
        "matchup_suggestions": all_suggestions,
        "injury_alerts": injuries,
        "news_alerts": news
    }
    
    output_file = "llm_research_output.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)
    
    print("="*80)
    print(f"✅ RESEARCH COMPLETE")
    print(f"Output saved to: {output_file}")
    print()
    print("NEXT STEPS:")
    print("1. Review suggested adjustments")
    print("2. Validate with historical data")
    print("3. Hardcode verified insights into MATCHUP_ADJUSTMENTS")
    print("4. Re-run enhancement pipeline")
    print("="*80)


if __name__ == "__main__":
    main()
