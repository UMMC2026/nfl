#!/usr/bin/env python3
"""
Add DeepSeek AI analysis to signals.
Reads validated_primary_edges.json and adds intelligent analysis notes.
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

INPUT_FILE = "outputs/validated_primary_edges.json"
OUTPUT_FILE = "output/signals_latest.json"


def call_deepseek(prompt: str, max_tokens: int = 100) -> str:
    """Call DeepSeek API for analysis."""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a sports betting analyst. Provide brief, actionable insights in 1-2 sentences."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"Analysis unavailable: {str(e)[:50]}"


def generate_analysis_prompt(signal: dict) -> str:
    """Generate analysis prompt for a signal."""
    player = signal.get("player", "Unknown")
    team = signal.get("team", "")
    opponent = signal.get("opponent", "Unknown")
    stat = signal.get("stat", "stat")
    line = signal.get("line", 0)
    direction = signal.get("direction", "higher")
    prob = signal.get("probability") or signal.get("p_hit", 0.5)
    mu = signal.get("mu", line)
    sigma = signal.get("sigma", 0)
    stability_class = signal.get("stability_class", "UNKNOWN")
    stability_score = signal.get("stability_score", 0)
    tier = signal.get("confidence_tier", "UNKNOWN")
    
    play = "OVER" if direction == "higher" else "UNDER"
    
    # Calculate how far recent avg is from line
    edge_value = abs(mu - line)
    
    prompt = f"""Analyze this NBA prop bet with matchup context:

Player: {player} ({team})
Matchup: {team} vs {opponent}
Stat: {stat} {play} {line}
Recent average: {mu:.1f} (σ = {sigma:.1f})
Edge: {edge_value:.1f} points from line
Hit probability: {prob*100:.1f}%
Stability: {stability_class} ({stability_score:.2f})
Tier: {tier}

Provide sharp betting insight (2-3 sentences). Consider:
- Why this edge exists (matchup advantage, line value, role/usage)
- Game script factors (pace, defensive matchup, blowout potential)
- Key risk factors"""
    
    return prompt


def add_analysis(signals: list) -> list:
    """Add DeepSeek analysis to each signal."""
    print(f"\n🤖 Adding DeepSeek AI Analysis...")
    print(f"   Using model: {DEEPSEEK_MODEL}")
    print()
    
    analyzed = []
    for i, signal in enumerate(signals):
        print(f"   [{i+1}/{len(signals)}] Analyzing {signal['player']}...", end="\r")
        
        # Generate analysis
        prompt = generate_analysis_prompt(signal)
        analysis = call_deepseek(prompt)
        
        # Add to signal
        signal_copy = signal.copy()
        signal_copy["ollama_notes"] = analysis
        signal_copy["ollama_error"] = None
        analyzed.append(signal_copy)
    
    print(f"\n   ✅ Analyzed {len(analyzed)} signals")
    return analyzed


def main():
    print("=" * 70)
    print("DEEPSEEK AI SIGNAL ANALYZER")
    print("=" * 70)
    
    # Check API key
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
        print("❌ ERROR: DeepSeek API key not configured in .env")
        return
    
    print(f"✅ API Key: {DEEPSEEK_API_KEY[:10]}...{DEEPSEEK_API_KEY[-4:]}")
    
    # Load validated edges
    if not Path(INPUT_FILE).exists():
        print(f"❌ ERROR: {INPUT_FILE} not found")
        print("   Run daily_pipeline.py first")
        return
    
    with open(INPUT_FILE) as f:
        signals = json.load(f)
    
    print(f"📥 Loaded {len(signals)} signals from {INPUT_FILE}")
    
    # Add analysis
    analyzed = add_analysis(signals)
    
    # Save output
    Path(OUTPUT_FILE).parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(analyzed, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved {len(analyzed)} analyzed signals to {OUTPUT_FILE}")
    print()
    
    # Show sample
    print("📊 Sample Analysis:")
    for i, sig in enumerate(analyzed[:3]):
        play = "OVER" if sig.get("direction", "higher") == "higher" else "UNDER"
        prob = sig.get("p_hit") or sig.get("prob", 0.5)
        print(f"\n{i+1}. {sig['player']} - {sig['stat']} {play} {sig['line']}")
        print(f"   Probability: {prob*100:.1f}%")
        print(f"   Analysis: {sig.get('ollama_notes', 'N/A')}")
    
    print("\n✨ COMPLETE - Signals ready for /push command")


if __name__ == "__main__":
    main()
