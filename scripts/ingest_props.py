"""
Normalize and filter raw props to clean feature set
Hard gates: CORE stats only, deduplication, validation
"""
import pandas as pd
from datetime import datetime

DATE = "2026-01-07"
INPUT = f"data/raw/raw_props_{DATE}.csv"
OUTPUT = f"data/features/props_clean_{DATE}.csv"

# CORE stats only (strict filter)
CORE_STATS = {"points", "rebounds", "assists", "pts+reb+ast", "3pm"}

print(f"📥 Loading: {INPUT}")
df = pd.read_csv(INPUT)

print(f"   Raw props: {len(df)}")

# Hard filters
df = df[df["stat"].isin(CORE_STATS)]
print(f"   After CORE filter: {len(df)}")

df = df[df["line"] > 0]
print(f"   After line validation: {len(df)}")

df = df.drop_duplicates(subset=["player", "stat", "line", "direction"])
print(f"   After deduplication: {len(df)}")

# Tag stat classification
df["stat_class"] = "core"

# Add metadata
df["ingested_at"] = datetime.utcnow().isoformat()

# Save
df.to_csv(OUTPUT, index=False)

print(f"✅ Clean props: {OUTPUT}")
print(f"   Total: {len(df)}")
print(f"   Games: {df['game'].nunique()}")
print(f"   Players: {df['player'].nunique()}")
