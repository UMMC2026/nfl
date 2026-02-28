"""De-duplicate calibration_history.csv"""
import csv
from pathlib import Path
from collections import OrderedDict

csv_path = Path("calibration_history.csv")
backup_path = Path("calibration_history_backup_20260118.csv")

# Read all rows
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    rows = list(reader)

print(f"Original rows: {len(rows)}")

# De-duplicate by (date, player, stat, line, direction)
seen = set()
unique_rows = []
duplicates = 0

for row in rows:
    # Create a unique key
    key = (
        row.get("date", ""),
        row.get("player", "").lower().strip(),
        row.get("stat", "").lower().strip(),
        row.get("line", ""),
        row.get("direction", "").lower().strip()
    )
    
    if key not in seen:
        seen.add(key)
        unique_rows.append(row)
    else:
        duplicates += 1

print(f"Duplicates removed: {duplicates}")
print(f"Unique rows: {len(unique_rows)}")

# Backup original
import shutil
shutil.copy(csv_path, backup_path)
print(f"Backup saved to: {backup_path}")

# Write de-duplicated file
with open(csv_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(unique_rows)

print(f"De-duplicated file saved to: {csv_path}")

# Quick stats
hits = sum(1 for r in unique_rows if r.get("actual_result", "").lower() == "hit")
misses = sum(1 for r in unique_rows if r.get("actual_result", "").lower() == "miss")
print(f"\nActual hit rate: {hits}/{hits+misses} = {hits/(hits+misses)*100:.1f}%" if hits+misses > 0 else "No results")
