"""
Fast Ollama integration - optimized for speed and reliability.
Analyzes your cheatsheet picks in real-time without timeouts.
"""
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional


class FastOllamaAnalyzer:
    """Fast Ollama analyzer with aggressive timeout handling."""
    
    def __init__(self, model: str = "mistral", timeout: int = 8):
        self.model = model
        self.timeout = timeout  # 8 seconds max per query
        self.success_count = 0
        self.timeout_count = 0
    
    def analyze_pick(self, pick: Dict) -> Dict:
        """
        Quickly analyze a single pick.
        Returns advisory notes - NOT ground truth.
        """
        player = pick.get('player', 'Unknown')
        prop = pick.get('stat', 'Unknown')
        line = pick.get('line', 0)
        avg = pick.get('mu', 0)
        direction = 'OVER' if avg > line else 'UNDER'
        edge = abs(avg - line)
        conf = pick.get('confidence', 0.5)
        
        # Build tight, focused prompt (minimal tokens)
        prompt = (
            f"NBA prop quick check:\n"
            f"Player: {player}\n"
            f"Prop: {prop} {direction} {line}\n"
            f"Avg: {avg:.1f}, Edge: {edge:.1f}\n"
            f"Conf: {conf*100:.0f}%\n\n"
            f"Is this reasonable? 1-sentence assessment only."
        )
        
        try:
            start = time.time()
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            elapsed = time.time() - start
            
            if result.returncode == 0:
                self.success_count += 1
                response = result.stdout.strip()[:200]  # Limit response size
                return {
                    'player': player,
                    'prop': prop,
                    'ollama_notes': response,
                    'time': f"{elapsed:.1f}s",
                    'status': '✅'
                }
            else:
                self.timeout_count += 1
                return {
                    'player': player,
                    'prop': prop,
                    'ollama_notes': 'Analysis skipped',
                    'time': f"{elapsed:.1f}s",
                    'status': '⏭️ '
                }
        
        except subprocess.TimeoutExpired:
            self.timeout_count += 1
            return {
                'player': player,
                'prop': prop,
                'ollama_notes': 'Timeout (>8s)',
                'time': f'{self.timeout}s+',
                'status': '⏱️ '
            }
        except Exception as e:
            self.timeout_count += 1
            return {
                'player': player,
                'prop': prop,
                'ollama_notes': f'Error: {str(e)[:50]}',
                'time': '0s',
                'status': '❌'
            }
    
    def batch_analyze(self, picks: List[Dict], max_picks: int = 10) -> List[Dict]:
        """Analyze top picks quickly."""
        print(f"\n🤖 OLLAMA QUICK ANALYSIS ({self.model})")
        print("=" * 70)
        print(f"Analyzing top {min(max_picks, len(picks))} picks ({self.timeout}s timeout)...\n")
        
        results = []
        for i, pick in enumerate(picks[:max_picks], 1):
            result = self.analyze_pick(pick)
            results.append(result)
            
            # Print real-time feedback
            print(
                f"{result['status']} {i:2}. {result['player']:20} "
                f"{result['prop']:20} {result['time']:>6} "
                f"| {result['ollama_notes'][:40]}"
            )
        
        # Summary
        total = self.success_count + self.timeout_count
        success_rate = (self.success_count / total * 100) if total > 0 else 0
        
        print("\n" + "=" * 70)
        print(f"Results: {self.success_count}/{total} successful ({success_rate:.0f}%)")
        print(f"Total time: {sum(float(r['time'].rstrip('s+')) for r in results):.1f}s")
        print("=" * 70)
        
        return results
    
    def get_summary(self, picks: List[Dict]) -> str:
        """Get expert summary of top picks."""
        top_3 = picks[:3]
        picks_str = "\n".join([
            f"• {p.get('player')} {p.get('stat')} "
            f"(Conf: {p.get('confidence', 0)*100:.0f}%)"
            for p in top_3
        ])
        
        prompt = (
            f"Quick expert summary of these 3 NBA prop picks:\n\n"
            f"{picks_str}\n\n"
            f"Best betting strategy? 1 paragraph max."
        )
        
        try:
            result = subprocess.run(
                ["ollama", "run", self.model, prompt],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return "Summary unavailable (timeout)"


def integrate_ollama_with_cheatsheet():
    """
    Load latest cheatsheet and enhance with Ollama analysis.
    """
    
    # Find latest cheatsheet
    output_dir = Path("outputs")
    reports = sorted(
        output_dir.glob("CHEATSHEET_*_STATISTICAL.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    
    if not reports:
        print("❌ No cheatsheet found. Run generate_cheatsheet.py first.")
        return
    
    latest = reports[0]
    print(f"📄 Using: {latest.name}")
    
    # Load hydrated picks
    with open("picks_hydrated.json") as f:
        picks = json.load(f)
    
    # Sort by confidence
    picks.sort(key=lambda p: p.get('confidence', 0), reverse=True)
    
    # Run Ollama analysis with llama3.1 (faster) and 20s timeout (CPU-bound)
    analyzer = FastOllamaAnalyzer(model="llama3.1:8b", timeout=20)
    results = analyzer.batch_analyze(picks, max_picks=10)
    
    # Get expert summary
    print("\n📊 EXPERT SUMMARY:")
    print("-" * 70)
    summary = analyzer.get_summary(picks)
    print(summary)
    
    # Save results
    output_file = output_dir / f"{latest.stem}_ollama_analysis.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'model': analyzer.model,
            'cheatsheet': latest.name,
            'detailed_analysis': results,
            'expert_summary': summary,
            'success_rate': f"{analyzer.success_count}/{analyzer.success_count + analyzer.timeout_count}"
        }, f, indent=2)
    
    print(f"\n✅ Analysis saved to: {output_file.name}")


if __name__ == "__main__":
    integrate_ollama_with_cheatsheet()
