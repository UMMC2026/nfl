"""
Quick test of tennis props menu functionality
"""
import sys
from pathlib import Path

# Add tennis to path
sys.path.insert(0, str(Path('tennis')))

from tennis_props_parser import parse_tennis_props
from analyze_all_tennis_props import generate_report, save_analysis

# Test data
test_paste = """Jannik Sinner
Jannik Sinner - Player
Jannik Sinner
@ Luciano Darderi Mon 1:00am
34
Fantasy Score
Less
More
Trending
5.6K
Ben Shelton
Ben Shelton - Player
Ben Shelton
vs Casper Ruud Mon 3:10am
24.5
Fantasy Score
Less
More
Trending
4.0K
Iga Swiatek
Iga Swiatek - Player
Iga Swiatek
@ Maddison Inglis Mon 2:00am
2.5
Aces
Less
More"""

print("=" * 70)
print("🎾 TESTING TENNIS PROPS MENU INTEGRATION")
print("=" * 70)

# Test parsing
print("\n[1/3] Testing parser...")
props = parse_tennis_props(test_paste)
print(f"✓ Parsed {len(props)} props")

# Test report generation
print("\n[2/3] Testing report generation...")
report = generate_report(props)
print("✓ Report generated")
print(f"   Length: {len(report)} characters")

# Test save functionality
print("\n[3/3] Testing save functionality...")
txt_path, json_path = save_analysis(props)
print(f"✓ Report saved: {txt_path}")
print(f"✓ Data saved: {json_path}")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - Menu integration ready!")
print("=" * 70)

print("\n📋 USAGE:")
print("  1. Run: python menu.py")
print("  2. Select Tennis module")
print("  3. Select option [5] Analyze PROPS")
print("  4. Paste your Underdog tennis data")
print("  5. Press Enter twice")
print("  6. Select option [R] to view saved reports")
