"""
Load actual analyzed picks from the JSON file and compare gates impact
"""
import json

# Load the actual analyzed data - THURDAYNBA100 has our target players
with open('outputs/THURDAYNBA100_RISK_FIRST_20260129_FROM_UD.json') as f:
    data = json.load(f)

# Data is a dict with categories: results contains all picks
all_picks = data.get('results', [])
print(f"Total picks in results: {len(all_picks)}")
print(f"Categories: strong={data.get('strong',0)}, lean={data.get('lean',0)}, no_play={data.get('no_play',0)}")
print()

# Find our 9 target picks from the cheatsheet
targets = [
    'Isaiah Hartenstein', 'Jalen Johnson', "Royce O'Neale", 'Josh Giddey', 
    'Andrew Wiggins', 'Jaden Ivey', 'Myles Turner', 'Jabari Smith Jr.', 'Mouhamed Gueye'
]

found_picks = []
for pick in all_picks:
    player = pick.get('player', '')
    if player in targets:
        found_picks.append(pick)
        
print(f"Found {len(found_picks)} of 9 target picks\n")

# Display detailed info for each
print("="*130)
print(f"{'Player':<25} {'Stat':<12} {'Line':>6} {'Dir':<7} {'Mu':>7} {'Sig':>6} {'Model%':>8} {'Eff%':>8} {'Decision':<10} {'Hybrid':<8}")
print("-"*130)

for p in found_picks:
    player = p.get('player', '')[:24]
    stat = p.get('stat', '')[:11]
    line = p.get('line', 0)
    direction = p.get('direction', '')[:6]
    mu = p.get('mu', 0)
    sigma = p.get('sigma', 0)
    model_conf = p.get('model_confidence', 0)
    eff_conf = p.get('effective_confidence', 0)
    decision = p.get('decision', '')
    hybrid_tier = p.get('hybrid_tier', '')
    
    print(f"{player:<25} {stat:<12} {line:>6.1f} {direction:<7} {mu:>7.1f} {sigma:>6.1f} {model_conf:>7.1f}% {eff_conf:>7.1f}% {decision:<10} {hybrid_tier:<8}")

print()
print("="*130)
print("GATE DETAILS FOR EACH PICK:")
print("="*120)

for p in found_picks:
    print(f"\n📊 {p.get('player')} - {p.get('stat').upper()} {p.get('direction').upper()} {p.get('line')}")
    
    # Quant framework details
    qf = p.get('quant_framework', {})
    if qf:
        if qf.get('variance_penalty'):
            vp = qf['variance_penalty']
            print(f"   ⚡ VARIANCE: CV={vp.get('cv', 0):.3f}, penalty={vp.get('total_penalty', 1):.3f}")
        if qf.get('edge_gate'):
            eg = qf['edge_gate']
            status = "✅ PASS" if eg.get('passes_gate', True) else "❌ FAIL"
            print(f"   ⚡ EDGE GATE: {eg.get('edge_percent', 0):.1f}% edge, EV={eg.get('ev_percent', 0):.1f}% {status}")
        if qf.get('multi_window_projection'):
            mw = qf['multi_window_projection']
            print(f"   📊 MULTI-WINDOW: L5={mw.get('L5')}, L10={mw.get('L10')}, weighted={mw.get('weighted_projection')}")
    
    # Hybrid confidence
    hc = p.get('hybrid_confidence', {})
    if hc:
        print(f"   📈 HYBRID: raw={hc.get('raw_probability', 0):.1f}%, eff={hc.get('effective_probability', 0):.1f}%, tier={hc.get('tier')}")
        print(f"      Stat mult={hc.get('stat_direction_multiplier', 1):.2f}, Sample mult={hc.get('sample_size_multiplier', 1):.2f}")
    
    # Context notes
    notes = p.get('context_notes', [])
    if notes:
        for note in notes[:3]:
            print(f"   💬 {note}")
    
    # Data driven adjustments
    dda = p.get('data_driven_adjustments', {})
    if dda:
        print(f"   📊 DATA-DRIVEN: {list(dda.keys())}")

# Summary stats
print("\n" + "="*120)
print("SUMMARY STATISTICS:")
print("="*120)
model_confs = [p.get('model_confidence', 0) for p in found_picks]
eff_confs = [p.get('effective_confidence', 0) for p in found_picks]

print(f"Model Confidence: min={min(model_confs):.1f}%, max={max(model_confs):.1f}%, avg={sum(model_confs)/len(model_confs):.1f}%")
print(f"Effective Confidence: min={min(eff_confs):.1f}%, max={max(eff_confs):.1f}%, avg={sum(eff_confs)/len(eff_confs):.1f}%")

# Count decisions
decisions = {}
for p in found_picks:
    d = p.get('decision', 'UNKNOWN')
    decisions[d] = decisions.get(d, 0) + 1
print(f"Decisions: {decisions}")
