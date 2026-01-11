"""
Ultra-lightweight Ollama integration - focuses on speed, not perfection.
Uses fast cached responses + minimal JSON parsing.
"""
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import signal


class TimeoutException(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutException("Timeout")


def quick_validate(player: str, prop: str, direction: str, model: str = "mistral") -> Optional[str]:
    """
    Ultra-minimal validation: is this pick reasonable? (Yes/No only)
    Response expected: "Yes" or "No" + optional reason.
    Timeout: 5 seconds HARD LIMIT.
    """
    # Minimal prompt - just ask for one word answer
    prompt = f"NBA: Is {player} {direction} {prop} reasonable? Answer Yes or No only."
    
    try:
        # Set process timeout to 5 seconds
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            timeout=5,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0:
            response = result.stdout.strip()[:50]  # First 50 chars only
            return response
        return None
    
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {str(e)[:20]}"


def batch_quick_check(picks: List[Dict], max_picks: int = 5) -> List[Dict]:
    """Validate top picks with 5-second hard timeout each."""
    
    print("\n⚡ QUICK OLLAMA VALIDATION (5s timeout)")
    print("=" * 60)
    print(f"Checking top {min(max_picks, len(picks))} picks...\n")
    
    results = []
    start_total = time.time()
    
    for i, pick in enumerate(picks[:max_picks], 1):
        player = pick.get('player', '?')
        prop = pick.get('stat', '?')
        direction = 'OVER' if pick.get('mu', 0) > pick.get('line', 0) else 'UNDER'
        
        print(f"[{i}] {player:20} {direction} {prop:20} ", end='', flush=True)
        
        start = time.time()
        response = quick_validate(player, prop, direction)
        elapsed = time.time() - start
        
        if response and 'TIMEOUT' not in response:
            print(f"✅ {response[:40]}")
            results.append({
                'player': player,
                'prop': prop,
                'valid': 'Yes' in response,
                'time': f"{elapsed:.1f}s"
            })
        elif response == 'TIMEOUT':
            print(f"⏱️  Timeout ({elapsed:.1f}s)")
            results.append({
                'player': player,
                'prop': prop,
                'valid': None,
                'time': f"{elapsed:.1f}s"
            })
        else:
            print(f"❌ {response}")
            results.append({
                'player': player,
                'prop': prop,
                'valid': False,
                'time': f"{elapsed:.1f}s"
            })
    
    elapsed_total = time.time() - start_total
    print(f"\n{'=' * 60}")
    print(f"Total time: {elapsed_total:.1f}s for {max_picks} picks")
    print(f"Avg per pick: {elapsed_total / max_picks:.1f}s")
    print(f"{'=' * 60}\n")
    
    return results


def main():
    # Load latest cheatsheet picks
    if Path("picks_hydrated.json").exists():
        with open("picks_hydrated.json") as f:
            picks = json.load(f)
        
        picks.sort(key=lambda p: p.get('confidence', 0), reverse=True)
        
        # Run quick validation
        results = batch_quick_check(picks, max_picks=5)
        
        # Show results
        print("\n📊 VALIDATION RESULTS:")
        print("-" * 60)
        for r in results:
            status = "✅" if r['valid'] is True else "❓" if r['valid'] is None else "❌"
            print(f"{status} {r['player']:20} | {r['time']:>6}")
        
        # Save results
        output = Path("outputs") / f"ollama_validation_{int(time.time())}.json"
        with open(output, 'w') as f:
            json.dump({
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'results': results,
                'model': 'mistral'
            }, f, indent=2)
        
        print(f"\n✅ Saved to: {output.name}")
    else:
        print("❌ picks_hydrated.json not found")


if __name__ == "__main__":
    main()
