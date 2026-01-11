#!/usr/bin/env python
# AUTHORITATIVE ENTRY POINT
# All system execution must originate here

"""
Main pipeline runner - one-button execution of the full signal processing flow.

Usage:
    python run_pipeline.py                    # Run with defaults
    python run_pipeline.py --skip-ollama      # Skip Ollama analysis
    python run_pipeline.py --min-tier STRONG  # Only STRONG+ signals
    python run_pipeline.py --max-per-player 1 # Max 1 signal per player
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
import sys

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent))

from engine.filters import filter_signals, build_signal_from_mc_result
from engine.correlation import block_correlated, block_same_player_max
from ollama.risk_analyst import run_ollama, skip_ollama
from telegram.formatter import format_signal_batch, format_parlay_suggestion


def load_monte_carlo_results(picks_file: str) -> list:
    """
    Load picks file and run Monte Carlo to generate raw signals.
    """
    import numpy as np
    from sports_quant.simulation.monte_carlo import run_monte_carlo
    
    with open(picks_file, 'r') as f:
        picks = json.load(f)
    
    results = []
    for pick in picks:
        vals = pick.get('recent_values', [])
        if len(vals) < 3:
            continue
        
        mean = np.mean(vals)
        var = np.var(vals)
        std = np.std(vals)
        line = pick['line']
        direction = pick['direction']
        
        # Run simulation
        sim = run_monte_carlo(line, mean, var, dist='normal', n_sims=10000, clip_min=0)
        
        # Get probability based on direction
        prob = sim['p_over'] if direction == 'higher' else sim['p_under']
        
        results.append({
            'player': pick['player'],
            'team': pick.get('team', ''),
            'stat': pick['stat'],
            'line': line,
            'direction': direction,
            'play': 'OVER' if direction == 'higher' else 'UNDER',
            'mean': mean,
            'std': std,
            'prob': prob,
            'p_hit': prob,
            'edge': mean - line if direction == 'higher' else line - mean
        })
    
    return results


def run_pipeline(
    picks_file: str = "picks_dec30_nba_full_filled.json",
    output_dir: str = "output",
    skip_ollama_analysis: bool = False,
    min_tier: str = "LEAN",
    max_per_player: int = 1,
    ollama_model: str = "llama3"
):
    """
    Run the full signal processing pipeline.
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("  UNDERDOG SIGNAL PIPELINE")
    print("=" * 60)
    print()
    
    # Step 1: Load Monte Carlo results
    print("[1/5] Running Monte Carlo simulation...")
    raw_signals = load_monte_carlo_results(picks_file)
    print(f"      Generated {len(raw_signals)} raw signals")
    
    # Step 2: Filter through qualification pipeline
    print(f"[2/5] Filtering signals (min tier: {min_tier})...")
    qualified = filter_signals(raw_signals, min_tier=min_tier)
    print(f"      Qualified: {len(qualified)} signals")
    
    # Step 3: Block correlated signals
    print(f"[3/5] Removing correlated signals (max {max_per_player} per player)...")
    filtered = block_correlated(qualified)
    filtered = block_same_player_max(filtered, max_per_player)
    print(f"      Remaining: {len(filtered)} signals")
    
    # Step 4: Ollama risk analysis
    print("[4/5] Running risk analysis...")
    if skip_ollama_analysis:
        final_signals = [skip_ollama(s, "Analysis skipped") for s in filtered]
        print("      (Ollama skipped)")
    else:
        final_signals = []
        for i, s in enumerate(filtered):
            print(f"      Analyzing {s['player']} ({i+1}/{len(filtered)})...", end="\r")
            final_signals.append(run_ollama(s, ollama_model))
        print(f"      Analyzed {len(final_signals)} signals          ")
    
    # Step 5: Save and format output
    print("[5/5] Generating output...")
    
    # Sort by probability
    final_signals.sort(key=lambda x: x.get('p_hit', 0), reverse=True)
    
    # Save JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_path / f"signals_{timestamp}.json"
    with open(json_path, 'w') as f:
        json.dump(final_signals, f, indent=2)
    print(f"      Saved: {json_path}")
    
    # Save Telegram payload
    telegram_payload = format_signal_batch(final_signals, f"NBA Signals - {datetime.now().strftime('%b %d')}")
    telegram_path = output_path / f"telegram_{timestamp}.txt"
    with open(telegram_path, 'w', encoding='utf-8') as f:
        f.write(telegram_payload)
        f.write("\n\n")
        f.write(format_parlay_suggestion(final_signals, 3))
    print(f"      Saved: {telegram_path}")
    
    # Print summary
    print()
    print("=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)
    print()
    
    slams = [s for s in final_signals if s.get('tier') == 'SLAM']
    strongs = [s for s in final_signals if s.get('tier') == 'STRONG']
    leans = [s for s in final_signals if s.get('tier') == 'LEAN']
    
    print(f"  🔥 SLAM:   {len(slams)}")
    print(f"  💪 STRONG: {len(strongs)}")
    print(f"  📊 LEAN:   {len(leans)}")
    print()
    
    # Print Telegram output
    print(telegram_payload)
    print()
    print(format_parlay_suggestion(final_signals, 3))
    
    return final_signals


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Underdog signal pipeline")
    parser.add_argument("--picks", default="picks_dec30_nba_full_filled.json", help="Input picks file")
    parser.add_argument("--output", default="output", help="Output directory")
    parser.add_argument("--skip-ollama", action="store_true", help="Skip Ollama analysis")
    parser.add_argument("--min-tier", default="LEAN", choices=["SLAM", "STRONG", "LEAN"], help="Minimum tier")
    parser.add_argument("--max-per-player", type=int, default=1, help="Max signals per player")
    parser.add_argument("--model", default="llama3", help="Ollama model to use")
    
    args = parser.parse_args()
    
    run_pipeline(
        picks_file=args.picks,
        output_dir=args.output,
        skip_ollama_analysis=args.skip_ollama,
        min_tier=args.min_tier,
        max_per_player=args.max_per_player,
        ollama_model=args.model
    )
if __name__ == "__main__":
    main()
