# auto_triage.py
import os
import shutil
from datetime import datetime

ROOT = "UNDERDOG_ANALYSIS"
QUARANTINE = f"archive/_quarantine_{datetime.now().strftime('%Y%m%d')}"

os.makedirs(QUARANTINE, exist_ok=True)

KEEP_FOLDERS = {"ingest", "engine", "render", "validate"}
KEEP_FILES = {"run_daily.py", "config.py"}

def should_archive(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()

    has_print = "print(" in code or "console.print" in code
    has_math = any(k in code for k in ["*", "/", "+", "-", "avg", "mean"])
    has_hard_data = any(k in code for k in [
        "DEFENSE_", "PLAYER_", "GAME_", "season_avg", "recent_", "trend", "snap_pct"
    ])

    # RULE 1: mixed responsibility
    if has_print and has_math:
        return "mixed_responsibility"

    # RULE 2: hard-coded sports reality
    if has_hard_data:
        return "hard_coded_data"

    return None

for root, _, files in os.walk(ROOT):
    for f in files:
        if not f.endswith(".py"):
            continue

        full_path = os.path.join(root, f)
        rel = os.path.relpath(full_path, ROOT)

        # Skip archive itself
        if rel.startswith("archive"):
            continue

        # Always keep core files
        if f in KEEP_FILES:
            continue

        # Keep allowed folders (tentatively)
        top_folder = rel.split(os.sep)[0]
        if top_folder in KEEP_FOLDERS:
            continue

        reason = should_archive(full_path)
        if reason:
            dest = os.path.join(QUARANTINE, rel.replace(os.sep, "_"))
            print(f"[ARCHIVE] {rel} → {reason}")
            shutil.move(full_path, dest)

print("\nTriage complete.")
print(f"Archived files are in: {QUARANTINE}")
