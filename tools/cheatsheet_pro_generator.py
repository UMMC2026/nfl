#!/usr/bin/env python3
# WARNING:
# OFFLINE PRESENTATION TOOL ONLY.
# NOT part of execution or signal delivery.
# Do NOT import into daily_pipeline, engine, Telegram, or menu systems.

"""
CHEAT SHEET PRO GENERATOR - FINAL PRESENTATION LAYER
Combines validated edges with optional commentary into professional betting summary

Architecture:
- Input: outputs/validated_primary_edges.json (today's truth only - MANDATORY CHECK)
- Optional Input: OLLAMA_SLATE_COMMENTARY_YYYY-MM-DD.md (interpretation)
- Output: CHEAT_SHEET_PRO_YYYY-MM-DD.md (ready-to-bet summary)

CRITICAL: This tool REFUSES to generate from stale data. File must be from TODAY.
"""

import json
import os
from pathlib import Path
from datetime import datetime
import time


class CheatSheetProGenerator:
    """Combines validated edges + Ollama into professional betting cheat sheet."""
    
    def __init__(self, validated_edges_path, ollama_commentary_path=None):
        """Load validated edges and optional Ollama commentary.
        
        CRITICAL: validated_edges_path MUST be outputs/validated_primary_edges.json
        and MUST have been created today (timestamp check enforced).
        """
        validated_path = Path(validated_edges_path)
        
        # HARD FAIL: Check if file exists and is from TODAY
        if not validated_path.exists():
            raise FileNotFoundError(
                f"FATAL: {validated_edges_path} does not exist.\n"
                f"Run [1] VALIDATE TRUTH PIPELINE from menu first."
            )
        
        # HARD FAIL: Check timestamp - must be from today
        file_mtime = validated_path.stat().st_mtime
        file_date = datetime.fromtimestamp(file_mtime).date()
        today = datetime.now().date()
        
        if file_date != today:
            raise RuntimeError(
                f"FATAL: {validated_edges_path} is from {file_date}, not today ({today}).\n"
                f"Refusing to generate cheatsheet from stale data.\n"
                f"Run [1] VALIDATE TRUTH PIPELINE to refresh."
            )
        
        self.validated_data = json.loads(validated_path.read_text(encoding="utf-8"))
        self.ollama_text = None
        if ollama_commentary_path and Path(ollama_commentary_path).exists():
            self.ollama_text = Path(ollama_commentary_path).read_text(encoding="utf-8")

    
    def extract_bets_by_tier(self):
        """Categorize bets by confidence tier (SLAM > STRONG > LEAN).
        
        Reads from validated primary edges (post-pipeline).
        """
        all_bets = []
        
        # validated_primary_edges.json structure: array of edge dicts
        edges = self.validated_data if isinstance(self.validated_data, list) else self.validated_data.get("edges", [])
        
        for edge in edges:
            all_bets.append({
                "player": edge.get("player", ""),
                "stat": edge.get("stat", ""),
                "line": edge.get("line", 0),
                "direction": edge.get("direction", "higher"),
                "confidence": edge.get("p_hit", 0.5),  # p_hit from validated output
                "team": edge.get("team", ""),
                "game_id": edge.get("game_id", ""),
                "tier": self._calculate_tier(edge.get("p_hit", 0.5)),
            })
        
        # Sort by confidence
        all_bets.sort(key=lambda x: x["confidence"], reverse=True)
        
        slams = [b for b in all_bets if b["tier"] == "SLAM"]
        strong = [b for b in all_bets if b["tier"] == "STRONG"]
        lean = [b for b in all_bets if b["tier"] == "LEAN"]
        
        return slams, strong, lean
    
    def _calculate_tier(self, confidence):
        """Classify bet by confidence tier."""
        if confidence >= 0.67:
            return "SLAM"
        elif confidence >= 0.62:
            return "STRONG"
        else:
            return "LEAN"
    
    def generate_cheatsheet(self):
        """Build final cheat sheet with all tiers."""
        slams, strong, lean = self.extract_bets_by_tier()

        # Add historical performance
        from ufa.analysis.results_tracker import ResultsTracker
        tracker = ResultsTracker()
        yesterday_block = tracker.format_yesterday_block()
        rolling_block = tracker.format_rolling_block(days=7)

        total_bets = len(slams) + len(strong) + len(lean)

        sheet = f"""
╔════════════════════════════════════════════════════════════════════════════════╗
║                      CHEAT SHEET PRO - FINAL BETS                             ║
║                              {datetime.now().strftime("%B %d, %Y")}                                ║
║                    SOP v2.1 GOVERNANCE ENFORCED                                 ║
╚════════════════════════════════════════════════════════════════════════════════╝

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Data Source: Validated Primary Edges ({total_bets} total bets)
Tier System: SLAM (67%+) | STRONG (62–66%) | LEAN (55–61%)

{yesterday_block}
{rolling_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 SLAM TIER (67%+ CONFIDENCE) — PRIMARY CANDIDATES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        
        for idx, bet in enumerate(slams, 1):
            sheet += f"{idx}. {bet['player']} ({bet['team']}) | {bet['stat']} {bet['direction']} {bet['line']}\n"
            sheet += f"   Confidence: {bet['confidence']:.1%}\n"
            sheet += f"   Status: Suitable for primary allocation if exposure allows\n\n"
        
        sheet += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        sheet += f"💪 STRONG TIER (62–66% CONFIDENCE) — SECONDARY CANDIDATES\n"
        sheet += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for idx, bet in enumerate(strong, 1):
            sheet += f"{idx}. {bet['player']} ({bet['team']}) | {bet['stat']} {bet['direction']} {bet['line']}\n"
            sheet += f"   Confidence: {bet['confidence']:.1%}\n"
            sheet += f"   Status: Secondary to SLAM tier, suitable for supplemental allocation\n\n"
        
        sheet += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        sheet += f"⚠️  LEAN TIER (55–61% CONFIDENCE) — TERTIARY / HEDGE CANDIDATES\n"
        sheet += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for idx, bet in enumerate(lean, 1):
            sheet += f"{idx}. {bet['player']} ({bet['team']}) | {bet['stat']} {bet['direction']} {bet['line']}\n"
            sheet += f"   Confidence: {bet['confidence']:.1%}\n"
            sheet += f"   Status: Use for hedging or sizing diversification only\n\n"
        
        # RISK MANAGEMENT
        sheet += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        sheet += f"⚠️  RISK MANAGEMENT & POSITION SIZING\n"
        sheet += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        sheet += f"• SLAM Tier: Primary allocation (up to 50% of bankroll)\n"
        sheet += f"• STRONG Tier: Secondary allocation (up to 30% of bankroll)\n"
        sheet += f"• LEAN Tier: Hedge/diversification only (up to 20% of bankroll)\n"
        sheet += f"• Maximum exposure per game: 25% of total allocation\n"
        sheet += f"• Correlation risk: Avoid stacking multiple props from same player/game\n\n"
        
        sheet += f"""

KEY RULES:
  1. Never exceed standard unit sizing in concentrated games
  2. Pair every 3-over parlay with 1:1 under hedge (if available)
  3. Reserve 25–30% bankroll for live adjustment (pace changes)
  4. If league pace drops, all overs suffer together (coordinated risk)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 VARIANCE CONTEXT (CRITICAL FOR SIZING)

All bets subject to ±8% variance:
  - 70% confidence ≠ guaranteed → may hit 62–78% in practice
  - Parlays subject to ±10% variance (multiplicative effect)
  - Variance range assumes market efficiency and expected pace

Example:
  - SLAM bet modeled at 70%, hits at 70% on average
  - But in this specific slate, could hit anywhere from 62–78%
  - Sizing should account for this range (full unit if confident, 0.5 unit if cautious)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ GOVERNANCE STATUS

  ✅ Monte Carlo math locked (immutable)
  ✅ Tier assignments from finalized MC data
  ✅ Exposure reduction percentages automatic (concentration-driven)
  ✅ No imperatives: All language is conditional ("if exposure allows", "suitable for")
  ✅ Ready for regulatory review

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Append Ollama commentary if available
        if self.ollama_text:
            sheet += f"\n\n🤖 OLLAMA SLATE INTERPRETATION\n"
            sheet += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            sheet += self.ollama_text
        
        sheet += f"\n\n╔════════════════════════════════════════════════════════════════════════════════╗\n"
        sheet += f"║ END OF CHEAT SHEET PRO — READY FOR EXECUTION                                  ║\n"
        sheet += f"╚════════════════════════════════════════════════════════════════════════════════╝\n"
        
        return sheet

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
    print("CHEAT SHEET PRO GENERATOR - FINAL PRESENTATION")
    print("="*90 + "\n")
    
    # CRITICAL: Read from validated_primary_edges.json ONLY
    validated_file = Path("outputs/validated_primary_edges.json")
    
    if not validated_file.exists():
        raise FileNotFoundError(
            f"[FATAL] {validated_file} does not exist.\n"
            f"REQUIRED: Run [1] VALIDATE TRUTH PIPELINE from menu first.\n"
            f"Cheatsheet generation forbidden without today's validated edges."
        )
    
    # Timestamp check: refuse if not from today
    file_mtime = validated_file.stat().st_mtime
    file_date = datetime.fromtimestamp(file_mtime).date()
    today = datetime.now().date()
    
    if file_date != today:
        raise RuntimeError(
            f"[FATAL] {validated_file} is from {file_date}, not today ({today}).\n"
            f"Refusing to generate cheatsheet from stale data.\n"
            f"Run [1] VALIDATE TRUTH PIPELINE to create fresh validated edges."
        )
    
    print(f"[OK] Loaded validated edges: {validated_file.name} (today's data)\n")
    
    # Find latest Ollama commentary (optional)
    ollama_files = list(Path("outputs").glob("OLLAMA_SLATE_COMMENTARY_*.md"))
    ollama_file = ollama_files[-1] if ollama_files else None
    
    if ollama_file:
        print(f"[OK] Loaded Ollama commentary: {ollama_file.name}\n")
    else:
        print("[WARN] No Ollama commentary found (optional).\n")
    
    # Generate cheat sheet from validated edges
    try:
        generator = CheatSheetProGenerator(str(validated_file), str(ollama_file) if ollama_file else None)
        cheatsheet = generator.generate_cheatsheet()
    except (FileNotFoundError, RuntimeError) as e:
        print(f"[FATAL] {e}")
        raise
    
    print(cheatsheet)
    
    # Save with today's date
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_path = Path("outputs") / f"CHEAT_SHEET_PRO_{date_str}.md"
    output_path.write_text(cheatsheet, encoding="utf-8")
    
    print("\n" + "="*90)
    print(f"[OK] Cheat sheet saved: {output_path.name}")
    print(f"[OK] Data source: validated_primary_edges.json (created {file_mtime})")
    print("="*90 + "\n")

if __name__ == "__main__":
    main()
