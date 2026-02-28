"""
NFL AI Commentary Generator
Uses DeepSeek API to generate contextual insights for NFL picks
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
import requests


def generate_nfl_commentary(picks: List[Dict[str, Any]], games_context: Dict = None) -> str:
    """
    Generate AI commentary for NFL picks.
    
    Args:
        picks: List of analyzed picks with probabilities
        games_context: Optional context about matchups, weather, injuries
    
    Returns:
        AI-generated commentary string
    """
    
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        return _generate_fallback_commentary(picks)
    
    # Build context for LLM
    context = _build_context_prompt(picks, games_context)
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an NFL analytics expert providing concise, "
                            "data-driven insights on prop bets. Focus on matchup dynamics, "
                            "recent trends, and risk factors. Keep responses under 300 words. "
                            "Use language like 'data suggests', 'trends indicate' - never imperatives."
                        )
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 400
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"⚠️  DeepSeek API error: {response.status_code}")
            return _generate_fallback_commentary(picks)
            
    except Exception as e:
        print(f"⚠️  AI commentary error: {e}")
        return _generate_fallback_commentary(picks)


def _build_context_prompt(picks: List[Dict[str, Any]], games_context: Dict = None) -> str:
    """Build prompt for LLM with pick context."""
    
    # Filter to playable picks
    playable = [p for p in picks 
                if p.get('tier') in ['SLAM', 'STRONG', 'LEAN'] 
                or p.get('action') in ['SLAM', 'STRONG', 'CONSIDER', 'LEAN']
                or p.get('grade') in ['A+', 'A', 'B']]
    
    if not playable:
        return "No playable NFL picks today. All props below confidence threshold."
    
    prompt = "Analyze the following NFL prop picks and provide brief insights:\n\n"
    
    # Helper to get probability as percentage
    def get_prob(p):
        prob = p.get('probability', 0)
        return prob * 100 if prob <= 1.0 else prob
    
    # Top picks
    for i, pick in enumerate(playable[:5], 1):
        prob = get_prob(pick)
        recent_avg = pick.get('mu', pick.get('recent_avg', 0))
        sigma = pick.get('sigma', 0)
        
        prompt += f"{i}. {pick.get('player')} ({pick.get('team')}) - "
        prompt += f"{pick.get('stat')} {pick.get('direction')} {pick.get('line')}\n"
        prompt += f"   Confidence: {prob:.1f}%, "
        prompt += f"Recent Avg: {recent_avg:.1f} (σ={sigma:.1f})\n"
        
        if pick.get('opponent'):
            prompt += f"   vs {pick['opponent']}\n"
    
    prompt += "\nProvide:\n"
    prompt += "1. Top plays rationale (why the probabilities are high)\n"
    prompt += "2. Key matchup factors to watch\n"
    prompt += "3. Risk warnings (injury concerns, weather, variance)\n"
    
    return prompt


def _generate_fallback_commentary(picks: List[Dict[str, Any]]) -> str:
    """Generate basic commentary without AI."""
    
    playable = [p for p in picks 
                if p.get('tier') in ['SLAM', 'STRONG', 'LEAN'] 
                or p.get('action') in ['SLAM', 'STRONG', 'CONSIDER', 'LEAN']
                or p.get('grade') in ['A+', 'A', 'B']]
    
    if not playable:
        return (
            "No playable picks found in today's NFL slate. "
            "All analyzed props fell below confidence thresholds. "
            "Consider lowering thresholds or analyzing different games."
        )
    
    # Helper to get probability as percentage
    def get_prob(p):
        prob = p.get('probability', 0)
        return prob * 100 if prob <= 1.0 else prob
    
    # Count stats
    total_plays = len(playable)
    probs = [get_prob(p) for p in playable]
    avg_prob = sum(probs) / len(probs) if probs else 0
    
    slams = len([p for p in playable if p.get('tier') == 'SLAM' or p.get('action') == 'SLAM'])
    strongs = len([p for p in playable if (p.get('tier') == 'STRONG' or p.get('action') == 'STRONG' or p.get('grade') in ['A', 'A+']) and p.get('tier') != 'SLAM'])
    
    commentary = f"Analysis identified {total_plays} playable props "
    commentary += f"with average confidence {avg_prob:.1f}%. "
    
    if slams > 0:
        commentary += f"{slams} SLAM-tier plays show exceptional edge. "
    
    if strongs > 0:
        commentary += f"{strongs} STRONG plays backed by statistical trends. "
    
    # Top player mention
    top_pick = playable[0]
    prob = get_prob(top_pick)
    commentary += f"Top pick: {top_pick.get('player')} "
    commentary += f"{top_pick.get('stat')} {top_pick.get('direction')} {top_pick.get('line')} "
    commentary += f"({prob:.0f}% confidence). "
    
    commentary += "Risk factors: Weather, late injury news, and volume volatility remain key concerns."
    
    return commentary


def add_commentary_to_analysis(analysis_file: Path) -> str:
    """
    Load NFL analysis JSON, generate commentary, return formatted text.
    
    Args:
        analysis_file: Path to NFL analysis JSON
    
    Returns:
        Formatted commentary string
    """
    
    if not analysis_file.exists():
        return "❌ Analysis file not found"
    
    with open(analysis_file, 'r') as f:
        data = json.load(f)
    
    # Handle both data formats
    picks = data.get('picks', data.get('results', []))
    games_context = data.get('games_context')
    
    print("🤖 Generating AI commentary...")
    commentary = generate_nfl_commentary(picks, games_context)
    
    return commentary


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate AI commentary for NFL picks")
    parser.add_argument("--file", type=str, help="Path to NFL analysis JSON")
    
    args = parser.parse_args()
    
    if not args.file:
        # Find latest NFL analysis
        outputs_dir = Path("outputs")
        nfl_files = sorted(outputs_dir.glob("nfl_analysis_*.json"), reverse=True)
        if not nfl_files:
            print("❌ No NFL analysis files found")
            exit(1)
        args.file = str(nfl_files[0])
        print(f"📁 Using: {args.file}")
    
    commentary = add_commentary_to_analysis(Path(args.file))
    
    print("\n" + "=" * 80)
    print("💬 AI COMMENTARY")
    print("=" * 80)
    print(commentary)
    print("=" * 80)
