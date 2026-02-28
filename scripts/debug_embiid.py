"""Debug why Embiid was rejected when he crushed it"""
import json

f = open('outputs/THUREND_RISK_FIRST_20260129_FROM_UD.json')
d = json.load(f)

# Find Embiid
for r in d['results']:
    if 'embiid' in r.get('player', '').lower() and r.get('stat') == 'points':
        print('=== JOEL EMBIID POINTS ANALYSIS ===')
        print(f"Player: {r.get('player')}")
        print(f"Line: {r.get('line')}")
        print(f"Direction: {r.get('direction')}")
        print(f"Status: {r.get('status')}")
        print(f"Confidence: {r.get('status_confidence', 0):.1f}%")
        print()
        print('=== THE PREDICTION ===')
        print(f"Mu (predicted avg): {r.get('mu', 0):.1f}")
        print(f"Sigma (std dev): {r.get('sigma', 0):.1f}")
        print(f"Z-score: {r.get('z_score', 0):.2f}")
        print(f"Edge %: {r.get('edge_percent', 0):.1f}%")
        print()
        print('=== CONTEXT NOTES ===')
        for note in r.get('context_notes', []):
            print(f"  {note}")
        print()
        print('=== GATE DETAILS ===')
        for gate in r.get('gate_details', []):
            print(f"  {gate.get('gate')}: {gate.get('reason')}")
        print()
        print('=== PENALTIES APPLIED ===')
        diag = r.get('edge_diagnostics', {}).get('penalties', {})
        for k, v in diag.items():
            print(f"  {k}: {v}")
        print()
        print('=== QUANT FRAMEWORK ===')
        qf = r.get('quant_framework', {})
        print(f"Edge gate passed: {qf.get('edge_gate_passed')}")
        eg = qf.get('edge_gate', {})
        print(f"Edge pct: {eg.get('edge_percent', 0):.1f}")
        print(f"Required edge: {eg.get('required_edge', 0):.1f}")
        print(f"Tier recommendation: {eg.get('tier_recommendation')}")
        break

print()
print('=' * 60)
print('=== STAR SCORERS BLOCKED (mu > line but NO_PLAY) ===')
print('=' * 60)

stars = []
for r in d['results']:
    if r.get('stat') != 'points':
        continue
    if r.get('direction') != 'higher':
        continue
    
    mu = r.get('mu', 0)
    line = r.get('line', 0)
    status = r.get('status', '')
    conf = r.get('status_confidence', 0)
    raw = r.get('edge_diagnostics', {}).get('penalties', {}).get('raw_probability', 0)
    
    # If predicted avg is above line, should be favorable for OVER
    if mu > line and status == 'NO_PLAY':
        edge = ((mu - line) / line) * 100
        stars.append({
            'player': r.get('player'),
            'line': line,
            'mu': mu,
            'edge_vs_line': edge,
            'raw_prob': raw,
            'final_prob': conf,
            'penalty': raw - conf if raw else 0
        })

stars.sort(key=lambda x: x['edge_vs_line'], reverse=True)
for s in stars[:15]:
    print(f"{s['player']}: Line {s['line']}, Predicted {s['mu']:.1f} (+{s['edge_vs_line']:.1f}pct edge)")
    print(f"   Raw: {s['raw_prob']:.0f}pct -> Final: {s['final_prob']:.0f}pct (PENALIZED {s['penalty']:.0f}pct)")
    print()
