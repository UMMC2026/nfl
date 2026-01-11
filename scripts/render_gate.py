"""
Pre-broadcast validation gate
Prevents bad data from reaching Telegram
"""
import pandas as pd
import sys

DATE = "2026-01-07"
FILE = f"data/features/props_clean_{DATE}.csv"

print(f"🔒 RENDER GATE: {FILE}")

try:
    df = pd.read_csv(FILE)
except FileNotFoundError:
    print(f"   ❌ File not found: {FILE}")
    sys.exit(1)

errors = []

# Check 1: No duplicate player-stat combinations
duplicates = df.duplicated(subset=["player", "stat"], keep=False)
if duplicates.any():
    dup_count = duplicates.sum()
    errors.append(f"Duplicate player-stat combinations detected ({dup_count})")
    print(f"   ⚠️  Duplicates found:")
    print(df[duplicates][["player", "stat", "line", "direction"]])

# Check 2: At least some props exist
if len(df) == 0:
    errors.append("No eligible props after filtering")

# Check 3: Required columns exist
required_cols = ["player", "stat", "line", "direction", "game"]
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    errors.append(f"Missing required columns: {missing_cols}")

# Check 4: No null critical fields
null_checks = ["player", "stat", "line"]
for col in null_checks:
    if col in df.columns and df[col].isnull().any():
        null_count = df[col].isnull().sum()
        errors.append(f"Null values in {col} ({null_count} rows)")

# Check 5: Lines are positive
if "line" in df.columns:
    invalid_lines = (df["line"] <= 0).sum()
    if invalid_lines > 0:
        errors.append(f"Invalid lines (≤0): {invalid_lines} rows")

# Report
if errors:
    print(f"   ❌ RENDER GATE FAILED")
    for i, e in enumerate(errors, 1):
        print(f"      {i}. {e}")
    print()
    print("   DO NOT BROADCAST until issues resolved")
    sys.exit(1)

print(f"   ✅ Render gate passed")
print(f"   Total props: {len(df)}")
print(f"   Games: {df['game'].nunique()}")
print(f"   Players: {df['player'].nunique()}")
print()
print("   CLEARED TO BROADCAST")
