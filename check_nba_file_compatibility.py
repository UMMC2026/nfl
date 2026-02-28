"""
Quick utility to check which RISK_FIRST files have NBA Role Layer data.
Shows compatible vs incompatible files for NBA Role Layer filter.
"""

import json
from pathlib import Path
from datetime import datetime

def check_file(file_path):
    """Check if file has NBA Role Layer data."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        picks = data.get("results", [])
        with_archetype = sum(1 for p in picks if p.get("nba_role_archetype"))
        with_specialist = sum(1 for p in picks if p.get("nba_specialist_flags"))
        
        return {
            "file": file_path.name,
            "modified": datetime.fromtimestamp(file_path.stat().st_mtime),
            "total_picks": len(picks),
            "with_archetype": with_archetype,
            "with_specialist": with_specialist,
            "compatible": with_archetype > 0
        }
    except Exception as e:
        return None

def main():
    print("="*80)
    print("NBA ROLE LAYER FILE COMPATIBILITY CHECKER")
    print("="*80)
    
    outputs_dir = Path("outputs")
    risk_files = sorted(outputs_dir.glob("*RISK_FIRST*.json"), 
                       key=lambda p: p.stat().st_mtime, 
                       reverse=True)
    
    if not risk_files:
        print("\n❌ No RISK_FIRST files found in outputs/")
        return
    
    print(f"\nFound {len(risk_files)} RISK_FIRST files\n")
    
    compatible = []
    incompatible = []
    
    for file_path in risk_files:
        result = check_file(file_path)
        if result:
            if result["compatible"]:
                compatible.append(result)
            else:
                incompatible.append(result)
    
    # Show compatible files
    if compatible:
        print("✅ COMPATIBLE FILES (WITH NBA Role Layer):")
        print("-" * 80)
        for r in compatible:
            specialist_info = f"({r['with_specialist']} specialist)" if r['with_specialist'] > 0 else "(no specialist data)"
            print(f"  ✓ {r['file']}")
            print(f"    Modified: {r['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    NBA Data: {r['with_archetype']}/{r['total_picks']} picks {specialist_info}")
            print()
    
    # Show incompatible files
    if incompatible:
        print("\n❌ INCOMPATIBLE FILES (NO NBA Role Layer):")
        print("-" * 80)
        for r in incompatible:
            print(f"  ✗ {r['file']}")
            print(f"    Modified: {r['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    Total picks: {r['total_picks']} (no NBA archetype data)")
            print()
    
    print("="*80)
    print(f"SUMMARY: {len(compatible)} compatible, {len(incompatible)} incompatible")
    print("="*80)
    
    if incompatible:
        print("\n💡 TIP: Re-run analysis (Menu → [2]) to regenerate incompatible files")
        print("   with NBA Role Layer data (archetypes + specialist flags)")
    
    print("\n📅 NBA Role Layer was added: January 26, 2026 13:30")
    print("   Files before this timestamp lack archetype/specialist data\n")

if __name__ == "__main__":
    main()
