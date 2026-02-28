"""Quick check of confidence values in JSON."""
import json

with open('outputs/THURDAYNBA100_RISK_FIRST_20260129_FROM_UD.json') as f:
    data = json.load(f)

targets = [
    ('Isaiah Hartenstein', 'rebounds', 6.5, 'higher'),
    ('Jalen Johnson', 'assists', 6.5, 'higher'),
    ("Royce O'Neale", 'rebounds', 4.5, 'higher'),
]

for t in targets:
    for r in data.get('results', []):
        if (r.get('player') == t[0] and 
            r.get('stat', '').lower() == t[1].lower() and
            abs(r.get('line', 0) - t[2]) < 0.1 and
            r.get('direction', '').lower() == t[3].lower()):
            print(f"{t[0]} {t[1]}:")
            print(f"  model_confidence: {r.get('model_confidence', 'N/A')}")
            print(f"  effective_confidence: {r.get('effective_confidence', 'N/A')}")
            hc = r.get('hybrid_confidence', {})
            if hc:
                print(f"  hybrid raw_prob: {hc.get('raw_probability', 'N/A')}")
                print(f"  hybrid eff_prob: {hc.get('effective_probability', 'N/A')}")
            print(f"  mu: {r.get('mu', 'N/A')}, sigma: {r.get('sigma', 'N/A')}")
            print()
            break
