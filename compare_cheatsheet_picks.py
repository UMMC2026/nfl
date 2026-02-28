"""
GATES COMPARISON - The 9 Cheatsheet Picks
=========================================
Shows exactly what data went into each pick and what gates affected it.
"""
import json

# Load the actual analyzed data
with open('outputs/THURDAYNBA100_RISK_FIRST_20260129_FROM_UD.json') as f:
    data = json.load(f)

results = data.get('results', [])

# The exact 9 picks from the cheatsheet
CHEATSHEET_PICKS = [
    {"player": "Isaiah Hartenstein", "stat": "rebounds", "line": 6.5, "direction": "higher", "cheatsheet_conf": 76.0, "tier": "STRONG"},
    {"player": "Jalen Johnson", "stat": "assists", "line": 6.5, "direction": "higher", "cheatsheet_conf": 67.9, "tier": "STRONG"},
    {"player": "Royce O'Neale", "stat": "rebounds", "line": 4.5, "direction": "higher", "cheatsheet_conf": 61.3, "tier": "LEAN"},
    {"player": "Josh Giddey", "stat": "assists", "line": 7.5, "direction": "higher", "cheatsheet_conf": 60.5, "tier": "LEAN"},
    {"player": "Andrew Wiggins", "stat": "rebounds", "line": 4.5, "direction": "higher", "cheatsheet_conf": 59.1, "tier": "LEAN"},
    {"player": "Jaden Ivey", "stat": "rebounds", "line": 1.5, "direction": "higher", "cheatsheet_conf": 58.9, "tier": "LEAN"},
    {"player": "Myles Turner", "stat": "rebounds", "line": 6.5, "direction": "lower", "cheatsheet_conf": 62.3, "tier": "LEAN"},
    {"player": "Jabari Smith Jr.", "stat": "rebounds", "line": 7.5, "direction": "lower", "cheatsheet_conf": 61.8, "tier": "LEAN"},
    {"player": "Mouhamed Gueye", "stat": "rebounds", "line": 5.5, "direction": "lower", "cheatsheet_conf": 59.3, "tier": "LEAN"},
]

def find_pick(results, player, stat, line, direction):
    """Find matching pick in results."""
    for r in results:
        if (r.get('player') == player and 
            r.get('stat', '').lower() == stat.lower() and 
            abs(r.get('line', 0) - line) < 0.1 and
            r.get('direction', '').lower() == direction.lower()):
            return r
    return None

print("=" * 130)
print("  GATES COMPARISON: Your 9 Cheatsheet Picks vs Actual Analyzed Data")
print("=" * 130)

# Table header
print(f"\n{'#':<3} {'Player':<22} {'Stat':<10} {'Line':>5} {'Dir':<7} | {'Mu':>6} {'Sig':>5} | {'Model%':>7} {'Eff%':>7} | {'Sheet%':>7} {'Delta':>7} | {'Decision':<10}")
print("-" * 130)

total_model = 0
total_eff = 0
total_sheet = 0
found_count = 0
decisions = {"STRONG": 0, "LEAN": 0, "PASS": 0, "NO_PLAY": 0, "SKIP": 0, "BLOCKED": 0}

for i, cp in enumerate(CHEATSHEET_PICKS, 1):
    match = find_pick(results, cp['player'], cp['stat'], cp['line'], cp['direction'])
    
    if match:
        found_count += 1
        mu = match.get('mu', 0)
        sigma = match.get('sigma', 0)
        model_conf = match.get('model_confidence', 0)
        eff_conf = match.get('effective_confidence', 0)
        decision = match.get('decision', 'UNKNOWN')
        sheet_conf = cp['cheatsheet_conf']
        delta = eff_conf - sheet_conf
        
        total_model += model_conf
        total_eff += eff_conf
        total_sheet += sheet_conf
        decisions[decision] = decisions.get(decision, 0) + 1
        
        # Mark big differences
        delta_marker = ""
        if abs(delta) > 10:
            delta_marker = " ***"
        elif abs(delta) > 5:
            delta_marker = " *"
        
        print(f"{i:<3} {cp['player']:<22} {cp['stat']:<10} {cp['line']:>5.1f} {cp['direction']:<7} | {mu:>6.1f} {sigma:>5.1f} | {model_conf:>6.1f}% {eff_conf:>6.1f}% | {sheet_conf:>6.1f}% {delta:>+6.1f}%{delta_marker} | {decision:<10}")
    else:
        print(f"{i:<3} {cp['player']:<22} {cp['stat']:<10} {cp['line']:>5.1f} {cp['direction']:<7} | {'--':>6} {'--':>5} | {'--':>7} {'--':>7} | {cp['cheatsheet_conf']:>6.1f}% {'--':>7} | NOT FOUND")

print("-" * 130)

if found_count > 0:
    avg_model = total_model / found_count
    avg_eff = total_eff / found_count
    avg_sheet = total_sheet / found_count
    print(f"{'AVG':<3} {'':<22} {'':<10} {'':<5} {'':<7} | {'':<6} {'':<5} | {avg_model:>6.1f}% {avg_eff:>6.1f}% | {avg_sheet:>6.1f}% {avg_eff - avg_sheet:>+6.1f}% | Found: {found_count}/9")

print("\n")
print("=" * 130)
print("  DETAILED BREAKDOWN: What Each Gate Did")
print("=" * 130)

for cp in CHEATSHEET_PICKS:
    match = find_pick(results, cp['player'], cp['stat'], cp['line'], cp['direction'])
    
    print(f"\n{'='*60}")
    print(f"  {cp['player']} - {cp['stat'].upper()} {cp['direction'].upper()} {cp['line']}")
    print(f"  Cheatsheet: {cp['cheatsheet_conf']:.1f}% ({cp['tier']})")
    print(f"{'='*60}")
    
    if not match:
        print("  ** NOT FOUND IN RESULTS **")
        continue
    
    mu = match.get('mu', 0)
    sigma = match.get('sigma', 0)
    model = match.get('model_confidence', 0)
    eff = match.get('effective_confidence', 0)
    
    print(f"\n  RAW DATA:")
    print(f"    Mu (projection): {mu:.2f}")
    print(f"    Sigma (std dev): {sigma:.2f}")
    print(f"    Z-score: {match.get('z_score', 0):.2f}")
    print(f"    Sample N: {match.get('sample_n', 'N/A')}")
    
    print(f"\n  CONFIDENCE FLOW:")
    print(f"    Model Confidence:     {model:.1f}%")
    print(f"    Effective Confidence: {eff:.1f}%")
    print(f"    Cheatsheet showed:    {cp['cheatsheet_conf']:.1f}%")
    print(f"    Delta (Eff - Model):  {eff - model:+.1f}%")
    
    # Show context adjustments
    context_notes = match.get('context_notes', [])
    if context_notes:
        print(f"\n  CONTEXT ADJUSTMENTS:")
        for note in context_notes:
            print(f"    - {note}")
    
    # Show gate details
    qf = match.get('quant_framework', {})
    if qf:
        print(f"\n  QUANT FRAMEWORK GATES:")
        if qf.get('enabled'):
            print(f"    Quant Framework: ENABLED")
        if qf.get('variance_penalty'):
            vp = qf['variance_penalty']
            print(f"    Variance Penalty: CV={vp.get('cv', 0):.3f}, multiplier={vp.get('total_penalty', 1):.3f}")
        if qf.get('edge_gate'):
            eg = qf['edge_gate']
            status = "PASS" if eg.get('passes_gate', True) else "FAIL"
            print(f"    Edge Gate: {eg.get('edge_percent', 0):.1f}% edge ({status})")
        if qf.get('multi_window_projection'):
            mw = qf['multi_window_projection']
            print(f"    Multi-Window: L5={mw.get('L5')}, L10={mw.get('L10')}, weighted={mw.get('weighted_projection')}")
    
    # Show hybrid confidence
    hc = match.get('hybrid_confidence', {})
    if hc:
        print(f"\n  HYBRID CONFIDENCE SYSTEM:")
        print(f"    Raw Probability: {hc.get('raw_probability', 0):.1f}%")
        print(f"    Effective Probability: {hc.get('effective_probability', 0):.1f}%")
        print(f"    Stat/Dir Multiplier: {hc.get('stat_direction_multiplier', 1):.2f}")
        print(f"    Sample Size Multiplier: {hc.get('sample_size_multiplier', 1):.2f}")
        print(f"    Hybrid Tier: {hc.get('tier', 'N/A')}")
    
    # Data driven adjustments
    dda = match.get('data_driven_adjustments', {})
    if dda:
        print(f"\n  DATA-DRIVEN ADJUSTMENTS:")
        for key, val in dda.items():
            print(f"    {key}: multiplier={val.get('multiplier', 1):.2f}")
    
    print(f"\n  FINAL DECISION: {match.get('decision', 'UNKNOWN')}")

print("\n\n")
print("=" * 130)
print("  SUMMARY: Decisions Distribution")
print("=" * 130)
print(f"\n  STRONG: {decisions.get('STRONG', 0)}")
print(f"  LEAN:   {decisions.get('LEAN', 0)}")
print(f"  PASS:   {decisions.get('PASS', 0)}")
print(f"  NO_PLAY: {decisions.get('NO_PLAY', 0)}")
print(f"  SKIP:   {decisions.get('SKIP', 0)}")
print(f"  BLOCKED: {decisions.get('BLOCKED', 0)}")

print("\n" + "=" * 130)
print("  KEY INSIGHTS")
print("=" * 130)
print("""
  The cheatsheet values come from a DIFFERENT confidence calculation than what's
  stored in the JSON. This could be due to:
  
  1. POST-PROCESSING: Cheatsheet generator may apply additional transformations
  2. TIER CORRECTION: Note "14 tier labels were corrected" in cheatsheet footer
  3. RENDERING LOGIC: Cheatsheet may use different display logic
  
  To understand the GATES ON vs OFF difference, we need to:
  1. Run fresh analysis with penalty_mode.json settings toggled
  2. Compare the SAME picks through BOTH configurations
  3. This test shows what the CURRENT configuration produces
""")
