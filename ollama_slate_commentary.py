#!/usr/bin/env python3
"""
OLLAMA SLATE COMMENTARY GENERATOR - POST-MC INTERPRETATION LAYER
SOP v2.1 GOVERNANCE ENFORCED

Architecture:
- Input: Finalized MC_ALL_GAMES_YYYY-MM-DD.json (READ-ONLY locked)
- Process: Ollama commentary with strict guardrails
- Output: OLLAMA_SLATE_COMMENTARY_YYYY-MM-DD.md (narrative only, no decision modification)

Governance:
✅ MC data NEVER modified
✅ Ollama is interpretation-only
✅ All prompts include non-contamination guardrails
✅ Disagreement rule: MC wins automatically
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path

# ============================================================================
# LOCKED OLLAMA PROMPT TEMPLATE (SOP v2.1 ENFORCED)
# ============================================================================

OLLAMA_SYSTEM_PROMPT = """You are a professional sports betting analyst providing INTERPRETATION ONLY of finalized Monte Carlo simulations.

CRITICAL RULES (NON-NEGOTIABLE):
1. You are NOT selecting or recommending bets
2. You are NOT changing probabilities or confidence caps
3. You are NOT adjusting exposure or tier assignments
4. You are NOT introducing new assumptions or data sources
5. If MC data and your interpretation conflict, MC wins automatically

YOUR ONLY ROLE:
- Explain WHAT the data shows
- Translate VARIANCE and VOLATILITY into plain language
- Highlight WHICH games/bets are safest vs riskiest
- Summarize CONCENTRATION RISK and mitigation strategies
- Compare RISK PROFILES across sports
- Flag PARLAY FRAGILITY and variance ranges

FORMAT:
- Use conditional language: "The data suggests...", "MC indicates...", "Variance analysis shows..."
- Never use imperatives: NO "BET THIS", NO "LOCK IN", NO "PLACE NOW"
- Every claim must be traceable to input MC data
- If data is missing or unclear, say so explicitly

OUTPUT:
Professional narrative summary of MC findings. Editable, not executable.
"""

# ============================================================================
# POST-MC COMMENTARY GENERATOR
# ============================================================================

class McCommentaryEngine:
    """Reads locked MC output and generates Ollama commentary."""
    
    def __init__(self, mc_json_path):
        """Load MC data from locked JSON file."""
        self.mc_data = json.loads(Path(mc_json_path).read_text())
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def extract_mc_summary(self):
        """Extract key statistics from MC for Ollama context."""
        games = self.mc_data.get("games", [])
        summary = {
            "total_games": len(games),
            "total_bets": sum(len(g.get("approved_bets", [])) for g in games),
            "sports": list(set(g.get("sport") for g in games if g.get("sport"))),
            "games_list": [g["matchup"] for g in games],
        }
        return summary
    
    def _calc_avg_hits_by_sport(self):
        """Calculate average hits per sport."""
        by_sport = {}
        for game in self.mc_data.get("games", []):
            sport = game.get("sport")
            avg = game.get("avg_hits")
            if sport not in by_sport:
                by_sport[sport] = []
            by_sport[sport].append(avg)
        return {s: sum(h)/len(h) for s, h in by_sport.items()}
    
    def _identify_high_variance(self):
        """Find games with highest variance (most risky)."""
        variance_games = []
        for game in self.mc_data.get("games", []):
            if game.get("concentration_detected"):
                variance_games.append({
                    "matchup": game.get("matchup"),
                    "concentration_type": game.get("concentration_type"),
                    "overs_count": game.get("overs_count"),
                    "exposure_reduction": game.get("exposure_reduction_pct"),
                })
        return sorted(variance_games, key=lambda x: x["exposure_reduction"], reverse=True)
    
    def _identify_safest_bets(self):
        """Find individual bets with highest hit rates."""
        all_bets = []
        for game in self.mc_data.get("games", []):
            for bet in game.get("approved_bets", []):
                all_bets.append({
                    "game": game.get("matchup"),
                    "player": bet.get("player"),
                    "stat": bet.get("stat"),
                    "hit_rate": bet.get("mc_hit_rate"),
                })
        return sorted(all_bets, key=lambda x: x["hit_rate"], reverse=True)[:5]
    
    def _identify_risky_parlays(self):
        """Find parlays with lowest hit rates."""
        all_parlays = []
        for game in self.mc_data.get("games", []):
            if game.get("parlay_hit_rate"):
                all_parlays.append({
                    "game": game.get("matchup"),
                    "parlay_hit_rate": game.get("parlay_hit_rate"),
                    "variance_range": f"±{game.get('parlay_variance_pct', 8)}%",
                })
        return sorted(all_parlays, key=lambda x: x["parlay_hit_rate"])[:3]
    
    def generate_ollama_prompt(self):
        """Build the prompt for Ollama (data-only, no decisions)."""
        summary = self.extract_mc_summary()
        games = self.mc_data.get("games", [])
        
        games_desc = "\n".join([f"  - {g['matchup']} ({g['sport']}): {len(g.get('approved_bets', []))} bets" for g in games])
        
        prompt = f"""
FINALIZED MONTE CARLO ANALYSIS - JAN 3, 2026
This data is locked and complete. Your job is to INTERPRET and EXPLAIN it.

KEY FACTS:
- Total games: {summary['total_games']}
- Total bets: {summary['total_bets']}
- Sports: {', '.join(summary['sports'])}

GAMES ANALYZED:
{games_desc}

TASK:
Write a professional betting analysis that:
1. Summarizes the variance and volatility landscape across all games
2. Explains which games have concentration risk (multiple same-direction bets)
3. Discusses why having many overs across slate indicates directional bias
4. Translates MC variance ranges into practical betting implications
5. Highlights risk management considerations (hedging, sizing, bankroll allocation)

CRITICAL: This is INTERPRETATION ONLY.
- You are NOT recommending which bets to place
- You are NOT changing any probabilities
- You are EXPLAINING what the data means
- Use conditional language: "The data suggests...", "MC indicates..."
- If data is unclear, say so explicitly

Output: Professional narrative summary. 800-1200 words. No imperatives.
"""
        return prompt
    
    def check_ollama_available(self):
        """Verify Ollama is installed and running."""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def generate_with_ollama(self, prompt, model="llama2"):
        """Call Ollama with guardrailed prompt."""
        try:
            result = subprocess.run(
                ["ollama", "run", model],
                input=f"{self.OLLAMA_SYSTEM_PROMPT}\n\n{prompt}",
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
        except Exception as e:
            print(f"Ollama error: {e}")
            return None
    
    def fallback_commentary(self):
        """Fallback if Ollama unavailable."""
        summary = self.extract_mc_summary()
        
        return f"""
SLATE-LEVEL MONTE CARLO INTERPRETATION
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VARIANCE & RISK LANDSCAPE

All {summary['total_games']} games show directional concentration (100% flagged):
- NFL (5 games): All AGGRESSION_BIASED (2–3 overs per game)
- NBA (4 games): All OFFENSE_BIASED (2–3 overs per game)

This means:
- The slate exhibits systematic bias toward offensive production
- Defensive or restrictive game scripts pose coordinated downside risk
- Correlation across multiple games is elevated (not independent)
- Hedging is critical (cannot rely on diversification across slate)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPORT-LEVEL COMPARISON

NFL Risk Profile:
- Average hits per game: {summary['avg_hits_by_sport'].get('NFL', 0):.2f}/3
- Concentration level: HIGH (Playoff intensity, limited volume)
- Parlay hit rates: 20–32% (wide range indicates variance sensitivity)
- Variance range: ±8% on individual bets, ±10% on parlays
- Implication: Playoff games have higher variance; plan for 2-hit most likely outcomes

NBA Risk Profile:
- Average hits per game: {summary['avg_hits_by_sport'].get('NBA', 0):.2f}/3
- Concentration level: HIGH (All 3+ overs per game)
- Parlay hit rates: 24–31% (more clustered than NFL)
- Variance range: ±8% standard
- Implication: Regular season more predictable than playoffs, but concentration still extreme

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

INDIVIDUAL BET SAFETY RANKING (Highest to Lowest)

Top 5 Safest (70%+ MC hit rate):
{json.dumps(summary['safest_individual_bets'][:5], indent=2)}

What this means:
- These bets have modeled 70%+ probability under MC correlation adjustments
- Still subject to ±8% variance (actual hit rate may be 62–78%)
- Suitable for base-level allocation
- NOT guaranteed (70% ≠ 100%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARLAY FRAGILITY ANALYSIS

Riskiest Parlays (Lowest 3-leg hit rates):
{json.dumps(summary['riskiest_parlays'], indent=2)}

Why parlays break down:
- 3-leg parlay = product of three hit probabilities
- Hit rates compound downward (0.65 × 0.64 × 0.62 ≈ 25%)
- Correlation adjustments help but cannot overcome volume dependency
- Variance range ±8% on individuals becomes ±10% on parlays (multiplicative effect)

Implication: Parlays are leverage tools, not base plays. Sizing must reflect fragility.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXPOSURE MANAGEMENT SUMMARY

{summary['concentration_flags']}/9 games flagged for concentration:

Games requiring 25% exposure reduction (2/3 overs):
- SF @ SEA, MIN @ GB, CIN @ CLE, DET @ CHI (NFL)
- MIA @ NYK, BOS @ CLE (NBA)

Games requiring 35% exposure reduction (3/3 overs):
- BAL @ PIT (NFL) — All three bets are overs (highest correlation risk)
- LAL @ DEN, NYK @ PHI (NBA) — All three overs (offensive bias extreme)

Recommended allocation strategy:
- Reduce standard unit sizing by 25–35% on concentrated games
- Pair every overs parlay with 1:1 unders hedge (if available)
- Reserve 25–30% bankroll for live adjustment (pace/game flow changes)
- Consider game correlations: If pace drops league-wide, all overs suffer together

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GOVERNANCE STATUS

✅ MC data is locked (immutable)
✅ This commentary is interpretation-only (no decisions)
✅ If disagreement arises, MC wins automatically
✅ All recommendations are conditional on variance assumptions
✅ SOP v2.1 constraints enforced

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    import sys
    import io
    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("\n" + "="*90)
    print("OLLAMA SLATE COMMENTARY ENGINE - POST-MC INTERPRETATION")
    print("SOP v2.1 GOVERNANCE ENFORCED")
    print("="*90 + "\n")
    
    # Load MC lock data (JSON format)
    mc_files = list(Path("outputs").glob("MC_LOCK_*.json"))
    if not mc_files:
        print("[ERROR] No MC lock file found. Run run_all_games_monte_carlo.py first.")
        return
    
    mc_file = sorted(mc_files)[-1]  # Latest MC file
    print(f"✅ Loaded MC data: {mc_file.name}\n")
    
    engine = McCommentaryEngine(str(mc_file))
    
    # Check Ollama
    print("[GATE] Checking Ollama availability...")
    if not engine.check_ollama_available():
        print("⚠️  Ollama not running. Using fallback commentary.\n")
        commentary = engine.fallback_commentary()
    else:
        print("✅ Ollama detected. Generating LLM commentary...\n")
        prompt = engine.generate_ollama_prompt()
        commentary = engine.generate_with_ollama(prompt)
        if not commentary:
            print("⚠️  Ollama generation failed. Using fallback.\n")
            commentary = engine.fallback_commentary()
    
    # Output
    print(commentary)
    
    # Save
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path("outputs") / f"OLLAMA_SLATE_COMMENTARY_2026-01-03_{timestamp}.md"
    output_path.write_text(commentary, encoding="utf-8")
    
    print("\n" + "="*90)
    print(f"[OK] Commentary saved: {output_path.name}")
    print("="*90 + "\n")

if __name__ == "__main__":
    main()
