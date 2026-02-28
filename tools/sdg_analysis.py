#!/usr/bin/env python3
"""
SDG Analysis Tool - Analyze Stat Deviation Gate results from analysis JSON
"""
import json
import sys
from pathlib import Path

def analyze_sdg(json_path: str):
    """Analyze SDG results from an analysis JSON file."""
    with open(json_path) as f:
        data = json.load(f)
    
    results = data.get('results', [])
    print(f"Total picks analyzed: {len(results)}")
    print()
    
    # Count by penalty level
    counts = {'PASS': 0, 'MEDIUM': 0, 'HEAVY': 0, 'missing': 0}
    heavy_picks = []
    medium_picks = []
    pass_picks = []
    
    for r in results:
        sdg = r.get('sdg_result', {})
        if isinstance(sdg, dict):
            level = sdg.get('penalty_level', 'missing')
            z = sdg.get('z_stat', 0)
            mult = sdg.get('multiplier', 1.0)
            mu = sdg.get('mu', 0)
            sigma = sdg.get('sigma', 1)
        else:
            level = 'missing'
            z = 0
            mult = 1.0
            mu = r.get('mu', 0)
            sigma = r.get('sigma', 1)
        
        if level == 'none':
            level = 'PASS'
        
        counts[level] = counts.get(level, 0) + 1
        
        pick_info = {
            'player': r.get('player', '?'),
            'stat': r.get('stat', '?'),
            'line': r.get('line', '?'),
            'direction': r.get('direction', '?'),
            'z': z,
            'mult': mult,
            'conf': r.get('confidence', 0) or 0,
            'mu': mu,
            'sigma': sigma
        }
        
        if level == 'HEAVY':
            heavy_picks.append(pick_info)
        elif level == 'MEDIUM':
            medium_picks.append(pick_info)
        elif level == 'PASS':
            pass_picks.append(pick_info)
    
    print("=" * 70)
    print("SDG PENALTY BREAKDOWN")
    print("=" * 70)
    print(f"PASS (|z| >= 0.5):    {counts.get('PASS', 0):4d} picks - NO penalty (line far from mean)")
    print(f"MEDIUM (|z| < 0.5):   {counts.get('MEDIUM', 0):4d} picks - 0.85x penalty (borderline)")
    print(f"HEAVY (|z| < 0.25):   {counts.get('HEAVY', 0):4d} picks - 0.70x penalty (COIN FLIP)")
    print(f"Missing SDG:          {counts.get('missing', 0):4d} picks")
    print()
    
    if heavy_picks:
        print("=" * 70)
        print("HEAVY PENALIZED (COIN FLIPS - AVOID THESE)")
        print("=" * 70)
        # Sort by confidence descending
        heavy_picks.sort(key=lambda x: x['conf'], reverse=True)
        for p in heavy_picks[:25]:
            print(f"  {p['player']:20s} {p['stat']:10s} {p['direction']:6s} {p['line']:5} | z={p['z']:+.2f} | conf={p['conf']:.1f}%")
        if len(heavy_picks) > 25:
            print(f"  ... and {len(heavy_picks) - 25} more")
        print()
    
    if medium_picks:
        print("=" * 70)
        print("MEDIUM PENALIZED (borderline - proceed with caution)")
        print("=" * 70)
        medium_picks.sort(key=lambda x: x['conf'], reverse=True)
        for p in medium_picks[:15]:
            print(f"  {p['player']:20s} {p['stat']:10s} {p['direction']:6s} {p['line']:5} | z={p['z']:+.2f} | conf={p['conf']:.1f}%")
        if len(medium_picks) > 15:
            print(f"  ... and {len(medium_picks) - 15} more")
        print()
    
    # Show best PASS picks (good edges)
    print("=" * 70)
    print("BEST PICKS THAT PASSED SDG (good deviation from mean)")
    print("=" * 70)
    pass_good = [p for p in pass_picks if p['conf'] >= 60]
    pass_good.sort(key=lambda x: x['conf'], reverse=True)
    for p in pass_good[:20]:
        print(f"  {p['player']:20s} {p['stat']:10s} {p['direction']:6s} {p['line']:5} | z={p['z']:+.2f} | conf={p['conf']:.1f}%")
    print()

if __name__ == "__main__":
    # Find latest analysis file
    outputs_dir = Path("outputs")
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        # Find most recent RISK_FIRST file
        files = list(outputs_dir.glob("*RISK_FIRST*FROM_UD.json"))
        if not files:
            print("No analysis files found!")
            sys.exit(1)
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        json_path = files[0]
        print(f"Analyzing: {json_path.name}")
        print()
    
    analyze_sdg(str(json_path))
