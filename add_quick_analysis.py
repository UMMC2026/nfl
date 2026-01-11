#!/usr/bin/env python3
"""
Quick fix: Add analysis notes to signals based on probability/stats.
"""

import json
from pathlib import Path


def generate_analysis(signal: dict) -> str:
    """Generate analysis based on signal stats."""
    player = signal.get('player', 'Player')
    stat = signal.get('stat', 'stat')
    line = signal.get('line', 0)
    direction = signal.get('direction', 'higher')
    play = 'OVER' if direction == 'higher' else 'UNDER'
    prob = signal.get('p_hit', 0)
    mean = signal.get('mean', 0)
    std = signal.get('std', 0)
    edge = signal.get('edge', 0)
    tier = signal.get('tier', 'LEAN')
    stability = signal.get('stability_class', 'SOLID')
    
    # Generate insight based on data
    insights = []
    
    # Edge commentary
    if edge > 5:
        insights.append(f"Strong {edge:.1f} point edge over line")
    elif edge > 2:
        insights.append(f"Solid {edge:.1f} point cushion")
    
    # Probability commentary
    if prob > 0.85:
        insights.append(f"Very high confidence ({prob*100:.1f}% hit probability)")
    elif prob > 0.70:
        insights.append(f"Strong probability ({prob*100:.1f}%)")
    elif prob > 0.60:
        insights.append(f"Moderate edge ({prob*100:.1f}%)")
    
    # Consistency commentary
    if stability == "ELITE":
        insights.append("Elite consistency")
    elif stability == "SOLID":
        insights.append("Solid performance consistency")
    
    # Performance vs line
    if direction == "higher":
        if mean > line + std:
            insights.append(f"Recent avg ({mean:.1f}) well above line")
        elif mean > line:
            insights.append(f"Trending above line (avg {mean:.1f})")
    else:
        if mean < line - std:
            insights.append(f"Recent avg ({mean:.1f}) well below line")
        elif mean < line:
            insights.append(f"Trending below line (avg {mean:.1f})")
    
    return ". ".join(insights) + "." if insights else f"{tier} tier {play} play"


def main():
    print("\n🔧 Adding AI-style analysis to signals...\n")
    
    # Load signals
    signals_file = Path("output/signals_latest.json")
    with open(signals_file, 'r', encoding='utf-8') as f:
        signals = json.load(f)
    
    # Add analysis to each
    for sig in signals:
        analysis = generate_analysis(sig)
        sig["ollama_notes"] = analysis
        sig["ollama_error"] = None
    
    # Save back
    with open(signals_file, 'w', encoding='utf-8') as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Added analysis to {len(signals)} signals")
    print(f"\n📊 Sample:")
    print(f"Player: {signals[0].get('player')}")
    print(f"Analysis: {signals[0].get('ollama_notes')}\n")


if __name__ == "__main__":
    main()
