"""
NFL SYSTEM FIX SCRIPT
Fixes flat probability issue and unfreezes system for Super Bowl
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def unfreeze_nfl_system():
    """Remove VERSION.lock freeze to allow new predictions."""
    
    version_lock = PROJECT_ROOT / "VERSION.lock"
    
    if not version_lock.exists():
        print("[OK] System not frozen (VERSION.lock not found)")
        return True
    
    print("[FIX] Unfreezing NFL system...")
    
    try:
        # Read current content
        with open(version_lock, 'r') as f:
            content = f.read()
        
        # Modify to ACTIVE status
        new_content = content.replace("STATUS: FROZEN", "STATUS: ACTIVE")
        new_content = new_content.replace("EXECUTION_MODE: MANUAL", "EXECUTION_MODE: INTERACTIVE")
        
        # Write back
        with open(version_lock, 'w') as f:
            f.write(new_content)
        
        print("[OK] System unfrozen - VERSION.lock updated")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to unfreeze: {e}")
        return False


def fix_confidence_caps():
    """Update analyze_nfl_props.py to remove flat 55% caps."""
    
    analyzer_file = PROJECT_ROOT / "analyze_nfl_props.py"
    
    if not analyzer_file.exists():
        print("[SKIP] analyze_nfl_props.py not found")
        return False
    
    print("[FIX] Updating confidence caps in analyzer...")
    
    try:
        with open(analyzer_file, 'r') as f:
            content = f.read()
        
        # Find and update the caps section
        old_caps = '''    # Determine cap based on stat
    if "td" in stat.lower():
        max_conf = caps.get("touchdown", 0.55)
    elif stat.lower() in ["pass_yds", "rush_yds", "rec_yds", "receptions"]:
        max_conf = caps.get("core", 0.70)
    else:
        max_conf = caps.get("alt", 0.65)'''
        
        new_caps = '''    # Determine cap based on stat (UPDATED FOR SUPER BOWL)
    if "td" in stat.lower():
        max_conf = caps.get("touchdown", 0.75)  # Increased from 0.55
    elif stat.lower() in ["pass_yds", "rush_yds", "rec_yds", "receptions"]:
        max_conf = caps.get("core", 0.85)  # Increased from 0.70
    else:
        max_conf = caps.get("alt", 0.80)  # Increased from 0.65'''
        
        if old_caps in content:
            content = content.replace(old_caps, new_caps)
            
            with open(analyzer_file, 'w') as f:
                f.write(content)
            
            print("[OK] Confidence caps updated:")
            print("     - Touchdowns: 0.55 -> 0.75")
            print("     - Core stats: 0.70 -> 0.85")
            print("     - Alt stats: 0.65 -> 0.80")
            return True
        else:
            print("[WARNING] Could not find caps section to update")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to update caps: {e}")
        return False


def add_tier_logic():
    """Add missing tier assignment logic to analyzer."""
    
    analyzer_file = PROJECT_ROOT / "analyze_nfl_props.py"
    
    print("[FIX] Adding tier assignment logic...")
    
    try:
        with open(analyzer_file, 'r') as f:
            content = f.read()
        
        # Check if tier logic exists
        if "def assign_tier(" in content or "tier = " in content:
            print("[OK] Tier logic already exists")
            return True
        
        # Add tier assignment after probability calculation
        tier_function = '''
def assign_tier(probability: float) -> str:
    """Assign confidence tier based on probability."""
    if probability >= 0.80:
        return "SLAM"
    elif probability >= 0.70:
        return "STRONG"
    elif probability >= 0.58:
        return "LEAN"
    else:
        return "NO_PLAY"
'''
        
        # Insert after imports
        import_end = content.find('\n\n', content.find('import'))
        if import_end > 0:
            content = content[:import_end] + tier_function + content[import_end:]
            
            with open(analyzer_file, 'w') as f:
                f.write(content)
            
            print("[OK] Tier assignment logic added")
            return True
        else:
            print("[WARNING] Could not find insertion point")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to add tier logic: {e}")
        return False


def create_superbowl_config():
    """Create Super Bowl specific configuration."""
    
    config_file = PROJECT_ROOT / "config" / "nfl_superbowl.json"
    config_file.parent.mkdir(exist_ok=True)
    
    print("[FIX] Creating Super Bowl configuration...")
    
    import json
    
    config = {
        "event": "Super Bowl LIX",
        "date": "2026-02-09",
        "location": "Caesars Superdome, New Orleans",
        "venue_type": "dome",
        "weather_impact": False,
        
        "confidence_boosts": {
            "playoff_experience": 0.03,
            "super_bowl_experience": 0.05,
            "prime_time_player": 0.02
        },
        
        "confidence_penalties": {
            "first_super_bowl": 0.03,
            "injury_uncertain": 0.10,
            "backup_player": 0.15
        },
        
        "simulation_adjustments": {
            "iterations": 20000,
            "variance_multiplier": 1.2,
            "use_playoff_stats": True,
            "playoff_games_weight": 2.0
        },
        
        "tier_thresholds": {
            "SLAM": 0.80,
            "STRONG": 0.70,
            "LEAN": 0.58,
            "min_edge": 0.03
        }
    }
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, indent=2, fp=f)
        
        print(f"[OK] Config created: {config_file}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to create config: {e}")
        return False


def main():
    """Run all fixes."""
    
    print("\n" + "=" * 80)
    print("NFL SYSTEM FIX SCRIPT - SUPER BOWL LIX PREPARATION")
    print("=" * 80 + "\n")
    
    fixes = [
        ("Unfreeze system", unfreeze_nfl_system),
        ("Update confidence caps", fix_confidence_caps),
        ("Add tier logic", add_tier_logic),
        ("Create Super Bowl config", create_superbowl_config),
    ]
    
    results = []
    for name, func in fixes:
        try:
            success = func()
            results.append((name, success))
        except Exception as e:
            print(f"[ERROR] {name} failed: {e}")
            results.append((name, False))
        print()
    
    # Summary
    print("=" * 80)
    print("FIX SUMMARY")
    print("=" * 80)
    
    for name, success in results:
        status = "[OK]" if success else "[FAILED]"
        print(f"{status:8s} {name}")
    
    successful = sum(1 for _, s in results if s)
    print(f"\n{successful}/{len(results)} fixes applied successfully")
    
    if successful == len(results):
        print("\n[SUCCESS] NFL system ready for Super Bowl analysis")
        print("\nNext steps:")
        print("1. Run NFL diagnostic: python scripts/diagnose_nfl_system.py")
        print("2. Ingest Super Bowl lines: python nfl_menu.py -> [1]")
        print("3. Analyze slate: python nfl_menu.py -> [2]")
    else:
        print("\n[WARNING] Some fixes failed - manual intervention may be needed")
    
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
