"""
Tennis Calibration Tracking Integration
=========================================
Saves Tennis picks to unified calibration system for accuracy monitoring.

Pattern: Copied from Soccer implementation (proven working)
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def save_picks_to_calibration(results: dict, slate_date: str = None) -> int:
    """
    Save analyzed Tennis picks to unified calibration tracker.
    
    Args:
        results: Results dict from calibrated_props_engine.analyze_slate()
                 Expected structure: {'tiers': {'SLAM': [...], 'STRONG': [...], 'LEAN': [...]}}
        slate_date: Optional date override (defaults to today)
    
    Returns:
        Number of picks saved
    """
    try:
        from calibration.unified_tracker import UnifiedCalibration, CalibrationPick
        
        tracker = UnifiedCalibration()
        date_str = slate_date or datetime.now().strftime("%Y-%m-%d")
        saved = 0
        
        # Extract picks from tiers
        for tier_name, tier_edges in results.get('tiers', {}).items():
            # Only track actionable tiers
            if tier_name not in ['SLAM', 'STRONG', 'LEAN']:
                continue
            
            for edge in tier_edges:
                player = edge.get('player', '').strip()
                stat = edge.get('stat', '').strip()
                line = edge.get('line', 0)
                direction = edge.get('direction', '').capitalize()  # higher → Higher
                prob = edge.get('probability', edge.get('confidence', 0))
                
                # Normalize probability to 0-100 scale
                if prob <= 1:
                    prob *= 100
                
                # Generate unique pick ID
                pick_id = f"tennis_{date_str}_{player}_{stat}_{line}_{direction}".replace(" ", "_")
                
                # Check if already exists
                existing = [p for p in tracker.picks if p.pick_id == pick_id]
                if existing:
                    continue
                
                pick = CalibrationPick(
                    pick_id=pick_id,
                    date=date_str,
                    sport="tennis",
                    player=player,
                    stat=stat,
                    line=line,
                    direction=direction,
                    probability=prob,
                    tier=tier_name,
                    team="N/A",          # Tennis has no teams
                    opponent="TBD",      # Would need match context
                    model_version="calibrated_props_v1"
                )
                
                tracker.add_pick(pick)
                saved += 1
        
        if saved > 0:
            print(f"\n📊 Calibration: Saved {saved} Tennis picks for tracking")
        
        return saved
        
    except ImportError as e:
        print(f"   ⚠️ Calibration module not available: {e}")
        return 0
    except Exception as e:
        print(f"   ⚠️ Calibration save failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def resolve_tennis_results():
    """
    Interactive result resolution for Tennis picks.
    
    TODO: Implement when needed. For now, manual resolution via:
      1. Check calibration_history.csv for tennis picks
      2. Look up match stats manually
      3. Update actual_value and outcome columns
    """
    print("\n⚠️ Tennis result resolution not yet implemented")
    print("   Manual process:")
    print("   1. Open calibration_history.csv")
    print("   2. Find tennis picks (sport=tennis)")
    print("   3. Look up match stats from Tennis Abstract or ATP/WTA")
    print("   4. Fill in actual_value and outcome columns")
    print("   5. Run: python -m calibration.unified_tracker --report --sport tennis")
    return 0
