"""Quick calibration backtest report."""
import pandas as pd
from pathlib import Path

df = pd.read_csv('calibration_history.csv')

print("=" * 60)
print("CALIBRATION BACKTEST REPORT")
print("=" * 60)
print(f"Date: 2026-01-16")
print(f"Total Picks: {len(df)}")
print()

# Overall
hits = (df['actual_result'] == 'hit').sum()
total = len(df)
print(f"OVERALL RECORD: {hits}/{total} ({100*hits/total:.1f}%)")
print()

# By Stat
print("BY STAT TYPE:")
print("-" * 40)
for stat in df['stat'].unique():
    subset = df[df['stat'] == stat]
    h = (subset['actual_result'] == 'hit').sum()
    t = len(subset)
    pct = 100 * h / t if t > 0 else 0
    print(f"  {stat:15} {h}/{t} ({pct:.0f}%)")

print()

# By Direction
print("BY DIRECTION:")
print("-" * 40)
for direction in df['direction'].unique():
    subset = df[df['direction'] == direction]
    h = (subset['actual_result'] == 'hit').sum()
    t = len(subset)
    pct = 100 * h / t if t > 0 else 0
    print(f"  {direction:15} {h}/{t} ({pct:.0f}%)")

print()

# By Player
print("BY PLAYER:")
print("-" * 40)
for player in df['player'].unique():
    subset = df[df['player'] == player]
    h = (subset['actual_result'] == 'hit').sum()
    t = len(subset)
    pct = 100 * h / t if t > 0 else 0
    status = "✓" if pct >= 50 else "✗"
    print(f"  {status} {player:20} {h}/{t} ({pct:.0f}%)")

print()
print("=" * 60)

# Insights
print("\nKEY INSIGHTS:")
print("-" * 40)

lower_df = df[df['direction'] == 'lower']
higher_df = df[df['direction'] == 'higher']

lower_rate = (lower_df['actual_result'] == 'hit').mean() * 100 if len(lower_df) > 0 else 0
higher_rate = (higher_df['actual_result'] == 'hit').mean() * 100 if len(higher_df) > 0 else 0

if lower_rate > higher_rate:
    print(f"  → LOWER picks performing better ({lower_rate:.0f}% vs {higher_rate:.0f}%)")
else:
    print(f"  → HIGHER picks performing better ({higher_rate:.0f}% vs {lower_rate:.0f}%)")

# Check 3pm
pm3_df = df[df['stat'] == '3pm']
if len(pm3_df) > 0:
    pm3_rate = (pm3_df['actual_result'] == 'hit').mean() * 100
    print(f"  → 3PM picks: {pm3_rate:.0f}% hit rate (small sample)")

print()
