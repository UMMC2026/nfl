"""
GATES ON vs OFF COMPARISON
==========================
Analyzes the 9 picks from NBA cheatsheet with both configurations:
- Current (HYBRID mode - most gates OFF)
- Professional (gates ON)

This shows exactly what each gate does to confidence scores.
"""
import json
import sys
from pathlib import Path
from copy import deepcopy

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from risk_first_analyzer import analyze_prop_with_gates, STATS_DICT, _LAST_SERIES_MAP

# The 9 picks from the cheatsheet
PICKS = [
    {"player": "Isaiah Hartenstein", "stat": "rebounds", "line": 6.5, "direction": "higher", "team": "OKC", "cheatsheet_conf": 76.0},
    {"player": "Jalen Johnson", "stat": "assists", "line": 6.5, "direction": "higher", "team": "ATL", "cheatsheet_conf": 67.9},
    {"player": "Royce O'Neale", "stat": "rebounds", "line": 4.5, "direction": "higher", "team": "PHX", "cheatsheet_conf": 61.3},
    {"player": "Josh Giddey", "stat": "assists", "line": 7.5, "direction": "higher", "team": "CHI", "cheatsheet_conf": 60.5},
    {"player": "Andrew Wiggins", "stat": "rebounds", "line": 4.5, "direction": "higher", "team": "GSW", "cheatsheet_conf": 59.1},
    {"player": "Jaden Ivey", "stat": "rebounds", "line": 1.5, "direction": "higher", "team": "DET", "cheatsheet_conf": 58.9},
    {"player": "Myles Turner", "stat": "rebounds", "line": 6.5, "direction": "lower", "team": "IND", "cheatsheet_conf": 62.3},
    {"player": "Jabari Smith Jr.", "stat": "rebounds", "line": 7.5, "direction": "lower", "team": "HOU", "cheatsheet_conf": 61.8},
    {"player": "Mouhamed Gueye", "stat": "rebounds", "line": 5.5, "direction": "lower", "team": "HOU", "cheatsheet_conf": 59.3},
]

def load_penalty_mode():
    """Load current penalty mode config."""
    config_path = Path(__file__).parent / "config" / "penalty_mode.json"
    with open(config_path, 'r') as f:
        return json.load(f)

def save_penalty_mode(config):
    """Save penalty mode config."""
    config_path = Path(__file__).parent / "config" / "penalty_mode.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

def get_gates_off_config():
    """Current HYBRID mode (most gates OFF)."""
    return {
        "master_penalties_off": True,
        "use_hybrid_confidence": True,
        "use_data_driven_penalties": True,
        "variance_penalty": False,
        "sample_penalty": False,
        "stat_penalty": False,
        "gate_penalties": False,
        "bootstrap_guard": False,
        "edge_gate": False,
        "context_adjustment": False,
        "stat_multipliers": False,
        "confidence_compression": False,
        "specialist_governance": False
    }

def get_gates_on_config():
    """Professional mode (gates ON)."""
    return {
        "master_penalties_off": False,
        "use_hybrid_confidence": True,
        "use_data_driven_penalties": True,
        "variance_penalty": True,
        "sample_penalty": True,
        "stat_penalty": True,
        "gate_penalties": True,
        "bootstrap_guard": True,
        "edge_gate": True,
        "context_adjustment": True,
        "stat_multipliers": True,
        "confidence_compression": True,
        "specialist_governance": True
    }

def analyze_picks_with_config(picks, config_name, active_settings):
    """Analyze all picks with given config."""
    # Temporarily update the penalty mode
    import risk_first_analyzer
    risk_first_analyzer.PENALTY_MODE = active_settings
    
    results = []
    for pick in picks:
        try:
            result = analyze_prop_with_gates(pick, verbose=False)
            results.append({
                "player": pick["player"],
                "stat": pick["stat"],
                "line": pick["line"],
                "direction": pick["direction"],
                "cheatsheet_conf": pick["cheatsheet_conf"],
                "model_confidence": result.get("model_confidence", 0),
                "effective_confidence": result.get("effective_confidence", 0),
                "decision": result.get("decision", "UNKNOWN"),
                "mu": result.get("mu", 0),
                "sigma": result.get("sigma", 0),
                "edge": result.get("edge", 0),
                "z_score": result.get("z_score", 0),
                "variance_penalty": result.get("quant_framework", {}).get("variance_penalty"),
                "edge_gate": result.get("quant_framework", {}).get("edge_gate"),
                "edge_gate_passed": result.get("quant_framework", {}).get("edge_gate_passed", True),
                "hybrid_tier": result.get("hybrid_tier"),
                "context_notes": result.get("context_notes", []),
                "compression_applied": result.get("compression_applied", False),
            })
        except Exception as e:
            results.append({
                "player": pick["player"],
                "stat": pick["stat"],
                "error": str(e)
            })
    
    return results

def format_comparison_table(off_results, on_results):
    """Format side-by-side comparison."""
    print("\n" + "="*120)
    print("  GATES OFF (Current HYBRID Mode) vs GATES ON (Professional Mode)")
    print("="*120)
    
    # Header
    print(f"\n{'Player':<22} {'Stat':<8} {'Line':>5} {'Dir':<6} | {'OFF Conf':>8} {'OFF Dec':<8} | {'ON Conf':>8} {'ON Dec':<8} | {'Δ Conf':>7} {'Impact':<15}")
    print("-"*120)
    
    total_off = 0
    total_on = 0
    passes_off = 0
    passes_on = 0
    
    for off, on in zip(off_results, on_results):
        if "error" in off or "error" in on:
            print(f"{off.get('player', 'ERROR'):<22} ERROR: {off.get('error', on.get('error', 'Unknown'))}")
            continue
            
        player = off["player"][:21]
        stat = off["stat"][:7]
        line = off["line"]
        direction = off["direction"][:5]
        
        off_conf = off["effective_confidence"]
        on_conf = on["effective_confidence"]
        off_dec = off["decision"]
        on_dec = on["decision"]
        
        delta = on_conf - off_conf
        
        # Determine impact
        if delta < -10:
            impact = "🔴 BIG DROP"
        elif delta < -5:
            impact = "⚠️ Moderate drop"
        elif delta < 0:
            impact = "↓ Small drop"
        elif delta > 10:
            impact = "🟢 BIG BOOST"
        elif delta > 5:
            impact = "✅ Moderate boost"
        elif delta > 0:
            impact = "↑ Small boost"
        else:
            impact = "— No change"
        
        # Decision change indicator
        if off_dec != on_dec:
            impact = f"⚡ {off_dec}→{on_dec}"
        
        print(f"{player:<22} {stat:<8} {line:>5.1f} {direction:<6} | {off_conf:>7.1f}% {off_dec:<8} | {on_conf:>7.1f}% {on_dec:<8} | {delta:>+6.1f}% {impact:<15}")
        
        total_off += off_conf
        total_on += on_conf
        if off_dec in ["PLAY", "STRONG", "LEAN"]:
            passes_off += 1
        if on_dec in ["PLAY", "STRONG", "LEAN"]:
            passes_on += 1
    
    print("-"*120)
    avg_off = total_off / len(off_results) if off_results else 0
    avg_on = total_on / len(on_results) if on_results else 0
    print(f"{'AVERAGES':<22} {'':<8} {'':<5} {'':<6} | {avg_off:>7.1f}% {passes_off:>8} | {avg_on:>7.1f}% {passes_on:>8} | {avg_on-avg_off:>+6.1f}%")
    
    return avg_off, avg_on

def print_detailed_breakdown(on_results):
    """Show what each gate did."""
    print("\n" + "="*100)
    print("  DETAILED GATE IMPACT BREAKDOWN (Gates ON)")
    print("="*100)
    
    for r in on_results:
        if "error" in r:
            continue
            
        print(f"\n📊 {r['player']} - {r['stat'].upper()} {r['direction'].upper()} {r['line']}")
        print(f"   μ={r['mu']:.1f}, σ={r['sigma']:.1f}, z-score={r['z_score']:.2f}")
        print(f"   Model Confidence: {r['model_confidence']:.1f}% → Effective: {r['effective_confidence']:.1f}%")
        
        # Show what gates applied
        gates_applied = []
        
        if r.get("variance_penalty"):
            vp = r["variance_penalty"]
            gates_applied.append(f"   ⚡ VARIANCE PENALTY: CV={vp.get('cv', 0):.2f} → {vp.get('total_penalty', 1):.2f}x multiplier")
        
        if r.get("edge_gate"):
            eg = r["edge_gate"]
            status = "✅ PASS" if eg.get("passes_gate", True) else "❌ FAIL"
            gates_applied.append(f"   ⚡ EDGE GATE: {eg.get('edge_percent', 0):.1f}% edge {status}")
        
        if r.get("compression_applied"):
            gates_applied.append(f"   ⚡ COMPRESSION: Outlier projection capped")
        
        if r.get("context_notes"):
            for note in r["context_notes"]:
                if any(x in note for x in ["Pace", "Matchup", "Elite D", "Weak D", "B2B"]):
                    gates_applied.append(f"   ⚡ CONTEXT: {note}")
        
        if r.get("hybrid_tier"):
            gates_applied.append(f"   📋 HYBRID TIER: {r['hybrid_tier']}")
        
        if gates_applied:
            for g in gates_applied:
                print(g)
        else:
            print("   (No specific gate adjustments logged)")
        
        print(f"   → DECISION: {r['decision']}")

def main():
    print("\n" + "🔬"*30)
    print("  PENALTY GATES COMPARISON TEST")
    print("🔬"*30)
    
    # Save original config
    original_config = load_penalty_mode()
    
    try:
        # Test with GATES OFF (current hybrid mode)
        print("\n[1/2] Analyzing with GATES OFF (current HYBRID mode)...")
        off_config = get_gates_off_config()
        off_results = analyze_picks_with_config(PICKS, "GATES_OFF", off_config)
        
        # Test with GATES ON (professional mode)
        print("[2/2] Analyzing with GATES ON (professional mode)...")
        on_config = get_gates_on_config()
        on_results = analyze_picks_with_config(PICKS, "GATES_ON", on_config)
        
        # Show comparison
        avg_off, avg_on = format_comparison_table(off_results, on_results)
        
        # Show detailed breakdown
        print_detailed_breakdown(on_results)
        
        # Summary
        print("\n" + "="*100)
        print("  SUMMARY")
        print("="*100)
        delta = avg_on - avg_off
        print(f"\n  Average Confidence: {avg_off:.1f}% (OFF) → {avg_on:.1f}% (ON) = {delta:+.1f}% change")
        
        if delta < 0:
            print(f"\n  ⚠️  Gates ON REDUCES confidence by {abs(delta):.1f}% on average")
            print("     This is EXPECTED - gates add conservatism to prevent overconfidence")
            print("     The question is: Does this improve your actual HIT RATE?")
        else:
            print(f"\n  ✅ Gates ON INCREASES confidence by {delta:.1f}% on average")
            print("     Some context adjustments (weak defense, pace) may boost certain picks")
        
        # Recommendation
        print("\n" + "-"*100)
        print("  RECOMMENDATION")
        print("-"*100)
        print("""
  Your current 48.5% hit rate (47/97 picks) suggests the system needs refinement.
  
  OPTIONS:
  1. ENABLE GATES SELECTIVELY - Start with:
     - edge_gate: true        (reject low-edge plays)
     - specialist_governance: true (BIG_MAN_3PM caps)
     - Keep others OFF until you validate
  
  2. RUN A/B TEST - Track next 50 picks:
     - 25 with current settings
     - 25 with gates ON
     - Compare hit rates
  
  3. TRUST CALIBRATION DATA - Your AST +20% boost is already helping.
     AST picks hit 60% vs overall 48.5%.
        """)
        
    finally:
        # Restore original config
        save_penalty_mode(original_config)
        print("\n✅ Original penalty_mode.json restored")

if __name__ == "__main__":
    main()
