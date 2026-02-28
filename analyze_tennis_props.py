"""
Tennis Props Analyzer - Standalone script
Just run and paste your Underdog props!
"""
import sys
sys.path.insert(0, r"C:\Users\hiday\UNDERDOG ANANLYSIS")

from tennis.tennis_props_parser import parse_tennis_props, analyze_tennis_props

print("=" * 65)
print("  TENNIS PROPS ANALYZER")
print("=" * 65)
print()
print("Paste your Underdog tennis props below.")
print("Type 'done' on a new line when finished.")
print()

lines = []
while True:
    try:
        line = input()
        if line.strip().lower() == 'done':
            break
        lines.append(line)
    except EOFError:
        break

if lines:
    paste = '\n'.join(lines)
    props = parse_tennis_props(paste)
    print(f"\n✓ Parsed {len(props)} props")
    if props:
        print(analyze_tennis_props(props))
    else:
        print("✗ No valid props found")
else:
    print("No input received")

input("\nPress Enter to exit...")
