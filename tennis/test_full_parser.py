"""Test full slate parsing"""
from tennis_props_parser import parse_tennis_props, analyze_tennis_props

with open("test_full_slates.txt") as f:
    paste = f.read()

props = parse_tennis_props(paste)
print(f"✅ Parsed {len(props)} props from verbose format\n")

for p in props:
    print(f"{p.player} | {p.stat} {p.line} | vs {p.opponent}")

print("\n" + "="*70)
print("RUNNING ANALYSIS ENGINE")
print("="*70 + "\n")

report = analyze_tennis_props(props, save=False)
print(report)
