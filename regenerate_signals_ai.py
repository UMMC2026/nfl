#!/usr/bin/env python3
"""
Regenerate signals_latest.json with DeepSeek AI analysis.

Reads from: outputs/validated_primary_edges.json
Writes to: output/signals_latest.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ollama.risk_analyst import batch_analyze, skip_ollama


def main():
    print("\n" + "="*70)
    print("SIGNAL REGENERATION WITH AI ANALYSIS")
    print("="*70 + "\n")
    
    # Load validated edges
    validated_file = Path("outputs/validated_primary_edges.json")
    
    if not validated_file.exists():
        print("❌ ERROR: outputs/validated_primary_edges.json not found")
        print("   Run daily_pipeline.py first to generate validated edges")
        return 1
    
    print(f"📥 Loading validated edges from {validated_file.name}...")
    with open(validated_file, 'r', encoding='utf-8') as f:
        edges = json.load(f)
    
    print(f"   Loaded {len(edges)} validated picks")
    print()
    
    # Filter to top signals (optional - can process all)
    # For now, let's process all but you can limit if needed
    signals_to_analyze = edges[:10]  # Top 10 for now to save time
    
    print(f"🤖 Running Ollama Mistral analysis on {len(signals_to_analyze)} signals...")
    print()
    
    # Run AI analysis using local Ollama
    analyzed_signals = batch_analyze(signals_to_analyze, model="mistral")
    
    # Add remaining signals without analysis (to keep full dataset)
    if len(edges) > len(signals_to_analyze):
        remaining = edges[len(signals_to_analyze):]
        for sig in remaining:
            sig = skip_ollama(sig, "Analysis not run (beyond top 10)")
        analyzed_signals.extend(remaining)
    
    print()
    print(f"✅ Analysis complete!")
    print()
    
    # Save to signals_latest.json
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / "signals_latest.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analyzed_signals, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved {len(analyzed_signals)} signals to {output_file}")
    print()
    
    # Show sample analysis
    if analyzed_signals and analyzed_signals[0].get("ollama_notes"):
        print("📊 Sample AI Analysis:")
        print("-" * 70)
        sig = analyzed_signals[0]
        print(f"Player: {sig.get('player')}")
        print(f"Stat: {sig.get('stat')} {sig.get('direction')} {sig.get('line')}")
        print(f"Tier: {sig.get('tier')} | Probability: {sig.get('p_hit', 0)*100:.1f}%")
        print(f"\nAI Insight:")
        print(sig.get('ollama_notes'))
        print("-" * 70)
    
    print()
    print("✨ READY FOR TELEGRAM BROADCAST")
    print("   Run: python start_bot.py")
    print("   Then use /push command to broadcast Pro signals")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
