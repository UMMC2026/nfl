"""Quick debug script to test the parser."""
from pathlib import Path
from golf.ingest import parse_underdog_golf_slate, load_slate_from_file

# Use both parsers
from golf.ingest.prizepicks_parser import parse_prizepicks_slate

with open("golf/inputs/slate.txt") as f:
    text = f.read()

# Try PrizePicks first
props_pp = parse_prizepicks_slate(text)
print(f"PrizePicks parser found: {len(props_pp)} props")

# Then Underdog
props_ud = parse_underdog_golf_slate(text)
print(f"Underdog parser found: {len(props_ud)} props")

print("\n--- Using PrizePicks Parser (32 props) ---")
for i, p in enumerate(props_pp, 1):
    player = p.get("player", "?")
    market = p.get("market", "?")
    line = p.get("line", "?")
    opponent = p.get("opponent", "")
    
    if opponent:
        print(f"{i}. [MATCHUP] {player} vs {opponent} | {market} @ {line}")
    else:
        print(f"{i}. {player} | {market} @ {line}")
