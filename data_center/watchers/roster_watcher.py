import time
import hashlib
import sys
from pathlib import Path

ROSTER_FILE = Path("data_center/rosters/NBA_active_roster_current.csv")
CHECK_INTERVAL = 30  # seconds


def file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def watch():
    if not ROSTER_FILE.exists():
        print(f"[WATCHER] Missing roster file: {ROSTER_FILE}")
        sys.exit(1)

    last_hash = file_hash(ROSTER_FILE)
    print("[WATCHER] Roster watcher active")

    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            new_hash = file_hash(ROSTER_FILE)
        except FileNotFoundError:
            print("[ALERT] Roster file removed — invalidate slips and rebuild")
            sys.exit(0)

        if new_hash != last_hash:
            print("[ALERT] Roster changed — invalidate slips and rebuild")
            last_hash = new_hash
            # In a live system, trigger a rebuild here
            sys.exit(0)


if __name__ == "__main__":
    watch()
