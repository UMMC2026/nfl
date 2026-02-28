"""Test parser with both slate formats"""
from tennis_props_parser import parse_tennis_props

# Format 1: Compact (from your second paste)
format1 = """athlete or team avatar
Tomas Machac
Machac vs Musetti - 5:30PM CST


8.5
Aces

Higher
0.96x
athlete or team avatar
Karen Khachanov
Darderi vs Khachanov - 5:30PM CST


18.5
Aces

Higher
0.98x"""

# Format 2: Verbose (from your first paste)
format2 = """Tomas MachacGoblin
Tomas Machac - Player
Tomas Machac
@ Lorenzo Musetti Fri 5:30pm

7.5
Aces
More

Lorenzo MusettiGoblin
Lorenzo Musetti - Player
Lorenzo Musetti
vs Tomas Machac Fri 5:30pm

6.5
Aces
More"""

print("=" * 70)
print("TESTING FORMAT 1 (COMPACT)")
print("=" * 70)
props1 = parse_tennis_props(format1)
print(f"Parsed {len(props1)} props from format 1\n")
for p in props1:
    print(f"{p.player} vs {p.opponent}")
    print(f"  {p.stat} {p.line}")
    print(f"  Higher: {p.higher_mult}x" if p.higher_mult else "  No multiplier")
    print()

print("\n" + "=" * 70)
print("TESTING FORMAT 2 (VERBOSE)")
print("=" * 70)
props2 = parse_tennis_props(format2)
print(f"Parsed {len(props2)} props from format 2\n")
for p in props2:
    print(f"{p.player} vs {p.opponent}")
    print(f"  {p.stat} {p.line}")
    print(f"  Match: {p.match_info}")
    print()

print("=" * 70)
print(f"TOTAL SUCCESS: {len(props1) + len(props2)} props parsed")
print("=" * 70)
