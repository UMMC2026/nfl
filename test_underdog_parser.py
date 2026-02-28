"""
Test the Underdog parser with the exact paste format
"""
from slate_menu import SlateManager

# Exact paste from user
paste_text = """Ryan RollinsDemon
MIL - G
Ryan Rollins     
@ ATL Mon 12:10pm

5.5
Rebounds
More
Trending
13.1K
Giannis Antetokounmpo
MIL - F
Giannis Antetokounmpo
@ ATL Mon 12:10pm
30.5
Points
Less
More
Trending
10.2K
Jalen Johnson
ATL - F
Jalen Johnson
vs MIL Mon 12:10pm
38.5
PRA
Less
More
Trending
6.4K
Jalen Johnson
ATL - F
Jalen Johnson
vs MIL Mon 12:10pm
21.5
Points
Less
More
Trending
5.7K
Kevin Porter
MIL - G-F
Kevin Porter
@ ATL Mon 12:10pm
28.5
PRA
Less
More
Trending
5.3K
Giannis Antetokounmpo
MIL - F
Giannis Antetokounmpo
@ ATL Mon 12:10pm
46.5
PRA
Less
More
Trending
5.0K
Kyle Kuzma
MIL - F
Kyle Kuzma
@ ATL Mon 12:10pm
9.5
Points
Less
More
Trending
4.8K
Bobby Portis
MIL - F
Bobby Portis
@ ATL Mon 12:10pm
11.5
Points
Less
More
Trending
4.6K
Jalen Johnson
ATL - F
Jalen Johnson
vs MIL Mon 12:10pm
7.5
Assists
Less
More
Trending
4.4K
Bobby Portis
MIL - F
Bobby Portis
@ ATL Mon 12:10pm
12.5
Pts+Asts
Less
More
Trending
4.3K
Nickeil Alexander-Walker
ATL - G
Nickeil Alexander-Walker
vs MIL Mon 12:10pm
19.5
Points
Less
More
Trending
4.0K
Giannis Antetokounmpo
MIL - F
Giannis Antetokounmpo
@ ATL Mon 12:10pm
10.5
Rebounds
Less"""

manager = SlateManager()
props = manager.parse_underdog_text(paste_text)

print(f"\n✓ Parsed {len(props)} props\n")

if props:
    for i, prop in enumerate(props, 1):
        print(f"{i}. {prop['player']:25} {prop['team']} {prop['stat']:12} {prop['line']:5.1f} {prop['direction']:7}")
    
    # Save to JSON for later use
    import json
    with open("test_underdog_parse.json", "w") as f:
        json.dump(props, f, indent=2)
    print(f"\n✓ Saved to test_underdog_parse.json")
else:
    print("❌ No props parsed - parser needs fixing")
