#!/usr/bin/env python3
"""
Immediate fix: Remove Jonas Valanciunas from hydrated picks so he cannot appear
in tonight's recommendations.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path


def remove_player_completely(player_name: str = "Jonas Valanciunas") -> int:
    """Remove all hydrated rows for the given player from picks_hydrated.json.

    Creates a timestamped backup before overwriting the file and writes a small
    manual_block_log.json with metadata about the operation.
    """

    print(f"\n🚨 REMOVING {player_name} from hydrated picks")

    src = Path("picks_hydrated.json")
    if not src.exists():
        print("picks_hydrated.json not found; nothing to do.")
        return 0

    # 1. Backup original
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = src.with_name(f"picks_hydrated_backup_{timestamp}.json")
    shutil.copy2(src, backup_path)
    print(f"📁 Backup created: {backup_path}")

    # 2. Load picks
    picks = json.loads(src.read_text(encoding="utf-8"))

    # 3. Filter out player
    original_count = len(picks)
    filtered_picks = [
        p for p in picks
        if player_name.lower() not in str(p.get("player", "")).lower()
    ]
    removed_count = original_count - len(filtered_picks)

    # 4. Save filtered list back to disk
    src.write_text(json.dumps(filtered_picks, indent=2), encoding="utf-8")

    # 5. Write simple metadata log
    meta = {
        "removed_player": player_name,
        "removed_at": datetime.now().isoformat(),
        "removed_count": removed_count,
        "reason": "Manual removal of mis-specified player (team/stats)",
        "backup_file": str(backup_path.name),
    }
    Path("manual_block_log.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"✅ Removed {removed_count} hydrated picks for {player_name}")
    return removed_count


if __name__ == "__main__":
    remove_player_completely("Jonas Valanciunas")
