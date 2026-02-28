import sys
from pathlib import Path

# Setup paths exactly like menu.py does
PROJECT_ROOT = Path(__file__).parent
TENNIS_DIR = PROJECT_ROOT / "tennis"

print(f"PROJECT_ROOT: {PROJECT_ROOT}")
print(f"TENNIS_DIR: {TENNIS_DIR}")

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TENNIS_DIR))

print(f"\nsys.path includes:")
for p in sys.path[:5]:
    print(f"  {p}")

try:
    print("\nTrying to import config.thresholds...")
    from config.thresholds import get_all_thresholds
    print("✓ SUCCESS: config.thresholds imported")
    
    print("\nTrying to import tennis.tennis_main...")
    from tennis.tennis_main import show_menu
    print("✓ SUCCESS: tennis.tennis_main imported")
    
except ImportError as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()
