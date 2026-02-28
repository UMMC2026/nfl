"""Quick test of tennis parser with raw Underdog paste"""
from tennis.calibrated_props_engine import CalibratedTennisPropsEngine

paste = """Kaja Juvan - Player
Kaja Juvan
vs Elena Ruxandra Bertea Mon 3:00am
21
Fantasy Score
Less
More
Trending
17.7K
Lulu Sun
Lulu Sun - Player
Lulu Sun
vs Misaki Matsuda 50m 26s
18.5
Total Games
Less
More
Trending
14.7K
Alycia Parks
Alycia Parks - Player
Alycia Parks
vs Julia Grabher Mon 4:40am
21
Total Games
Less
More
Trending
12.0K
Karolina Pliskova
Karolina Pliskova - Player
Karolina Pliskova
vs Anastasia Zakharova Mon 3:00am
21.5
Total Games
Less
More
Trending
9.8K
Emma Raducanu
Emma Raducanu - Player
Emma Raducanu
vs Greet Minnen Mon 10:00am
20.5
Total Games
Less
More
Trending
8.2K"""

engine = CalibratedTennisPropsEngine()
props = engine.parse_underdog_paste(paste)
print(f"Parsed {len(props)} props:")
for p in props:
    print(f"  {p['player']} - {p['stat']} {p['line']} {p['direction']}")
engine.close()
