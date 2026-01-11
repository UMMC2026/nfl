"""
Manual prop entry template - use when you have clean data to input directly
For pasted sportsbook UI, use parse_raw_props.py instead
"""
import pandas as pd
from datetime import datetime

# EDIT THESE LINES ONLY
DATE = "2026-01-07"
SNAPSHOT_TIME = datetime.now().strftime("%H:%M")

rows = [
    # game, player, team, opp, stat, line, direction
    ("LAL@NOP","LeBron James","LAL","NOP","Points",23.5,"Lower"),
    ("LAL@NOP","LeBron James","LAL","NOP","Assists",8.5,"Lower"),
    ("MIL@CHI","Giannis Antetokounmpo","MIL","CHI","Points",30.5,"Higher"),
]

df = pd.DataFrame(rows, columns=[
    "game","player","team","opponent","stat","line","direction"
])

df.insert(0,"date",DATE)
df["snapshot_time"] = SNAPSHOT_TIME

out = f"data/raw/raw_props_{DATE}.csv"
df.to_csv(out, index=False)

print(f"✅ Raw props created: {out}")
print(f"   Total props: {len(df)}")
