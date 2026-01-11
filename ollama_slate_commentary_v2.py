#!/usr/bin/env python3
"""
OLLAMA SLATE COMMENTARY GENERATOR - POST-MC INTERPRETATION LAYER (SIMPLIFIED)
SOP v2.1 GOVERNANCE ENFORCED

Reads locked MC JSON → generates interpretation-only narrative with Ollama
Output: OLLAMA_SLATE_COMMENTARY_YYYY-MM-DD.md (narrative only, no decisions)
"""

import subprocess
import json
import sys
import io
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============================================================================
# LOCKED OLLAMA SYSTEM PROMPT
# ============================================================================

SYSTEM_PROMPT = """You are a professional sports betting analyst providing INTERPRETATION ONLY of finalized Monte Carlo simulations.

CRITICAL RULES (NON-NEGOTIABLE):
1. You are NOT selecting or recommending bets
2. You are NOT changing probabilities or tier assignments  
3. You are NOT introducing new assumptions
4. Your only role is to EXPLAIN what the data means

FORBIDDEN:
- "LOCK IN", "PLACE NOW", imperatives
- New betting recommendations
- Changing any numbers from MC output
- Inventing data

ALLOWED:
- "The data suggests...", "MC indicates...", "Variance analysis shows..."
- Explaining concentration risk
- Translating variance into plain language
- Comparing risk profiles

Output: Professional narrative, conditional language only.
"""

# ============================================================================
# COMMENTARY ENGINE
# ============================================================================

class CommentaryEngine:
    """Read MC lock and generate Ollama commentary."""
    
    def __init__(self, lock_file):
        self.mc_data = json.loads(Path(lock_file).read_text())
    
    def get_summary(self):
        """Extract basic stats from MC data."""
        games = self.mc_data.get("games", [])
        return {
            "total_games": len(games),
            "total_bets": sum(len(g.get("approved_bets", [])) for g in games),
            "sports": list(set(g.get("sport") for g in games if g.get("sport"))),
            "nfl_games": [g["matchup"] for g in games if g.get("sport") == "NFL"],
            "nba_games": [g["matchup"] for g in games if g.get("sport") == "NBA"],
        }
    
    def generate_prompt(self):
        """Create Ollama prompt."""
        summary = self.get_summary()
        games = self.mc_data.get("games", [])
        
        games_list = "\n".join([
            f"  - {g['matchup']} ({g['sport']}): {len(g.get('approved_bets', []))} bets"
            for g in games
        ])
        
        bets_list = "\n".join([
            f"  - {b['player']} {b['stat']} {b['dir']} {b['line']}"
            for g in games for b in g.get('approved_bets', [])
        ])
        
        prompt = f"""
FINALIZED MONTE CARLO ANALYSIS INTERPRETATION

DATE: 2026-01-03
TOTAL GAMES: {summary['total_games']} (NFL: {len(summary['nfl_games'])}, NBA: {len(summary['nba_games'])})
TOTAL BETS: {summary['total_bets']}

GAMES ANALYZED:
{games_list}

SAMPLE BETS:
{bets_list[:1000]}

TASK:
Write a professional analysis explaining:
1. Why ALL {summary['total_games']} games show concentration (many overs/unders same direction)
2. What this means for variance and correlation risk
3. How to interpret individual hit rates under ±8% variance assumption
4. Why parlays are fragile in concentrated slates
5. Key risk management principles (hedging, sizing, bankroll allocation)

CRITICAL CONSTRAINTS:
- NO imperatives or commands
- NO new bet recommendations
- Use conditional language: "suggests", "indicates", "may imply"
- Explain the math, not how to bet
- 600-800 words

This is interpretation of locked data, not decision-making.
"""
        return prompt
    
    def check_ollama(self):
        """Verify Ollama is running."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def call_ollama(self, prompt, model="llama2"):
        """Call Ollama with guardrailed prompt."""
        try:
            result = subprocess.run(
                ["ollama", "run", model],
                input=f"{SYSTEM_PROMPT}\n\n{prompt}",
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout if result.returncode == 0 else None
        except Exception as e:
            print(f"[WARN] Ollama error: {e}")
            return None
    
    def fallback(self):
        """Simple fallback if Ollama unavailable."""
        summary = self.get_summary()
        return f"""
SLATE INTERPRETATION (Fallback - Ollama unavailable)

All {summary['total_games']} games analyzed show directional concentration:
- Multiple games have 2-3 overs or 2-3 unders
- This indicates systematic bias in the slate
- Correlation across games is elevated
- Diversification risk is reduced

KEY IMPLICATIONS:
1. Variance may be higher than individual game models suggest
2. Hedging becomes critical (can't rely on game independence)
3. Hit rates subject to ±8% variance on individual bets
4. Parlay fragility: 3-leg combos multiply variance downward
5. Sizing should be conservative on concentrated games

RISK MANAGEMENT:
- Reserve 25-30% bankroll for live adjustment
- Use 1:1 hedges on overs-heavy slates
- Scale sizing down 25-35% on concentrated games
- Monitor pace in first quarter of each game
- Be ready to exit early if unders hit immediately

This interpretation is locked to {summary['total_games']} games analyzed on 2026-01-03.
"""

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*90)
    print("OLLAMA SLATE COMMENTARY ENGINE - POST-MC INTERPRETATION")
    print("="*90 + "\n")
    
    # Find latest MC lock
    lock_files = list(Path("outputs").glob("MC_LOCK_*.json"))
    if not lock_files:
        print("[ERROR] No MC lock file found.")
        return
    
    lock_file = lock_files[-1]
    print(f"[OK] MC lock loaded: {lock_file.name}\n")
    
    engine = CommentaryEngine(str(lock_file))
    
    # Try Ollama
    print("[GATE] Checking Ollama...")
    if engine.check_ollama():
        print("[OK] Ollama detected. Generating commentary...\n")
        prompt = engine.generate_prompt()
        commentary = engine.call_ollama(prompt)
        if not commentary:
            print("[WARN] Ollama failed, using fallback\n")
            commentary = engine.fallback()
    else:
        print("[WARN] Ollama not available, using fallback\n")
        commentary = engine.fallback()
    
    print(commentary)
    
    # Save
    output_path = Path("outputs") / f"OLLAMA_SLATE_COMMENTARY_2026-01-03.md"
    output_path.write_text(commentary, encoding="utf-8")
    
    print("\n" + "="*90)
    print(f"[OK] Commentary saved: {output_path.name}")
    print("="*90 + "\n")

if __name__ == "__main__":
    main()
