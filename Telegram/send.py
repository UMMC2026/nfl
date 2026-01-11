"""
Governed Telegram Sender — ONLY sends validated picks.

Rule: All Telegram messages must come from outputs/validated_primary_edges.json
Fail loud if file is missing or stale.
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Ensure project root is on PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Telegram.transport import send_message
from utils.freshness import assert_fresh

BASE_DIR = Path(__file__).resolve().parents[1]
VALIDATED_FILE = BASE_DIR / "outputs" / "validated_primary_edges.json"


def load_json(path: Path):
    """Load JSON file with error handling."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"❌ Validated picks not found: {path}\n"
            f"Run engine.slate_roster_validator.validate_and_render() first."
        )
    except json.JSONDecodeError as e:
        raise RuntimeError(f"❌ Invalid JSON in {path}: {e}")


def send_governed_telegram(max_age_seconds: int = 3600):
    """
    Send Telegram messages ONLY from validated picks.

    Args:
        max_age_seconds: Max age of validated file (default 1 hour)

    Raises:
        RuntimeError: If validation file is missing or stale
    """
    # GUARD 1: File must exist and be fresh
    assert_fresh(str(VALIDATED_FILE), max_age=max_age_seconds)

    # GUARD 2: Load validated picks
    data = load_json(VALIDATED_FILE)
    # Support both legacy dict-with-picks and new list-format outputs
    if isinstance(data, dict):
        picks = data.get("picks", [])
    else:
        picks = data

    if not picks:
        print("⚠️  No picks in validated file. Aborting Telegram send.")
        return

    # GUARD 3: Send only primary signals
    sent = 0
    for p in picks:
        if not p.get("is_primary", False):
            continue

        msg = (
            f"📊 {p.get('player', 'UNKNOWN')} | "
            f"{p.get('direction', '?').upper()} {p.get('line', '?')} {p.get('stat', '?')}\n"
            f"Prob: {int(p.get('probability', 0) * 100)}% | "
            f"Tier: {p.get('confidence_tier', 'UNKNOWN')}"
        )

        try:
            send_message(msg)
            sent += 1
        except Exception as e:
            print(f"❌ Failed to send for {p.get('player')}: {e}")
            continue

    print(f"✅ Telegram: {sent} primary signals sent")


if __name__ == "__main__":
    send_governed_telegram()
