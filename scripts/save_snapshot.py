"""
Append clean props to historical market snapshot database
Used for long-term learning and CLV tracking
"""
import pandas as pd
from pathlib import Path

DATE = "2026-01-07"
FEATURES = f"data/features/props_clean_{DATE}.csv"
HISTORY = Path("data/history/market_snapshots.csv")

print(f"📦 Saving snapshot to history")

df = pd.read_csv(FEATURES)

# Create history directory if needed
HISTORY.parent.mkdir(parents=True, exist_ok=True)

# Append to history (create file if first time)
df.to_csv(
    HISTORY, 
    mode="a", 
    header=not HISTORY.exists(), 
    index=False
)

# Count total historical records
if HISTORY.exists():
    total_records = len(pd.read_csv(HISTORY))
else:
    total_records = len(df)

print(f"   ✅ Appended {len(df)} props")
print(f"   Total historical records: {total_records}")
print(f"   Database: {HISTORY}")
