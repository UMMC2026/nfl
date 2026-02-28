"""Check what probability method was used for each pick."""
import json

with open('outputs/THURDAYNBA100_RISK_FIRST_20260129_FROM_UD.json') as f:
    data = json.load(f)

targets = [
    ('Isaiah Hartenstein', 'rebounds', 6.5, 'higher'),
    ('Jalen Johnson', 'assists', 6.5, 'higher'),
    ("Royce O'Neale", 'rebounds', 4.5, 'higher'),
    ('Josh Giddey', 'assists', 7.5, 'higher'),
    ('Andrew Wiggins', 'rebounds', 4.5, 'higher'),
    ('Myles Turner', 'rebounds', 6.5, 'lower'),
    ('Jabari Smith Jr.', 'rebounds', 7.5, 'lower'),
]

print("=" * 100)
print("PROBABILITY METHOD ANALYSIS")
print("=" * 100)

for t in targets:
    for r in data.get('results', []):
        if (r.get('player') == t[0] and 
            r.get('stat', '').lower() == t[1].lower() and
            abs(r.get('line', 0) - t[2]) < 0.1 and
            r.get('direction', '').lower() == t[3].lower()):
            
            print(f"\n{t[0]} - {t[1]} {t[3]} {t[2]}")
            print(f"  mu={r.get('mu', 0):.2f}, sigma={r.get('sigma', 0):.2f}")
            print(f"  model_confidence: {r.get('model_confidence', 0):.1f}%")
            print(f"  effective_confidence: {r.get('effective_confidence', 0):.1f}%")
            
            # Check prob method
            prob_method = r.get('prob_method', 'N/A')
            print(f"  prob_method: {prob_method}")
            
            prob_details = r.get('prob_method_details', {})
            if prob_details:
                print(f"  prob_details:")
                for k, v in prob_details.items():
                    print(f"    {k}: {v}")
            
            # Check for empirical hit rate
            sample_n = r.get('sample_n', 0)
            print(f"  sample_n: {sample_n}")
            break
